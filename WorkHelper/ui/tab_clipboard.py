from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QAbstractNativeEventFilter, QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QImage, QKeyEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget

from app import config
from app.clipboard_watcher import ClipboardWatcher
from app.hotkey_manager import USER32, WM_HOTKEY
from app.utils import new_id, now_iso, short_preview
from ui.common import (
    CARD_ACTION_ICON_SIZE,
    CARD_ACTION_ROW_MARGIN_X,
    CARD_ACTION_ROW_MARGIN_Y,
    CARD_ACTION_ROW_SPACING,
    CARD_CONTENT_TOP_MARGIN,
    GridPanel,
    SortControls,
    add_favorite_badge_to_card,
    apply_manual_reorder,
    ask_modern_question,
    bottom_action_bar,
    bump_usage,
    make_card,
    make_icon_button,
    remove_favorite_badge_from_card,
    set_card_action_widget,
)


IMAGE_THUMB_SIZE = 52
MINI_IMAGE_THUMB_SIZE = 28
MINI_COPY_BUTTON_WIDTH = 64
MINI_COPY_BUTTON_HEIGHT = 26


def is_image_item(item: dict) -> bool:
    return item.get("type") == "image"


def display_copied_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except Exception:
        return value.replace("T", " ")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def image_path(item: dict) -> Path:
    raw = item.get("path", "")
    path = Path(raw)
    return path if path.is_absolute() else config.BASE_DIR / raw


def stable_image_signature(image: QImage) -> str:
    normalized = image.convertToFormat(QImage.Format.Format_RGBA8888)
    bits = normalized.constBits()
    bits.setsize(normalized.sizeInBytes())
    digest = hashlib.sha1(bytes(bits)).hexdigest()
    return f"{normalized.width()}x{normalized.height()}:{digest}"


class PopupNumberFilter(QAbstractNativeEventFilter):
    def __init__(self, popup: "ClipboardMiniPopup") -> None:
        super().__init__()
        self.popup = popup

    def nativeEventFilter(self, event_type, message):
        try:
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and 5201 <= int(msg.wParam) <= 5205:
                self.popup.copy_by_number(int(msg.wParam) - 5200)
                return True, 0
        except Exception:
            pass
        return False, 0


