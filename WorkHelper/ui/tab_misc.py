from __future__ import annotations

import colorsys

from PyQt6.QtCore import QPoint, QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
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
from ui.common import ask_modern_question


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
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.hex_value = QLineEdit("#3B6CF5")
        self.hex_value.editingFinished.connect(self.apply_hex)
        self.rgb_fields = [self.spin(0, 255) for _ in range(3)]
        self.hsl_fields = [self.spin(0, 360), self.spin(0, 100), self.spin(0, 100)]
        for field in self.rgb_fields:
            field.valueChanged.connect(self.apply_rgb)
        for field in self.hsl_fields:
            field.valueChanged.connect(self.apply_hsl)
        self.rgb_text = QLineEdit()
        self.rgb_text.setReadOnly(True)
        self.hsl_text = QLineEdit()
        self.hsl_text.setReadOnly(True)
        self.swatch = QLabel("")
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

        row = QHBoxLayout()
        row.addStretch(1)
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
            row.addWidget(button)
        layout.addLayout(row)
        self.refresh()
        self.set_color("#3B6CF5", add_history=False)

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
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.virtualGeometry())
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
        layout = QFormLayout(self)
        self.color = QLineEdit(main.settings.get("mouse_highlight_color", "#FFDD33"))
        self.shape = QComboBox()
        self.shape.addItems(["원", "채워진 원", "사각형", "채워진 사각형", "십자"])
        self.shape.setCurrentText(main.settings.get("mouse_highlight_shape", "원"))
        self.size = QSlider(Qt.Orientation.Horizontal)
        self.size.setRange(0, 100)
        self.size.setValue(int(main.settings.get("mouse_highlight_size", 50)))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(int(main.settings.get("mouse_highlight_opacity", 50)))
        self.shape.currentTextChanged.connect(self.apply_live)
        self.size.valueChanged.connect(self.apply_live)
        self.opacity.valueChanged.connect(self.apply_live)
        row = QHBoxLayout()
        on = QPushButton("켜기")
        off = QPushButton("끄기")
        pick = QPushButton("색 선택")
        on.clicked.connect(self.enable)
        off.clicked.connect(self.disable)
        pick.clicked.connect(self.pick)
        for widget in [on, off, pick]:
            row.addWidget(widget)
        row.addStretch(1)
        layout.addRow("색상", self.color)
        layout.addRow("모양", self.shape)
        layout.addRow("크기", self.size)
        layout.addRow("투명도", self.opacity)
        layout.addRow("", row)

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
        "특수문자": "★ ☆ ♥ ♡ ◆ ◇ ● ○ ■ □ ▲ △ ▼ ▽ → ← ↑ ↓ ↔ ↕ ✓ ✔ ✕ ✖ ✚ ✦ ✧ ※ 〒 ☎ ☑ ☐ ⚠ ⚡ ♠ ♣ ♦ ♪ ♫".split(),
    }

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self.rows = QVBoxLayout(container)
        self.rows.setContentsMargins(6, 6, 6, 6)
        self.rows.setSpacing(8)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        clear = QPushButton("최근 이모지 초기화")
        clear.clicked.connect(self.clear_usage)
        bottom.addWidget(clear)
        layout.addLayout(bottom)
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
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self.rows = QVBoxLayout(container)
        self.rows.setContentsMargins(6, 6, 6, 6)
        self.rows.setSpacing(8)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        clear = QPushButton("최근 특수문자 초기화")
        clear.clicked.connect(self.clear_usage)
        bottom.addWidget(clear)
        layout.addLayout(bottom)
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
        self.inner_tabs = QTabWidget()
        self.inner_tabs.addTab(ColorToolsTab(main), "컬러")
        self.inner_tabs.addTab(EmojiTab(main), "이모지")
        self.inner_tabs.addTab(SpecialCharTab(main), "특수문자")
        self.inner_tabs.addTab(MouseHighlightTab(main), "마우스 하이라이트")
        layout.addWidget(self.inner_tabs, 1)

    def trigger_screen_draw(self) -> None:
        self.inner_tabs.setCurrentIndex(0)
        color_tab = self.inner_tabs.widget(0)
        if isinstance(color_tab, ColorToolsTab):
            color_tab.pick_screen_color()
