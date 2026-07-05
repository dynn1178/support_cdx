from __future__ import annotations

import random
import subprocess
import sys
from datetime import date as py_date, datetime, time as dt_time, timedelta
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QDate, QDateTime, QEasingCurve, QEvent, QMimeData, QPoint, QPropertyAnimation, QRect, QRectF, QSize, QTime, QTimer, Qt
from PyQt6.QtGui import QCursor, QDrag, QTextCharFormat, QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QApplication,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import new_id, now_iso, short_preview
from ui.common import (
    CARD_ACTION_ICON_SIZE,
    CARD_ACTION_ROW_MARGIN_X,
    CARD_ACTION_ROW_MARGIN_Y,
    CARD_ACTION_ROW_SPACING,
    BOTTOM_ACTION_HEIGHT,
    CORNER_CONTROL_HEIGHT,
    CORNER_SEARCH_WIDTH,
    GRID_PANEL_MARGINS,
    PRIORITY_STYLES,
    GridPanel,
    SortControls,
    add_card_actions,
    add_card_status_label,
    add_favorite_badge_to_card,
    apply_manual_reorder,
    apply_modern_dialog_style,
    ask_modern_question,
    bottom_action_bar,
    bump_usage,
    confirm_delete,
    fit_combo_to_contents,
    make_card,
    make_icon_button,
    normalize_todo_groups,
    remove_favorite_badge_from_card,
    set_card_action_widget,
    set_corner_button_policy,
    show_card_status,
    show_modern_info,
    show_topmost_modern_info,
    show_modern_warning,
)
from ui.groups import (
    GROUP_SCOPE_MEMO,
    GroupDialog,
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



from ui.memo_windows import (  # noqa: E402
    MEMO_COLOR_LIST,
    MEMO_COLORS,
    MEMO_INDEX_EMOJIS,
    CornerGrip,
    MemoIndexCard,
    MemoIndexFace,
    StickyMemoDialog,
)
# 하위 호환 재노출 — tab_todo는 tab_memo를 임포트하지 않으므로 순환이 없다.
from ui.tab_todo import ScheduleListTab, TodoListTab, display_datetime  # noqa: E402,F401

MEMO_BOTTOM_ACTION_STYLE = (
    "QPushButton {"
    "background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px;"
    "padding: 6px 12px; color: #1F2433; font-weight: 700;"
    f"min-height: {BOTTOM_ACTION_HEIGHT - 8}px;"
    "}"
    "QPushButton:hover { background: #EEF4FF; border-color: #3B6CF5; }"
    "QPushButton:pressed { background: #F8FAFC; }"
    "QPushButton:disabled { background: #E5E7EB; color: #94A3B8; border: 1px solid #CBD5E1; }"
)


def memo_card_preview(text: str, limit: int = 160, max_lines: int = 2) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    preview = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        preview += " ..."
    if len(preview) <= limit:
        return preview
    return preview[: limit - 1].rstrip() + "..."



class MemoDialog(QDialog):
    def __init__(self, memo: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("메모")
        apply_modern_dialog_style(self)
        self.memo = memo or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._memo_option_rows: list[QWidget] = []
        self.title = QLineEdit(self.memo.get("title", ""))
        self.content = QTextEdit()
        self.content.setPlainText(self.memo.get("content", ""))
        self.pinned = QCheckBox("즐겨찾기")
        self.pinned.setToolTip("체크하면 메모 탭 목록에서 이 메모가 먼저 표시되고 별표가 표시됩니다.")
        self.pinned.setChecked(bool(self.memo.get("favorite", self.memo.get("pinned"))))
        self.always_on_top = QCheckBox("스티커 항상 위")
        self.always_on_top.setChecked(bool(self.memo.get("always_on_top", True)))
        self.open_as_sticker = QCheckBox("스티커로 띄우기")
        self.open_as_sticker.setChecked(False)
        self.background = QComboBox()
        self.background.addItems(list(MEMO_COLORS))
        _is_new = not self.memo.get("id")
        _bg_default = self.memo.get("background") or (random.choice(MEMO_COLOR_LIST) if _is_new else "노랑")
        self.background.setCurrentText(_bg_default if _bg_default in MEMO_COLORS else "노랑")
        form.addRow("제목", self.title)
        form.addRow("내용", self.content)
        form.addRow("배경색", self.background)
        form.addRow(self.open_as_sticker)
        form.addRow(self.pinned)
        form.addRow(self.always_on_top)
        for option in (self.pinned, self.always_on_top):
            label = form.labelForField(option)
            if label is not None:
                label.hide()
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        data = dict(self.memo)
        if not data.get("id"):
            data["id"] = new_id("mm")
            data["created_at"] = now_iso()
            data["sort_order"] = 0
            data["usage_count"] = 0
        data.update(
            {
                "title": self.title.text().strip(),
                "content": self.content.toPlainText(),
                "favorite": self.pinned.isChecked(),
                "pinned": self.pinned.isChecked(),
                "always_on_top": self.always_on_top.isChecked(),
                "background": self.background.currentText(),
                "_open_sticker_after_save": self.open_as_sticker.isChecked(),
                "updated_at": now_iso(),
            }
        )
        return data


class MemoListTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.sticky_windows: dict[str, StickyMemoDialog | MemoIndexCard] = {}
        self._recently_closed_sticker_keys: list[str] = []
        self.group_id = ""
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
        add_btn = QPushButton("+ 메모")
        add_btn.clicked.connect(lambda: self.edit_memo())
        group_btn = QPushButton("+ 그룹 생성")
        group_btn.clicked.connect(self.create_group_clicked)
        expand_btn = QPushButton("모두 펼치기")
        expand_btn.clicked.connect(self.expand_all_stickers)
        collapse_btn = QPushButton("모두 접기")
        collapse_btn.clicked.connect(self.collapse_all_stickers)
        arrange_btn = QPushButton("정렬")
        arrange_btn.clicked.connect(self.arrange_compact_stickers)
        self.expand_btn = expand_btn
        self.collapse_btn = collapse_btn
        self.arrange_btn = arrange_btn
        sticker_toggle_btn = QPushButton("★ 열기/닫기")
        sticker_toggle_btn.clicked.connect(self.toggle_pinned_stickers)
        close_all_btn = QPushButton("열기/닫기")
        close_all_btn.clicked.connect(self.toggle_recent_stickers)
        for button in (expand_btn, collapse_btn, arrange_btn, sticker_toggle_btn, close_all_btn, group_btn, add_btn):
            button.setFixedHeight(30)
            button.setStyleSheet(MEMO_BOTTOM_ACTION_STYLE)
        self.grid = GridPanel(columns=2)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        # 탭(메뉴 줄) 아래에 그룹 경로(브레드크럼) 표시
        self.breadcrumb = make_breadcrumb_label(self.enter_group)
        page_layout.addWidget(self.breadcrumb)
        page_layout.addWidget(self.grid, 1)
        page_layout.addLayout(bottom_action_bar(expand_btn, collapse_btn, arrange_btn, sticker_toggle_btn, close_all_btn, group_btn, add_btn))
        self.tabs.addTab(page, "메모")
        layout.addWidget(self.tabs, 1)
        self._sync_index_action_buttons()

    def _ordered_memos(self, source_items: list[dict] | None = None) -> list[dict]:
        items = source_items if source_items is not None else self.main.data.get("memos", [])
        memos = self.sort_controls.sort_items(items, lambda item: item.get("title") or item.get("content", ""))
        if not self.sort_controls.is_manual():
            memos = sorted(memos, key=lambda item: not self.is_favorite_memo(item))
        return memos

    def _sync_index_action_buttons(self) -> None:
        is_index = self._display_mode() == "index"
        for button in (getattr(self, "expand_btn", None), getattr(self, "collapse_btn", None), getattr(self, "arrange_btn", None)):
            if button is not None:
                button.setEnabled(not is_index)
                button.setFixedHeight(BOTTOM_ACTION_HEIGHT)
                button.setStyleSheet(MEMO_BOTTOM_ACTION_STYLE)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        searching = bool(q)
        data = self.main.data
        self.group_id = valid_group_id(data, GROUP_SCOPE_MEMO, self.group_id)
        source_items = data.get("memos", [])
        memos = self._ordered_memos(source_items)
        self._sync_index_action_buttons()
        offset = 0
        meta: list[tuple[str, object]] = []
        if not searching:
            if self.group_id:
                current = group_by_id(data, self.group_id)
                cards.append(make_back_card(self.go_back_group, 96))
                meta.append(("target", str(current.get("parent_id") or "") if current else ""))
            for group in groups_in(data, GROUP_SCOPE_MEMO, self.group_id):
                cards.append(self._make_memo_group_card(group))
                meta.append(("target", group_id(group)))
            offset = len(cards)
        visible_memos = []
        for memo in memos:
            if q and q not in (memo.get("title", "") + " " + memo.get("content", "")).lower():
                continue
            if not searching and item_group_id(memo) != self.group_id:
                continue
            card = make_card(
                memo.get("title", "(제목 없음)"),
                memo_card_preview(memo.get("content", ""), 160, max_lines=3),
                card_height=96,
                subtitle_max_lines=3,
                dense=True,
                v_center=True,
            )
            self.add_memo_actions(card, memo)
            visible_memos.append(memo)
            cards.append(card)
            meta.append(("item", memo))
        callback = (lambda old, new, off=offset: self.reorder_items(source_items, visible_memos, old - off, new - off)) if self.sort_controls.is_manual() else None
        drop_handler = self._make_drop_handler(meta) if not searching else None
        self.grid.add_cards(cards, on_reorder=callback, on_drop=drop_handler)
        self.refresh_breadcrumb()
        if self._display_mode() == "index":
            self._arrange_index_cards()

    # --- 그룹(폴더) -----------------------------------------------------

    def _make_drop_handler(self, meta: list[tuple[str, object]]):
        """메모 카드를 그룹/뒤로가기 카드 위에 드롭하면 해당 그룹으로 이동."""

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
        update_breadcrumb_label(self.breadcrumb, self.main.data, self.group_id)

    def enter_group(self, gid: str) -> None:
        self.group_id = gid
        self.refresh()

    def go_back_group(self) -> None:
        current = group_by_id(self.main.data, self.group_id)
        self.enter_group(str(current.get("parent_id") or "") if current else "")

    def create_group_clicked(self) -> None:
        dialog = GroupDialog()
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "그룹명을 입력해주세요.")
                continue
            create_group(self.main.data, GROUP_SCOPE_MEMO, self.group_id, value["name"], value["icon"])
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
        if not confirm_delete(self, "선택한 그룹을 삭제할까요?\n그룹 안의 메모와 하위 그룹은 상위 경로로 이동합니다."):
            return
        delete_group(self.main.data, group, [self.main.data.get("memos", [])])
        self.main.save_data()

    def toggle_group_favorite_clicked(self, group: dict, card: QWidget, button) -> None:
        toggle_group_favorite(group, card, button)
        QTimer.singleShot(0, self.main.save_data)

    def move_memo_to_group(self, memo: dict) -> None:
        show_move_to_group_menu(self, self.main.data, GROUP_SCOPE_MEMO, memo, self.main.save_data)

    def _make_memo_group_card(self, group: dict) -> QWidget:
        subtitle = count_group_contents(
            self.main.data, GROUP_SCOPE_MEMO, group_id(group), self.main.data.get("memos", [])
        )
        return make_group_card(
            group,
            subtitle,
            on_open=lambda g=group: self.enter_group(group_id(g)),
            on_favorite=self.toggle_group_favorite_clicked,
            on_edit=self.edit_group,
            on_delete=self.delete_group_clicked,
            card_height=96,
        )

    def is_favorite_memo(self, memo: dict) -> bool:
        return bool(memo.get("favorite", memo.get("pinned")))

    def style_memo_favorite_button(self, button, memo: dict) -> None:
        color = "#F5B301" if self.is_favorite_memo(memo) else "#A3A8B3"
        button.setText("★")
        button.setStyleSheet(
            f'QToolButton#iconButton {{ color: {color}; font-family: "Segoe UI Symbol", "Malgun Gothic"; font-size: 13pt; font-weight: 900; padding: 0 0 2px 0; '
            f"min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }}"
            f"QToolButton#iconButton:hover {{ color: {color}; background: transparent; }}"
        )

    def add_memo_actions(self, card: QWidget, memo: dict) -> None:
        add_card_status_label(card)
        if self.is_favorite_memo(memo):
            add_favorite_badge_to_card(card)
        action_page = QWidget()
        action_page.setObjectName("cardActionBar")
        row = QHBoxLayout(action_page)
        row.setContentsMargins(CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y, CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y)
        row.setSpacing(CARD_ACTION_ROW_SPACING)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        _sz = QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)
        pin = make_icon_button("pin", "즐겨찾기", lambda checked=False, value=memo, c=card: self.toggle_pin(value, c, pin), size=_sz)
        self.style_memo_favorite_button(pin, memo)
        row.addWidget(pin)
        row.addWidget(make_icon_button("sticker", "스티커", lambda checked=False, value=memo: self.show_sticker(value), size=_sz))
        row.addWidget(make_icon_button("📂", "그룹으로 이동", lambda checked=False, value=memo: self.move_memo_to_group(value), size=_sz))
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=memo: self.edit_memo(value), size=_sz))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=memo: self.delete_memo(value), True, size=_sz))
        set_card_action_widget(card, action_page)

    def toggle_pin(self, memo: dict, card: QWidget | None = None, button: QWidget | None = None) -> None:
        memo["favorite"] = not self.is_favorite_memo(memo)
        memo["pinned"] = bool(memo["favorite"])
        if button is not None:
            self.style_memo_favorite_button(button, memo)
        if card is not None:
            if self.is_favorite_memo(memo):
                add_favorite_badge_to_card(card)
            else:
                remove_favorite_badge_from_card(card)
            show_card_status(card, "즐겨찾기 등록!" if self.is_favorite_memo(memo) else "즐겨찾기 해제!")
        self.main.save_data()

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()
        if self._display_mode() == "index":
            self._arrange_index_cards()

    def memo_key(self, memo: dict) -> str:
        return str(memo.get("id") or id(memo))

    def memo_by_key(self, memo_key: str) -> dict | None:
        for memo in self.main.data.get("memos", []):
            if self.memo_key(memo) == memo_key:
                return memo
        return None

    def _display_mode(self) -> str:
        return str(getattr(self.main, "settings", {}).get("sticky_memo_display_mode", "floating") or "floating")

    def show_sticker(self, memo: dict, track_usage: bool = True, raise_window: bool = True, toggle_existing: bool = True) -> None:
        if self._display_mode() == "index":
            self._show_index_card(memo, track_usage=track_usage, raise_window=raise_window, toggle_existing=toggle_existing)
            return
        key = self.memo_key(memo)
        dialog = self.sticky_windows.get(key)
        if dialog is not None and dialog.isVisible():
            if toggle_existing:
                dialog.accept()
                return
            if raise_window:
                dialog.raise_()
                dialog.activateWindow()
            return
        if track_usage:
            bump_usage(memo)
            self.main.save_usage_data()
        dialog = StickyMemoDialog(memo, self.main, self.refresh)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, memo_key=key: self.forget_sticker(memo_key))
        self.sticky_windows[key] = dialog
        dialog.show()
        if raise_window:
            dialog.raise_()

    def _show_index_card(self, memo: dict, track_usage: bool = True, raise_window: bool = True, toggle_existing: bool = True) -> None:
        key = self.memo_key(memo)
        card = self.sticky_windows.get(key)
        if card is not None and card.isVisible():
            if toggle_existing:
                card.accept()
                return
            if raise_window:
                card.raise_()
            return
        if track_usage:
            bump_usage(memo)
            self.main.save_usage_data()
        card = MemoIndexCard(memo, self.main, self.refresh)
        card.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        card.destroyed.connect(lambda _obj=None, memo_key=key: self.forget_sticker(memo_key))
        self.sticky_windows[key] = card
        # 초기 배치: 지정 모니터 지정 면의 Y 슬롯에 놓기
        settings = getattr(self.main, "settings", {})
        screens = QApplication.screens()
        mon = max(0, min(len(screens) - 1, int(settings.get("sticky_memo_arrange_monitor", 1) or 1) - 1))
        screen = screens[mon] if screens else QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            side = str(settings.get("sticky_memo_index_side", "right") or "right")
            start_pct = int(settings.get("sticky_memo_index_start_y", 0) or 0)
            start_y = area.top() + int(area.height() * start_pct / 100)
            open_cards = [d for k2, d in self.sticky_windows.items() if d is not card and isinstance(d, MemoIndexCard) and d.isVisible()]
            slot_y = start_y + len(open_cards) * (MemoIndexCard.COMPACT_H + MemoIndexCard.COMPACT_GAP)
            card_x = area.right() - MemoIndexCard.COMPACT_W if side == "right" else area.left()
            card.set_position(card_x, slot_y)
        card.show()
        if raise_window:
            card.raise_()
        self._arrange_index_cards()

    def forget_sticker(self, memo_key: str) -> None:
        self.sticky_windows.pop(memo_key, None)

    def visible_stickers(self) -> list:
        return [dialog for dialog in self.sticky_windows.values() if dialog.isVisible()]

    def expand_all_stickers(self) -> None:
        for dialog in self.visible_stickers():
            if isinstance(dialog, StickyMemoDialog) and dialog.compact:
                dialog.compact = False
                dialog.apply_compact_state(save=False)
                dialog.raise_()
                dialog.persist()

    def collapse_all_stickers(self) -> None:
        for dialog in self.visible_stickers():
            if isinstance(dialog, StickyMemoDialog) and not dialog.compact:
                dialog.compact = True
                dialog.apply_compact_state(save=False)
                dialog.persist()

    def toggle_recent_stickers(self) -> None:
        visible = self.visible_stickers()
        if visible:
            self._recently_closed_sticker_keys = [
                key for key, dialog in self.sticky_windows.items()
                if dialog in visible and dialog.isVisible()
            ]
            for dialog in visible:
                dialog.accept()
            return
        if not self._recently_closed_sticker_keys:
            return
        keys = list(self._recently_closed_sticker_keys)
        self._recently_closed_sticker_keys = []
        for memo_key in keys:
            memo = self.memo_by_key(memo_key)
            if memo is not None:
                self.show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def close_all_stickers(self) -> None:
        self._recently_closed_sticker_keys = []
        for dialog in self.visible_stickers():
            dialog.accept()

    def reopen_stickers_for_mode(self) -> None:
        visible_keys = [
            key for key, dialog in list(self.sticky_windows.items())
            if dialog.isVisible()
        ]
        if not visible_keys:
            return
        for dialog in list(self.sticky_windows.values()):
            if dialog.isVisible():
                dialog.accept()
        QApplication.processEvents()
        for key in visible_keys:
            memo = self.memo_by_key(key)
            if memo is not None:
                self.show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def toggle_pinned_stickers(self) -> None:
        memos = self.main.data.get("memos", [])
        pinned = [memo for memo in memos if self.is_favorite_memo(memo)]
        if not pinned:
            return
        open_keys = {key for key, dlg in self.sticky_windows.items() if dlg.isVisible()}
        any_open = any(self.memo_key(m) in open_keys for m in pinned)
        if any_open:
            for memo in pinned:
                key = self.memo_key(memo)
                dialog = self.sticky_windows.get(key)
                if dialog is not None and dialog.isVisible():
                    dialog.accept()
        else:
            for memo in pinned:
                self.show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def arrange_compact_stickers(self) -> None:
        if self._display_mode() == "index":
            self._arrange_index_cards()
            return
        stickers = [d for d in self.visible_stickers() if isinstance(d, StickyMemoDialog)]
        if not stickers:
            return
        settings = getattr(self.main, "settings", {})
        screens = QApplication.screens()
        monitor_index = int(settings.get("sticky_memo_arrange_monitor", 1) or 1)
        screen = screens[max(0, min(len(screens) - 1, monitor_index - 1))] if screens else None
        screen = screen or QApplication.screenAt(stickers[0].pos()) or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        margin = 18
        gap = 0
        corner = str(settings.get("sticky_memo_arrange_corner", "top_right") or "top_right")
        top_anchor = corner in {"top_right", "top_left"}
        right_anchor = corner in {"top_right", "bottom_right"}
        y = area.top() + margin if top_anchor else area.bottom() - margin + 1
        for dialog in stickers:
            x = area.right() - dialog.width() - margin + 1 if right_anchor else area.left() + margin
            if top_anchor:
                if y + dialog.height() > area.bottom() - margin + 1:
                    y = area.top() + margin
                place_y = y
            else:
                if y - dialog.height() < area.top() + margin:
                    y = area.bottom() - margin + 1
                place_y = y - dialog.height()
            dialog.move(x, place_y)
            y = dialog.geometry().bottom() + 1 + gap if top_anchor else dialog.geometry().top() - gap
            dialog.raise_()
            dialog.persist()

    def _arrange_index_cards(self) -> None:
        cards = [d for d in self.visible_stickers() if isinstance(d, MemoIndexCard)]
        if not cards:
            return
        order = {self.memo_key(memo): idx for idx, memo in enumerate(self._ordered_memos())}
        cards.sort(key=lambda card: order.get(self.memo_key(card.memo), len(order)))
        settings = getattr(self.main, "settings", {})
        screens = QApplication.screens()
        mon = max(0, min(len(screens) - 1, int(settings.get("sticky_memo_arrange_monitor", 1) or 1) - 1))
        screen = screens[mon] if screens else None
        screen = screen or QApplication.screenAt(cards[0].pos()) or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        side = str(settings.get("sticky_memo_index_side", "right") or "right")
        start_pct = int(settings.get("sticky_memo_index_start_y", 0) or 0)
        start_y = area.top() + int(area.height() * start_pct / 100)
        card_x = area.right() - MemoIndexCard.COMPACT_W if side == "right" else area.left()
        y = start_y
        for card in cards:
            if hasattr(card, "reset_compact_geometry"):
                card.reset_compact_geometry()
            card.set_position(card_x, y)
            y += MemoIndexCard.COMPACT_H + MemoIndexCard.COMPACT_GAP
            card.raise_()
        if self.main is not None:
            config.save_template(self.main.template_index, self.main.data)

    def commit_index_card_order(self, dragged: "MemoIndexCard") -> None:
        """드래그로 이동한 카드의 세로 위치를 기준으로 인덱스 순서를 확정한다."""
        cards = [d for d in self.visible_stickers() if isinstance(d, MemoIndexCard)]
        if not cards:
            return
        if len(cards) == 1:
            self._arrange_index_cards()
            return

        def slot_key(card: MemoIndexCard) -> float:
            # 드래그된 카드는 현재 창 위치(핸들이 가리키는 곳), 나머지는 고정 슬롯 기준.
            if card is dragged or card._base_y is None:
                return card.geometry().top() + MemoIndexCard.COMPACT_H / 2
            return card._base_y + MemoIndexCard.COMPACT_H / 2

        cards.sort(key=slot_key)
        # 열린 카드들의 새 순서를 화면에 보이던 전체 순서에 반영한다.
        # 닫혀 있는 메모의 상대 위치는 그대로 둔다.
        ordered = self._ordered_memos()
        open_keys = {self.memo_key(card.memo) for card in cards}
        positions = [index for index, memo in enumerate(ordered) if self.memo_key(memo) in open_keys]
        for position, card in zip(positions, cards):
            ordered[position] = card.memo
        for index, memo in enumerate(ordered):
            memo["sort_order"] = index
        # 드래그 결과가 정렬 기준에 덮이지 않도록 수동 정렬로 전환한다.
        mode = self.sort_controls.mode
        manual_index = mode.findData("manual")
        if manual_index >= 0 and mode.currentIndex() != manual_index:
            mode.blockSignals(True)
            mode.setCurrentIndex(manual_index)
            mode.blockSignals(False)
            self.sort_controls.update_order_enabled()
        self.main.save_data()  # refresh_all_tabs → refresh → _arrange_index_cards

    def handle_screen_layout_changed(self) -> None:
        """모니터 연결/배율 변경 후 열려 있는 메모 창을 새 화면 기준으로 복구한다."""
        if self._display_mode() == "index":
            # 이동 왕복(WM_MOVE)만으로는 배율 변경 후 프레임리스 카드의 백킹스토어가
            # 이전 DPI로 렌더링된 채 남는 환경이 있다. 표시 모드 전환과 동일하게
            # 카드를 닫고 다시 만들어 새 배율 기준 네이티브 윈도우로 재생성한다.
            self.reopen_stickers_for_mode()
            self._arrange_index_cards()
        else:
            self.arrange_compact_stickers()

    def _sync_open_sticker(self, memo: dict) -> None:
        dialog = self.sticky_windows.get(self.memo_key(memo))
        if dialog is not None and dialog.isVisible() and hasattr(dialog, "reload_from_memo"):
            dialog.reload_from_memo()

    def edit_memo(self, memo: dict | None = None) -> None:
        dialog = MemoDialog(memo)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("title"):
                show_modern_warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            open_sticker = bool(value.pop("_open_sticker_after_save", False))
            items = self.main.data.setdefault("memos", [])
            if memo in items:
                memo.clear()
                memo.update(value)
                saved_memo = memo
            else:
                value["sort_order"] = len(items)
                # 새 메모는 현재 열려 있는 그룹(폴더)에 등록한다.
                value.setdefault("group_id", self.group_id)
                items.append(value)
                saved_memo = value
            self.main.save_data()
            self._sync_open_sticker(saved_memo)
            self.refresh()
            if open_sticker:
                self.show_sticker(saved_memo, track_usage=False, raise_window=True, toggle_existing=False)
            return

    def delete_memo(self, memo: dict) -> None:
        if not confirm_delete(self, "선택한 메모를 삭제할까요?"):
            return
        key = self.memo_key(memo)
        dialog = self.sticky_windows.get(key)
        if dialog is not None and dialog.isVisible():
            dialog.accept()
        self.sticky_windows.pop(key, None)
        self.main.data.get("memos", []).remove(memo)
        self.main.save_data()
        self.refresh()


