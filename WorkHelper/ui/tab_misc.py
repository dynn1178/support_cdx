from __future__ import annotations

import colorsys

from PyQt6.QtCore import QPoint, QPointF, QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.screen_utils import virtual_screen_geometry
from app.theme import THEMES
from app.utils import new_id, now_iso
from ui.tab_image import capture_screen_rect, copy_pixmap_to_clipboard
from ui.common import ask_modern_question, bottom_action_bar, show_modern_info, show_modern_warning


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError("HEX 형식이 아닙니다.")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


class MagnifierLabel(QLabel):
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        painter.setPen(QPen(QColor("#FFFFFF"), 3))
        painter.drawLine(center.x(), 0, center.x(), self.height())
        painter.drawLine(0, center.y(), self.width(), center.y())
        painter.setPen(QPen(QColor("#E11D48"), 1))
        painter.drawLine(center.x(), 0, center.x(), self.height())
        painter.drawLine(0, center.y(), self.width(), center.y())
        painter.drawEllipse(center, 5, 5)


class MagnifierPopup(QDialog):
    color_selected = pyqtSignal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setFixedSize(180, 210)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.preview = MagnifierLabel()
        self.preview.setFixedSize(168, 168)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview)
        layout.addWidget(self.label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(30)

    def refresh(self) -> None:
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        if not screen:
            return
        local = pos - screen.geometry().topLeft()
        zoom = screen.grabWindow(0, local.x() - 10, local.y() - 10, 21, 21)
        one = screen.grabWindow(0, local.x(), local.y(), 1, 1).toImage()
        if one.isNull():
            return
        color = one.pixelColor(0, 0)
        self.preview.setPixmap(zoom.scaled(168, 168, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation))
        self.label.setText(color.name().upper())
        self.move(pos.x() + 18, pos.y() + 18)

    def mousePressEvent(self, event) -> None:
        pos = QCursor.pos()
        self.color_selected.emit(pos.x(), pos.y())
        self.accept()


class ColorToolsTab(QWidget):
    screen_pixel_requested = pyqtSignal(int, int)

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._updating = False
        self.screen_pixel_requested.connect(self.capture_screen_pixel)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        content = QWidget()
        layout = QVBoxLayout(content)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.hex_value = QLineEdit("#3B6CF5")
        self.hex_value.setMaximumWidth(340)
        self.hex_value.editingFinished.connect(self.apply_hex)
        self.rgb_fields = [self.spin(0, 255) for _ in range(3)]
        self.hsl_fields = [self.spin(0, 360), self.spin(0, 100), self.spin(0, 100)]
        for field in self.rgb_fields:
            field.valueChanged.connect(self.apply_rgb)
        for field in self.hsl_fields:
            field.valueChanged.connect(self.apply_hsl)
        self.rgb_text = QLineEdit()
        self.rgb_text.setMaximumWidth(340)
        self.rgb_text.setReadOnly(True)
        self.hsl_text = QLineEdit()
        self.hsl_text.setMaximumWidth(340)
        self.hsl_text.setReadOnly(True)
        self.swatch = QLabel("")
        self.swatch.setMaximumWidth(340)
        self.swatch.setFixedHeight(52)
        form.addRow("HEX", self.hex_value)
        form.addRow("RGB 입력", self.field_row(self.rgb_fields))
        form.addRow("HSL 입력", self.field_row(self.hsl_fields))
        hint = QLabel("H 0~360, S/L 0~100 기준으로 입력합니다.")
        hint.setObjectName("mutedText")
        form.addRow("", hint)
        form.addRow("RGB", self.rgb_text)
        form.addRow("HSL", self.hsl_text)
        form.addRow("미리보기", self.swatch)
        self.history_grid = QGridLayout()
        self.history_grid.setContentsMargins(0, 0, 0, 0)
        self.history_grid.setHorizontalSpacing(6)
        self.history_grid.setVerticalSpacing(6)
        self.history_grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        history_holder = QWidget()
        history_holder.setLayout(self.history_grid)
        history_holder.setFixedHeight(26)
        history_holder.setFixedWidth(22 * 20 + 6 * 19)
        form.addRow("최근 색상", history_holder)
        layout.addLayout(form)
        layout.addStretch(1)

        buttons = []
        for text, callback in [
            ("색 선택", self.pick_color),
            ("화면에서 찍기", self.pick_screen_color),
            ("HEX 복사", lambda: self.main.app.clipboard().setText(self.hex_value.text())),
            ("RGB 복사", lambda: self.main.app.clipboard().setText(self.rgb_text.text())),
            ("HSL 복사", lambda: self.main.app.clipboard().setText(self.hsl_text.text())),
            ("최근 색상 초기화", self.clear_history),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            buttons.append(button)
        root.addWidget(content, 1)
        root.addLayout(bottom_action_bar(*buttons))
        self.refresh()
        colors = self.main.settings.get("color_history", [])
        if colors:
            default_color = colors[0].get("hex", "#94AEF4")
        else:
            default_color = THEMES.get(self.main.settings.get("theme", "light"), THEMES["light"]).get("highlight", "#94AEF4")
        self.set_color(default_color, add_history=False)

    def spin(self, low: int, high: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setFixedWidth(64)
        return spin

    def field_row(self, fields: list[QSpinBox]) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        for field in fields:
            row.addWidget(field)
        row.addStretch(1)
        return widget

    def refresh(self) -> None:
        while self.history_grid.count():
            item = self.history_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        colors = self.main.settings.setdefault("color_history", [])
        for index, item in enumerate(colors[:20]):
            hex_value = item.get("hex", "")
            button = QPushButton("")
            button.setFixedSize(22, 22)
            button.setToolTip(hex_value)
            button.setStyleSheet(f"QPushButton {{ background: {hex_value}; border: 1px solid #6B7280; padding: 0; }}")
            button.clicked.connect(lambda checked=False, value=hex_value: self.set_color(value, add_history=False))
            self.history_grid.addWidget(button, 0, index)
        self.history_grid.setColumnStretch(len(colors[:20]), 1)

    def pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.hex_value.text()), self, "색 선택")
        if color.isValid():
            self.set_color(color.name().upper())

    def pick_screen_color(self) -> None:
        try:
            from pynput import mouse as pynput_mouse
        except Exception:
            return
        popup = MagnifierPopup(self)

        def on_click(x, y, _button, pressed):
            if not pressed:
                return None
            self.screen_pixel_requested.emit(int(x), int(y))
            QTimer.singleShot(0, popup.accept)
            return False

        listener = pynput_mouse.Listener(on_click=on_click)
        listener.start()
        popup.exec()
        try:
            listener.stop()
        except Exception:
            pass

    def capture_screen_pixel(self, x: int, y: int) -> None:
        screen = QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        if not screen:
            return
        local = QPoint(x, y) - screen.geometry().topLeft()
        one = screen.grabWindow(0, local.x(), local.y(), 1, 1).toImage()
        if one.isNull():
            return
        self.set_color(one.pixelColor(0, 0).name().upper())

    def apply_hex(self) -> None:
        self.set_color(self.hex_value.text())

    def apply_rgb(self) -> None:
        if self._updating:
            return
        self.set_rgb(*(field.value() for field in self.rgb_fields))

    def apply_hsl(self) -> None:
        if self._updating:
            return
        h, s, l = [field.value() for field in self.hsl_fields]
        r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
        self.set_rgb(round(r * 255), round(g * 255), round(b * 255))

    def set_color(self, value: str, add_history: bool = True) -> None:
        try:
            self.set_rgb(*hex_to_rgb(value), add_history=add_history)
        except Exception:
            return

    def set_rgb(self, r: int, g: int, b: int, add_history: bool = True) -> None:
        self._updating = True
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        hex_value = rgb_to_hex(r, g, b)
        self.hex_value.setText(hex_value)
        for field, value in zip(self.rgb_fields, [r, g, b]):
            field.setValue(value)
        for field, value in zip(self.hsl_fields, [round(h * 360), round(s * 100), round(l * 100)]):
            field.setValue(value)
        self.rgb_text.setText(f"rgb({r}, {g}, {b})")
        self.hsl_text.setText(f"hsl({round(h * 360)}, {round(s * 100)}%, {round(l * 100)}%)")
        self.swatch.setStyleSheet(f"background: {hex_value}; border: 1px solid #6B7280; border-radius: 8px;")
        self._updating = False
        if add_history:
            self.add_history(hex_value)

    def add_history(self, hex_value: str) -> None:
        colors = self.main.settings.setdefault("color_history", [])
        colors[:] = [item for item in colors if item.get("hex") != hex_value]
        colors.insert(0, {"hex": hex_value, "rgb": self.rgb_text.text(), "hsl": self.hsl_text.text()})
        del colors[20:]
        self.main.save_data()
        self.refresh()

    def clear_history(self) -> None:
        if not ask_modern_question(self, "최근 색상 초기화", "최근 색상 이력을 모두 지울까요?", None, "초기화", "취소"):
            return
        self.main.settings["color_history"] = []
        config.save_settings(self.main.settings)
        self.refresh()

    def apply_theme(self) -> None:
        colors = self.main.settings.get("color_history", [])
        if not colors:
            highlight = THEMES.get(self.main.settings.get("theme", "light"), THEMES["light"]).get("highlight", "#94AEF4")
            self.set_color(highlight, add_history=False)


class MouseHighlightOverlay(QWidget):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if hasattr(Qt.WindowType, "NoDropShadowWindowHint"):
            flags |= Qt.WindowType.NoDropShadowWindowHint
        if hasattr(Qt.WindowType, "WindowTransparentForInput"):
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(1.0)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cursor_pos = QCursor.pos()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.follow_cursor)
        self.timer.start(24)
        self.follow_cursor()

    def follow_cursor(self) -> None:
        rect = virtual_screen_geometry()
        if not rect.isNull():
            self.setGeometry(rect)
        self.cursor_pos = QCursor.pos()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.settings.get("mouse_highlight_color", "#FFDD33"))
        color.setAlpha(round(int(self.settings.get("mouse_highlight_opacity", 50)) * 2.55))
        shape = self.settings.get("mouse_highlight_shape", "원")
        size = max(4, int(self.settings.get("mouse_highlight_size", 50)))
        center = self.cursor_pos - self.geometry().topLeft()
        rect = QRect(center.x() - size // 2, center.y() - size // 2, size, size)
        if shape.startswith("채워진"):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, 4))
        if "십자" in shape:
            painter.drawLine(center.x(), center.y() - size // 2, center.x(), center.y() + size // 2)
            painter.drawLine(center.x() - size // 2, center.y(), center.x() + size // 2, center.y())
        elif "사각형" in shape:
            painter.drawRect(rect)
        else:
            painter.drawEllipse(rect)


class MouseHighlightTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        content = QWidget()
        layout = QFormLayout(content)
        self.color = QLineEdit(main.settings.get("mouse_highlight_color", "#FFDD33"))
        self.color.setMaximumWidth(340)
        self.shape = QComboBox()
        self.shape.setMaximumWidth(340)
        self.shape.addItems(["원", "채워진 원", "사각형", "채워진 사각형", "십자"])
        self.shape.setCurrentText(main.settings.get("mouse_highlight_shape", "원"))
        self.size = QSlider(Qt.Orientation.Horizontal)
        self.size.setMaximumWidth(340)
        self.size.setRange(0, 100)
        self.size.setValue(int(main.settings.get("mouse_highlight_size", 50)))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setMaximumWidth(340)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(int(main.settings.get("mouse_highlight_opacity", 50)))
        highlight = THEMES.get(main.settings.get("theme", "light"), THEMES["light"]).get("highlight", "#94AEF4")
        slider_style = self._slider_style(highlight)
        self.size.setStyleSheet(slider_style)
        self.opacity.setStyleSheet(slider_style)
        self.shape.currentTextChanged.connect(self.apply_live)
        self.size.valueChanged.connect(self.apply_live)
        self.opacity.valueChanged.connect(self.apply_live)
        on = QPushButton("켜기")
        off = QPushButton("끄기")
        pick = QPushButton("색 선택")
        on.clicked.connect(self.enable)
        off.clicked.connect(self.disable)
        pick.clicked.connect(self.pick)
        layout.addRow("색상", self.color)
        layout.addRow("모양", self.shape)
        layout.addRow("크기", self.size)
        layout.addRow("투명도", self.opacity)
        root.addWidget(content, 1)
        root.addLayout(bottom_action_bar(on, off, pick))

    def pick(self) -> None:
        color = QColorDialog.getColor(QColor(self.color.text()), self, "하이라이트 색")
        if color.isValid():
            self.color.setText(color.name().upper())
            self.apply_live()

    def current_values(self) -> dict:
        return {
            "mouse_highlight_color": self.color.text().strip() or "#FFDD33",
            "mouse_highlight_shape": self.shape.currentText(),
            "mouse_highlight_size": self.size.value(),
            "mouse_highlight_opacity": self.opacity.value(),
        }

    def apply_live(self) -> None:
        self.main.settings.update(self.current_values())
        if self.main.mouse_highlight_overlay is not None:
            self.main.mouse_highlight_overlay.settings = self.main.settings
            self.main.mouse_highlight_overlay.follow_cursor()

    def enable(self) -> None:
        self.apply_live()
        self.main.save_data()
        self.main.set_mouse_highlight(True)

    def disable(self) -> None:
        self.main.set_mouse_highlight(False)

    @staticmethod
    def _slider_style(highlight: str) -> str:
        return f"""
            QSlider::groove:horizontal {{
                height: 6px; background: rgba(148,163,184,70); border: 0; border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {highlight}; border: 0; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 15px; height: 15px; margin: -5px 0;
                background: #FFFFFF; border: 1px solid {highlight}; border-radius: 8px;
            }}
        """

    def apply_theme(self) -> None:
        highlight = THEMES.get(self.main.settings.get("theme", "light"), THEMES["light"]).get("highlight", "#94AEF4")
        slider_style = self._slider_style(highlight)
        self.size.setStyleSheet(slider_style)
        self.opacity.setStyleSheet(slider_style)


class ScreenDrawOverlay(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        rect = virtual_screen_geometry()
        self.setGeometry(rect)
        self.canvas = QPixmap(rect.size())
        self.canvas.fill(Qt.GlobalColor.transparent)
        self.draw_bounds: QRect | None = None
        self.last_pos: QPoint | None = None
        self.last_mid: QPointF | None = None
        self.color = QColor("#FFDD33")
        self.stroke_width = 8
        self.mode = "highlight"
        self.background_mode = "screen"
        self.screen_scope = "all"
        self.background_snapshot: QPixmap | None = None
        self.background_blur_snapshot: QPixmap | None = None

        toolbar = QWidget(self)
        toolbar.setObjectName("screenDrawToolbar")
        toolbar.setStyleSheet(
            """
            QWidget#screenDrawToolbar { background: rgba(17, 24, 39, 230); border-radius: 10px; }
            QPushButton, QComboBox, QSpinBox { min-height: 28px; border: 0; border-radius: 6px; padding: 2px 10px; background: #FFFFFF; color: #111827; font-weight: 700; }
            QPushButton#closeButton { background: #EF4444; color: white; }
            """
        )
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("형광펜", "highlight")
        self.mode_combo.addItem("펜", "pen")
        self.mode_combo.addItem("지우개", "eraser")
        self.mode_combo.setMinimumWidth(110)
        self.mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 60)
        self.width_spin.setValue(self.stroke_width)
        self.width_spin.setSuffix(" px")
        self.width_spin.setMinimumWidth(88)
        self.color_btn = QPushButton("색상")
        clear_btn = QPushButton("초기화")
        save_btn = QPushButton("컨닝페이퍼 저장")
        close_btn = QPushButton("닫기")
        close_btn.setObjectName("closeButton")
        self.bg_combo = QComboBox()
        self.bg_combo.addItem("윈도우 화면", "screen")
        self.bg_combo.addItem("어두운 배경", "dark")
        self.bg_combo.addItem("밝은 배경", "glass")
        self.bg_combo.setMinimumWidth(128)
        self.bg_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        row.addWidget(self.bg_combo)
        row.addWidget(self.mode_combo)
        row.addWidget(QLabel("굵기"))
        row.addWidget(self.width_spin)
        row.addWidget(self.color_btn)
        row.addWidget(clear_btn)
        row.addWidget(save_btn)
        row.addWidget(close_btn)
        toolbar.adjustSize()
        self.toolbar = toolbar
        self.place_toolbar_on_target_screen()

        self.mode_combo.currentIndexChanged.connect(lambda _=0: setattr(self, "mode", self.mode_combo.currentData()))
        self.bg_combo.currentIndexChanged.connect(self.set_background_mode)
        self.width_spin.valueChanged.connect(self.set_stroke_width)
        self.color_btn.clicked.connect(self.pick_color)
        clear_btn.clicked.connect(self.clear_canvas)
        save_btn.clicked.connect(self.save_to_cheat_sheet)
        close_btn.clicked.connect(self.hide)
        self.apply_default_color_for_background()

    def virtual_screen_rect(self) -> QRect:
        return virtual_screen_geometry()

    def active_screen_rect(self) -> QRect:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        return screen.geometry() if screen else self.virtual_screen_rect()

    def target_screen_rect(self) -> QRect:
        return self.active_screen_rect() if self.screen_scope == "active" else self.virtual_screen_rect()

    def place_toolbar_on_target_screen(self) -> None:
        primary = QApplication.primaryScreen()
        if self.screen_scope == "active":
            target = self.active_screen_rect()
        elif primary:
            target = primary.geometry()
        else:
            target = self.geometry()
        if target.isNull():
            self.toolbar.move(24, 24)
            return
        local_top_left = target.topLeft() - self.geometry().topLeft()
        self.toolbar.move(local_top_left + QPoint(24, 24))

    def refresh_geometry(self, screen_scope: str | None = None) -> None:
        if screen_scope:
            self.screen_scope = screen_scope
        rect = self.target_screen_rect()
        if rect == self.geometry():
            self.place_toolbar_on_target_screen()
            return
        old_canvas = self.canvas
        old_geometry = self.geometry()
        self.setGeometry(rect)
        self.canvas = QPixmap(rect.size())
        self.canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.canvas)
        offset = old_geometry.topLeft() - rect.topLeft()
        painter.drawPixmap(offset, old_canvas)
        painter.end()
        if self.draw_bounds is not None:
            self.draw_bounds.translate(offset)
            self.draw_bounds = self.draw_bounds.intersected(self.canvas.rect())
        self.place_toolbar_on_target_screen()

    def set_background_mode(self) -> None:
        self.background_mode = self.bg_combo.currentData() or "screen"
        self.apply_default_color_for_background()
        if self.background_mode == "glass":
            self.capture_virtual_background()
        self.update()

    def set_background_mode_value(self, mode: str) -> None:
        index = self.bg_combo.findData(mode)
        if index >= 0:
            self.bg_combo.setCurrentIndex(index)
        self.background_mode = mode
        self.apply_default_color_for_background()
        if self.background_mode == "glass":
            self.capture_virtual_background()
        self.update()

    def apply_default_color_for_background(self) -> None:
        default_colors = {
            "screen": "#FFDD33",
            "dark": "#FFFFFF",
            "glass": "#111111",
        }
        self.color = QColor(default_colors.get(self.background_mode, "#FFDD33"))
        text_color = "#111827" if self.color.lightness() > 180 else "#FFFFFF"
        self.color_btn.setStyleSheet(f"background:{self.color.name()}; color:{text_color};")

    def capture_virtual_background(self) -> None:
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
            QApplication.processEvents()
        snapshot = QPixmap(self.size())
        snapshot.fill(Qt.GlobalColor.transparent)
        painter = QPainter(snapshot)
        pixmap = capture_screen_rect(self.geometry())
        if not pixmap.isNull():
            painter.drawPixmap(0, 0, pixmap)
        painter.end()
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()
            self.setFocus()
        self.background_snapshot = snapshot
        small_width = max(1, snapshot.width() // 12)
        small_height = max(1, snapshot.height() // 12)
        self.background_blur_snapshot = snapshot.scaled(
            small_width,
            small_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).scaled(
            snapshot.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def pick_color(self) -> None:
        color = QColorDialog.getColor(self.color, self, "화면 그리기 색상")
        if color.isValid():
            self.color = color
            text_color = "#111827" if self.color.lightness() > 180 else "#FFFFFF"
            self.color_btn.setStyleSheet(f"background:{self.color.name()}; color:{text_color};")

    def set_stroke_width(self, value: int) -> None:
        self.stroke_width = max(1, min(60, value))
        if self.width_spin.value() != self.stroke_width:
            self.width_spin.setValue(self.stroke_width)

    def clear_canvas(self) -> None:
        self.canvas.fill(Qt.GlobalColor.transparent)
        self.draw_bounds = None
        self.update()

    def paint_background(self, painter: QPainter, target: QRect | None = None) -> None:
        rect = target or self.rect()
        if self.background_mode == "dark":
            painter.fillRect(rect, QColor(0, 0, 0, 120))
        elif self.background_mode == "glass":
            if self.background_blur_snapshot is not None and not self.background_blur_snapshot.isNull():
                painter.drawPixmap(0, 0, self.background_blur_snapshot)
            painter.fillRect(rect, QColor(255, 255, 255, 132))
            painter.fillRect(rect, QColor(232, 238, 246, 45))
        else:
            painter.fillRect(rect, QColor(0, 0, 0, 1))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self.paint_background(painter)
        painter.drawPixmap(0, 0, self.canvas)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if self.toolbar.geometry().contains(event.position().toPoint()):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_pos = event.position().toPoint()
            self.last_mid = QPointF(self.last_pos)
            self.draw_to(self.last_pos)

    def mouseMoveEvent(self, event) -> None:
        if self.last_pos is None:
            return
        pos = event.position().toPoint()
        self.draw_to(pos)

    def draw_to(self, pos: QPoint) -> None:
        previous = self.last_pos
        painter = QPainter(self.canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.mode == "eraser":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setPen(QPen(Qt.GlobalColor.transparent, self.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            color = QColor(self.color)
            color.setAlpha(90 if self.mode == "highlight" else 230)
            cap = Qt.PenCapStyle.FlatCap if self.mode == "highlight" else Qt.PenCapStyle.RoundCap
            painter.setPen(QPen(color, self.stroke_width, Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin))
        if self.last_pos == pos:
            painter.drawPoint(pos)
        elif self.mode == "eraser":
            painter.drawLine(self.last_pos, pos)
        else:
            start = self.last_mid if self.last_mid is not None else QPointF(self.last_pos)
            mid = QPointF((self.last_pos.x() + pos.x()) / 2, (self.last_pos.y() + pos.y()) / 2)
            path = QPainterPath(start)
            path.quadTo(QPointF(self.last_pos), mid)
            painter.drawPath(path)
            self.last_mid = mid
        painter.end()
        self.remember_draw_bounds(previous or pos, pos)
        self.last_pos = pos
        update_rect = QRect(previous or pos, pos).normalized().adjusted(-self.stroke_width - 8, -self.stroke_width - 8, self.stroke_width + 8, self.stroke_width + 8)
        self.update(update_rect)

    def remember_draw_bounds(self, start: QPoint, end: QPoint) -> None:
        margin = self.stroke_width // 2 + 8
        rect = QRect(start, end).normalized().adjusted(-margin, -margin, margin, margin)
        rect = rect.intersected(self.canvas.rect())
        self.draw_bounds = rect if self.draw_bounds is None else self.draw_bounds.united(rect).intersected(self.canvas.rect())

    def grab_background(self, crop: QRect) -> QPixmap:
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
            QApplication.processEvents()
        global_top_left = self.geometry().topLeft() + crop.topLeft()
        shot = capture_screen_rect(QRect(global_top_left, crop.size()))
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()
            self.setFocus()
        if shot.isNull():
            shot = QPixmap(crop.size())
            shot.fill(Qt.GlobalColor.transparent)
        return shot

    def compose_crop(self, crop: QRect) -> QPixmap:
        result = self.grab_background(crop)
        painter = QPainter(result)
        if self.background_mode == "dark":
            painter.fillRect(result.rect(), QColor(0, 0, 0, 120))
        elif self.background_mode == "glass":
            small_width = max(1, result.width() // 12)
            small_height = max(1, result.height() // 12)
            blurred = result.scaled(
                small_width,
                small_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ).scaled(result.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, 0, blurred)
            painter.fillRect(result.rect(), QColor(255, 255, 255, 132))
            painter.fillRect(result.rect(), QColor(232, 238, 246, 45))
        painter.drawPixmap(0, 0, self.canvas.copy(crop))
        painter.end()
        return result

    def relative_asset_path(self, path) -> str:
        try:
            return str(path.resolve().relative_to(config.BASE_DIR.resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

    def save_to_cheat_sheet(self) -> None:
        if self.draw_bounds is None or self.draw_bounds.isEmpty():
            show_modern_warning(self, "저장할 그리기 없음", "먼저 화면 위에 표시를 그려주세요.")
            return
        crop = self.draw_bounds.adjusted(-30, -30, 30, 30).intersected(self.canvas.rect())
        pixmap = self.compose_crop(crop)
        image_dir = config.BASE_DIR / "assets" / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_id = new_id("img")
        path = image_dir / f"screen_draw_{image_id}.png"
        if not pixmap.save(str(path), "PNG"):
            show_modern_warning(self, "저장 실패", "그리기 이미지를 저장하지 못했습니다.")
            return
        copy_pixmap_to_clipboard(pixmap)
        images = self.main.data.setdefault("images", [])
        created_at = now_iso()
        images.append(
            {
                "id": image_id,
                "name": f"화면 그리기 {created_at[:16].replace('T', ' ')}",
                "path": self.relative_asset_path(path),
                "path_type": "relative",
                "hotkey": None,
                "sort_order": len(images),
                "display_scale": 100,
                "created_at": created_at,
                "usage_count": 0,
            }
        )
        self.main.save_data()
        show_modern_info(self, "저장 완료", "그린 영역을 컨닝페이퍼에 등록하고 클립보드에 복사했습니다.")

    def mouseReleaseEvent(self, event) -> None:
        self.last_pos = None
        self.last_mid = None

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta:
            step = 1 if delta > 0 else -1
            self.set_stroke_width(self.stroke_width + step)
        event.accept()


class ScreenDrawTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.overlay: ScreenDrawOverlay | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        info = QLabel(
            "발표 중 현재 화면 위에 형광펜, 펜, 지우개로 표시할 수 있습니다.\n"
            "마우스 휠로 굵기를 조절할 수 있고, 마우스 하이라이트나 캡처 기능과 함께 사용할 수 있습니다."
        )
        info.setWordWrap(True)
        hotkey_note = QLabel("단축키는 설정 → 단축키 탭에서 변경할 수 있습니다.")
        hotkey_note.setObjectName("mutedText")
        option_grid = QGridLayout()
        option_grid.setContentsMargins(0, 0, 0, 0)
        option_grid.setHorizontalSpacing(14)
        option_grid.setVerticalSpacing(6)
        bg_label = QLabel("배경 화면")
        self.background_combo = QComboBox()
        self.background_combo.addItem("윈도우 화면", "screen")
        self.background_combo.addItem("어두운 배경", "dark")
        self.background_combo.addItem("밝은 배경", "glass")
        self.background_combo.setMinimumWidth(180)
        screen_label = QLabel("그리기 범위")
        self.screen_scope_combo = QComboBox()
        self.screen_scope_combo.addItem("전체 모니터", "all")
        self.screen_scope_combo.addItem("현재 마우스 위치 모니터", "active")
        self.screen_scope_combo.setMinimumWidth(180)
        option_grid.addWidget(bg_label, 0, 0)
        option_grid.addWidget(self.background_combo, 0, 1)
        option_grid.addWidget(screen_label, 0, 2)
        option_grid.addWidget(self.screen_scope_combo, 0, 3)
        option_grid.setColumnStretch(4, 1)
        start = QPushButton("화면 그리기 시작")
        start.clicked.connect(self.start_overlay)
        layout.addWidget(info)
        layout.addWidget(hotkey_note)
        layout.addLayout(option_grid)
        layout.addStretch(1)
        root.addWidget(content, 1)
        root.addLayout(bottom_action_bar(start))

    def start_overlay(self) -> None:
        if self.overlay is None:
            self.overlay = ScreenDrawOverlay(self.main)
        self.overlay.refresh_geometry(self.screen_scope_combo.currentData() or "all")
        self.overlay.set_background_mode_value(self.background_combo.currentData() or "screen")
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.overlay.setFocus()


class EmojiTab(QWidget):
    CATEGORIES = {
        "사용 이력": [],
        "얼굴": "😀 😃 😄 😁 😆 😅 😂 🤣 🥲 ☺️ 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😝 😜 🤪 🤨 🧐 🤓 😎 🥸 🤩 🥳 😏 😒 😞 😔 😟 😕 🙁 ☹️ 😣 😖 😫 😩 🥺 😢 😭 😤 😠 😡 🤬 🤯 😳 🥵 🥶 😱 😨 😰 😥 😓 🤗 🤔 🫣 🤭 🫢 🫡 🤫 🫠 🤥 😶 😐 😑 😬 🙄 😯 😦 😧 😮 😲 🥱 😴 🤤 😪 😮‍💨 😵 😵‍💫 🤐 🥴 🤢 🤮 🤧 😷 🤒 🤕".split(),
        "사람": "👋 🤚 🖐 ✋ 🖖 👌 🤌 🤏 ✌️ 🤞 🫰 🤟 🤘 🤙 👈 👉 👆 🖕 👇 ☝️ 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 🫶 👐 🤲 🤝 🙏 ✍️ 💅 🤳 💪 🦾 🦿 🦵 🦶 👂 🦻 👃 🧠 🫀 🫁 🦷 🦴 👀 👁 👅 👄 🫦 👶 🧒 👦 👧 🧑 👱 👨 🧔 👩 🧓 👴 👵".split(),
        "동물/자연": "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐻‍❄️ 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🙈 🙉 🙊 🐒 🐔 🐧 🐦 🐤 🦆 🦅 🦉 🦇 🐺 🐗 🐴 🦄 🐝 🪱 🐛 🦋 🐌 🐞 🐜 🪰 🪲 🪳 🦟 🦗 🕷 🦂 🐢 🐍 🦎 🦖 🦕 🐙 🦑 🦐 🦞 🦀 🪼 🐠 🐟 🐬 🐳 🐋 🦈 🐊 🐅 🐆 🦓 🦍 🦧 🐘 🦛 🦏 🐪 🦒 🦘 🦬 🌵 🎄 🌲 🌳 🌴 🪵 🌱 🌿 ☘️ 🍀 🎍 🪴 🌸 🌼 🌻 🌞 🌝 🌛 🌜 ⭐ 🌟 ✨ ⚡ 🔥 💧 🌊".split(),
        "음식": "🍏 🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🫒 🥑 🍆 🥔 🥕 🌽 🌶 🫑 🥒 🥬 🥦 🧄 🧅 🍄 🥜 🫘 🌰 🍞 🥐 🥖 🫓 🥨 🥯 🥞 🧇 🧀 🍖 🍗 🥩 🥓 🍔 🍟 🍕 🌭 🥪 🌮 🌯 🫔 🥙 🧆 🥚 🍳 🥘 🍲 🫕 🥣 🥗 🍿 🧈 🧂 🍱 🍘 🍙 🍚 🍛 🍜 🍝 🍠 🍢 🍣 🍤 🍥 🥮 🍡 🥟 🥠 🥡 🍦 🍧 🍨 🍩 🍪 🎂 🍰 🧁 🥧 🍫 🍬 🍭 🍮 🍯".split(),
        "활동/물건": "⚽ 🏀 🏈 ⚾ 🥎 🎾 🏐 🏉 🥏 🎱 🪀 🏓 🏸 🏒 🏑 🥍 🏏 🪃 🥅 ⛳ 🪁 🏹 🎣 🤿 🥊 🥋 🎽 🛹 🛼 🛷 ⛸ 🥌 🎿 ⛷ 🏂 🪂 🏋️ 🤼 🤸 ⛹️ 🤺 🤾 🏌️ 🧘 🛀 🛌 🎮 🕹 🎲 ♟ 🎯 🎳 🎭 🎨 🧵 🪡 🧶 🪢 👓 🕶 🥽 🥼 🦺 👔 👕 👖 🧣 🧤 🧥 🧦 👗 👘 🥻 🩱 🩲 🩳 👙 👚 👛 👜 👝 🛍 🎒 🩴 👞 👟 🥾 🥿 👠 👡 🩰 👢 👑 👒 🎩 🎓 🧢 🪖 ⛑ 💄 💍 💼 📱 💻 ⌨️ 🖥 🖨 🖱 🕹 🗜 💽 💾 💿 📀 📼 📷 📸 📹 🎥 📽 🎞 📞 ☎️ 📟 📠 📺 📻 🎙 🎚 🎛 🧭 ⏱ ⏲ ⏰ 🕰 ⌛ ⏳ 📡 🔋 🪫 🔌 💡 🔦 🕯 🪔 🧯 🛢 💸 💵 💴 💶 💷 🪙 💰 💳 💎 ⚖️ 🪜 🧰 🪛 🔧 🔨 ⚒ 🛠 ⛏ 🪚 🔩 ⚙️ 🧱 ⛓ 🧲 🔫 💣 🧨 🪓 🔪 🗡 ⚔️ 🛡 🚬 ⚰️ 🪦 ⚱️ 🏺 🔮 📿 🧿 🪬 💈 ⚗️ 🔭 🔬 🕳 🩹 🩺 💊 💉 🩸 🧬 🦠 🧫 🧪 🌡 🧹 🪠 🧽 🧴 🛎 🔑 🗝 🚪 🪑 🛋 🛏 🪞 🪟 🧳 🛒 🎁 🎈 🎏 🎀 🪄 🪅 🎊 🎉".split(),
        "기호": "❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 ☮️ ✝️ ☪️ 🕉 ☸️ ✡️ 🔯 🕎 ☯️ ☦️ 🛐 ⛎ ♈ ♉ ♊ ♋ ♌ ♍ ♎ ♏ ♐ ♑ ♒ ♓ 🆔 ⚛️ 🉑 ☢️ ☣️ 📴 📳 🈶 🈚 🈸 🈺 🈷️ ✴️ 🆚 💮 🉐 ㊙️ ㊗️ 🈴 🈵 🈹 🈲 🅰️ 🅱️ 🆎 🆑 🅾️ 🆘 ❌ ⭕ 🛑 ⛔ 📛 🚫 💯 💢 ♨️ 🚷 🚯 🚳 🚱 🔞 📵 🚭 ❗ ❕ ❓ ❔ ‼️ ⁉️ 🔅 🔆 〽️ ⚠️ 🚸 🔱 ⚜️ 🔰 ♻️ ✅ 🈯 💹 ❇️ ✳️ ❎ 🌐 💠 Ⓜ️ 🌀 💤 🏧 🚾 ♿ 🅿️ 🛗 🈳 🈂️ 🛂 🛃 🛄 🛅 🚹 🚺 🚼 ⚧ 🚻 🚮 🎦 📶 🈁 🔣 ℹ️ 🔤 🔡 🔠 🆖 🆗 🆙 🆒 🆕 🆓 0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟 🔢 #️⃣ *️⃣ ⏏️ ▶️ ⏸ ⏯ ⏹ ⏺ ⏭ ⏮ ⏩ ⏪ ⏫ ⏬ ◀️ 🔼 🔽 ➡️ ⬅️ ⬆️ ⬇️ ↗️ ↘️ ↙️ ↖️ ↕️ ↔️ ↪️ ↩️ ⤴️ ⤵️ 🔀 🔁 🔂 🔄 🔃 🎵 🎶 ➕ ➖ ➗ ✖️ 🟰 ♾ 💲 💱 ™️ ©️ ®️ 〰️ ➰ ➿ 🔚 🔙 🔛 🔝 🔜 ✔️ ☑️ 🔘 🔴 🟠 🟡 🟢 🔵 🟣 ⚫ ⚪ 🟤 🔺 🔻 🔸 🔹 🔶 🔷 🔳 🔲 ▪️ ▫️ ◾ ◽ ◼️ ◻️ 🟥 🟧 🟨 🟩 🟦 🟪 ⬛ ⬜ 🟫".split(),
        "국기": "🇰🇷 🇺🇸 🇯🇵 🇨🇳 🇬🇧 🇫🇷 🇩🇪 🇨🇦 🇦🇺 🇮🇹 🇪🇸 🇧🇷 🇲🇽 🇮🇳 🇸🇬 🇹🇭 🇻🇳 🇵🇭 🇮🇩 🇲🇾 🇳🇿 🇹🇼 🇭🇰 🇪🇺 🇦🇷 🇦🇹 🇧🇪 🇨🇭 🇨🇱 🇨🇴 🇨🇿 🇩🇰 🇪🇬 🇫🇮 🇬🇷 🇭🇺 🇮🇪 🇮🇱 🇳🇱 🇳🇴 🇵🇱 🇵🇹 🇸🇦 🇸🇪 🇹🇷 🇺🇦 🇿🇦".split(),
    }
    # 특수문자 카테고리는 '특수문자' 탭(SpecialCharTab)과 내용이 중복되므로 이모지 탭에서는 제외한다.

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self.rows = QVBoxLayout(container)
        self.rows.setContentsMargins(6, 6, 6, 6)
        self.rows.setSpacing(8)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        clear = QPushButton("최근 이모지 초기화")
        clear.clicked.connect(self.clear_usage)
        root.addWidget(content, 1)
        root.addLayout(bottom_action_bar(clear))
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        usage = self.main.settings.setdefault("emoji_usage", {})
        used = sorted(usage, key=lambda emoji: int(usage.get(emoji, 0)), reverse=True)
        categories = dict(self.CATEGORIES)
        categories["사용 이력"] = used
        for name, emojis in categories.items():
            if name == "사용 이력" and not emojis:
                continue
            box = QWidget()
            box.setObjectName("card")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 6, 8, 8)
            box_layout.setSpacing(4)
            title = QLabel(name)
            title.setObjectName("cardTitle")
            box_layout.addWidget(title)
            grid_holder = QWidget()
            grid_holder.setStyleSheet("background: transparent;")
            grid = QGridLayout(grid_holder)
            grid.setContentsMargins(0, 0, 0, 0)
            is_usage = name == "사용 이력"
            grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            grid.setHorizontalSpacing(4 if is_usage else 0)
            grid.setVerticalSpacing(0)
            for index, emoji in enumerate(emojis):
                button = QPushButton(emoji)
                button.setFlat(True)
                button.setFixedSize(26 if is_usage else 22, 24 if is_usage else 22)
                button.setStyleSheet("QPushButton { border: 0; padding: 0; font-size: 13pt; background: transparent; } QPushButton:hover { background: rgba(59,108,245,35); }")
                button.clicked.connect(lambda checked=False, value=emoji: self.copy_emoji(value))
                row, col = (0, index) if is_usage else divmod(index, 28)
                grid.addWidget(button, row, col)
            box_layout.addWidget(grid_holder, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(box)
        self.rows.addStretch(1)

    def copy_emoji(self, emoji: str) -> None:
        self.main.app.clipboard().setText(emoji)
        usage = self.main.settings.setdefault("emoji_usage", {})
        usage[emoji] = int(usage.get(emoji, 0)) + 1
        config.save_settings(self.main.settings)
        QTimer.singleShot(60, self.refresh)

    def clear_usage(self) -> None:
        if not ask_modern_question(self, "최근 이모지 초기화", "최근 이모지 사용 이력을 모두 지울까요?", None, "초기화", "취소"):
            return
        self.main.settings["emoji_usage"] = {}
        config.save_settings(self.main.settings)
        self.refresh()


class SpecialCharTab(QWidget):
    CATEGORIES: dict[str, list[str]] = {
        "사용 이력": [],
        "일반 기호": [
            "★", "☆", "♥", "♡", "◆", "◇", "●", "○", "■", "□", "▲", "△", "▼", "▽",
            "✓", "✔", "✕", "✖", "✗", "✘", "✚", "✦", "✧", "※", "〒", "☎", "☏",
            "☑", "☐", "⚠", "⚡", "♠", "♣", "♦", "♪", "♫", "♩", "♬", "♭", "♮", "♯",
            "☀", "☁", "☂", "☃", "☄", "☞", "☜", "☝", "☟",
            "♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓", "⛎",
        ],
        "화살표": [
            "←", "→", "↑", "↓", "↔", "↕", "↖", "↗", "↘", "↙",
            "⇐", "⇒", "⇑", "⇓", "⇔", "⇕", "⇖", "⇗", "⇘", "⇙",
            "⟵", "⟶", "⟷", "⟸", "⟹", "⟺",
            "➡", "⬅", "⬆", "⬇", "⬈", "⬉", "⬊", "⬋",
            "▸", "◂", "▹", "◃", "➤", "➢", "➣", "➥", "➦", "➧", "➨",
            "↩", "↪", "↫", "↬", "↭",
        ],
        "수학 기호": [
            "±", "×", "÷", "≠", "≈", "≤", "≥", "≪", "≫", "∞",
            "√", "∑", "∏", "∂", "∫", "∮", "∴", "∵", "∝",
            "∈", "∉", "∋", "∌", "⊂", "⊃", "⊄", "⊅", "⊆", "⊇",
            "∩", "∪", "∀", "∃", "∄", "∅", "∧", "∨", "¬",
            "⊕", "⊗", "≡", "≢", "≅", "≇", "≃", "≄", "∇", "∆",
        ],
        "단위/통화": [
            "°", "℃", "℉", "%", "‰", "‱",
            "㎝", "㎞", "㎡", "㎥", "㎎", "㎏", "㎖", "㎗", "㎘", "㎜", "㎛", "㎚", "㏄",
            "½", "⅓", "¼", "¾", "⅔", "⅛", "⅜", "⅝", "⅞",
            "¹", "²", "³", "⁴", "₁", "₂", "₃", "₄",
            "™", "©", "®", "§", "¶", "†", "‡", "№", "℗",
            "₩", "¥", "£", "€", "$", "¢", "₦", "₹", "₫", "₱",
        ],
        "문장부호": [
            "·", "…", "‥", "‐", "‑", "‒", "–", "—", "―",
            "¡", "¿", "‼", "⁉",
            "′", "″", "‵", "‶", "‷", "〝", "〞",
            "「", "」", "『", "』", "〔", "〕", "【", "】",
            "《", "》", "〈", "〉", "〖", "〗", "〘", "〙", "〚", "〛",
            "‹", "›", "«", "»",
        ],
        "원문자/로마자": [
            "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
            "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳",
            "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ",
            "ⅰ", "ⅱ", "ⅲ", "ⅳ", "ⅴ", "ⅵ", "ⅶ", "ⅷ", "ⅸ", "ⅹ",
            "⑴", "⑵", "⑶", "⑷", "⑸", "⑹", "⑺", "⑻", "⑼", "⑽", "⑾", "⑿", "⒀", "⒁", "⒂",
            "㉠", "㉡", "㉢", "㉣", "㉤", "㉥", "㉦", "㉧", "㉨", "㉩",
            "㉪", "㉫", "㉬", "㉭", "㉮", "㉯", "㉰", "㉱", "㉲", "㉳",
            "㉴", "㉵", "㉶", "㉷", "㉸", "㉹", "㉺", "㉻",
        ],
        "도형/선": [
            "─", "│", "┌", "┐", "└", "┘", "├", "┤", "┬", "┴", "┼",
            "━", "┃", "┏", "┓", "┗", "┛", "┣", "┫", "┳", "┻", "╋",
            "╔", "╗", "╚", "╝", "╠", "╣", "╦", "╩", "╬", "═", "║",
            "▀", "▄", "█", "░", "▒", "▓",
            "◤", "◥", "◢", "◣", "◰", "◱", "◲", "◳",
        ],
        "그리스 문자": [
            "Α", "Β", "Γ", "Δ", "Ε", "Ζ", "Η", "Θ", "Ι", "Κ", "Λ", "Μ",
            "Ν", "Ξ", "Ο", "Π", "Ρ", "Σ", "Τ", "Υ", "Φ", "Χ", "Ψ", "Ω",
            "α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ",
            "ν", "ξ", "ο", "π", "ρ", "σ", "τ", "υ", "φ", "χ", "ψ", "ω",
        ],
        "히라가나": [
            "あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ",
            "さ", "し", "す", "せ", "そ", "た", "ち", "つ", "て", "と",
            "な", "に", "ぬ", "ね", "の", "は", "ひ", "ふ", "へ", "ほ",
            "ま", "み", "む", "め", "も", "や", "ゆ", "よ", "ら", "り",
            "る", "れ", "ろ", "わ", "を", "ん", "ぁ", "ぃ", "ぅ", "ぇ", "ぉ",
            "っ", "ゃ", "ゅ", "ょ",
            "が", "ぎ", "ぐ", "げ", "ご", "ざ", "じ", "ず", "ぜ", "ぞ",
            "だ", "ぢ", "づ", "で", "ど", "ば", "び", "ぶ", "べ", "ぼ",
            "ぱ", "ぴ", "ぷ", "ぺ", "ぽ",
        ],
        "가타카나": [
            "ア", "イ", "ウ", "エ", "オ", "カ", "キ", "ク", "ケ", "コ",
            "サ", "シ", "ス", "セ", "ソ", "タ", "チ", "ツ", "テ", "ト",
            "ナ", "ニ", "ヌ", "ネ", "ノ", "ハ", "ヒ", "フ", "ヘ", "ホ",
            "マ", "ミ", "ム", "メ", "モ", "ヤ", "ユ", "ヨ", "ラ", "リ",
            "ル", "レ", "ロ", "ワ", "ヲ", "ン", "ァ", "ィ", "ゥ", "ェ", "ォ",
            "ッ", "ャ", "ュ", "ョ",
            "ガ", "ギ", "グ", "ゲ", "ゴ", "ザ", "ジ", "ズ", "ゼ", "ゾ",
            "ダ", "ヂ", "ヅ", "デ", "ド", "バ", "ビ", "ブ", "ベ", "ボ",
            "パ", "ピ", "プ", "ペ", "ポ",
        ],
        "키릴 문자": [
            "А", "Б", "В", "Г", "Д", "Е", "Ё", "Ж", "З", "И", "Й", "К",
            "Л", "М", "Н", "О", "П", "Р", "С", "Т", "У", "Ф", "Х", "Ц",
            "Ч", "Ш", "Щ", "Ъ", "Ы", "Ь", "Э", "Ю", "Я",
            "а", "б", "в", "г", "д", "е", "ё", "ж", "з", "и", "й", "к",
            "л", "м", "н", "о", "п", "р", "с", "т", "у", "ф", "х", "ц",
            "ч", "ш", "щ", "ъ", "ы", "ь", "э", "ю", "я",
        ],
    }

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self.rows = QVBoxLayout(container)
        self.rows.setContentsMargins(6, 6, 6, 6)
        self.rows.setSpacing(8)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        clear = QPushButton("최근 특수문자 초기화")
        clear.clicked.connect(self.clear_usage)
        root.addWidget(content, 1)
        root.addLayout(bottom_action_bar(clear))
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        usage = self.main.settings.setdefault("special_char_usage", {})
        used = sorted(usage, key=lambda ch: int(usage.get(ch, 0)), reverse=True)
        categories = dict(self.CATEGORIES)
        categories["사용 이력"] = used
        for name, chars in categories.items():
            if name == "사용 이력" and not chars:
                continue
            box = QWidget()
            box.setObjectName("card")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 6, 8, 8)
            box_layout.setSpacing(4)
            title = QLabel(name)
            title.setObjectName("cardTitle")
            box_layout.addWidget(title)
            grid_holder = QWidget()
            grid_holder.setStyleSheet("background: transparent;")
            grid = QGridLayout(grid_holder)
            grid.setContentsMargins(0, 0, 0, 0)
            is_usage = name == "사용 이력"
            grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            grid.setHorizontalSpacing(4 if is_usage else 0)
            grid.setVerticalSpacing(0)
            for index, ch in enumerate(chars):
                button = QPushButton(ch)
                button.setFlat(True)
                button.setFixedSize(26 if is_usage else 22, 24 if is_usage else 22)
                button.setStyleSheet("QPushButton { border: 0; padding: 0; font-size: 11pt; background: transparent; } QPushButton:hover { background: rgba(59,108,245,35); }")
                button.clicked.connect(lambda checked=False, value=ch: self.copy_char(value))
                row, col = (0, index) if is_usage else divmod(index, 28)
                grid.addWidget(button, row, col)
            box_layout.addWidget(grid_holder, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(box)
        self.rows.addStretch(1)

    def copy_char(self, ch: str) -> None:
        self.main.app.clipboard().setText(ch)
        usage = self.main.settings.setdefault("special_char_usage", {})
        usage[ch] = int(usage.get(ch, 0)) + 1
        config.save_settings(self.main.settings)
        QTimer.singleShot(60, self.refresh)

    def clear_usage(self) -> None:
        if not ask_modern_question(self, "최근 특수문자 초기화", "최근 특수문자 사용 이력을 모두 지울까요?", None, "초기화", "취소"):
            return
        self.main.settings["special_char_usage"] = {}
        config.save_settings(self.main.settings)
        self.refresh()


class MiscTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        self._color_tab = ColorToolsTab(main)
        self._mouse_tab = MouseHighlightTab(main)
        tabs.addTab(self._color_tab, "컬러")
        tabs.addTab(EmojiTab(main), "이모지")
        tabs.addTab(SpecialCharTab(main), "특수문자")
        tabs.addTab(self._mouse_tab, "마우스 하이라이트")
        tabs.addTab(ScreenDrawTab(main), "화면 그리기")
        layout.addWidget(tabs, 1)

    def apply_theme(self) -> None:
        self._color_tab.apply_theme()
        self._mouse_tab.apply_theme()

    def start_screen_draw(self) -> None:
        tab_widget = self.findChild(QTabWidget)
        if tab_widget is None:
            return
        for index in range(tab_widget.count()):
            widget = tab_widget.widget(index)
            if isinstance(widget, ScreenDrawTab):
                tab_widget.setCurrentIndex(index)
                widget.start_overlay()
                return
