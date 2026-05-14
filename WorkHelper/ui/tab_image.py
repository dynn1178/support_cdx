from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QPoint, QRect, QSize, QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
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
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import display_hotkey, new_id, now_iso, resolve_image_path
from ui.common import GridPanel, HotkeyFields, SortControls, add_card_actions, apply_manual_reorder, bump_usage, confirm_delete, confirm_shift_digit_hotkey, make_card, make_icon_button, show_modern_info


def active_window_title() -> str:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


def active_window_rect() -> QRect:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    screen = QApplication.primaryScreen()
    return screen.geometry() if screen else QRect()


def _scaled_pixels(value: int, scale: float) -> int:
    return max(1, int(value * scale + 0.9999))


def screen_capture_scale(rect: QRect) -> float:
    scales = [
        float(screen.devicePixelRatio())
        for screen in QApplication.screens()
        if rect.intersects(screen.geometry())
    ]
    if scales:
        return max(scales)
    screen = QApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen else 1.0


def capture_screen_rect(rect: QRect) -> QPixmap:
    """Capture a logical screen rect while preserving native high-DPI pixels."""
    if rect.width() < 1 or rect.height() < 1:
        return QPixmap()
    scale = screen_capture_scale(rect)
    pixmap = QPixmap(_scaled_pixels(rect.width(), scale), _scaled_pixels(rect.height(), scale))
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    for screen in QApplication.screens():
        intersected = rect.intersected(screen.geometry())
        if intersected.isEmpty():
            continue
        local = intersected.translated(-screen.geometry().topLeft())
        part = screen.grabWindow(0, local.x(), local.y(), local.width(), local.height())
        if part.isNull():
            continue
        painter.drawPixmap(intersected.topLeft() - rect.topLeft(), part)
    painter.end()
    return pixmap


def next_capture_jpg_path(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for number in range(1, 1000):
        path = directory / f"{stamp}_{number:03d}.jpg"
        if not path.exists():
            return path
    return directory / f"{stamp}_{new_id('capture')}.jpg"


def save_capture_jpg(pixmap: QPixmap, path: Path) -> bool:
    return pixmap.save(str(path), "JPG", 95)


class ScreenCaptureDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.origin = None
        self.selection = QRect()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        virtual_rect = QApplication.primaryScreen().virtualGeometry()
        for screen in QApplication.screens():
            virtual_rect = virtual_rect.united(screen.geometry())
        self.setGeometry(virtual_rect)
        self.setWindowOpacity(0.25)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event) -> None:
        self.origin = event.position().toPoint()
        self.rubber_band.setGeometry(QRect(self.origin, self.origin))
        self.rubber_band.show()

    def mouseMoveEvent(self, event) -> None:
        if self.origin is not None:
            self.rubber_band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event) -> None:
        self.selection = self.rubber_band.geometry().translated(self.geometry().topLeft())
        self.accept()


