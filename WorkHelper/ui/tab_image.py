from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QEventLoop, QPoint, QRect, QSize, QThreadPool, QTimer, Qt
from PyQt6.QtGui import QColor, QCursor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.screen_utils import virtual_screen_geometry
from app.utils import display_hotkey, new_id, now_iso, resolve_image_path
from ui.snip import PinnedImageWindow, SnipEditorWindow, SnipOverlay
from ui.common import (
    CARD_ACTION_ICON_SIZE,
    CARD_ACTION_ROW_MARGIN_X,
    CARD_ACTION_ROW_MARGIN_Y,
    CARD_ACTION_ROW_SPACING,
    CARD_CONTENT_TOP_MARGIN,
    GridPanel,
    HotkeyFields,
    SortControls,
    add_card_actions,
    apply_manual_reorder,
    bottom_action_bar,
    bump_usage,
    confirm_delete,
    confirm_shift_digit_hotkey,
    fit_combo_to_contents,
    ImageSaveWorker,
    make_card,
    make_icon_button,
    set_card_action_widget,
    show_modern_info,
    show_modern_warning,
)
from ui.groups import (
    GROUP_SCOPE_CHEAT,
    GroupDialog,
    build_group_combo,
    count_group_contents,
    create_group,
    delete_group,
    group_by_id,
    group_id,
    groups_in,
    item_group_id,
    make_back_card,
    make_breadcrumb_label,
    make_group_card,
    show_move_to_group_menu,
    toggle_group_favorite,
    update_breadcrumb_label,
    valid_group_id,
)

STEEL_CUT_CARD_HEIGHT = 82


def active_window_title() -> str:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szDevice", ctypes.c_wchar * 32),
    ]


def _physical_rect_to_logical(rect: QRect) -> QRect:
    """Convert a GetWindowRect-style physical-pixel rect to Qt's logical coordinates.

    GetWindowRect always reports physical pixels once the process is
    per-monitor DPI aware, but the rest of the capture pipeline (screen
    geometry, rubber-band selections) works in Qt's logical/scaled pixels.
    Without this conversion, capturing the active window on any monitor
    that isn't at 100% scaling grabs the wrong region.
    """
    try:
        user32 = ctypes.windll.user32
        win_rect = ctypes.wintypes.RECT(rect.left(), rect.top(), rect.right(), rect.bottom())
        hmonitor = user32.MonitorFromRect(ctypes.byref(win_rect), 2)  # MONITOR_DEFAULTTONEAREST
        info = _MonitorInfoEx()
        info.cbSize = ctypes.sizeof(_MonitorInfoEx)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return rect
        for screen in QApplication.screens():
            if screen.name() != info.szDevice:
                continue
            dpr = float(screen.devicePixelRatio()) or 1.0
            dx = rect.left() - info.rcMonitor.left
            dy = rect.top() - info.rcMonitor.top
            logical_left = screen.geometry().left() + round(dx / dpr)
            logical_top = screen.geometry().top() + round(dy / dpr)
            return QRect(logical_left, logical_top, round(rect.width() / dpr), round(rect.height() / dpr))
    except Exception:
        pass
    return rect


def active_window_rect() -> QRect:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            physical = QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
            return _physical_rect_to_logical(physical)
    except Exception:
        pass
    screen = QApplication.primaryScreen()
    return screen.geometry() if screen else QRect()


def exec_capture_dialog(dialog: QDialog) -> QDialog.DialogCode:
    return dialog.exec()


def copy_pixmap_to_clipboard(pixmap: QPixmap) -> None:
    if pixmap.isNull():
        return
    image = pixmap.toImage().copy()
    clipboard = QApplication.clipboard()
    app = QApplication.instance()
    if app is not None:
        app._last_capture_clipboard_image = image

    def image_is_current() -> bool:
        current = clipboard.image()
        return (
            not current.isNull()
            and current.size() == image.size()
            and current.format() == image.format()
        )

    def set_image(force: bool = False) -> None:
        mime = clipboard.mimeData()
        if not force and mime is not None and mime.hasText() and not mime.hasImage():
            return
        if force or not image_is_current():
            clipboard.setImage(image)
            QApplication.processEvents()

    set_image(force=True)
    for delay in (35, 90, 180, 320):
        QTimer.singleShot(delay, set_image)


def _screen_source_rect(screen, logical_rect: QRect, full_pixmap: QPixmap) -> QRect:
    geometry = screen.geometry()
    local = logical_rect.translated(-geometry.topLeft())
    scale_x = full_pixmap.width() / max(1, geometry.width())
    scale_y = full_pixmap.height() / max(1, geometry.height())
    left = round(local.left() * scale_x)
    top = round(local.top() * scale_y)
    right = round((local.right() + 1) * scale_x)
    bottom = round((local.bottom() + 1) * scale_y)
    return QRect(left, top, max(1, right - left), max(1, bottom - top))


