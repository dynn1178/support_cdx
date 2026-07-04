from __future__ import annotations

"""Snipaste 스타일 캡처 도구.

- SnipOverlay: 화면을 얼려두고 커서 아래 UI 요소를 자동 탐지해
  클릭(요소)/드래그(영역)/PrtSc(전체)/Alt+PrtSc(창)로 영역을 지정한다.
- SnipEditorWindow: 캡처 직후 나타나는 프레임 없는 최상위 편집 창.
  도형/화살표/선/연필/형광펜/텍스트 + 되돌리기/다시실행 + 저장/복사/고정.
- PinnedImageWindow: 테두리 없는 최상위 고정 창. 우클릭 메뉴로
  복사/저장/확대(30~100%)/회전·뒤집기/이동 기능을 제공한다.

좌표계 규칙: 캡처 파이프라인의 원본 데이터는 항상 "물리 픽셀"
(모니터 배율을 곱한 실제 픽셀)로 다루고, 화면에 표시할 때만 해당
모니터의 devicePixelRatio로 나눠 논리 좌표로 변환한다. 이렇게 하면
배율이 100%가 아닌 모니터에서도 선택 영역과 결과물이 1:1로 일치하고
원본 화질이 그대로 유지된다.
"""

import ctypes
import ctypes.wintypes as wintypes
import math
import sys
import threading
import time
from dataclasses import dataclass, field

from PyQt6.QtCore import (
    QEventLoop,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSizeF,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QCursor,
    QFont,
    QFontMetricsF,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
    QShortcut,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSlider,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

IS_WINDOWS = sys.platform.startswith("win")

ACCENT = "#2563EB"
DIM_ALPHA = 85

# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------

if IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    try:
        _dwmapi = ctypes.windll.dwmapi
    except Exception:  # pragma: no cover
        _dwmapi = None
else:  # pragma: no cover
    _user32 = _kernel32 = _dwmapi = None

DWMWA_CLOAKED = 14
DWMWA_EXTENDED_FRAME_BOUNDS = 9


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", ctypes.c_uint32),
        ("szDevice", ctypes.c_wchar * 32),
    ]


def _physical_monitor_rects() -> dict[str, QRect]:
    """모니터 장치 이름 → 가상 화면 기준 물리 픽셀 QRect."""
    result: dict[str, QRect] = {}
    if not IS_WINDOWS:
        return result
    try:
        proc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(wintypes.RECT), ctypes.c_void_p,
        )

        def _cb(hmon, _hdc, _rc, _lp):
            info = _MONITORINFOEX()
            info.cbSize = ctypes.sizeof(_MONITORINFOEX)
            if _user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcMonitor
                result[info.szDevice.rstrip("\x00")] = QRect(
                    r.left, r.top, r.right - r.left, r.bottom - r.top
                )
            return True

        _user32.EnumDisplayMonitors(None, None, proc(_cb), 0)
    except Exception:
        pass
    return result


def _window_title(hwnd: int) -> str:
    if not IS_WINDOWS or not hwnd:
        return ""
    try:
        length = _user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


def _window_rect_physical(hwnd: int) -> QRect:
    """DWM 확장 프레임 기준의 창 물리 픽셀 rect (그림자 여백 제외)."""
    if not IS_WINDOWS or not hwnd:
        return QRect()
    rect = wintypes.RECT()
    try:
        if _dwmapi is not None:
            hr = _dwmapi.DwmGetWindowAttribute(
                wintypes.HWND(hwnd),
                ctypes.c_uint32(DWMWA_EXTENDED_FRAME_BOUNDS),
                ctypes.byref(rect),
                ctypes.sizeof(rect),
            )
            if hr == 0:
                return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    try:
        if _user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    return QRect()


@dataclass
class WindowInfo:
    hwnd: int
    rect: QRect
    title: str


def enumerate_capture_windows() -> list[WindowInfo]:
    """Z-순서(위→아래)의 보이는 최상위 창 목록. 자기 프로세스 창은 제외."""
    windows: list[WindowInfo] = []
    if not IS_WINDOWS:
        return windows
    own_pid = _kernel32.GetCurrentProcessId()
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x20
    WS_EX_LAYERED = 0x00080000
    LWA_ALPHA = 0x2

    def _cb(hwnd, _lp):
        try:
            if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
                return True
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == own_pid:
                return True
            # 클릭 통과(입력 투명) 오버레이 창(마우스 커서 오버레이 등)은
            # 사용자가 캡처하려는 대상이 아니므로 후보에서 제외한다.
            exstyle = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if exstyle & WS_EX_TRANSPARENT:
                return True
            # 완전 투명(alpha 0)으로 숨겨둔 레이어드 창도 눈에 보이지 않는
            # 배경 창이므로 제외한다. 이런 창이 최상단에 있으면 뒤쪽 배경이
            # 선택된 것처럼 보이는 원인이 된다.
            if exstyle & WS_EX_LAYERED:
                alpha = ctypes.c_ubyte(255)
                flags = ctypes.c_uint32(0)
                if _user32.GetLayeredWindowAttributes(
                    hwnd, None, ctypes.byref(alpha), ctypes.byref(flags)
                ) and (flags.value & LWA_ALPHA) and alpha.value == 0:
                    return True
            if _dwmapi is not None:
                cloaked = ctypes.c_uint32(0)
                if (
                    _dwmapi.DwmGetWindowAttribute(
                        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
                    )
                    == 0
                    and cloaked.value
                ):
                    return True
            rect = _window_rect_physical(int(hwnd))
            if rect.width() < 4 or rect.height() < 4:
                return True
            windows.append(WindowInfo(int(hwnd), rect, _window_title(int(hwnd))))
        except Exception:
            pass
        return True

    try:
        _user32.EnumWindows(proc(_cb), 0)
    except Exception:
        pass
    return windows


def _foreground_hwnd() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        return int(_user32.GetForegroundWindow())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# 좌표 매핑 + 화면 스냅샷
# ---------------------------------------------------------------------------


@dataclass
class ScreenEntry:
    screen: object
    logical: QRect
    physical: QRect
    dpr: float


class ScreenMap:
    """논리(Qt) 좌표 ↔ 물리(Win32) 좌표 변환 테이블."""

    def __init__(self) -> None:
        self.entries: list[ScreenEntry] = []
        phys_by_name = _physical_monitor_rects()
        for screen in QApplication.screens():
            logical = QRect(screen.geometry())
            dpr = float(screen.devicePixelRatio()) or 1.0
            physical = phys_by_name.get(screen.name())
            if physical is None or physical.isEmpty():
                physical = QRect(
                    logical.x(), logical.y(),
                    round(logical.width() * dpr), round(logical.height() * dpr),
                )
            self.entries.append(ScreenEntry(screen, logical, QRect(physical), dpr))

    def physical_virtual_rect(self) -> QRect:
        rect = QRect()
        for entry in self.entries:
            rect = rect.united(entry.physical) if not rect.isNull() else QRect(entry.physical)
        return rect

    def entry_for_logical(self, pos: QPoint) -> ScreenEntry | None:
        for entry in self.entries:
            if entry.logical.contains(pos):
                return entry
        return self.entries[0] if self.entries else None

    def entry_for_physical(self, pos: QPoint) -> ScreenEntry | None:
        for entry in self.entries:
            if entry.physical.contains(pos):
                return entry
        return self.entries[0] if self.entries else None

    def entry_for_physical_rect(self, rect: QRect) -> ScreenEntry | None:
        best = None
        best_area = -1
        for entry in self.entries:
            overlap = rect.intersected(entry.physical)
            area = overlap.width() * overlap.height()
            if area > best_area:
                best_area = area
                best = entry
        return best

    def to_physical_point(self, pos: QPoint) -> QPoint:
        entry = self.entry_for_logical(pos)
        if entry is None:
            return QPoint(pos)
        dx = pos.x() - entry.logical.x()
        dy = pos.y() - entry.logical.y()
        x = entry.physical.x() + round(dx * entry.dpr)
        y = entry.physical.y() + round(dy * entry.dpr)
        return QPoint(
            min(max(x, entry.physical.left()), entry.physical.right() + 1),
            min(max(y, entry.physical.top()), entry.physical.bottom() + 1),
        )

    def to_logical_rect(self, rect: QRect) -> QRect:
        entry = self.entry_for_physical_rect(rect)
        if entry is None:
            return QRect(rect)
        dx = rect.x() - entry.physical.x()
        dy = rect.y() - entry.physical.y()
        return QRect(
            entry.logical.x() + round(dx / entry.dpr),
            entry.logical.y() + round(dy / entry.dpr),
            max(1, round(rect.width() / entry.dpr)),
            max(1, round(rect.height() / entry.dpr)),
        )