class FixedSizeCaptureDialog(QDialog):
    def __init__(self, size: QSize, initial_top_left: QPoint | None = None) -> None:
        super().__init__()
        self.selection = QRect()
        self.drag_start: QPoint | None = None
        self.box_size = QSize(max(10, size.width()), max(10, size.height()))
        self.initial_top_left = initial_top_left
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.rubber_band.setStyleSheet("border: 4px solid #2563EB; background: rgba(37, 99, 235, 48);")
        self.capture_button = QPushButton("이 영역 캡처", self)
        self.capture_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_button.setStyleSheet(
            "QPushButton { background:#2563EB; color:white; border:0; border-radius:8px; padding:7px 14px; font-weight:800; }"
        )
        self.capture_button.clicked.connect(self.accept_capture)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        virtual_rect = QApplication.primaryScreen().virtualGeometry()
        for screen in QApplication.screens():
            virtual_rect = virtual_rect.united(screen.geometry())
        self.setGeometry(virtual_rect)
        if self.initial_top_left is not None:
            self.initial_top_left = self.initial_top_left - virtual_rect.topLeft()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("QDialog { background: rgba(15, 23, 42, 58); }")
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.rubber_band.setCursor(Qt.CursorShape.SizeAllCursor)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center = self.rect().center()
        top_left = self.initial_top_left if hasattr(self, "initial_top_left") and self.initial_top_left is not None else QPoint(center.x() - self.box_size.width() // 2, center.y() - self.box_size.height() // 2)
        self.rubber_band.setGeometry(QRect(top_left, self.box_size).intersected(self.rect()))
        self.rubber_band.show()
        self.position_capture_button()

    def mousePressEvent(self, event) -> None:
        if not self.rubber_band.geometry().contains(event.position().toPoint()):
            self.drag_start = None
            return
        self.drag_start = event.position().toPoint() - self.rubber_band.geometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self.drag_start is None:
            return
        top_left = event.position().toPoint() - self.drag_start
        rect = QRect(top_left, self.box_size)
        bounds = self.rect()
        if rect.left() < bounds.left():
            rect.moveLeft(bounds.left())
        if rect.top() < bounds.top():
            rect.moveTop(bounds.top())
        if rect.right() > bounds.right():
            rect.moveRight(bounds.right())
        if rect.bottom() > bounds.bottom():
            rect.moveBottom(bounds.bottom())
        self.rubber_band.setGeometry(rect)
        self.position_capture_button()

    def mouseReleaseEvent(self, event) -> None:
        self.drag_start = None

    def position_capture_button(self) -> None:
        self.capture_button.adjustSize()
        band = self.rubber_band.geometry()
        x = min(max(band.right() - self.capture_button.width(), 8), self.width() - self.capture_button.width() - 8)
        y = band.bottom() + 10
        if y + self.capture_button.height() > self.height() - 8:
            y = max(8, band.top() - self.capture_button.height() - 10)
        self.capture_button.move(x, y)
        self.capture_button.show()

    def accept_capture(self) -> None:
        self.selection = self.rubber_band.geometry().translated(self.geometry().topLeft())
        self.accept()


class ImageDialog(QDialog):
    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("이미지")
        self.item = item or {}
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
        capture = ScreenCaptureDialog()
        if capture.exec() != capture.DialogCode.Accepted or capture.selection.width() < 3 or capture.selection.height() < 3:
            return
        rect = capture.selection
        pixmap = capture_screen_rect(rect)
        percent = int(self.capture_scale.currentText().replace("%", ""))
        if percent != 100:
            pixmap = pixmap.scaled(
                max(1, pixmap.width() * percent // 100),
                max(1, pixmap.height() * percent // 100),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
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
            }
        )
        return data


class ImageViewerDialog(QDialog):
    def __init__(self, image_path: str, title: str, scale: int = 100, stay_on_top: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(title)
        if stay_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.original = QPixmap(image_path)
        if self.original.isNull():
            self.label.setText("이미지를 불러오지 못했습니다.")
        else:
            self.apply_scale(scale)
        layout.addWidget(self.label)

    def apply_scale(self, scale: int) -> None:
        width = max(1, self.original.width() * scale // 100)
        height = max(1, self.original.height() * scale // 100)
        scaled = self.original.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.label.setPixmap(scaled)
        self.resize(scaled.width() + 24, scaled.height() + 24)


class SteelCutViewerDialog(QDialog):
    def __init__(self, image_path: str, title: str) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        ctrl = QHBoxLayout()
        opacity_label = QLabel("투명도")
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(120)
        self.opacity_slider.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))
        self.pin_check = QCheckBox("항상 위")
        self.pin_check.setChecked(True)
        self.pin_check.toggled.connect(self._toggle_pin)
        ctrl.addWidget(opacity_label)
        ctrl.addWidget(self.opacity_slider)
        ctrl.addStretch(1)
        ctrl.addWidget(self.pin_check)
        layout.addLayout(ctrl)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.image_label.setText("이미지를 불러오지 못했습니다.")
        else:
            self.image_label.setPixmap(pixmap)
            self.resize(pixmap.width() + 24, pixmap.height() + 64)
        layout.addWidget(self.image_label)

    def _toggle_pin(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()


class PaintCanvas(QWidget):
    def __init__(self, image_path: str) -> None:
        super().__init__()
        self.base = QPixmap(image_path)
        self.overlay = QPixmap(self.base.size())
        self.overlay.fill(Qt.GlobalColor.transparent)
        self.tool = "pen"
        self.stroke_color = QColor("#ff2d55")
        self.stroke_width = 4
        self.fill_enabled = False
        self.fill_opacity = 35
        self.start_pos: QPoint | None = None
        self.last_pos: QPoint | None = None
        self.preview = QPixmap()
        self.setFixedSize(self.base.size() if not self.base.isNull() else QSize(520, 320))

    def composed_pixmap(self) -> QPixmap:
        if self.base.isNull():
            return QPixmap()
        result = QPixmap(self.base.size())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.drawPixmap(0, 0, self.base)
        painter.drawPixmap(0, 0, self.overlay)
        painter.end()
        return result

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self.base.isNull():
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "이미지를 불러올 수 없습니다.")
        else:
            painter.drawPixmap(0, 0, self.base)
            painter.drawPixmap(0, 0, self.overlay)
            if not self.preview.isNull():
                painter.drawPixmap(0, 0, self.preview)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if self.base.isNull() or event.button() != Qt.MouseButton.LeftButton:
            return
        self.start_pos = event.position().toPoint()
        self.last_pos = self.start_pos
        self.preview = QPixmap()

    def mouseMoveEvent(self, event) -> None:
        if self.start_pos is None:
            return
        pos = event.position().toPoint()
        if self.tool == "pen":
            painter = QPainter(self.overlay)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(self.stroke_color, self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(self.last_pos, pos)
            painter.end()
            self.last_pos = pos
        else:
            self.preview = QPixmap(self.overlay.size())
            self.preview.fill(Qt.GlobalColor.transparent)
            self._draw_shape(self.preview, self.start_pos, pos)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self.start_pos is None or event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if self.tool != "pen":
            self._draw_shape(self.overlay, self.start_pos, pos)
            self.preview = QPixmap()
        self.start_pos = None
        self.last_pos = None
        self.update()

    def _draw_shape(self, target: QPixmap, start: QPoint, end: QPoint) -> None:
        rect = QRect(start, end).normalized()
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.stroke_color, self.stroke_width))
        if self.fill_enabled and self.tool in {"rect", "ellipse"}:
            fill = QColor(self.stroke_color)
            fill.setAlphaF(self.fill_opacity / 100.0)
            painter.setBrush(QBrush(fill))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.tool == "line":
            painter.drawLine(start, end)
        elif self.tool == "ellipse":
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        painter.end()


class SteelCutViewerDialog(QDialog):
    def __init__(self, image_path: str, title: str) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        ctrl = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(120)
        self.opacity_slider.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))
        self.tool_combo = QComboBox()
        self.tool_combo.addItem("펜", "pen")
        self.tool_combo.addItem("선", "line")
        self.tool_combo.addItem("사각형", "rect")
        self.tool_combo.addItem("원", "ellipse")
        self.color_btn = QPushButton("색상")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 40)
        self.width_spin.setValue(4)
        self.width_spin.setSuffix(" px")
        self.fill_check = QCheckBox("채우기")
        self.fill_opacity = QSlider(Qt.Orientation.Horizontal)
        self.fill_opacity.setRange(0, 100)
        self.fill_opacity.setValue(35)
        self.fill_opacity.setFixedWidth(90)
        copy_btn = QPushButton("복사")
        self.pin_check = QCheckBox("항상 위")
        self.pin_check.setChecked(True)
        self.pin_check.toggled.connect(self._toggle_pin)
        ctrl.addWidget(QLabel("창 투명도"))
        ctrl.addWidget(self.opacity_slider)
        ctrl.addWidget(self.tool_combo)
        ctrl.addWidget(self.color_btn)
        ctrl.addWidget(self.width_spin)
        ctrl.addWidget(self.fill_check)
        ctrl.addWidget(QLabel("채움 투명도"))
        ctrl.addWidget(self.fill_opacity)
        ctrl.addStretch(1)
        ctrl.addWidget(copy_btn)
        ctrl.addWidget(self.pin_check)
        layout.addLayout(ctrl)

        self.canvas = PaintCanvas(image_path)
        layout.addWidget(self.canvas)
        if not self.canvas.base.isNull():
            self.resize(self.canvas.base.width() + 24, self.canvas.base.height() + 88)

        self.tool_combo.currentIndexChanged.connect(lambda _=0: setattr(self.canvas, "tool", self.tool_combo.currentData()))
        self.color_btn.clicked.connect(self.choose_color)
        self.width_spin.valueChanged.connect(lambda value: setattr(self.canvas, "stroke_width", value))
        self.fill_check.toggled.connect(lambda value: setattr(self.canvas, "fill_enabled", value))
        self.fill_opacity.valueChanged.connect(lambda value: setattr(self.canvas, "fill_opacity", value))
        copy_btn.clicked.connect(self.copy_to_clipboard)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Copy), self, activated=self.copy_to_clipboard)

    def choose_color(self) -> None:
        color = QColorDialog.getColor(self.canvas.stroke_color, self, "색상 선택")
        if color.isValid():
            self.canvas.stroke_color = color
            self.color_btn.setStyleSheet(f"background:{color.name()}; color:white;")

    def copy_to_clipboard(self) -> None:
        pixmap = self.canvas.composed_pixmap()
        if not pixmap.isNull():
            QApplication.clipboard().setPixmap(pixmap)

    def _toggle_pin(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()


class SteelCutViewerDialog(QDialog):
    def __init__(self, image_path: str, title: str) -> None:
        super().__init__()
        self.image_path = image_path
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setStyleSheet(
            """
            QDialog { background: #F7F8FB; }
            QWidget#toolbarSection { background: #FFFFFF; border: 1px solid #E3E7EF; border-radius: 8px; }
            QLabel#toolbarTitle { color: #475467; font-size: 9pt; font-weight: 800; }
            QPushButton, QComboBox, QSpinBox {
                min-height: 24px; max-height: 24px; border: 1px solid #D0D5DD; border-radius: 6px;
                background: #FFFFFF; padding: 1px 8px;
            }
            QPushButton:hover, QComboBox:hover, QSpinBox:hover { border-color: #8EA4C8; }
            QPushButton#primaryButton { background: #2563EB; border-color: #2563EB; color: #FFFFFF; font-weight: 800; }
            QPushButton#colorButton { background: #ff2d55; border-color: #ff2d55; color: #FFFFFF; font-weight: 800; }
            QCheckBox { color: #344054; spacing: 6px; }
            QSlider { background: transparent; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        drawing_section = self._section()
        drawing = QHBoxLayout(drawing_section)
        drawing.setContentsMargins(10, 5, 10, 5)
        drawing.setSpacing(6)
        drawing.addWidget(self._section_title("그리기"))

        self.tool_combo = QComboBox()
        self.tool_combo.addItem("펜", "pen")
        self.tool_combo.addItem("선", "line")
        self.tool_combo.addItem("사각형", "rect")
        self.tool_combo.addItem("원", "ellipse")
        self.tool_combo.setMinimumWidth(90)
        self.tool_combo.view().setMinimumWidth(90)
        self.color_btn = QPushButton("색상")
        self.color_btn.setObjectName("colorButton")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 40)
        self.width_spin.setValue(4)
        self.width_spin.setSuffix(" px")
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 40)
        self.width_slider.setValue(4)
        self.width_slider.setFixedWidth(90)
        self.fill_check = QCheckBox("채우기")
        self.fill_opacity = QSlider(Qt.Orientation.Horizontal)
        self.fill_opacity.setRange(0, 100)
        self.fill_opacity.setValue(35)
        self.fill_opacity.setFixedWidth(110)
        drawing.setSpacing(8)
        drawing.addWidget(self.tool_combo)
        drawing.addSpacing(12)
        drawing.addWidget(self.color_btn)
        drawing.addSpacing(12)
        drawing.addWidget(QLabel("두께"))
        drawing.addWidget(self.width_spin)
        drawing.addWidget(self.width_slider)
        drawing.addSpacing(12)
        drawing.addWidget(self.fill_check)
        drawing.addWidget(QLabel("채움 투명도"))
        drawing.addWidget(self.fill_opacity)
        drawing.addStretch(1)
        layout.addWidget(drawing_section)

        system_section = self._section()
        system = QHBoxLayout(system_section)
        system.setContentsMargins(10, 5, 10, 5)
        system.setSpacing(6)
        system.addWidget(self._section_title("창 / 저장"))

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(130)
        copy_btn = QPushButton("복사")
        reset_btn = QPushButton("초기화")
        self.save_with_drawing = QCheckBox("저장 시 그리기 포함")
        self.save_with_drawing.setChecked(True)
        save_btn = QPushButton("저장")
        save_btn.setObjectName("primaryButton")
        self.pin_check = QCheckBox("항상 위")
        self.pin_check.setChecked(True)
        system.addWidget(QLabel("창 투명도"))
        system.addWidget(self.opacity_slider)
        system.addStretch(1)
        system.addWidget(self.pin_check)
        system.addWidget(self.save_with_drawing)
        system.addWidget(reset_btn)
        system.addWidget(copy_btn)
        system.addWidget(save_btn)
        layout.addWidget(system_section)

        self.canvas = PaintCanvas(image_path)
        self.canvas.setStyleSheet("border: 1px solid #D0D5DD; border-radius: 8px; background: #FFFFFF;")
        layout.addWidget(self.canvas, 1, Qt.AlignmentFlag.AlignCenter)
        if not self.canvas.base.isNull():
            self.resize(self.canvas.base.width() + 32, self.canvas.base.height() + 116)

        self.opacity_slider.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))
        self.pin_check.toggled.connect(self._toggle_pin)
        self.tool_combo.currentIndexChanged.connect(lambda _=0: setattr(self.canvas, "tool", self.tool_combo.currentData()))
        self.color_btn.clicked.connect(self.choose_color)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        self.width_slider.valueChanged.connect(self._on_width_changed)
        self.fill_check.toggled.connect(lambda value: setattr(self.canvas, "fill_enabled", value))
        self.fill_opacity.valueChanged.connect(lambda value: setattr(self.canvas, "fill_opacity", value))
        copy_btn.clicked.connect(self.copy_to_clipboard)
        reset_btn.clicked.connect(self.clear_drawing)
        save_btn.clicked.connect(self.save_current_image)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Copy), self, activated=self.copy_to_clipboard)

    def _section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("toolbarSection")
        return section

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("toolbarTitle")
        label.setFixedWidth(72)
        return label

    def choose_color(self) -> None:
        color = QColorDialog.getColor(self.canvas.stroke_color, self, "색상 선택")
        if color.isValid():
            self.canvas.stroke_color = color
            self.color_btn.setStyleSheet(f"background:{color.name()}; border-color:{color.name()}; color:white;")

    def copy_to_clipboard(self) -> None:
        pixmap = self.canvas.composed_pixmap()
        if not pixmap.isNull():
            QApplication.clipboard().setPixmap(pixmap)

    def clear_drawing(self) -> None:
        self.canvas.overlay.fill(Qt.GlobalColor.transparent)
        self.canvas.preview = QPixmap()
        self.canvas.update()

    def save_current_image(self) -> None:
        pixmap = self.canvas.composed_pixmap() if self.save_with_drawing.isChecked() else self.canvas.base
        if pixmap.isNull() or not pixmap.save(self.image_path, "PNG"):
            QMessageBox.warning(self, "저장 실패", "스틸 컷 이미지를 저장하지 못했습니다.")
            return
        if self.save_with_drawing.isChecked():
            self.canvas.base = pixmap
            self.canvas.overlay.fill(Qt.GlobalColor.transparent)
            self.canvas.update()
        show_modern_info(self, "저장 완료", "스틸 컷 이미지를 저장했습니다.")

    def _toggle_pin(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _on_width_changed(self, value: int) -> None:
        self.canvas.stroke_width = value
        self.width_spin.blockSignals(True)
        self.width_spin.setValue(value)
        self.width_spin.blockSignals(False)
        self.width_slider.blockSignals(True)
        self.width_slider.setValue(value)
        self.width_slider.blockSignals(False)


class ImageTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
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
        self.list = GridPanel(columns=2)
        self.steel_cut_list = GridPanel(columns=2)
        add_btn = QPushButton("+ 이미지")
        add_btn.clicked.connect(self.edit_image)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        save_folder_btn = QPushButton("저장 폴더 열기")
        save_folder_btn.clicked.connect(self.open_saved_image_folder)
        row.addWidget(save_folder_btn)
        row.addWidget(add_btn)
        page_layout.addLayout(row)
        steel_page = QWidget()
        steel_layout = QVBoxLayout(steel_page)
        steel_layout.setContentsMargins(0, 0, 0, 0)
        steel_layout.setSpacing(8)
        steel_hint = QLabel(
            "참고해야 할 창이 자꾸 뒤로 숨을 때, 스틸 컷 화면을 띄워보세요. "
            "일주일 이상 사용하지 않은 스틸 컷은 자동 삭제됩니다."
        )
        steel_hint.setObjectName("mutedText")
        steel_hint.setWordWrap(True)
        steel_layout.addSpacing(8)
        steel_layout.addWidget(steel_hint)
        steel_hint.hide()
        steel_layout.addWidget(self.steel_cut_list, 1)
        reset_row = QHBoxLayout()
        reset_btn = QPushButton("초기화")
        reset_btn.setText("저장 폴더 열기")
        reset_btn.clicked.connect(self.open_screenshot_folder)
        reset_row.addStretch(1)
        reset_row.addWidget(reset_btn)
        steel_layout.addLayout(reset_row)
        self.tabs.addTab(steel_page, "캡처 & 그리기")
        self.tabs.addTab(page, "컨닝페이퍼")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        self.cleanup_steel_cuts()
        cards = []
        q = self.search.text().strip().lower()
        source_items = self.main.data.get("images", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name") or value.get("path", ""))
        for item in visible_items:
            if q and q not in (item.get("name", "") + " " + item.get("path", "")).lower():
                continue
            card = make_card(item.get("name", "(이름 없음)"), "", display_hotkey(item.get("hotkey")), card_size="a")
            add_card_actions(
                card,
                [
                    ("view", "보기", lambda checked=False, value=item: self.view_image(value), False),
                    ("edit", "수정", lambda checked=False, value=item: self.edit_image(value), False),
                    ("delete", "삭제", lambda checked=False, value=item: self.delete_image(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, visible_items, old, new)) if self.sort_controls.is_manual() else None
        self.list.add_cards(cards, on_reorder=callback)
        self.refresh_steel_cuts(q)

    def refresh_steel_cuts(self, q: str = "") -> None:
        source_items = self.main.data.setdefault("steel_cuts", [])
        visible_items = sorted(source_items, key=lambda value: value.get("created_at", ""), reverse=True)[:50]
        cards = []
        for item in visible_items:
            haystack = f"{item.get('window_title', '')} {item.get('created_at', '')}".lower()
            if q and q not in haystack:
                continue
            cards.append(self.make_steel_cut_card(item))
        self.steel_cut_list.add_cards(cards, on_reorder=None)

    def make_steel_cut_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        image = QLabel()
        image.setFixedSize(QSize(110, 74))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setStyleSheet("background:#F8FAFC;border:1px solid #E5E7EB;border-radius:5px;")
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            image.setText("이미지 없음")
        else:
            image.setPixmap(pixmap.scaled(QSize(108, 72), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch(1)
        btn_row.addWidget(make_icon_button("view", "보기", lambda checked=False, value=item: self.view_steel_cut(value)))
        btn_row.addWidget(make_icon_button("open", "컨닝페이퍼로 이동", lambda checked=False, value=item: self.move_steel_cut_to_cheat_sheet(value)))
        btn_row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_steel_cut(value), True))
        right.addLayout(btn_row)

        layout.addLayout(right, 1)
        return card

    def format_created_at(self, value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
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

    def steel_cut_capture_rect(self) -> QRect:
        mode = self.main.settings.get("steel_cut_capture_mode", "region")
        if mode == "full":
            rect = QApplication.primaryScreen().virtualGeometry()
            for screen in QApplication.screens():
                rect = rect.united(screen.geometry())
            return rect
        if mode == "window":
            return active_window_rect()
        if mode == "fixed":
            width = int(self.main.settings.get("steel_cut_fixed_width", 800) or 800)
            height = int(self.main.settings.get("steel_cut_fixed_height", 450) or 450)
            raw_x = self.main.settings.get("steel_cut_fixed_x")
            raw_y = self.main.settings.get("steel_cut_fixed_y")
            initial = QPoint(int(raw_x), int(raw_y)) if raw_x is not None and raw_y is not None else None
            capture = FixedSizeCaptureDialog(QSize(width, height), initial)
            if capture.exec() != capture.DialogCode.Accepted:
                return QRect()
            self.main.settings["steel_cut_fixed_x"] = capture.selection.x()
            self.main.settings["steel_cut_fixed_y"] = capture.selection.y()
            config.save_settings(self.main.settings)
            return capture.selection
        capture = ScreenCaptureDialog()
        if capture.exec() != capture.DialogCode.Accepted:
            return QRect()
        return capture.selection

    def capture_steel_cut(self) -> None:
        title = active_window_title()
        rect = self.steel_cut_capture_rect()
        if rect.width() < 3 or rect.height() < 3:
            return
        pixmap = self.capture_selection(rect)
        QApplication.clipboard().setPixmap(pixmap)
        target = next_capture_jpg_path(self.screenshot_dir())
        if not save_capture_jpg(pixmap, target):
            QMessageBox.warning(self, "스틸 컷 실패", "스크린샷을 저장하지 못했습니다.")
            return
        items = self.main.data.setdefault("steel_cuts", [])
        value = {
            "id": new_id("steel"),
            "path": self.relative_asset_path(target),
            "path_type": "relative",
            "window_title": title or "창 제목 없음",
            "created_at": now_iso(),
            "last_used_at": now_iso(),
            "sort_order": len(items),
            "usage_count": 0,
        }
        items.append(value)
        self.main.save_data()
        self.tabs.setCurrentIndex(0)
        self.refresh()
        self.view_steel_cut(value, copy_to_clipboard=True)

    def view_image(self, item: dict) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "이미지 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        bump_usage(item)
        self.main.save_usage_data()
        dialog = ImageViewerDialog(path, item.get("name", "이미지"), int(item.get("display_scale", 100)), stay_on_top=True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()

    def view_steel_cut(self, item: dict, copy_to_clipboard: bool = False) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "스틸 컷 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        bump_usage(item)
        item["last_used_at"] = now_iso()
        self.main.save_usage_data()
        # 참조를 self에 보관해 GC 충돌 방지, WA_DeleteOnClose로 Qt가 직접 정리
        self._steel_cut_viewer = SteelCutViewerDialog(path, item.get("window_title", "스틸 컷"))
        self._steel_cut_viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._steel_cut_viewer.show()
        self._steel_cut_viewer.raise_()
        self._steel_cut_viewer.activateWindow()
        if copy_to_clipboard:
            QTimer.singleShot(0, self._steel_cut_viewer.copy_to_clipboard)

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
        show_modern_info(self, "이동 완료", "캡처 & 그리기 항목을 컨닝페이퍼에 등록했습니다.")

    def delete_steel_cut(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 스틸 컷을 삭제할까요?"):
            return
        items = self.main.data.get("steel_cuts", [])
        if item in items:
            items.remove(item)
        self.delete_steel_cut_file(item)
        self.main.save_data()

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
        dialog = ImageDialog(item)
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