def capture_screen_rect(rect: QRect) -> QPixmap:
    """Capture the selected logical rect exactly on mixed-DPI monitor setups."""
    if rect.width() < 1 or rect.height() < 1:
        return QPixmap()
    pillow_capture = capture_screen_rect_with_pillow(rect)
    if not pillow_capture.isNull():
        return pillow_capture
    captures: list[tuple[object, QRect, QPixmap, QRect]] = []
    for screen in QApplication.screens():
        intersected = rect.intersected(screen.geometry())
        if intersected.isEmpty():
            continue
        full = screen.grabWindow(0)
        if full.isNull():
            continue
        source = _screen_source_rect(screen, intersected, full).intersected(full.rect())
        if source.isEmpty():
            continue
        captures.append((screen, intersected, full, source))
    if not captures:
        return QPixmap()
    if len(captures) == 1 and captures[0][1] == rect:
        screen, intersected, full, source = captures[0]
        pixmap = full.copy(source)
        # Measure DPR from the physical pixel buffer divided by the screen's
        # logical width — not the selection width. Using intersected.width()
        # (the selection rect) would give a wildly wrong ratio whenever the
        # capture rect is smaller than the screen (e.g. window capture mode).
        measured_dpr = full.width() / max(1, screen.geometry().width())
        pixmap.setDevicePixelRatio(measured_dpr if measured_dpr > 0 else 1.0)
        return pixmap

    pixmap = QPixmap(rect.size())
    pixmap.setDevicePixelRatio(1.0)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    for _screen, intersected, full, source in captures:
        target = intersected.translated(-rect.topLeft())
        painter.drawPixmap(target, full, source)
    painter.end()
    return pixmap


def crop_pixmap_dip(pixmap: QPixmap, local_rect: QRect) -> QPixmap:
    """Crop `local_rect` (device-independent pixels) out of `pixmap`.

    QPixmap.copy() takes its rectangle in the pixmap's raw device-pixel
    buffer, not in the device-independent coordinates implied by its
    devicePixelRatio(). A snapshot grabbed on a single non-100%-scaled
    monitor (see capture_screen_rect()'s single-capture branch) keeps a raw
    buffer larger than its DIP size, so a naive copy() with a DIP rect grabs
    the wrong region. Scale the rect by the pixmap's own ratio first.
    """
    dpr = pixmap.devicePixelRatio() or 1.0
    if abs(dpr - 1.0) < 0.001:
        raw_rect = local_rect
    else:
        raw_rect = QRect(
            round(local_rect.left() * dpr),
            round(local_rect.top() * dpr),
            round(local_rect.width() * dpr),
            round(local_rect.height() * dpr),
        )
    cropped = pixmap.copy(raw_rect)
    cropped.setDevicePixelRatio(dpr)
    return cropped


def next_capture_path(directory: Path, suffix: str = ".jpg") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for number in range(1, 1000):
        path = directory / f"{stamp}_{number:03d}{suffix}"
        if not path.exists():
            return path
    return directory / f"{stamp}_{new_id('capture')}{suffix}"


def next_capture_jpg_path(directory: Path) -> Path:
    return next_capture_path(directory, ".jpg")


def save_capture_jpg(pixmap: QPixmap, path: Path) -> bool:
    return pixmap.save(str(path), "JPG", 95)


def capture_screen_rect_with_pillow(rect: QRect) -> QPixmap:
    if not sys.platform.startswith("win") or rect.width() < 1 or rect.height() < 1:
        return QPixmap()
    # ImageGrab's bbox is in physical pixels, but `rect` is in Qt's logical
    # (DPI-scaled) coordinates. Those only line up when every monitor the
    # selection touches is at 100% scaling; on a scaled monitor this grabs a
    # smaller/shifted physical region than what was actually dragged. Skip
    # the fast path there so capture_screen_rect() falls back to the
    # per-screen grabWindow path below, which already scales correctly.
    for screen in QApplication.screens():
        if abs(screen.devicePixelRatio() - 1.0) > 0.001 and rect.intersects(screen.geometry()):
            return QPixmap()
    try:
        from PIL import ImageGrab
    except Exception:
        return QPixmap()
    try:
        image = ImageGrab.grab(
            bbox=(rect.left(), rect.top(), rect.right() + 1, rect.bottom() + 1),
            all_screens=True,
        ).convert("RGBA")
    except Exception:
        return QPixmap()
    # The 100%-scaling assumption above can still be wrong (e.g. a stale or
    # rounded devicePixelRatio() reported by Qt). If the grabbed image isn't
    # exactly the requested logical size, the bbox didn't line up with
    # physical pixels 1:1, so discard it and let the caller fall back to the
    # per-screen grabWindow path instead of returning a shifted/scaled image.
    if image.width != rect.width() or image.height != rect.height():
        return QPixmap()
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)