class FrozenScreens:
    """오버레이를 띄우는 순간의 화면을 모니터별 물리 픽셀로 얼려둔다."""

    def __init__(self, smap: ScreenMap) -> None:
        self.smap = smap
        self.shots: dict[str, QPixmap] = {}
        self._grab_all()

    def _grab_all(self) -> None:
        virt = self.smap.physical_virtual_rect()
        full: QImage | None = None
        if IS_WINDOWS and not virt.isEmpty():
            try:
                from PIL import ImageGrab

                image = ImageGrab.grab(all_screens=True).convert("RGBA")
                data = image.tobytes("raw", "RGBA")
                full = QImage(
                    data, image.width, image.height, QImage.Format.Format_RGBA8888
                ).copy()
            except Exception:
                full = None
        for entry in self.smap.entries:
            shot = QPixmap()
            if full is not None:
                local = entry.physical.translated(-virt.topLeft())
                cropped = full.copy(local)
                if not cropped.isNull():
                    shot = QPixmap.fromImage(cropped)
            if shot.isNull():
                try:
                    fallback = entry.screen.grabWindow(0)
                    fallback.setDevicePixelRatio(1.0)
                    shot = fallback
                except Exception:
                    shot = QPixmap()
            shot.setDevicePixelRatio(1.0)
            self.shots[entry.screen.name()] = shot

    def shot_for(self, entry: ScreenEntry) -> QPixmap:
        return self.shots.get(entry.screen.name(), QPixmap())

    def grab_physical(self, rect: QRect) -> QPixmap:
        """물리 픽셀 rect를 얼려둔 스냅샷에서 그대로 잘라낸다 (재캡처 없음)."""
        parts: list[tuple[ScreenEntry, QRect]] = []
        for entry in self.smap.entries:
            overlap = rect.intersected(entry.physical)
            if not overlap.isEmpty() and not self.shot_for(entry).isNull():
                parts.append((entry, overlap))
        if not parts:
            return QPixmap()
        if len(parts) == 1 and parts[0][1] == rect:
            entry, overlap = parts[0]
            shot = self.shot_for(entry)
            local = overlap.translated(-entry.physical.topLeft())
            piece = shot.copy(local)
            piece.setDevicePixelRatio(entry.dpr)
            return piece
        out = QPixmap(rect.size())
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        for entry, overlap in parts:
            shot = self.shot_for(entry)
            source = overlap.translated(-entry.physical.topLeft())
            target = overlap.translated(-rect.topLeft())
            painter.drawPixmap(target, shot, source)
        painter.end()
        out.setDevicePixelRatio(1.0)
        return out


# ---------------------------------------------------------------------------
# UI 요소 탐지 (UI Automation, 백그라운드 스레드)
# ---------------------------------------------------------------------------


_uia_modules: tuple | None = None
_uia_failed = False


def _ensure_uia_modules() -> tuple | None:
    """comtypes를 메인 스레드에서 import/코드 생성한다.

    comtypes는 import하는 스레드에서 COM을 초기화하고 atexit 정리도 그 짝에
    맞춰 등록하므로, 수명이 짧은 워커 스레드에서 최초 import하면 프로세스
    종료 시 크래시가 난다. 메인 스레드에서 한 번만 import해 두고 워커는
    명시적 CoInitializeEx/CoUninitialize 쌍만 쓴다.
    """
    global _uia_modules, _uia_failed
    if _uia_modules is not None or _uia_failed or not IS_WINDOWS:
        return _uia_modules
    try:
        import comtypes
        import comtypes.client as cc

        cc.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIAC

        _uia_modules = (comtypes, cc, UIAC)
    except Exception:
        _uia_failed = True
        _uia_modules = None
    return _uia_modules


class ElementResolver(QThread):
    """창 핸들 단위로 UIA 트리를 캐시해 커서 아래 UI 요소 rect를 제공한다.

    ElementFromPoint는 전체 화면을 덮은 오버레이 자신을 맞히기 때문에 쓰지 않고,
    창 핸들에서 출발하는 FindAllBuildCache(서브트리 1회 왕복)로 요소 rect들을
    모아 로컬에서 히트테스트한다. 오버레이와의 충돌·클릭 유실이 원천적으로 없다.

    Chromium 계열(브라우저, Electron)은 접근성 트리를 첫 UIA 조회 후에야
    비동기로 활성화하므로, 결과가 얕으면(RICH_THRESHOLD 미만) 시간 간격을
    두고 몇 차례 재조회한다.
    """

    ready = pyqtSignal(int)

    MAX_ELEMENTS = 4000
    RICH_THRESHOLD = 40
    MAX_ATTEMPTS = 3
    RETRY_INTERVAL = 0.6  # seconds

    def __init__(self) -> None:
        super().__init__()
        self._modules = _ensure_uia_modules()
        self._cv = threading.Condition()
        self._pending: list[int] = []
        self._results: dict[int, list[QRect]] = {}
        self._attempts: dict[int, int] = {}
        self._last_attempt: dict[int, float] = {}
        self._stop = False

    def request(self, hwnd: int) -> None:
        now = time.monotonic()
        with self._cv:
            rects = self._results.get(hwnd)
            if rects is not None and (
                len(rects) >= self.RICH_THRESHOLD
                or self._attempts.get(hwnd, 0) >= self.MAX_ATTEMPTS
            ):
                return
            if hwnd in self._pending:
                return
            if now - self._last_attempt.get(hwnd, 0.0) < self.RETRY_INTERVAL:
                return
            self._last_attempt[hwnd] = now
            self._pending.append(hwnd)
            self._cv.notify()

    def rects_for(self, hwnd: int) -> list[QRect] | None:
        with self._cv:
            return self._results.get(hwnd)

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify()

    # --- thread body -------------------------------------------------

    def run(self) -> None:  # pragma: no cover - COM 워커 스레드
        uia = cache_request = tree_scope = None
        comtypes = None
        com_initialized = False
        if self._modules is not None:
            comtypes, cc, UIAC = self._modules
            try:
                comtypes.CoInitializeEx(getattr(comtypes, "COINIT_MULTITHREADED", 0x0))
                com_initialized = True
                uia = cc.CreateObject(UIAC.CUIAutomation, interface=UIAC.IUIAutomation)
                cache_request = uia.CreateCacheRequest()
                cache_request.AddProperty(30001)  # UIA_BoundingRectanglePropertyId
                cache_request.AddProperty(30022)  # UIA_IsOffscreenPropertyId
                tree_scope = UIAC.TreeScope_Subtree
            except Exception:
                uia = None
        try:
            while True:
                with self._cv:
                    while not self._pending and not self._stop:
                        self._cv.wait(0.25)
                    if self._stop:
                        break
                    hwnd = self._pending.pop(0)
                    self._attempts[hwnd] = self._attempts.get(hwnd, 0) + 1
                rects: list[QRect] = []
                if uia is not None:
                    try:
                        rects = self._uia_rects(uia, cache_request, tree_scope, hwnd)
                    except Exception:
                        rects = []
                if not rects:
                    rects = self._child_hwnd_rects(hwnd)
                window_rect = _window_rect_physical(hwnd)
                clipped = []
                for rect in rects:
                    rect = rect.intersected(window_rect) if not window_rect.isEmpty() else rect
                    if rect.width() >= 4 and rect.height() >= 4:
                        clipped.append(rect)
                clipped.sort(key=lambda r: r.width() * r.height())
                with self._cv:
                    self._results[hwnd] = clipped
                self.ready.emit(hwnd)
        finally:
            # COM 객체를 이 스레드에서 먼저 해제한 뒤 CoUninitialize해야
            # 프로세스 종료 시 크래시가 나지 않는다.
            cache_request = None
            uia = None
            if com_initialized and comtypes is not None:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

    def _uia_rects(self, uia, cache_request, tree_scope, hwnd: int) -> list[QRect]:
        element = uia.ElementFromHandle(hwnd)
        found = element.FindAllBuildCache(tree_scope, uia.ControlViewCondition, cache_request)
        rects: list[QRect] = []
        count = min(found.Length, self.MAX_ELEMENTS)
        for index in range(count):
            try:
                item = found.GetElement(index)
                if item.CachedIsOffscreen:
                    continue
                r = item.CachedBoundingRectangle
                rect = QRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
                if rect.width() >= 4 and rect.height() >= 4:
                    rects.append(rect)
            except Exception:
                continue
        return rects

    def _child_hwnd_rects(self, hwnd: int) -> list[QRect]:
        rects: list[QRect] = []
        if not IS_WINDOWS:
            return rects
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _cb(child, _lp):
            try:
                if _user32.IsWindowVisible(child):
                    rect = _window_rect_physical(int(child))
                    if rect.width() >= 4 and rect.height() >= 4:
                        rects.append(rect)
            except Exception:
                pass
            return True

        try:
            _user32.EnumChildWindows(wintypes.HWND(hwnd), proc(_cb), 0)
        except Exception:
            pass
        return rects


# ---------------------------------------------------------------------------
# 캡처 오버레이
# ---------------------------------------------------------------------------


@dataclass
class SnipResult:
    pixmap: QPixmap
    phys_rect: QRect
    logical_rect: QRect
    window_title: str