class ClipboardMiniPopup(QDialog):
    number_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget, items: list[dict]) -> None:
        super().__init__(None)
        self.parent_tab = parent
        self.items = items
        self.number_filter = PopupNumberFilter(self)
        self.registered_number_hotkeys: list[int] = []
        self.previous_hwnd = 0
        self._closing = False
        self.setWindowTitle("클립보드")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(430)
        self.setStyleSheet(
            """
            QPushButton#miniCopyButton {
                padding: 0;
                min-width: 54px; max-width: 54px;
                min-height: 24px; max-height: 24px;
            }
            """
        )
        self.number_selected.connect(self.copy_by_number)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        rows = QVBoxLayout(container)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(3)

        if not self.items:
            rows.addWidget(self._empty_row())
        else:
            for index, item in enumerate(self.items, start=1):
                rows.addWidget(self._item_row(index, item))
        rows.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        footer = QHBoxLayout()
        hint = QLabel("1~5번 단축키를 누르면 바로 복사됩니다.")
        hint.setObjectName("mutedText")
        close_btn = QPushButton("닫기")
        close_btn.setFixedWidth(72)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(hint, 1)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        visible_rows = min(max(len(self.items), 1), 5)
        self.setFixedHeight(58 + visible_rows * 36)
        self.start_number_hotkeys()
        QTimer.singleShot(0, self.activate_popup)
        QTimer.singleShot(80, self.force_activate)
        QTimer.singleShot(180, self.force_activate)

    def activate_popup(self) -> None:
        try:
            self.previous_hwnd = int(USER32.GetForegroundWindow())
        except Exception:
            self.previous_hwnd = 0
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(cursor.x() + 12, area.left()), area.right() - self.width())
            y = min(max(cursor.y() + 12, area.top()), area.bottom() - self.height())
            self.move(x, y)
        self.force_activate()

    def force_activate(self) -> None:
        if self._closing or not self.isVisible():
            return
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        try:
            hwnd = int(self.winId())
            USER32.ShowWindow(hwnd, 5)
            USER32.BringWindowToTop(hwnd)
            USER32.SetForegroundWindow(hwnd)
            USER32.SetActiveWindow(hwnd)
        except Exception:
            pass

    def start_number_hotkeys(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.installNativeEventFilter(self.number_filter)
        hwnd = int(self.winId())
        for number in range(1, 6):
            hotkey_id = 5200 + number
            if USER32.RegisterHotKey(hwnd, hotkey_id, 0, ord(str(number))):
                self.registered_number_hotkeys.append(hotkey_id)

    def stop_number_hotkeys(self) -> None:
        hwnd = int(self.winId())
        for hotkey_id in self.registered_number_hotkeys:
            try:
                USER32.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass
        self.registered_number_hotkeys.clear()
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeNativeEventFilter(self.number_filter)
            except Exception:
                pass

    def _empty_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 4, 6, 4)
        label = QLabel("클립보드 이력이 없습니다.")
        layout.addWidget(label)
        return row

    def _item_row(self, index: int, item: dict) -> QWidget:
        row = QWidget()
        row.setObjectName("card")
        row.setFixedHeight(33)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        number = QLabel(str(index) if index <= 5 else "")
        number.setObjectName("kbd")
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setFixedWidth(24)
        if is_image_item(item):
            thumb = QLabel()
            thumb.setFixedSize(MINI_IMAGE_THUMB_SIZE, MINI_IMAGE_THUMB_SIZE)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(image_path(item)))
            if not pixmap.isNull():
                thumb.setPixmap(pixmap.scaled(MINI_IMAGE_THUMB_SIZE, MINI_IMAGE_THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                thumb.setText("이미지")
            text = QLabel(display_copied_at(item.get("copied_at", "")))
            text.setToolTip(display_copied_at(item.get("copied_at", "")))
        else:
            text = QLabel(short_preview(item.get("text", ""), 70))
            text.setToolTip(item.get("text", ""))
        text.setWordWrap(False)
        text.setMinimumWidth(0)
        text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        copy_btn = QPushButton("복사")
        copy_btn.setObjectName("miniCopyButton")
        copy_btn.setFixedSize(54, 24)
        copy_btn.clicked.connect(lambda checked=False, value=item: self.copy_and_close(value))

        layout.addWidget(number)
        if is_image_item(item):
            layout.addWidget(thumb)
        layout.addWidget(text, 1)
        layout.addWidget(copy_btn)
        return row

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        text = event.text()
        if text in {"1", "2", "3", "4", "5"}:
            self.copy_by_number(int(text))
            return
        super().keyPressEvent(event)

    def copy_by_number(self, number: int) -> None:
        if self._closing:
            return
        index = number - 1
        if 0 <= index < min(len(self.items), 5):
            self.copy_and_close(self.items[index])

    def copy_and_close(self, item: dict) -> None:
        if self._closing:
            return
        self._closing = True
        self.accept()
        if is_image_item(item):
            copy_to_clipboard(item)
        else:
            self.parent_tab.main.paste_text(item.get("text", ""))

    def done(self, result: int) -> None:
        self.stop_number_hotkeys()
        super().done(result)
        self.restore_previous_window()

    def restore_previous_window(self) -> None:
        if not self.previous_hwnd:
            return
        try:
            USER32.SetForegroundWindow(self.previous_hwnd)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        self.stop_number_hotkeys()
        super().closeEvent(event)


class ClipboardTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.history = config.load_clipboard_history()
        self._mini_popup: ClipboardMiniPopup | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(120)
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
        clear_btn = QPushButton("클립보드 초기화")
        clear_btn.clicked.connect(self.clear_history)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.list, 1)
        page_layout.addLayout(bottom_action_bar(clear_btn))
        self.tabs.addTab(page, "클립보드")
        layout.addWidget(self.tabs, 1)
        self.watcher = ClipboardWatcher()
        self.watcher.new_item.connect(self.add_history)
        self.watcher.start()
        self.last_image_signature = ""
        self.ignore_next_image = False
        self.image_timer = QTimer(self)
        self.image_timer.timeout.connect(self.check_image_clipboard)
        self.image_timer.start(700)

    def stop(self) -> None:
        self.watcher.stop()
        self.watcher.wait(1000)
        self.image_timer.stop()

    def add_history(self, text: str) -> None:
        items = self.history.setdefault("history", [])
        if items and items[0].get("text") == text:
            return
        items.insert(
            0,
            {
                "id": new_id("cb"),
                "type": "text",
                "text": text,
                "copied_at": now_iso(),
                "created_at": now_iso(),
                "sort_order": len(items),
                "usage_count": 0,
                "pinned": False,
            },
        )
        limit = int(self.main.data.get("settings", {}).get("clipboard_history_limit", 50))
        pinned = [item for item in items if item.get("pinned")]
        unpinned = [item for item in items if not item.get("pinned")][: max(0, limit - len(pinned))]
        self.history["history"] = pinned + unpinned
        config.save_clipboard_history(self.history)
        self.refresh()

    def check_image_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if not mime or not mime.hasImage():
            return
        if self.ignore_next_image:
            self.ignore_next_image = False
            return
        image = clipboard.image()
        if image.isNull():
            return
        signature = stable_image_signature(image)
        if signature == self.last_image_signature:
            return
        self.last_image_signature = signature
        if self.history.get("history") and self.history["history"][0].get("image_signature") == signature:
            return
        self.add_image_history(image, signature)

    def add_image_history(self, image: QImage, signature: str) -> None:
        items = self.history.setdefault("history", [])
        item_id = new_id("cbimg")
        config.CLIPBOARD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        path = config.CLIPBOARD_IMAGE_DIR / f"{item_id}.png"
        if not image.save(str(path), "PNG"):
            return
        copied_at = now_iso()
        items.insert(
            0,
            {
                "id": item_id,
                "type": "image",
                "path": str(path),
                "copied_at": copied_at,
                "created_at": copied_at,
                "sort_order": len(items),
                "usage_count": 0,
                "pinned": False,
                "image_signature": signature,
                "width": image.width(),
                "height": image.height(),
            },
        )
        self.trim_history()
        config.save_clipboard_history(self.history)
        self.refresh()

    def trim_history(self) -> None:
        items = self.history.setdefault("history", [])
        limit = int(self.main.data.get("settings", {}).get("clipboard_history_limit", 50))
        pinned = [item for item in items if item.get("pinned")]
        unpinned = [item for item in items if not item.get("pinned")][: max(0, limit - len(pinned))]
        kept = pinned + unpinned
        kept_ids = {item.get("id") for item in kept}
        for item in items:
            if item.get("id") in kept_ids or not is_image_item(item):
                continue
            try:
                image_path(item).unlink(missing_ok=True)
            except Exception:
                pass
        self.history["history"] = kept

    def refresh(self) -> None:
        cards = []
        query = self.search.text().strip().lower()
        source_items = self.history.get("history", [])
        items = self.sort_controls.sort_items(source_items, lambda value: value.get("text") or value.get("copied_at", ""))
        if not self.sort_controls.is_manual():
            items = sorted(items, key=lambda item: not item.get("pinned"))
        for item in items:
            searchable = item.get("text", "") if not is_image_item(item) else f"이미지 {display_copied_at(item.get('copied_at', ''))}"
            if query and query not in searchable.lower():
                continue
            if is_image_item(item):
                card = self.make_image_card(item)
            else:
                text = item.get("text", "")
                card = make_card(text, "", word_wrap=True, title_max_lines=2, title_bold=False, title_line_height=20, card_size="a")
            if item.get("pinned"):
                if is_image_item(item):
                    self.add_image_pin_badge(card)
                else:
                    add_favorite_badge_to_card(card)
            self.add_card_actions(card, item)
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, items, old, new)) if self.sort_controls.is_manual() else None
        self.list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        config.save_clipboard_history(self.history)
        self.refresh()

    def style_pin_button(self, button, pinned: bool) -> None:
        color = "#F5B301" if pinned else "#A3A8B3"
        button.setText("★")
        button.setStyleSheet(
            f'QToolButton#iconButton {{ color: {color}; font-family: "Segoe UI Symbol", "Malgun Gothic"; '
            "font-size: 13pt; font-weight: 900; padding: 0 0 2px 0; "
            "min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }"
            f"QToolButton#iconButton:hover {{ color: {color}; background: transparent; }}"
        )

    def add_card_actions(self, card: QWidget, item: dict) -> None:
        action_page = QWidget()
        row = QHBoxLayout(action_page)
        row.setContentsMargins(CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y, CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y)
        row.setSpacing(CARD_ACTION_ROW_SPACING)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        _sz = QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)
        row.addWidget(make_icon_button("copy", "복사", lambda checked=False, value=item: self.copy_item(value), size=_sz))
        pin_btn = make_icon_button("pin", "고정/해제", lambda checked=False, value=item, c=card: self.toggle_pin(value, c, pin_btn), size=_sz)
        self.style_pin_button(pin_btn, bool(item.get("pinned")))
        row.addWidget(pin_btn)
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_item(value), True, size=_sz))
        set_card_action_widget(card, action_page)

    def copy_item(self, item: dict) -> None:
        bump_usage(item)
        if is_image_item(item):
            self.ignore_next_image = True
        copy_to_clipboard(item)
        config.save_clipboard_history(self.history)
        self.refresh()

    def toggle_pin(self, item: dict, card: QWidget | None = None, button=None) -> None:
        item["pinned"] = not item.get("pinned")
        if button is not None:
            self.style_pin_button(button, bool(item.get("pinned")))
        if card is not None:
            if item.get("pinned"):
                if is_image_item(item):
                    self.add_image_pin_badge(card)
                else:
                    add_favorite_badge_to_card(card)
            else:
                if is_image_item(item):
                    self.remove_image_pin_badge(card)
                else:
                    remove_favorite_badge_from_card(card)
        config.save_clipboard_history(self.history)

    def delete_item(self, item: dict) -> None:
        self.history.get("history", []).remove(item)
        if is_image_item(item):
            try:
                image_path(item).unlink(missing_ok=True)
            except Exception:
                pass
        config.save_clipboard_history(self.history)
        self.refresh()

    def clear_history(self) -> None:
        items = list(self.history.get("history", []))
        if not items:
            return
        if not ask_modern_question(self, "클립보드 초기화", "저장된 클립보드 이력을 모두 삭제할까요?", yes_text="삭제", no_text="취소"):
            return
        for item in items:
            if is_image_item(item):
                try:
                    image_path(item).unlink(missing_ok=True)
                except Exception:
                    pass
        self.history["history"] = []
        config.save_clipboard_history(self.history)
        self.refresh()

    def cleanup_expired_images(self, days: int = 7) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        kept = []
        removed = 0
        for item in self.history.get("history", []):
            if not is_image_item(item):
                kept.append(item)
                continue
            raw_date = item.get("copied_at") or item.get("created_at") or ""
            try:
                copied_at = datetime.fromisoformat(raw_date)
            except Exception:
                copied_at = datetime.fromtimestamp(image_path(item).stat().st_mtime) if image_path(item).exists() else datetime.now()
            if copied_at >= cutoff:
                kept.append(item)
                continue
            try:
                image_path(item).unlink(missing_ok=True)
            except Exception:
                pass
            removed += 1
        if removed:
            self.history["history"] = kept
            config.save_clipboard_history(self.history)
        referenced = {image_path(item).resolve() for item in kept if is_image_item(item)}
        if config.CLIPBOARD_IMAGE_DIR.exists():
            for path in config.CLIPBOARD_IMAGE_DIR.glob("*.png"):
                try:
                    if path.resolve() not in referenced and datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                        path.unlink(missing_ok=True)
                        removed += 1
                except Exception:
                    pass
        return removed

    def show_mini_popup(self) -> None:
        if self._mini_popup is not None and self._mini_popup.isVisible():
            self._mini_popup.force_activate()
            return
        limit = int(self.main.data.get("settings", {}).get("clipboard_history_limit", 50))
        popup = ClipboardMiniPopup(self, self.history.get("history", [])[:limit])
        self._mini_popup = popup
        popup.finished.connect(lambda _result, dialog=popup: self.clear_mini_popup(dialog))
        popup.exec()

    def clear_mini_popup(self, dialog: ClipboardMiniPopup) -> None:
        if self._mini_popup is dialog:
            self._mini_popup = None

    def make_image_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        card.setFixedHeight(72)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, CARD_CONTENT_TOP_MARGIN, 10, 8)
        layout.setSpacing(8)
        preview = QLabel()
        preview.setFixedSize(IMAGE_THUMB_SIZE, IMAGE_THUMB_SIZE)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(image_path(item)))
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(IMAGE_THUMB_SIZE, IMAGE_THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            preview.setText("이미지")
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)
        title = QLabel("이미지")
        title.setObjectName("cardTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        time_label = QLabel(display_copied_at(item.get("copied_at", "")))
        time_label.setObjectName("cardSubtitle")
        text_col.addLayout(title_row)
        text_col.addWidget(time_label)
        text_col.addStretch(1)
        card._image_title_row = title_row
        layout.addWidget(preview)
        layout.addLayout(text_col, 1)
        return card

    def add_image_pin_badge(self, card: QWidget) -> None:
        row = getattr(card, "_image_title_row", None)
        if row is None:
            return
        self.remove_image_pin_badge(card)
        badge = QLabel("★")
        badge.setObjectName("cardFavoriteBadge")
        badge.setFixedSize(16, 18)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            'QLabel#cardFavoriteBadge { color: #F5B301; background: transparent; border: 0; '
            'font-family: "Segoe UI Symbol", "Malgun Gothic"; font-size: 11pt; font-weight: 900; padding: 0 0 1px 0; }'
        )
        row.insertWidget(max(0, row.count() - 1), badge)
        card._image_pin_badge = badge

    def remove_image_pin_badge(self, card: QWidget) -> None:
        badge = getattr(card, "_image_pin_badge", None)
        if badge is None:
            return
        try:
            badge.hide()
            badge.setParent(None)
            badge.deleteLater()
        except RuntimeError:
            pass
        card._image_pin_badge = None


def copy_to_clipboard(item: dict) -> None:
    clipboard = QApplication.clipboard()
    if is_image_item(item):
        image = QImage(str(image_path(item)))
        if not image.isNull():
            clipboard.setImage(image)
        return
    clipboard.setText(item.get("text", ""))