def _capture_per_screen_physical(screens: list) -> "list[QPixmap | None]":
    """각 모니터를 물리 해상도 그대로 캡처한다 (오버레이 표시용).

    PIL ImageGrab.grab(all_screens=True)로 가상 화면 전체를 물리 픽셀 단위로
    한 번만 캡처한 뒤, Win32 EnumDisplayMonitors로 얻은 물리 좌표를 사용해
    각 모니터 영역을 크롭하고 해당 화면의 devicePixelRatio를 설정한다.
    grabWindow(0)는 nativeSize=-1 처리 방식이 Qt 버전·플랫폼마다 달라
    반환 픽스맵 크기와 DPR이 불일치할 수 있으므로 이 방법을 대신 사용한다.
    """
    if not sys.platform.startswith("win") or not screens:
        return [None] * len(screens)
    try:
        from PIL import ImageGrab
    except Exception:
        return [None] * len(screens)
    try:
        user32 = ctypes.windll.user32
        # 가상 화면 물리 원점 (SM_XVIRTUALSCREEN=76, SM_YVIRTUALSCREEN=77)
        virt_left: int = user32.GetSystemMetrics(76)
        virt_top: int = user32.GetSystemMetrics(77)

        class _MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint32),
                ("rcMonitor", ctypes.wintypes.RECT),
                ("rcWork", ctypes.wintypes.RECT),
                ("dwFlags", ctypes.c_uint32),
                ("szDevice", ctypes.c_wchar * 32),
            ]

        phys_by_name: dict[str, tuple[int, int, int, int]] = {}

        _MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(ctypes.wintypes.RECT), ctypes.c_void_p,
        )

        def _cb(hMon, _hdc, _lpRc, _dw):
            info = _MONITORINFOEX()
            info.cbSize = ctypes.sizeof(_MONITORINFOEX)
            if user32.GetMonitorInfoW(hMon, ctypes.byref(info)):
                name = info.szDevice.rstrip("\x00")
                r = info.rcMonitor
                phys_by_name[name] = (r.left, r.top, r.right - r.left, r.bottom - r.top)
            return True

        user32.EnumDisplayMonitors(None, None, _MonitorEnumProc(_cb), 0)

        # 가상 화면 전체를 물리 해상도로 한 번 캡처
        full_img = ImageGrab.grab(all_screens=True).convert("RGBA")

        result: list[QPixmap | None] = []
        for screen in screens:
            phys = phys_by_name.get(screen.name())
            if phys is None:
                result.append(None)
                continue
            pl, pt, pw, ph = phys
            # PIL 이미지 좌표 = 물리 좌표 - 가상 화면 원점
            cl, ct = pl - virt_left, pt - virt_top
            cropped = full_img.crop((cl, ct, cl + pw, ct + ph))
            raw = cropped.tobytes("raw", "RGBA")
            qimg = QImage(raw, pw, ph, QImage.Format.Format_RGBA8888).copy()
            pix = QPixmap.fromImage(qimg)
            pix.setDevicePixelRatio(screen.devicePixelRatio())
            result.append(pix)

        return result
    except Exception:
        return [None] * len(screens)