class _SnipPanel(QWidget):
    """모니터 하나를 덮는 오버레이 패널. Qt가 모니터별 DPR을 자동 적용한다."""

    def __init__(self, entry: ScreenEntry, shot: QPixmap, coordinator: "SnipOverlay") -> None:
        super().__init__()
        self.entry = entry
        self.shot = shot
        self.coordinator = coordinator
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setGeometry(entry.logical)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def _local_rect(self, phys: QRect) -> QRectF:
        entry = self.entry
        return QRectF(
            (phys.x() - entry.physical.x()) / entry.dpr,
            (phys.y() - entry.physical.y()) / entry.dpr,
            phys.width() / entry.dpr,
            phys.height() / entry.dpr,
        )

    # 캡처 결과물은 FrozenScreens 스냅샷에서 잘라내므로, 오버레이에만
    # 그려지는 이 안내는 캡처 이미지에 절대 포함되지 않는다.
    HELP_LINES = [
        ("클릭", "감지된 영역 캡처"),
        ("드래그", "원하는 영역 캡처"),
        ("Z", "겹친 영역 전환"),
        ("A", "전체 화면 캡처"),
        ("S", "활성 창 캡처"),
        ("Enter", "선택 영역 캡처"),
        ("ESC", "캡처 취소"),
    ]

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not self.shot.isNull():
            painter.drawPixmap(self.rect(), self.shot)
        painter.fillRect(self.rect(), QColor(0, 0, 0, DIM_ALPHA))
        selection = self.coordinator.selection_phys
        if selection.isEmpty():
            self._draw_help(painter)
            painter.end()
            return
        clipped = selection.intersected(self.entry.physical)
        if clipped.isEmpty():
            self._draw_help(painter)
            painter.end()
            return
        target = self._local_rect(clipped)
        if not self.shot.isNull():
            source = QRectF(
                clipped.x() - self.entry.physical.x(),
                clipped.y() - self.entry.physical.y(),
                clipped.width(),
                clipped.height(),
            )
            painter.drawPixmap(target, self.shot, source)
        pen = QPen(QColor(ACCENT), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(target)
        if self.entry.physical.contains(selection.topLeft()):
            self._draw_badge(painter, target, selection)
        self._draw_help(painter)
        painter.end()

    def _draw_help(self, painter: QPainter) -> None:
        """우측 하단 단축키 안내 (오버레이 전용, 캡처 영역에는 미포함)."""
        key_font = QFont("Malgun Gothic", 9)
        key_font.setBold(True)
        text_font = QFont("Malgun Gothic", 9)
        key_metrics = QFontMetricsF(key_font)
        text_metrics = QFontMetricsF(text_font)
        pad = 12.0
        row_h = max(key_metrics.height(), text_metrics.height()) + 6.0
        key_col = max(key_metrics.horizontalAdvance(key) for key, _desc in self.HELP_LINES) + 14.0
        text_col = max(text_metrics.horizontalAdvance(desc) for _key, desc in self.HELP_LINES)
        width = pad * 2 + key_col + 10.0 + text_col
        height = pad * 2 + row_h * len(self.HELP_LINES)
        margin = 18.0
        box = QRectF(self.width() - width - margin, self.height() - height - margin, width, height)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(QColor(17, 24, 39, 205))
        painter.drawRoundedRect(box, 9, 9)
        y = box.top() + pad
        for key, desc in self.HELP_LINES:
            key_rect = QRectF(box.left() + pad, y, key_col, row_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 34))
            painter.drawRoundedRect(key_rect.adjusted(0, 1, -8, -5), 4, 4)
            painter.setFont(key_font)
            painter.setPen(QColor("#93C5FD"))
            painter.drawText(
                key_rect.adjusted(0, 0, -8, -4), Qt.AlignmentFlag.AlignCenter, key
            )
            painter.setFont(text_font)
            painter.setPen(QColor(241, 245, 249))
            painter.drawText(
                QRectF(box.left() + pad + key_col + 10.0, y, text_col + 4, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                desc,
            )
            y += row_h

    def _draw_badge(self, painter: QPainter, target: QRectF, selection: QRect) -> None:
        text = f"{selection.width()} × {selection.height()}"
        font = QFont("Malgun Gothic", 9)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        pad_x, pad_y = 8.0, 4.0
        width = metrics.horizontalAdvance(text) + pad_x * 2
        height = metrics.height() + pad_y * 2
        x = target.left()
        y = target.top() - height - 6
        if y < 4:
            y = target.top() + 6
        if x + width > self.width() - 4:
            x = max(4.0, self.width() - width - 4)
        badge = QRectF(x, y, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(17, 24, 39, 225))
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

    # --- 입력 위임 -----------------------------------------------------

    def mousePressEvent(self, event) -> None:
        self.activateWindow()
        if event.button() == Qt.MouseButton.LeftButton:
            self.coordinator.panel_press(event.globalPosition().toPoint())
        elif event.button() == Qt.MouseButton.RightButton:
            self.coordinator.cancel()

    def mouseMoveEvent(self, event) -> None:
        self.coordinator.panel_move(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.coordinator.panel_release(event.globalPosition().toPoint())

    def keyPressEvent(self, event) -> None:
        if not self.coordinator.panel_key(event):
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        # Windows는 PrintScreen을 KeyRelease로만 전달한다.
        if event.key() == Qt.Key.Key_Print:
            self.coordinator.panel_print_screen(bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
            return
        super().keyReleaseEvent(event)


class SnipOverlay(QObject):
    """요소 자동 탐지 + 클릭/드래그/전체/창 캡처 오버레이."""

    DRAG_THRESHOLD = 5  # 물리 px

    def __init__(self) -> None:
        super().__init__()
        self.selection_phys = QRect()
        self._smap: ScreenMap | None = None
        self._frozen: FrozenScreens | None = None
        self._windows: list[WindowInfo] = []
        self._resolver: ElementResolver | None = None
        self._panels: list[_SnipPanel] = []
        self._loop: QEventLoop | None = None
        self._origin_phys: QPoint | None = None
        self._dragging = False
        self._hover_hwnd = 0
        self._hover_title = ""
        self._accepted_rect: QRect | None = None
        self._accepted_title = ""
        self._foreground_hwnd = 0
        self._print_handled = False
        # Z 키로 같은 위치에 겹쳐 있는 요소/창 영역을 순환 선택하는 상태
        self._cycle_rects: list[tuple[QRect, str]] = []
        self._cycle_index = -1
        self._cycle_anchor: QPoint | None = None

    # --- 실행 ----------------------------------------------------------

    def exec(self) -> SnipResult | None:
        if not QApplication.screens():
            return None
        self._foreground_hwnd = _foreground_hwnd()
        self._smap = ScreenMap()
        self._frozen = FrozenScreens(self._smap)
        self._windows = enumerate_capture_windows()
        self._resolver = ElementResolver()
        self._resolver.ready.connect(self._on_elements_ready)
        self._resolver.start()

        for entry in self._smap.entries:
            panel = _SnipPanel(entry, self._frozen.shot_for(entry), self)
            self._panels.append(panel)
        for panel in self._panels:
            panel.show()
        cursor = QCursor.pos()
        for panel in self._panels:
            if panel.geometry().contains(cursor):
                panel.activateWindow()
                panel.setFocus()
                break
        self._update_hover(cursor)

        self._loop = QEventLoop()
        self._loop.exec()

        for panel in self._panels:
            panel.close()
            panel.deleteLater()
        self._panels.clear()
        if self._resolver is not None:
            self._resolver.stop()
            self._resolver.wait(1500)

        if self._accepted_rect is None or self._frozen is None or self._smap is None:
            return None
        rect = self._accepted_rect
        if rect.width() < 3 or rect.height() < 3:
            return None
        pixmap = self._frozen.grab_physical(rect)
        if pixmap.isNull():
            return None
        return SnipResult(
            pixmap=pixmap,
            phys_rect=QRect(rect),
            logical_rect=self._smap.to_logical_rect(rect),
            window_title=self._accepted_title,
        )

    # --- 상태 갱신 ------------------------------------------------------

    def _set_selection(self, rect: QRect) -> None:
        if rect == self.selection_phys:
            return
        self.selection_phys = QRect(rect)
        for panel in self._panels:
            panel.update()

    def _is_overlay_like(self, info: WindowInfo) -> bool:
        """제목 없이 모니터 전체(이상)를 덮는 창은 투명 오버레이 호스트일
        가능성이 높다. 이런 창이 커서를 가로채면 뒤쪽 배경 전체가 선택된
        것처럼 보이므로 히트테스트에서 후순위로 미룬다."""
        if info.title:
            return False
        if self._smap is None:
            return False
        for entry in self._smap.entries:
            if info.rect.contains(entry.physical):
                return True
        return False

    def _hit_window(self, phys: QPoint) -> WindowInfo | None:
        candidates = [info for info in self._windows if info.rect.contains(phys)]
        if not candidates:
            return None
        # 오버레이성(제목 없음 + 화면 전체 덮음) 창은 실제 창이 있으면 제외.
        solid = [info for info in candidates if not self._is_overlay_like(info)]
        pool = solid or candidates
        # 캡처를 시작한 시점의 전면(활성) 창을 우선한다. 그보다 위에 있는
        # 창들이 전부 제목 없는 보조 창이라면 사용자가 보고 있는 것은
        # 전면 창이므로, 최상단 레이어의 창이 더 자주 선택되게 된다.
        for index, info in enumerate(pool):
            if info.hwnd == self._foreground_hwnd:
                if all(not above.title for above in pool[:index]):
                    return info
                break
        return pool[0]

    def _update_hover(self, global_logical: QPoint) -> None:
        if self._smap is None:
            return
        phys = self._smap.to_physical_point(global_logical)
        info = self._hit_window(phys)
        if info is None:
            self._hover_hwnd = 0
            self._hover_title = ""
            entry = self._smap.entry_for_physical(phys)
            self._set_selection(entry.physical if entry else QRect())
            return
        self._hover_hwnd = info.hwnd
        self._hover_title = info.title
        best = info.rect
        if self._resolver is not None:
            # request()는 이미 충분한 결과가 있거나 재시도 한도를 넘긴 창을
            # 스스로 걸러내므로 hover마다 불러도 안전하다 (얕은 트리 재조회용).
            self._resolver.request(info.hwnd)
            rects = self._resolver.rects_for(info.hwnd)
            if rects:
                for rect in rects:  # 면적 오름차순 → 처음 맞는 것이 최소 요소
                    if rect.contains(phys):
                        best = rect
                        break
        self._set_selection(best)

    def _on_elements_ready(self, hwnd: int) -> None:
        if not self._dragging and hwnd == self._hover_hwnd and self._cycle_anchor is None:
            self._update_hover(QCursor.pos())

    # --- 패널 콜백 -------------------------------------------------------

    def panel_press(self, global_pos: QPoint) -> None:
        if self._smap is None:
            return
        self._origin_phys = self._smap.to_physical_point(global_pos)
        self._dragging = False

    def panel_move(self, global_pos: QPoint) -> None:
        if self._smap is None:
            return
        if self._origin_phys is None:
            # Z 순환 중에는 커서가 실제로 이동했을 때만 순환을 풀고
            # 자동 탐지로 복귀한다 (미세 떨림으로 풀리지 않도록).
            if self._cycle_anchor is not None:
                delta = self._smap.to_physical_point(global_pos) - self._cycle_anchor
                if abs(delta.x()) < self.DRAG_THRESHOLD and abs(delta.y()) < self.DRAG_THRESHOLD:
                    return
                self._reset_cycle()
            self._update_hover(global_pos)
            return
        current = self._smap.to_physical_point(global_pos)
        if not self._dragging:
            delta = current - self._origin_phys
            if abs(delta.x()) < self.DRAG_THRESHOLD and abs(delta.y()) < self.DRAG_THRESHOLD:
                return
            self._dragging = True
        self._set_selection(QRect(self._origin_phys, current).normalized())

    def panel_release(self, global_pos: QPoint) -> None:
        if self._smap is None:
            return
        if self._dragging:
            current = self._smap.to_physical_point(global_pos)
            rect = QRect(self._origin_phys, current).normalized()
            self._accept(rect, self._hover_title)
            return
        self._origin_phys = None
        # 클릭: 현재 하이라이트된 요소/창 캡처 (Z 순환 중이면 그 선택을 유지)
        if self._cycle_anchor is None:
            self._update_hover(global_pos)
        if not self.selection_phys.isEmpty():
            self._accept(self.selection_phys, self._hover_title)

    def panel_key(self, event) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not self.selection_phys.isEmpty():
                self._accept(self.selection_phys, self._hover_title)
            return True
        if key == Qt.Key.Key_Z:
            self._cycle_overlap()
            return True
        if key == Qt.Key.Key_A:
            if self._smap is not None:
                self._accept(self._smap.physical_virtual_rect(), "전체 화면")
            return True
        if key == Qt.Key.Key_S:
            self._capture_active_window()
            return True
        if key == Qt.Key.Key_Print:
            self.panel_print_screen(bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
            return True
        return False

    def _capture_active_window(self) -> None:
        """S: 캡처를 시작한 시점에 활성화되어 있던 창만 캡처한다."""
        if self._smap is None:
            return
        hwnd = self._foreground_hwnd or self._hover_hwnd
        rect = _window_rect_physical(hwnd)
        title = _window_title(hwnd)
        if rect.isEmpty():
            rect = self._smap.physical_virtual_rect()
            title = "전체 화면"
        self._accept(rect, title or "활성 창")

    # --- Z: 겹친 영역 순환 -------------------------------------------------

    def _reset_cycle(self) -> None:
        self._cycle_rects = []
        self._cycle_index = -1
        self._cycle_anchor = None

    def _cycle_candidates(self, phys: QPoint) -> list[tuple[QRect, str]]:
        """커서 아래에 겹쳐 있는 후보 영역: 각 창의 (작은 요소 → 창 전체) 순.

        같은 자리에 창이 여러 장 겹쳐 있으면 z-순서대로 이어 붙이므로
        Z를 누를 때마다 앞 창의 요소 → 앞 창 전체 → 뒤 창 ... 로 전환된다.
        """
        candidates: list[tuple[QRect, str]] = []
        seen: set[tuple[int, int, int, int]] = set()

        def push(rect: QRect, title: str) -> None:
            key = (rect.x(), rect.y(), rect.width(), rect.height())
            if key not in seen and rect.width() >= 3 and rect.height() >= 3:
                seen.add(key)
                candidates.append((QRect(rect), title))

        for info in self._windows:
            if not info.rect.contains(phys):
                continue
            if self._resolver is not None:
                rects = self._resolver.rects_for(info.hwnd) or []
                for rect in rects:  # 면적 오름차순
                    if rect.contains(phys):
                        push(rect, info.title)
            push(info.rect, info.title)
        return candidates

    def _cycle_overlap(self) -> None:
        """Z: 동일 위치에 겹쳐 있는 요소/창 영역을 순서대로 전환한다."""
        if self._smap is None:
            return
        phys = self._smap.to_physical_point(QCursor.pos())
        if self._cycle_anchor is None or not self._cycle_rects:
            self._cycle_rects = self._cycle_candidates(phys)
            self._cycle_anchor = QPoint(phys)
            # 현재 선택된 영역 다음 후보부터 시작한다.
            self._cycle_index = -1
            for index, (rect, _title) in enumerate(self._cycle_rects):
                if rect == self.selection_phys:
                    self._cycle_index = index
                    break
        if not self._cycle_rects:
            return
        self._cycle_index = (self._cycle_index + 1) % len(self._cycle_rects)
        rect, title = self._cycle_rects[self._cycle_index]
        self._hover_title = title
        self._set_selection(rect)

    def panel_print_screen(self, alt: bool) -> None:
        if self._print_handled or self._smap is None:
            return
        self._print_handled = True
        if alt:
            hwnd = self._hover_hwnd or self._foreground_hwnd
            rect = _window_rect_physical(hwnd)
            title = _window_title(hwnd)
            if rect.isEmpty():
                rect = self._smap.physical_virtual_rect()
                title = ""
            self._accept(rect, title)
        else:
            self._accept(self._smap.physical_virtual_rect(), "전체 화면")

    def _accept(self, rect: QRect, title: str) -> None:
        if rect.width() < 3 or rect.height() < 3:
            self._print_handled = False
            return
        self._accepted_rect = QRect(rect)
        self._accepted_title = title or _window_title(self._foreground_hwnd)
        if self._loop is not None:
            self._loop.quit()

    def cancel(self) -> None:
        self._accepted_rect = None
        if self._loop is not None:
            self._loop.quit()


# ---------------------------------------------------------------------------
# 주석(그리기) 데이터
# ---------------------------------------------------------------------------


@dataclass
class Annotation:
    tool: str  # rect | ellipse | arrow | line | pen | marker | text | mosaic
    color: QColor
    width: float  # 물리 px
    points: list[QPointF] = field(default_factory=list)
    text: str = ""
    font_px: float = 24.0
    mosaic_shape: str = "rect"  # pen | rect | ellipse
    mosaic_pixel: int = 12  # 물리 px 블록 크기
    mosaic_effect: str = "pixel"  # pixel | blur

    def render(self, painter: QPainter, base: QPixmap | None = None) -> None:
        if self.tool == "mosaic":
            self._render_mosaic(painter, base)
            return
        color = QColor(self.color)
        if self.tool == "marker":
            color.setAlpha(110)
        pen = QPen(color, self.width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.tool in ("rect", "ellipse"):
            if len(self.points) < 2:
                return
            rect = QRectF(self.points[0], self.points[-1]).normalized()
            if self.tool == "rect":
                painter.drawRect(rect)
            else:
                painter.drawEllipse(rect)
        elif self.tool == "line":
            if len(self.points) < 2:
                return
            painter.drawLine(self.points[0], self.points[-1])
        elif self.tool == "arrow":
            if len(self.points) < 2:
                return
            self._render_arrow(painter, color)
        elif self.tool in ("pen", "marker"):
            if len(self.points) < 2:
                if self.points:
                    painter.drawPoint(self.points[0])
                return
            path = QPainterPath(self.points[0])
            for point in self.points[1:]:
                path.lineTo(point)
            painter.drawPath(path)
        elif self.tool == "text":
            self._render_text(painter, color)

    def _render_arrow(self, painter: QPainter, color: QColor) -> None:
        start, end = self.points[0], self.points[-1]
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        head_len = max(10.0, self.width * 3.5)
        head_wid = head_len * 0.7
        base = QPointF(end.x() - ux * head_len, end.y() - uy * head_len)
        perp = QPointF(-uy, ux)
        left = QPointF(base.x() + perp.x() * head_wid / 2, base.y() + perp.y() * head_wid / 2)
        right = QPointF(base.x() - perp.x() * head_wid / 2, base.y() - perp.y() * head_wid / 2)
        painter.drawLine(start, base)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([end, left, right]))

    def _render_text(self, painter: QPainter, color: QColor) -> None:
        if not self.text or not self.points:
            return
        font = self._text_font()
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetricsF(font)
        x = self.points[0].x()
        y = self.points[0].y() + metrics.ascent()
        for line in self.text.splitlines() or [self.text]:
            painter.drawText(QPointF(x, y), line)
            y += metrics.lineSpacing()

    def _text_font(self) -> QFont:
        font = QFont("Malgun Gothic")
        font.setPixelSize(max(8, round(self.font_px)))
        font.setBold(True)
        return font

    # --- 모자이크 / 블러 ---------------------------------------------------

    def _mosaic_path(self) -> QPainterPath:
        path = QPainterPath()
        if self.mosaic_shape == "pen":
            if not self.points:
                return path
            if len(self.points) < 2:
                path.addEllipse(self.points[0], self.width / 2, self.width / 2)
                return path
            stroke = QPainterPath(self.points[0])
            for point in self.points[1:]:
                stroke.lineTo(point)
            stroker = QPainterPathStroker()
            stroker.setWidth(max(2.0, self.width))
            stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
            stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            return stroker.createStroke(stroke)
        if len(self.points) < 2:
            return path
        rect = QRectF(self.points[0], self.points[-1]).normalized()
        if self.mosaic_shape == "ellipse":
            path.addEllipse(rect)
        else:
            path.addRect(rect)
        return path

    def _render_mosaic(self, painter: QPainter, base: QPixmap | None) -> None:
        if base is None or base.isNull():
            return
        path = self._mosaic_path()
        if path.isEmpty():
            return
        bounding = path.boundingRect().toAlignedRect().intersected(base.rect())
        if bounding.width() < 2 or bounding.height() < 2:
            return
        key = (
            base.cacheKey(), bounding.x(), bounding.y(), bounding.width(), bounding.height(),
            self.mosaic_pixel, self.mosaic_effect,
        )
        cached = getattr(self, "_mosaic_cache", None)
        if cached is None or cached[0] != key:
            region = base.copy(bounding)
            block = max(2, int(self.mosaic_pixel))
            down_w = max(1, bounding.width() // block)
            down_h = max(1, bounding.height() // block)
            # 블러는 부드럽게 축소→확대, 모자이크는 최근접 픽셀로 축소→확대
            mode = (
                Qt.TransformationMode.SmoothTransformation
                if self.mosaic_effect == "blur"
                else Qt.TransformationMode.FastTransformation
            )
            down = region.scaled(down_w, down_h, Qt.AspectRatioMode.IgnoreAspectRatio, mode)
            processed = down.scaled(
                bounding.width(), bounding.height(), Qt.AspectRatioMode.IgnoreAspectRatio, mode
            )
            self._mosaic_cache = (key, processed)
            cached = self._mosaic_cache
        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(bounding.topLeft(), cached[1])
        painter.restore()

    # --- 지우개 히트테스트 ---------------------------------------------------

    def hit_test(self, point: QPointF) -> bool:
        if not self.points:
            return False
        margin = max(self.width, 6.0) + 10.0
        if self.tool == "text":
            metrics = QFontMetricsF(self._text_font())
            lines = self.text.splitlines() or [self.text]
            width = max((metrics.horizontalAdvance(line) for line in lines), default=0.0)
            height = metrics.lineSpacing() * max(1, len(lines))
            rect = QRectF(self.points[0], QSizeF(width, height))
            return rect.adjusted(-6, -6, 6, 6).contains(point)
        if self.tool == "mosaic":
            return self._mosaic_path().contains(point)
        path = QPainterPath()
        if self.tool in ("rect", "ellipse"):
            if len(self.points) < 2:
                return False
            rect = QRectF(self.points[0], self.points[-1]).normalized()
            if self.tool == "ellipse":
                path.addEllipse(rect)
            else:
                path.addRect(rect)
        elif len(self.points) >= 2:
            path.moveTo(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
        else:
            dx = point.x() - self.points[0].x()
            dy = point.y() - self.points[0].y()
            return math.hypot(dx, dy) <= margin
        stroker = QPainterPathStroker()
        stroker.setWidth(margin)
        return stroker.createStroke(path).contains(point)


# ---------------------------------------------------------------------------
# 편집 캔버스
# ---------------------------------------------------------------------------


class AnnotationCanvas(QWidget):
    """물리 픽셀 원본 위에 벡터 주석을 얹어 그리는 캔버스.

    주석은 항상 원본(물리 픽셀) 좌표로 저장하고, 화면에는 display_scale로
    축소/확대해 보여준다. 저장 시 원본 해상도로 다시 렌더링하므로 배율이
    걸린 모니터에서도 화질 손실이 없다.
    """

    changed = pyqtSignal()

    def __init__(self, base: QPixmap, display_scale: float) -> None:
        super().__init__()
        self.base = QPixmap(base)
        self.base.setDevicePixelRatio(1.0)
        self.scale = max(0.05, float(display_scale))
        self.annotations: list[Annotation] = []
        # undo/redo는 연산 단위로 기록한다: ("add", ann) | ("remove", [(index, ann), ...])
        self._undo_ops: list[tuple] = []
        self._redo_ops: list[tuple] = []
        self.tool = "none"
        self.shape_kind = "rect"
        self.color = QColor("#EF4444")
        self.width_display = 3
        self.mosaic_shape = "rect"
        self.mosaic_pixel_display = 12
        self.mosaic_effect = "pixel"
        self._active: Annotation | None = None
        self._erase_batch: list[tuple[int, Annotation]] | None = None
        self._drag_origin: QPoint | None = None
        self._text_edit: QTextEdit | None = None
        self._text_anchor_raw: QPointF | None = None
        self.setFixedSize(
            max(1, round(self.base.width() * self.scale)),
            max(1, round(self.base.height() * self.scale)),
        )
        self._apply_cursor()

    # --- 도구/옵션 -------------------------------------------------------

    def set_tool(self, tool: str) -> None:
        self.commit_text()
        self.tool = tool
        self._apply_cursor()

    def _apply_cursor(self) -> None:
        if self.tool == "none":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.tool == "text":
            self.setCursor(Qt.CursorShape.IBeamCursor)
        elif self.tool == "eraser":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def raw_width(self) -> float:
        return max(1.0, self.width_display / self.scale)

    def raw_font_px(self) -> float:
        return max(10.0, (10 + self.width_display * 3) / self.scale)

    def to_raw(self, pos) -> QPointF:
        return QPointF(pos.x() / self.scale, pos.y() / self.scale)

    # --- undo/redo -------------------------------------------------------

    def can_undo(self) -> bool:
        return bool(self._undo_ops)

    def can_redo(self) -> bool:
        return bool(self._redo_ops)

    def undo(self) -> None:
        self.commit_text()
        if not self._undo_ops:
            return
        op = self._undo_ops.pop()
        if op[0] == "add":
            annotation = op[1]
            if annotation in self.annotations:
                self.annotations.remove(annotation)
        else:  # remove → 지웠던 항목을 원래 위치에 복원
            for index, annotation in sorted(op[1]):
                self.annotations.insert(min(index, len(self.annotations)), annotation)
        self._redo_ops.append(op)
        self.update()
        self.changed.emit()

    def redo(self) -> None:
        if not self._redo_ops:
            return
        op = self._redo_ops.pop()
        if op[0] == "add":
            self.annotations.append(op[1])
        else:
            for _index, annotation in op[1]:
                if annotation in self.annotations:
                    self.annotations.remove(annotation)
        self._undo_ops.append(op)
        self.update()
        self.changed.emit()

    def _push(self, annotation: Annotation) -> None:
        self.annotations.append(annotation)
        self._undo_ops.append(("add", annotation))
        self._redo_ops.clear()
        self.update()
        self.changed.emit()

    # --- 합성 -------------------------------------------------------------

    def composed_pixmap(self) -> QPixmap:
        self.commit_text()
        out = QPixmap(self.base)
        out.setDevicePixelRatio(1.0)
        if self.annotations:
            painter = QPainter(out)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            for annotation in self.annotations:
                annotation.render(painter, self.base)
            painter.end()
        return out

    # --- 그리기 ------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.scale(self.scale, self.scale)
        for annotation in self.annotations:
            annotation.render(painter, self.base)
        if self._active is not None:
            self._active.render(painter, self.base)
        painter.end()

    # --- 마우스 ------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool == "none":
            self._drag_origin = event.globalPosition().toPoint() - self.window().pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self.tool == "text":
            self.commit_text()
            self._begin_text(event.position())
            return
        raw = self.to_raw(event.position())
        if self.tool == "eraser":
            self.commit_text()
            self._erase_batch = []
            self._erase_at(raw)
            return
        if self.tool == "mosaic":
            pen_mode = self.mosaic_shape == "pen"
            self._active = Annotation(
                tool="mosaic",
                color=QColor(self.color),
                width=self.raw_width() * (3.0 if pen_mode else 1.0),
                points=[raw],
                mosaic_shape=self.mosaic_shape,
                mosaic_pixel=max(2, round(self.mosaic_pixel_display / self.scale)),
                mosaic_effect=self.mosaic_effect,
            )
            return
        self._active = Annotation(
            tool=self.shape_kind if self.tool == "shape" else self.tool,
            color=QColor(self.color),
            width=self.raw_width() * (2.6 if self.tool == "marker" else 1.0),
            points=[raw],
        )

    def _is_freehand(self, annotation: Annotation) -> bool:
        if annotation.tool in ("pen", "marker"):
            return True
        return annotation.tool == "mosaic" and annotation.mosaic_shape == "pen"

    def mouseMoveEvent(self, event) -> None:
        if self.tool == "none" and self._drag_origin is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_origin)
            return
        if self.tool == "eraser" and self._erase_batch is not None:
            self._erase_at(self.to_raw(event.position()))
            return
        if self._active is None:
            return
        raw = self.to_raw(event.position())
        if self._is_freehand(self._active):
            self._active.points.append(raw)
        else:
            if len(self._active.points) > 1:
                self._active.points[-1] = raw
            else:
                self._active.points.append(raw)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool == "none":
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        if self.tool == "eraser":
            if self._erase_batch:
                self._undo_ops.append(("remove", self._erase_batch))
                self._redo_ops.clear()
                self.changed.emit()
            self._erase_batch = None
            return
        if self._active is not None:
            if len(self._active.points) >= 2:
                self._push(self._active)
            self._active = None
            self.update()

    def _erase_at(self, raw: QPointF) -> None:
        """커서 아래 가장 위에 그려진 주석 하나를 지운다 (제스처 단위 undo)."""
        if self._erase_batch is None:
            return
        for index in range(len(self.annotations) - 1, -1, -1):
            annotation = self.annotations[index]
            try:
                hit = annotation.hit_test(raw)
            except Exception:
                hit = False
            if hit:
                self.annotations.pop(index)
                self._erase_batch.append((index, annotation))
                self.update()
                break

    # --- 텍스트 ------------------------------------------------------------

    def _begin_text(self, display_pos) -> None:
        editor = QTextEdit(self)
        editor.setFrameShape(QFrame.Shape.NoFrame)
        font = QFont("Malgun Gothic")
        font.setPixelSize(max(8, round(self.raw_font_px() * self.scale)))
        font.setBold(True)
        editor.setFont(font)
        editor.setStyleSheet(
            "QTextEdit { background: rgba(255,255,255,40); border: 1px dashed %s; color: %s; }"
            % (ACCENT, self.color.name())
        )
        editor.setPlaceholderText("텍스트 입력")
        width = max(160, self.width() - int(display_pos.x()) - 8)
        editor.setGeometry(int(display_pos.x()), int(display_pos.y()), min(width, 320), 72)
        editor.show()
        editor.setFocus()
        editor.installEventFilter(self)
        self._text_edit = editor
        self._text_anchor_raw = self.to_raw(display_pos)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._text_edit:
            if event.type() == event.Type.FocusOut:
                self.commit_text()
                return False
            if event.type() == event.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._discard_text()
                return True
        return super().eventFilter(obj, event)

    def commit_text(self) -> None:
        editor = self._text_edit
        if editor is None:
            return
        self._text_edit = None
        text = editor.toPlainText().rstrip()
        anchor = self._text_anchor_raw
        editor.deleteLater()
        self._text_anchor_raw = None
        if text and anchor is not None:
            self._push(
                Annotation(
                    tool="text",
                    color=QColor(self.color),
                    width=1.0,
                    points=[anchor],
                    text=text,
                    font_px=self.raw_font_px(),
                )
            )

    def _discard_text(self) -> None:
        editor = self._text_edit
        self._text_edit = None
        self._text_anchor_raw = None
        if editor is not None:
            editor.deleteLater()


# ---------------------------------------------------------------------------
# 편집 창
# ---------------------------------------------------------------------------

_TOOL_DEFS = [
    ("shape", "🟦", "도형 (사각형/원)"),
    ("arrow", "↗️", "화살표"),
    ("line", "📏", "직선"),
    ("pen", "✏️", "연필"),
    ("marker", "🖍️", "형광펜"),
    ("mosaic", "🌫️", "모자이크 / 블러"),
    ("text", "🔤", "텍스트"),
    ("eraser", "🧽", "지우개 (그린 항목 삭제)"),
]

_PALETTE = ["#EF4444", "#F97316", "#FACC15", "#22C55E", "#3B82F6", "#8B5CF6", "#111827", "#FFFFFF"]

# QToolButton 크기를 고정(min=max)하지 않으면 이모지 글리프가 패딩과 겹쳐
# 세로로 눌린 것처럼 잘려 보인다. 버튼 박스를 넉넉히 고정하고 패딩은 0으로.
# 컬러 이모지("Segoe UI Emoji")를 쓰고, 툴바가 아이콘보다 길쭉해 보이지
# 않도록 버튼 박스를 28x26으로 잡는다.
_TOOLBAR_QSS = f"""
QWidget#snipBar {{
    background: #FFFFFF;
    border: 1px solid #D8DEE9;
    border-radius: 8px;
}}
QWidget#snipBar QToolButton {{
    border: 0; border-radius: 6px; padding: 0px;
    font-family: "Segoe UI Emoji", "Malgun Gothic";
    font-size: 11pt; font-weight: 700; color: #334155; background: transparent;
    min-width: 28px; max-width: 28px; min-height: 26px; max-height: 26px;
}}
QWidget#snipBar QToolButton:hover {{ background: #EEF2FF; }}
QWidget#snipBar QToolButton:checked {{ background: #DBEAFE; color: {ACCENT}; }}
QWidget#snipBar QToolButton:disabled {{ color: #C3CAD6; }}
QWidget#snipBar QToolButton#wideButton {{
    min-width: 52px; max-width: 72px; padding: 0px 6px; font-size: 9pt;
    font-family: "Malgun Gothic";
}}
QWidget#snipBar QLabel {{ color: #64748B; font-size: 9pt; }}
"""


class SnipEditorWindow(QWidget):
    """캡처 직후 나타나는 프레임 없는 최상위 편집 창."""

    def __init__(self, pixmap: QPixmap, logical_anchor: QRect, window_title: str, tab) -> None:
        super().__init__()
        self.tab = tab
        self.capture_title = window_title or "창 제목 없음"
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        anchor_center = logical_anchor.center() if not logical_anchor.isNull() else QCursor.pos()
        screen = QApplication.screenAt(anchor_center) or QApplication.primaryScreen()
        dpr = float(screen.devicePixelRatio()) or 1.0
        pix_dpr = float(pixmap.devicePixelRatio()) or 1.0
        display_scale = 1.0 / (pix_dpr if abs(pix_dpr - 1.0) > 0.001 else dpr)
        available = screen.availableGeometry()
        raw_size = QSize(pixmap.width(), pixmap.height())
        max_w = available.width() * 0.92
        max_h = available.height() * 0.86
        if raw_size.width() * display_scale > max_w:
            display_scale = max_w / raw_size.width()
        if raw_size.height() * display_scale > max_h:
            display_scale = max_h / raw_size.height()

        self.canvas = AnnotationCanvas(pixmap, display_scale)
        self.canvas.changed.connect(self._sync_history_buttons)

        margin = 14
        outer = QVBoxLayout(self)
        outer.setContentsMargins(margin, margin, margin, margin)
        frame = QFrame()
        frame.setObjectName("snipEditorFrame")
        frame.setStyleSheet(
            "QFrame#snipEditorFrame { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; }"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 110))
        frame.setGraphicsEffect(shadow)
        outer.addWidget(frame)

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(6, 6, 6, 6)
        inner.setSpacing(6)
        inner.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignHCenter)
        inner.addWidget(self._build_toolbar(), 0, Qt.AlignmentFlag.AlignHCenter)
        self.options_bar = self._build_options_bar()
        inner.addWidget(self.options_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        self.options_bar.hide()

        self._install_shortcuts()
        self._place(logical_anchor, available, margin)

    # --- UI 구성 -----------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("snipBar")
        bar.setStyleSheet(_TOOLBAR_QSS)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(2)
        self.tool_buttons: dict[str, QToolButton] = {}
        for tool, glyph, tip in _TOOL_DEFS:
            button = QToolButton()
            button.setText(glyph)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, value=tool: self._select_tool(value if checked else "none"))
            layout.addWidget(button)
            self.tool_buttons[tool] = button
        layout.addWidget(self._separator())
        self.undo_btn = self._action_button("↩️", "되돌리기 (Ctrl+Z)", self._undo)
        self.redo_btn = self._action_button("↪️", "다시 실행 (Ctrl+Y)", self._redo)
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)
        layout.addWidget(self._separator())
        layout.addWidget(self._action_button("📌", "고정 (화면에 붙이기)", self._pin))
        layout.addWidget(self._action_button("📋", "클립보드 복사 (Ctrl+C)", self._copy))
        layout.addWidget(self._action_button("💾", "캡처 · 그리기에 저장 (Ctrl+S)", self._save))
        layout.addWidget(self._action_button("🗂️", "다른 이름으로 저장", self._save_as))
        layout.addWidget(self._action_button("🧾", "컨닝페이퍼로 이동", self._move_to_cheat))
        layout.addWidget(self._separator())
        layout.addWidget(self._action_button("❌", "닫기 (Esc)", self.close))
        self._sync_history_buttons()
        return bar

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet("color: #E2E8F0;")
        return line

    def _action_button(self, glyph: str, tip: str, callback) -> QToolButton:
        button = QToolButton()
        button.setText(glyph)
        button.setToolTip(tip)
        button.clicked.connect(callback)
        return button

    def _build_options_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("snipBar")
        bar.setStyleSheet(_TOOLBAR_QSS)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(4)

        # 도형 모양 (도형 도구 전용)
        self.shape_rect_btn = self._option_toggle("▭", "사각형", lambda: self._set_shape("rect"))
        self.shape_rect_btn.setChecked(True)
        self.shape_ellipse_btn = self._option_toggle("◯", "원", lambda: self._set_shape("ellipse"))
        self._shape_sep = self._separator()
        layout.addWidget(self.shape_rect_btn)
        layout.addWidget(self.shape_ellipse_btn)
        layout.addWidget(self._shape_sep)

        # 모자이크 컨트롤 (모자이크 도구 전용): 적용 모양 + 효과 + 픽셀 크기
        self.mosaic_pen_btn = self._option_toggle("✎", "연필로 칠해서 적용", lambda: self._set_mosaic_shape("pen"))
        self.mosaic_rect_btn = self._option_toggle("▭", "사각형 영역 적용", lambda: self._set_mosaic_shape("rect"))
        self.mosaic_rect_btn.setChecked(True)
        self.mosaic_ellipse_btn = self._option_toggle("◯", "원 영역 적용", lambda: self._set_mosaic_shape("ellipse"))
        self.mosaic_pixel_btn = self._option_toggle("모자이크", "픽셀 모자이크", lambda: self._set_mosaic_effect("pixel"))
        self.mosaic_pixel_btn.setObjectName("wideButton")
        self.mosaic_pixel_btn.setChecked(True)
        self.mosaic_blur_btn = self._option_toggle("블러", "흐림 효과", lambda: self._set_mosaic_effect("blur"))
        self.mosaic_blur_btn.setObjectName("wideButton")
        self.mosaic_pixel_label = QLabel("픽셀 크기")
        self.mosaic_pixel_slider = QSlider(Qt.Orientation.Horizontal)
        self.mosaic_pixel_slider.setRange(4, 64)
        self.mosaic_pixel_slider.setValue(self.canvas.mosaic_pixel_display)
        self.mosaic_pixel_slider.setFixedWidth(80)
        self.mosaic_pixel_slider.valueChanged.connect(
            lambda value: setattr(self.canvas, "mosaic_pixel_display", value)
        )
        self._mosaic_sep = self._separator()
        for widget in (
            self.mosaic_pen_btn, self.mosaic_rect_btn, self.mosaic_ellipse_btn,
            self.mosaic_pixel_btn, self.mosaic_blur_btn,
            self.mosaic_pixel_label, self.mosaic_pixel_slider, self._mosaic_sep,
        ):
            layout.addWidget(widget)

        # 색상 (그리기/텍스트 도구)
        self.swatch_buttons: list[QToolButton] = []
        for color_hex in _PALETTE:
            swatch = QToolButton()
            swatch.setCheckable(True)
            swatch.setToolTip(color_hex)
            swatch.setStyleSheet(
                "QToolButton { background: %s; border: 2px solid #E2E8F0; border-radius: 10px;"
                " min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; padding: 0; }"
                "QToolButton:checked { border-color: %s; }" % (color_hex, ACCENT)
            )
            swatch.clicked.connect(lambda checked, value=color_hex: self._set_color(value))
            layout.addWidget(swatch)
            self.swatch_buttons.append(swatch)
        self.custom_color_btn = QToolButton()
        self.custom_color_btn.setText("…")
        self.custom_color_btn.setToolTip("다른 색상")
        self.custom_color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self.custom_color_btn)
        self._color_sep = self._separator()
        layout.addWidget(self._color_sep)

        self.width_label = QLabel("굵기")
        layout.addWidget(self.width_label)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 16)
        self.width_slider.setValue(self.canvas.width_display)
        self.width_slider.setFixedWidth(90)
        self.width_slider.valueChanged.connect(self._set_width)
        layout.addWidget(self.width_slider)
        self._sync_swatches()
        return bar

    def _option_toggle(self, glyph: str, tip: str, callback) -> QToolButton:
        button = QToolButton()
        button.setText(glyph)
        button.setToolTip(tip)
        button.setCheckable(True)
        button.clicked.connect(callback)
        return button

    def _install_shortcuts(self) -> None:
        bindings = [
            (QKeySequence(QKeySequence.StandardKey.Undo), self._undo),
            (QKeySequence("Ctrl+Y"), self._redo),
            (QKeySequence("Ctrl+Shift+Z"), self._redo),
            (QKeySequence(QKeySequence.StandardKey.Copy), self._copy),
            (QKeySequence("Ctrl+S"), self._save),
        ]
        for sequence, callback in bindings:
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _place(self, anchor: QRect, available: QRect, margin: int) -> None:
        self.adjustSize()
        if anchor.isNull():
            target = QPoint(
                available.center().x() - self.width() // 2,
                available.center().y() - self.height() // 2,
            )
        else:
            target = QPoint(anchor.left() - margin - 7, anchor.top() - margin - 7)
        x = min(max(target.x(), available.left()), available.right() - self.width() + 1)
        y = min(max(target.y(), available.top()), available.bottom() - self.height() + 1)
        self.move(QPoint(x, y))

    # --- 도구/옵션 상태 ------------------------------------------------------

    def _select_tool(self, tool: str) -> None:
        for name, button in self.tool_buttons.items():
            button.setChecked(name == tool)
        self.canvas.set_tool(tool)
        self.options_bar.setVisible(tool not in ("none", "eraser"))
        is_shape = tool == "shape"
        self.shape_rect_btn.setVisible(is_shape)
        self.shape_ellipse_btn.setVisible(is_shape)
        self._shape_sep.setVisible(is_shape)
        is_mosaic = tool == "mosaic"
        for widget in (
            self.mosaic_pen_btn, self.mosaic_rect_btn, self.mosaic_ellipse_btn,
            self.mosaic_pixel_btn, self.mosaic_blur_btn,
            self.mosaic_pixel_label, self.mosaic_pixel_slider, self._mosaic_sep,
        ):
            widget.setVisible(is_mosaic)
        # 모자이크는 색상이 필요 없다. 굵기 슬라이더는 연필 모드의 붓 두께로 쓰인다.
        show_colors = tool in ("shape", "arrow", "line", "pen", "marker", "text")
        for widget in self.swatch_buttons:
            widget.setVisible(show_colors)
        self.custom_color_btn.setVisible(show_colors)
        self._color_sep.setVisible(show_colors)
        self.width_label.setText("크기" if tool == "text" else "굵기")
        if tool == "marker" and self.canvas.color.name().upper() not in ("#FACC15", "#FDE047"):
            self._set_color("#FACC15")
        self.adjustSize()

    def _set_shape(self, kind: str) -> None:
        self.canvas.shape_kind = kind
        self.shape_rect_btn.setChecked(kind == "rect")
        self.shape_ellipse_btn.setChecked(kind == "ellipse")

    def _set_mosaic_shape(self, kind: str) -> None:
        self.canvas.mosaic_shape = kind
        self.mosaic_pen_btn.setChecked(kind == "pen")
        self.mosaic_rect_btn.setChecked(kind == "rect")
        self.mosaic_ellipse_btn.setChecked(kind == "ellipse")

    def _set_mosaic_effect(self, effect: str) -> None:
        self.canvas.mosaic_effect = effect
        self.mosaic_pixel_btn.setChecked(effect == "pixel")
        self.mosaic_blur_btn.setChecked(effect == "blur")

    def _set_color(self, color_hex: str) -> None:
        self.canvas.color = QColor(color_hex)
        self._sync_swatches()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self.canvas.color, self, "색상 선택")
        if color.isValid():
            self.canvas.color = color
            self._sync_swatches()

    def _sync_swatches(self) -> None:
        current = self.canvas.color.name().upper()
        for button, color_hex in zip(self.swatch_buttons, _PALETTE):
            button.setChecked(color_hex.upper() == current)

    def _set_width(self, value: int) -> None:
        self.canvas.width_display = value

    def _sync_history_buttons(self) -> None:
        self.undo_btn.setEnabled(self.canvas.can_undo())
        self.redo_btn.setEnabled(self.canvas.can_redo())

    def _undo(self) -> None:
        self.canvas.undo()
        self._sync_history_buttons()

    def _redo(self) -> None:
        self.canvas.redo()
        self._sync_history_buttons()

    # --- 액션 ---------------------------------------------------------------

    def _copy(self) -> None:
        copy_snip_to_clipboard(self.canvas.composed_pixmap())

    def _save(self) -> None:
        self.tab.save_snip_capture(self.canvas.composed_pixmap(), self.capture_title)
        self.close()

    def _save_as(self) -> None:
        save_pixmap_as(self, self.canvas.composed_pixmap())

    def _move_to_cheat(self) -> None:
        if self.tab.move_snip_to_cheat_sheet(self.canvas.composed_pixmap(), self.capture_title):
            self.close()

    def _pin(self) -> None:
        composed = self.canvas.composed_pixmap()
        top_left = self.canvas.mapToGlobal(QPoint(0, 0))
        pinned = PinnedImageWindow(composed, top_left, self.capture_title, self.tab)
        self.tab.register_snip_window(pinned)
        pinned.show()
        self.close()


# ---------------------------------------------------------------------------
# 고정 창
# ---------------------------------------------------------------------------


class PinnedImageWindow(QWidget):
    """테두리 없는 최상위 고정 창. 모든 조작은 우클릭 메뉴로 한다."""

    ZOOM_LEVELS = (30, 50, 70, 100, 150, 200)
    MARGIN = 12

    def __init__(self, pixmap: QPixmap, logical_pos: QPoint, window_title: str, tab) -> None:
        super().__init__()
        self.tab = tab
        self.capture_title = window_title or "고정 이미지"
        self.raw = QPixmap(pixmap)
        self.raw.setDevicePixelRatio(1.0)
        self.zoom = 100
        self._drag_offset: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.frame = QFrame()
        self.frame.setObjectName("snipPinFrame")
        self.frame.setStyleSheet(
            "QFrame#snipPinFrame { background: #FFFFFF; border: 1px solid rgba(100,116,139,90); border-radius: 3px; }"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(15, 23, 42, 120))
        self.frame.setGraphicsEffect(shadow)
        outer.addWidget(self.frame)

        inner = QVBoxLayout(self.frame)
        inner.setContentsMargins(1, 1, 1, 1)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(self.label)

        self.move(logical_pos - QPoint(self.MARGIN + 1, self.MARGIN + 1))
        self._refresh_view()

    # --- 표시 ---------------------------------------------------------------

    def _current_dpr(self) -> float:
        screen = self.screen() or QApplication.primaryScreen()
        return float(screen.devicePixelRatio()) or 1.0 if screen else 1.0

    def _refresh_view(self) -> None:
        dpr = self._current_dpr()
        device_w = max(1, round(self.raw.width() * self.zoom / 100))
        device_h = max(1, round(self.raw.height() * self.zoom / 100))
        scaled = self.raw.scaled(
            device_w,
            device_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self.label.setPixmap(scaled)
        self.label.setFixedSize(max(1, round(device_w / dpr)), max(1, round(device_h / dpr)))
        self.adjustSize()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        pixmap = self.label.pixmap()
        if pixmap is not None and abs(pixmap.devicePixelRatio() - self._current_dpr()) > 0.001:
            self._refresh_view()

    # --- 이동 ---------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    # --- 우클릭 메뉴 ----------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("이미지 복사", self._copy)
        menu.addAction("다른 이름으로 이미지 저장...", self._save_as)
        menu.addSeparator()
        menu.addAction("툴바 보기 (편집)", self._open_editor)
        menu.addSeparator()

        zoom_menu = menu.addMenu("확대")
        zoom_group = QActionGroup(zoom_menu)
        zoom_group.setExclusive(True)
        for level in self.ZOOM_LEVELS:
            action = QAction(f"{level}%", zoom_menu, checkable=True)
            action.setChecked(level == self.zoom)
            action.triggered.connect(lambda checked, value=level: self._set_zoom(value))
            zoom_group.addAction(action)
            zoom_menu.addAction(action)

        transform_menu = menu.addMenu("이미지 처리")
        transform_menu.addAction("왼쪽 회전", lambda: self._transform(rotate=-90))
        transform_menu.addAction("오른쪽 회전", lambda: self._transform(rotate=90))
        transform_menu.addAction("수평 뒤집기", lambda: self._transform(flip_h=True))
        transform_menu.addAction("수직 뒤집기", lambda: self._transform(flip_v=True))

        menu.addSeparator()
        menu.addAction("캡처 · 그리기에 저장", self._save_to_steel)
        self._build_cheat_menu(menu.addMenu("컨닝페이퍼로 이동"))
        menu.addSeparator()
        menu.addAction("닫기", self.close)
        menu.exec(event.globalPos())

    def _build_cheat_menu(self, menu: QMenu) -> None:
        """컨닝페이퍼로 이동: 저장할 그룹(폴더)을 골라서 넣을 수 있다."""
        menu.addAction("🏠 최상위", lambda: self._move_to_cheat(""))
        data = getattr(getattr(self.tab, "main", None), "data", None)
        if not isinstance(data, dict):
            return
        try:
            from ui.groups import GROUP_SCOPE_CHEAT, group_icon, group_id, groups_in
        except Exception:
            return

        def add_actions(parent_id: str, depth: int) -> None:
            for group in groups_in(data, GROUP_SCOPE_CHEAT, parent_id):
                gid = group_id(group)
                label = ("    " * depth) + f"{group_icon(group)} {group.get('name', '')}"
                menu.addAction(label, lambda checked=False, value=gid: self._move_to_cheat(value))
                add_actions(gid, depth + 1)

        add_actions("", 0)

    # --- 메뉴 액션 -------------------------------------------------------------

    def _copy(self) -> None:
        copy_snip_to_clipboard(self.raw)

    def _save_as(self) -> None:
        save_pixmap_as(self, self.raw)

    def _open_editor(self) -> None:
        """고정 이미지를 편집 툴바가 있는 창으로 다시 연다."""
        anchor = QRect(self.label.mapToGlobal(QPoint(0, 0)), self.label.size())
        editor = SnipEditorWindow(self.raw, anchor, self.capture_title, self.tab)
        self.tab.register_snip_window(editor)
        editor.show()
        editor.raise_()
        editor.activateWindow()
        self.close()

    def set_zoom(self, level: int) -> None:
        """가장 가까운 지원 배율로 스냅해 적용한다."""
        self._set_zoom(min(self.ZOOM_LEVELS, key=lambda value: abs(value - level)))

    def _set_zoom(self, level: int) -> None:
        self.zoom = level
        self._refresh_view()

    def _transform(self, rotate: int = 0, flip_h: bool = False, flip_v: bool = False) -> None:
        transform = QTransform()
        if rotate:
            transform.rotate(rotate)
        if flip_h:
            transform.scale(-1, 1)
        if flip_v:
            transform.scale(1, -1)
        self.raw = self.raw.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        self.raw.setDevicePixelRatio(1.0)
        self._refresh_view()

    def _save_to_steel(self) -> None:
        self.tab.save_snip_capture(self.raw, self.capture_title)

    def _move_to_cheat(self, group_id: str = "") -> None:
        if self.tab.move_snip_to_cheat_sheet(self.raw, self.capture_title, group_id):
            self.close()


# ---------------------------------------------------------------------------
# 공용 유틸
# ---------------------------------------------------------------------------


def copy_snip_to_clipboard(pixmap: QPixmap) -> None:
    if pixmap.isNull():
        return
    image = pixmap.toImage().copy()
    clipboard = QApplication.clipboard()
    app = QApplication.instance()
    if app is not None:
        app._last_capture_clipboard_image = image

    def set_image() -> None:
        current = clipboard.image()
        if current.isNull() or current.size() != image.size():
            clipboard.setImage(image)

    clipboard.setImage(image)
    for delay in (60, 180, 350):
        QTimer.singleShot(delay, set_image)


def save_pixmap_as(parent: QWidget, pixmap: QPixmap) -> None:
    from datetime import datetime

    default = f"snip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path, selected = QFileDialog.getSaveFileName(
        parent, "다른 이름으로 저장", default, "PNG 이미지 (*.png);;JPG 이미지 (*.jpg)"
    )
    if not path:
        return
    fmt = "JPG" if path.lower().endswith((".jpg", ".jpeg")) else "PNG"
    pixmap.save(path, fmt, 95 if fmt == "JPG" else -1)