class _ScreenCapturePanel(QDialog):
    """단일 모니터를 덮는 캡처 오버레이 패널.

    단일 대형 창으로 전체 가상 화면을 덮으면 Qt가 창 전체에 단일 DPR을 적용하여
    150% 배율 모니터에서 콘텐츠가 67% 크기로 축소된다. 모니터별 독립 창을 쓰면
    Qt가 각 창에 해당 모니터의 올바른 DPR을 자동으로 설정한다.
    """

    def __init__(self, screen, clip: QPixmap | None, coordinator: "ScreenCaptureDialog") -> None:
        super().__init__()
        self._clip = clip
        self._coordinator = coordinator
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setGeometry(screen.geometry())
        if clip is None:
            self.setWindowOpacity(0.25)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._clip is not None:
            # drawPixmap(rect, pixmap): 클립의 물리 픽셀을 패널 물리 영역에 1:1 매핑.
            # drawPixmap(0, 0, pixmap)은 DI 크기로 그리기 때문에 패널 DPR과 클립 DPR이
            # 다르면 내용이 잘리거나 왜곡된다. rect 형태는 DPR 불일치를 무시하고
            # 항상 패널 전체를 올바르게 채운다.
            painter.drawPixmap(self.rect(), self._clip)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 70))
        painter.end()

    def mousePressEvent(self, event) -> None:
        # 클릭한 패널에 포커스를 넘겨 ESC 키 입력을 받을 수 있게 한다
        self.activateWindow()
        self._coordinator._panel_press(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:
        self._coordinator._panel_move(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event) -> None:
        self._coordinator._panel_release(event.globalPosition().toPoint())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._coordinator._panel_escape()
        else:
            super().keyPressEvent(event)


class ScreenCaptureDialog(QDialog):
    """모니터별 독립 패널(_ScreenCapturePanel)로 구성된 영역 선택 오버레이.

    외부 인터페이스(exec, selection, DialogCode)는 QDialog와 동일하게 유지한다.
    """

    def __init__(self, snapshot: QPixmap | None = None, snapshot_rect: QRect | None = None) -> None:
        super().__init__()
        self.origin: QPoint | None = None
        self._current: QPoint | None = None
        self.selection = QRect()
        self._snapshot = snapshot
        self._snapshot_rect = snapshot_rect or virtual_screen_geometry()
        self._panels: list[_ScreenCapturePanel] = []
        self._loop: "QEventLoop | None" = None
        self._accepted = False
        # 이 QDialog 자체는 숨김 — 실제 화면 표시는 패널이 담당
        self.setWindowFlags(Qt.WindowType.Tool)
        self.resize(1, 1)
        self.move(-32000, -32000)

    def exec(self) -> "QDialog.DialogCode":  # type: ignore[override]
        self._accepted = False
        self._panels.clear()

        # PIL + Win32 EnumDisplayMonitors로 각 모니터를 물리 해상도 그대로 캡처한다.
        # grabWindow(0)는 Qt 버전에 따라 nativeSize=-1 처리 방식이 달라
        # 반환 픽스맵의 크기·DPR이 불일치하여 왜곡이 발생한다.
        # _capture_per_screen_physical은 Win32 물리 좌표를 직접 사용하므로 정확하다.
        screens = QApplication.screens()
        per_screen_grabs = _capture_per_screen_physical(screens)

        for screen, grab in zip(screens, per_screen_grabs):
            clip: QPixmap | None = grab if (grab is not None and not grab.isNull()) else None
            if clip is None and self._snapshot is not None and not self._snapshot.isNull():
                # 폴백: 합성 스냅샷에서 추출
                local = screen.geometry().translated(-self._snapshot_rect.topLeft())
                extracted = crop_pixmap_dip(self._snapshot, local)
                if not extracted.isNull():
                    clip = extracted
            panel = _ScreenCapturePanel(screen, clip, self)
            self._panels.append(panel)

        for panel in self._panels:
            panel.show()

        # 커서가 위치한 패널에 키보드 포커스를 부여해 ESC 키가 즉시 동작하도록 한다
        cursor_pos = QCursor.pos()
        for panel in self._panels:
            if panel.geometry().contains(cursor_pos):
                panel.activateWindow()
                break

        self._loop = QEventLoop()
        self._loop.exec()

        for panel in self._panels:
            panel.close()
            panel.deleteLater()
        self._panels.clear()

        return QDialog.DialogCode.Accepted if self._accepted else QDialog.DialogCode.Rejected

    def _panel_press(self, global_pos: QPoint) -> None:
        self.origin = global_pos
        self._current = global_pos
        self._refresh_rubber_bands()

    def _panel_move(self, global_pos: QPoint) -> None:
        if self.origin is None:
            return
        self._current = global_pos
        self._refresh_rubber_bands()

    def _panel_release(self, global_pos: QPoint) -> None:
        if self.origin is not None:
            self.selection = QRect(self.origin, global_pos).normalized()
        self._accepted = True
        if self._loop is not None:
            self._loop.quit()

    def _panel_escape(self) -> None:
        self._accepted = False
        if self._loop is not None:
            self._loop.quit()

    def _refresh_rubber_bands(self) -> None:
        if self.origin is None or self._current is None:
            return
        sel = QRect(self.origin, self._current).normalized()
        for panel in self._panels:
            intersected = sel.intersected(panel.geometry())
            if intersected.isEmpty():
                panel.rubber_band.hide()
            else:
                panel.rubber_band.setGeometry(intersected.translated(-panel.geometry().topLeft()))
                panel.rubber_band.show()


class ImageDialog(QDialog):
    def __init__(self, item: dict | None = None, data: dict | None = None, default_group_id: str = "") -> None:
        super().__init__()
        self.setWindowTitle("이미지")
        self.item = item or {}
        self.group_combo = build_group_combo(
            data or {}, GROUP_SCOPE_CHEAT, self.item.get("group_id", "") if item else default_group_id
        )
        fit_combo_to_contents(self.group_combo, 160)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.item.get("name", ""))
        self.path = QLineEdit(self.item.get("path", ""))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        self.url = QLineEdit()
        self.capture_scale = QComboBox()
        self.capture_scale.addItems(["100%", "75%", "50%"])
        current_scale = f"{int(self.item.get('display_scale', 100))}%"
        self.capture_scale.setCurrentText(current_scale if current_scale in ["100%", "75%", "50%"] else "100%")
        browse = QPushButton("파일")
        download = QPushButton("URL")
        capture = QPushButton("드래그 캡처")
        browse.clicked.connect(self.browse)
        download.clicked.connect(self.download_url)
        capture.clicked.connect(self.capture_screen)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        form.addRow("이름", self.name)
        form.addRow("저장 위치", self.group_combo)
        form.addRow("이미지 경로", row)
        form.addRow("단축키", self.hotkey)
        url_row = QHBoxLayout()
        url_row.addWidget(self.url, 1)
        url_row.addWidget(download)
        form.addRow("이미지 URL", url_row)
        capture_row = QHBoxLayout()
        capture_row.addWidget(self.capture_scale)
        capture_row.addWidget(capture)
        form.addRow("표시/저장 크기", capture_row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.path.setText(path)

    def image_dir(self) -> Path:
        path = config.BASE_DIR / "assets" / "images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def screenshot_dir(self) -> Path:
        config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        return config.SCREENSHOT_DIR

    def saved_image_dir(self) -> Path:
        path = config.BASE_DIR / "save_image"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_asset_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(config.BASE_DIR.resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

    def open_screenshot_folder(self) -> None:
        folder = self.screenshot_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc:
            QMessageBox.warning(self, "폴더 열기 실패", str(exc))

    def open_saved_image_folder(self) -> None:
        folder = self.saved_image_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc:
            QMessageBox.warning(self, "폴더 열기 실패", str(exc))

    def open_screenshot_folder(self) -> None:
        folder = self.screenshot_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc:
            QMessageBox.warning(self, "폴더 열기 실패", str(exc))

    def download_url(self) -> None:
        url = self.url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL 필요", "이미지 URL을 먼저 입력해 주세요.")
            return
        try:
            import requests

            response = requests.get(url, timeout=20)
            response.raise_for_status()
            suffix = Path(urlparse(url).path).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
                suffix = ".png"
            target = self.image_dir() / f"{new_id('image')}{suffix}"
            target.write_bytes(response.content)
            self.path.setText(self.relative_asset_path(target))
        except Exception as exc:
            QMessageBox.warning(self, "다운로드 실패", str(exc))

    def capture_screen(self) -> None:
        screens = QApplication.screens()
        if not screens:
            QMessageBox.warning(self, "캡처 실패", "사용 가능한 화면이 없습니다.")
            return
        snapshot_rect = virtual_screen_geometry()
        snapshot = capture_screen_rect(snapshot_rect)
        capture = ScreenCaptureDialog(snapshot, snapshot_rect)
        if exec_capture_dialog(capture) != capture.DialogCode.Accepted or capture.selection.width() < 3 or capture.selection.height() < 3:
            return
        rect = capture.selection
        pixmap = crop_pixmap_dip(snapshot, rect.translated(-snapshot_rect.topLeft()))
        percent = int(self.capture_scale.currentText().replace("%", ""))
        if percent != 100:
            pixmap = pixmap.scaled(
                max(1, pixmap.width() * percent // 100),
                max(1, pixmap.height() * percent // 100),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        copy_pixmap_to_clipboard(pixmap)
        target = next_capture_jpg_path(self.saved_image_dir())
        if not save_capture_jpg(pixmap, target):
            QMessageBox.warning(self, "캡처 실패", "스크린샷을 저장하지 못했습니다.")
            return
        self.path.setText(self.relative_asset_path(target))

    def value(self) -> dict:
        data = dict(self.item)
        path = self.path.text().strip()
        data.update(
            {
                "name": self.name.text().strip(),
                "path": path,
                "path_type": "absolute" if Path(path).is_absolute() else "relative",
                "display_scale": int(self.capture_scale.currentText().replace("%", "")),
                "hotkey": self.hotkey.value(),
                "group_id": self.group_combo.currentData() or "",
            }
        )
        return data


class ImageTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._snip_windows: list[QWidget] = []
        self._snip_active = False
        self.cheat_group_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(140)
        self.search.setFixedHeight(26)
        self.search.setStyleSheet("QLineEdit { padding: 1px 6px; font-size: 9pt; }")
        self.search.textChanged.connect(self.refresh)
        self.sort_controls = SortControls(self.refresh)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        corner_layout.addWidget(self.search)
        corner_layout.addWidget(self.sort_controls)
        self.tabs = QTabWidget()
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.list = GridPanel(columns=3)
        self.steel_cut_list = GridPanel(columns=3)
        add_btn = QPushButton("+ 이미지")
        add_btn.clicked.connect(self.edit_image)
        group_btn = QPushButton("+ 그룹 생성")
        group_btn.clicked.connect(self.create_group_clicked)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        # 탭(메뉴 줄) 아래에 그룹 경로(브레드크럼) 표시
        self.breadcrumb = make_breadcrumb_label(self.enter_group)
        page_layout.addWidget(self.breadcrumb)
        page_layout.addWidget(self.list, 1)
        save_folder_btn = QPushButton("저장 폴더 열기")
        save_folder_btn.clicked.connect(self.open_saved_image_folder)
        page_layout.addLayout(bottom_action_bar(save_folder_btn, group_btn, add_btn))
        steel_page = QWidget()
        steel_layout = QVBoxLayout(steel_page)
        steel_layout.setContentsMargins(0, 0, 0, 0)
        steel_layout.setSpacing(0)
        steel_layout.addWidget(self.steel_cut_list, 1)
        reset_btn = QPushButton("초기화")
        reset_btn.setText("저장 폴더 열기")
        reset_btn.clicked.connect(self.open_screenshot_folder)
        steel_layout.addLayout(bottom_action_bar(reset_btn))
        self.tabs.addTab(steel_page, "캡처 · 그리기")
        self.tabs.addTab(page, "컨닝페이퍼")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

    def _on_tab_changed(self, _index: int) -> None:
        if hasattr(self.main, "update_group_breadcrumb"):
            self.main.update_group_breadcrumb()

    def refresh(self) -> None:
        self.cleanup_steel_cuts()
        cards = []
        q = self.search.text().strip().lower()
        searching = bool(q)
        data = self.main.data
        self.cheat_group_id = valid_group_id(data, GROUP_SCOPE_CHEAT, self.cheat_group_id)
        source_items = data.get("images", [])
        sorted_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name") or value.get("path", ""))
        offset = 0
        meta: list[tuple[str, object]] = []
        if not searching:
            if self.cheat_group_id:
                current = group_by_id(data, self.cheat_group_id)
                cards.append(make_back_card(self.go_back_group, card_height=72))
                meta.append(("target", str(current.get("parent_id") or "") if current else ""))
            for group in groups_in(data, GROUP_SCOPE_CHEAT, self.cheat_group_id):
                cards.append(self._make_cheat_group_card(group))
                meta.append(("target", group_id(group)))
            offset = len(cards)
        visible_items = []
        for item in sorted_items:
            if q and q not in (item.get("name", "") + " " + item.get("path", "")).lower():
                continue
            if not searching and item_group_id(item) != self.cheat_group_id:
                continue
            card = make_card(item.get("name", "(이름 없음)"), "", display_hotkey(item.get("hotkey")), card_size="a")
            add_card_actions(
                card,
                [
                    ("view", "보기", lambda checked=False, value=item: self.view_image(value), False),
                    ("📂", "그룹으로 이동", lambda checked=False, value=item: self.move_image_to_group(value), False),
                    ("edit", "수정", lambda checked=False, value=item: self.edit_image(value), False),
                    ("delete", "삭제", lambda checked=False, value=item: self.delete_image(value), True),
                ],
            )
            visible_items.append(item)
            cards.append(card)
            meta.append(("item", item))
        callback = (lambda old, new, off=offset: self.reorder_items(source_items, visible_items, old - off, new - off)) if self.sort_controls.is_manual() else None
        drop_handler = self._make_drop_handler(meta) if not searching else None
        self.list.add_cards(cards, on_reorder=callback, on_drop=drop_handler)
        self.refresh_breadcrumb()
        self.refresh_steel_cuts(q)

    # --- 컨닝페이퍼 그룹(폴더) -------------------------------------------

    def _make_drop_handler(self, meta: list[tuple[str, object]]):
        """이미지 카드를 그룹/뒤로가기 카드 위에 드롭하면 해당 그룹으로 이동."""

        def handle(old_index: int, new_index: int) -> bool:
            if not (0 <= old_index < len(meta) and 0 <= new_index < len(meta)):
                return False
            src_kind, src_value = meta[old_index]
            dst_kind, dst_value = meta[new_index]
            if src_kind != "item" or dst_kind != "target":
                return False
            src_value["group_id"] = dst_value
            self.main.save_data()
            return True

        return handle

    def refresh_breadcrumb(self) -> None:
        update_breadcrumb_label(self.breadcrumb, self.main.data, self.cheat_group_id)

    def enter_group(self, gid: str) -> None:
        self.cheat_group_id = gid
        self.refresh()

    def go_back_group(self) -> None:
        current = group_by_id(self.main.data, self.cheat_group_id)
        self.enter_group(str(current.get("parent_id") or "") if current else "")

    def create_group_clicked(self) -> None:
        dialog = GroupDialog()
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "그룹명을 입력해주세요.")
                continue
            create_group(self.main.data, GROUP_SCOPE_CHEAT, self.cheat_group_id, value["name"], value["icon"])
            self.main.save_data()
            return

    def edit_group(self, group: dict) -> None:
        dialog = GroupDialog(group)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "그룹명을 입력해주세요.")
                continue
            group["name"] = value["name"]
            group["icon"] = value["icon"]
            self.main.save_data()
            return

    def delete_group_clicked(self, group: dict) -> None:
        if not confirm_delete(self, "선택한 그룹을 삭제할까요?\n그룹 안의 항목과 하위 그룹은 상위 경로로 이동합니다."):
            return
        delete_group(self.main.data, group, [self.main.data.get("images", [])])
        self.main.save_data()

    def toggle_group_favorite_clicked(self, group: dict, card: QWidget, button) -> None:
        toggle_group_favorite(group, card, button)
        QTimer.singleShot(0, self.main.save_data)

    def move_image_to_group(self, item: dict) -> None:
        show_move_to_group_menu(self, self.main.data, GROUP_SCOPE_CHEAT, item, self.main.save_data)

    def _make_cheat_group_card(self, group: dict) -> QWidget:
        subtitle = count_group_contents(
            self.main.data, GROUP_SCOPE_CHEAT, group_id(group), self.main.data.get("images", [])
        )
        return make_group_card(
            group,
            subtitle,
            on_open=lambda g=group: self.enter_group(group_id(g)),
            on_favorite=self.toggle_group_favorite_clicked,
            on_edit=self.edit_group,
            on_delete=self.delete_group_clicked,
            card_height=72,
        )

    def refresh_steel_cuts(self, q: str = "") -> None:
        source_items = self.main.data.setdefault("steel_cuts", [])
        cutoff = datetime.now() - timedelta(days=3)
        visible_items = [
            item
            for item in source_items
            if self.is_recent_steel_cut(item, cutoff)
        ]
        visible_items = sorted(visible_items, key=lambda value: value.get("created_at", ""), reverse=True)[:30]
        cards = []
        for item in visible_items:
            haystack = f"{item.get('window_title', '')} {item.get('created_at', '')}".lower()
            if q and q not in haystack:
                continue
            cards.append(self.make_steel_cut_card(item))
        self.steel_cut_list.add_cards(cards, on_reorder=None)

    def is_recent_steel_cut(self, item: dict, cutoff: datetime) -> bool:
        try:
            created = datetime.fromisoformat(str(item.get("created_at", "")))
        except ValueError:
            return True
        return created >= cutoff

    def make_steel_cut_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        card.setFixedHeight(STEEL_CUT_CARD_HEIGHT)
        card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, CARD_CONTENT_TOP_MARGIN, 10, 10)
        layout.setSpacing(10)

        image = QLabel()
        image.setFixedSize(QSize(92, 52))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setStyleSheet("background:#F8FAFC;border:1px solid #E5E7EB;border-radius:5px;")
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            image.setText("이미지 없음")
        else:
            image.setPixmap(pixmap.scaled(QSize(90, 50), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(image)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)

        title = QLabel(item.get("window_title") or "창 제목 없음")
        title.setObjectName("cardTitle")
        title.setWordWrap(False)
        right.addWidget(title)

        created = QLabel(self.format_created_at(item.get("created_at", "")))
        created.setObjectName("mutedText")
        right.addWidget(created)

        right.addStretch(1)

        layout.addLayout(right, 1)
        action_page = QWidget()
        action_row = QHBoxLayout(action_page)
        action_row.setContentsMargins(CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y, CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y)
        action_row.setSpacing(CARD_ACTION_ROW_SPACING)
        action_row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        icon_size = QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)
        action_row.addWidget(make_icon_button("view", "보기", lambda checked=False, value=item: self.view_steel_cut(value), size=icon_size))
        action_row.addWidget(make_icon_button("➡️", "컨닝페이퍼로 이동", lambda checked=False, value=item: self.move_steel_cut_to_cheat_sheet(value), size=icon_size))
        action_row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_steel_cut(value), True, size=icon_size))
        set_card_action_widget(card, action_page)
        return card

    def format_created_at(self, value: str) -> str:
        try:
            dt = datetime.fromisoformat(value)
            return f"{dt.month}/{dt.day} {dt.hour}:{dt.minute:02d}"
        except ValueError:
            return value

    def cleanup_steel_cuts(self) -> None:
        self.main.data.setdefault("steel_cuts", [])

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def image_dir(self) -> Path:
        path = config.BASE_DIR / "assets" / "images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def screenshot_dir(self) -> Path:
        config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        return config.SCREENSHOT_DIR

    def saved_image_dir(self) -> Path:
        path = config.BASE_DIR / "save_image"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_asset_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(config.BASE_DIR.resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

    def open_screenshot_folder(self) -> None:
        folder = self.screenshot_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc:
            QMessageBox.warning(self, "폴더 열기 실패", str(exc))

    def open_saved_image_folder(self) -> None:
        folder = self.saved_image_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc:
            QMessageBox.warning(self, "폴더 열기 실패", str(exc))

    def capture_selection(self, rect: QRect) -> QPixmap:
        return capture_screen_rect(rect)

    def capture_steel_cut(self) -> None:
        """캡처는 항상 스마트 캡처(요소 인식 + 드래그 + A/S/Z 단축키)로 동작한다."""
        if self._snip_active:
            return
        self.start_snip_capture()

    def start_snip_capture(self) -> None:
        """Snipaste 스타일 캡처: UI 요소 자동 탐지 + 클릭/드래그/PrtSc/Alt+PrtSc."""
        self._snip_active = True
        try:
            overlay = SnipOverlay()
            result = overlay.exec()
        finally:
            self._snip_active = False
        if result is None:
            return
        copy_pixmap_to_clipboard(result.pixmap)
        self.open_snip_editor(result.pixmap, result.logical_rect, result.window_title or "창 제목 없음")

    def open_snip_editor(self, pixmap: QPixmap, anchor: QRect, title: str) -> None:
        editor = SnipEditorWindow(pixmap, anchor, title, self)
        self.register_snip_window(editor)
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def register_snip_window(self, window: QWidget) -> None:
        self._snip_windows.append(window)
        window.destroyed.connect(lambda _=None, value=window: self._forget_snip_window(value))

    def _forget_snip_window(self, window: QWidget) -> None:
        if window in self._snip_windows:
            self._snip_windows.remove(window)

    def save_snip_capture(self, pixmap: QPixmap, title: str) -> None:
        """편집/고정 창의 '저장' → 캡처 · 그리기 목록에 등록."""
        if pixmap.isNull():
            return
        target = next_capture_path(self.screenshot_dir(), ".png")
        window_title = title or "창 제목 없음"
        worker = ImageSaveWorker(pixmap.toImage(), target, "PNG", -1)
        worker.signals.finished.connect(lambda path, ok, value=window_title: self.finish_steel_cut_capture(path, ok, value))
        QThreadPool.globalInstance().start(worker)

    def move_snip_to_cheat_sheet(self, pixmap: QPixmap, title: str, group_id: str = "") -> bool:
        """편집/고정 창의 '컨닝페이퍼로 이동' → 지정한 그룹(기본 최상위)에 등록."""
        if pixmap.isNull():
            return False
        target = next_capture_path(self.saved_image_dir(), ".png")
        if not pixmap.save(str(target), "PNG"):
            QMessageBox.warning(self, "저장 실패", "이미지를 저장하지 못했습니다.")
            return False
        images = self.main.data.setdefault("images", [])
        images.append(
            {
                "id": new_id("img"),
                "name": title or "캡처",
                "path": self.relative_asset_path(target),
                "path_type": "relative",
                "hotkey": None,
                "sort_order": len(images),
                "display_scale": 100,
                "created_at": now_iso(),
                "usage_count": 0,
                "group_id": valid_group_id(self.main.data, GROUP_SCOPE_CHEAT, group_id),
            }
        )
        self.main.save_data()
        self.refresh()
        return True

    def finish_steel_cut_capture(self, image_path: str, ok: bool, title: str) -> None:
        if not ok:
            QMessageBox.warning(self, "스틸 컷 실패", "스크린샷을 저장하지 못했습니다.")
            return
        items = self.main.data.setdefault("steel_cuts", [])
        value = {
            "id": new_id("steel"),
            "path": self.relative_asset_path(Path(image_path)),
            "path_type": "relative",
            "window_title": title,
            "created_at": now_iso(),
            "last_used_at": now_iso(),
            "sort_order": len(items),
            "usage_count": 0,
        }
        items.append(value)
        self.main.save_data()
        self.tabs.setCurrentIndex(0)
        self.refresh()

    def view_image(self, item: dict) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "이미지 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        bump_usage(item)
        self.main.save_usage_data()
        self.open_pinned_image(QPixmap(path), item.get("name", "이미지"), int(item.get("display_scale", 100) or 100))

    def view_steel_cut(self, item: dict, copy_to_clipboard: bool = False) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "스틸 컷 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        bump_usage(item)
        item["last_used_at"] = now_iso()
        self.main.save_usage_data()
        pixmap = QPixmap(path)
        self.open_pinned_image(pixmap, item.get("window_title", "스틸 컷"))
        if copy_to_clipboard and not pixmap.isNull():
            copy_pixmap_to_clipboard(pixmap)

    def open_pinned_image(self, pixmap: QPixmap, title: str, scale: int = 100) -> PinnedImageWindow | None:
        """저장된 이미지를 고정(핀) 창으로 연다. 우클릭 메뉴로 조작한다."""
        if pixmap.isNull():
            QMessageBox.warning(self, "이미지 없음", "이미지를 불러오지 못했습니다.")
            return None
        window = PinnedImageWindow(pixmap, QPoint(0, 0), title, self)
        if scale != 100:
            window.set_zoom(scale)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        available = screen.availableGeometry()
        window.adjustSize()
        window.move(
            available.center().x() - window.width() // 2,
            available.center().y() - window.height() // 2,
        )
        self.register_snip_window(window)
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def delete_steel_cut_file(self, item: dict) -> None:
        try:
            path = Path(resolve_image_path(item.get("path", ""), config.BASE_DIR))
            if path.exists() and config.BASE_DIR.resolve() in path.resolve().parents:
                path.unlink()
        except Exception:
            pass

    def move_steel_cut_to_cheat_sheet(self, item: dict) -> None:
        source = Path(resolve_image_path(item.get("path", ""), config.BASE_DIR))
        if not source.exists():
            QMessageBox.warning(self, "스틸 컷 없음", f"파일을 찾을 수 없습니다.\n{source}")
            return
        target = self.saved_image_dir() / source.name
        if target.exists():
            target = self.saved_image_dir() / f"{source.stem}_{new_id('save')}{source.suffix or '.png'}"
        try:
            shutil.move(str(source), str(target))
        except Exception as exc:
            QMessageBox.warning(self, "이동 실패", str(exc))
            return
        images = self.main.data.setdefault("images", [])
        images.append(
            {
                "id": new_id("img"),
                "name": item.get("window_title") or "스틸 컷",
                "path": self.relative_asset_path(target),
                "path_type": "relative",
                "hotkey": None,
                "sort_order": len(images),
                "display_scale": 100,
                "created_at": now_iso(),
                "usage_count": 0,
            }
        )
        steel_items = self.main.data.get("steel_cuts", [])
        if item in steel_items:
            steel_items.remove(item)
        self.main.save_data()
        self.refresh()
        show_modern_info(self, "이동 완료", "캡처 · 그리기 항목을 컨닝페이퍼에 등록했습니다.")

    def delete_steel_cut(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 스틸 컷을 삭제할까요?"):
            return
        items = self.main.data.get("steel_cuts", [])
        if item in items:
            items.remove(item)
        self.delete_steel_cut_file(item)
        self.main.save_data()
        self.refresh()

    def clear_steel_cuts(self) -> None:
        items = self.main.data.get("steel_cuts", [])
        if not items:
            show_modern_info(self, "초기화", "삭제할 스틸 컷이 없습니다.")
            return
        if not confirm_delete(self, f"스틸 컷 {len(items)}개를 모두 삭제할까요?"):
            return
        for item in list(items):
            self.delete_steel_cut_file(item)
        self.main.data["steel_cuts"] = []
        self.main.save_data()

    def edit_image(self, item: dict | None = None) -> None:
        dialog = ImageDialog(item, self.main.data, self.cheat_group_id)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                QMessageBox.warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            if not value.get("path"):
                QMessageBox.warning(dialog, "입력 확인", "이미지 경로를 지정해주세요.")
                continue
            conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
            if conflict:
                QMessageBox.warning(dialog, "단축키 충돌", conflict)
                continue
            if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
                continue
            if not value.get("id"):
                value["id"] = new_id("img")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault("images", []))
                value["usage_count"] = 0
            items = self.main.data.setdefault("images", [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def delete_image(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 이미지를 삭제할까요?"):
            return
        self.main.data.get("images", []).remove(item)
        self.main.save_data()
        self.refresh()
