from __future__ import annotations

"""바로가기/메모/컨닝페이퍼 공용 그룹(폴더) 기능.

- 그룹은 템플릿 데이터의 data["groups"] 리스트에 저장한다.
  {id, scope, parent_id, name, icon, favorite, created_at, sort_order}
- 각 항목(런처/메모/이미지)은 "group_id" 필드로 소속 그룹을 가리킨다.
  ""(빈 값)은 최상위를 뜻한다. 그룹 안에 그룹을 만들어 상/하위 폴더처럼
  중첩할 수 있다.
"""

from html import escape
from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.utils import new_id, now_iso
from ui.common import (
    CARD_ACTION_ICON_SIZE,
    add_favorite_badge_to_card,
    apply_modern_dialog_style,
    make_card,
    make_icon_button,
    remove_favorite_badge_from_card,
    set_card_action_widget,
)

GROUP_SCOPE_SITE = "launcher_site"
GROUP_SCOPE_FILE = "launcher_file"
GROUP_SCOPE_MEMO = "memo"
GROUP_SCOPE_CHEAT = "cheat"

GROUP_ICON_EMOJIS = [
    "📁", "📂", "🗂️", "⭐", "💼", "🏠", "🏢", "🛠️", "⚙️", "🔖",
    "🌐", "🔗", "📄", "📝", "🗒️", "🧾", "📊", "📈", "💡", "🎯",
    "🎨", "🎵", "🎮", "☕", "🛒", "💳", "🔒", "🔑", "❤️", "🔥",
]
DEFAULT_GROUP_ICON = "📁"


# ---------------------------------------------------------------------------
# 데이터 헬퍼
# ---------------------------------------------------------------------------


def data_groups(data: dict) -> list[dict]:
    groups = data.setdefault("groups", [])
    return groups if isinstance(groups, list) else []


def item_group_id(item: dict) -> str:
    return str(item.get("group_id") or "")


def group_id(group: dict) -> str:
    return str(group.get("id") or "")


def group_icon(group: dict) -> str:
    return str(group.get("icon") or "").strip() or DEFAULT_GROUP_ICON


def group_by_id(data: dict, gid: str) -> dict | None:
    for group in data_groups(data):
        if group_id(group) == gid:
            return group
    return None


def groups_in(data: dict, scope: str, parent_id: str = "") -> list[dict]:
    """scope의 parent_id 바로 아래 그룹 목록 (즐겨찾기 → 등록순)."""
    result = [
        group
        for group in data_groups(data)
        if group.get("scope") == scope and str(group.get("parent_id") or "") == parent_id
    ]
    result.sort(key=lambda g: (not bool(g.get("favorite")), int(g.get("sort_order", 0) or 0)))
    return result


def items_in_group(items: list[dict], gid: str) -> list[dict]:
    return [item for item in items if item_group_id(item) == gid]


def group_path(data: dict, gid: str) -> list[dict]:
    """최상위 → 현재 그룹까지의 체인. 잘못된 참조는 그 지점에서 끊는다."""
    chain: list[dict] = []
    seen: set[str] = set()
    current = group_by_id(data, gid)
    while current is not None and group_id(current) not in seen:
        seen.add(group_id(current))
        chain.append(current)
        current = group_by_id(data, str(current.get("parent_id") or ""))
    chain.reverse()
    return chain


def group_path_text(data: dict, gid: str) -> str:
    chain = group_path(data, gid)
    if not chain:
        return ""
    return " › ".join(f"{group_icon(g)} {g.get('name', '')}" for g in chain)


def valid_group_id(data: dict, scope: str, gid: str) -> str:
    """저장된 group_id가 삭제된 그룹을 가리키면 최상위로 되돌린다."""
    if not gid:
        return ""
    group = group_by_id(data, gid)
    return gid if group is not None and group.get("scope") == scope else ""


def create_group(data: dict, scope: str, parent_id: str, name: str, icon: str) -> dict:
    group = {
        "id": new_id("grp"),
        "scope": scope,
        "parent_id": parent_id,
        "name": name,
        "icon": icon or DEFAULT_GROUP_ICON,
        "favorite": False,
        "created_at": now_iso(),
        "sort_order": len(data_groups(data)),
    }
    data_groups(data).append(group)
    return group


def delete_group(data: dict, group: dict, item_lists: list[list[dict]]) -> None:
    """그룹 삭제. 하위 그룹과 소속 항목은 부모(상위) 경로로 올린다."""
    gid = group_id(group)
    parent_id = str(group.get("parent_id") or "")
    for child in data_groups(data):
        if str(child.get("parent_id") or "") == gid:
            child["parent_id"] = parent_id
    for items in item_lists:
        for item in items:
            if item_group_id(item) == gid:
                item["group_id"] = parent_id
    groups = data_groups(data)
    if group in groups:
        groups.remove(group)


def count_group_contents(data: dict, scope: str, gid: str, items: list[dict]) -> str:
    sub_groups = len(groups_in(data, scope, gid))
    direct_items = len(items_in_group(items, gid))
    parts = []
    if sub_groups:
        parts.append(f"그룹 {sub_groups}")
    parts.append(f"항목 {direct_items}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# 그룹 등록/수정 다이얼로그
# ---------------------------------------------------------------------------


class GroupDialog(QDialog):
    def __init__(self, group: dict | None = None) -> None:
        super().__init__()
        self.group = group or {}
        self.setWindowTitle("그룹 수정" if group else "그룹 생성")
        apply_modern_dialog_style(self)
        self.setMinimumWidth(380)
        self.selected_icon = group_icon(self.group)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        self.name = QLineEdit(str(self.group.get("name", "")))
        self.name.setPlaceholderText("그룹 이름")
        form.addRow("그룹명", self.name)
        layout.addLayout(form)

        icon_label = QLabel("아이콘")
        layout.addWidget(icon_label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        self.icon_buttons: list[QPushButton] = []
        for index, emoji in enumerate(GROUP_ICON_EMOJIS):
            button = QPushButton(emoji)
            button.setCheckable(True)
            button.setFixedSize(30, 28)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid rgba(148, 163, 184, 55);"
                " border-radius: 5px; font-size: 11pt; padding: 0; }"
                "QPushButton:hover { background: rgba(148, 163, 184, 28); }"
                "QPushButton:checked { background: rgba(59, 108, 245, 38); border-color: #3B6CF5; }"
            )
            button.clicked.connect(lambda checked=False, value=emoji: self._select_icon(value))
            self.icon_buttons.append(button)
            grid.addWidget(button, index // 10, index % 10)
        layout.addLayout(grid)
        self._sync_icons()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name.setFocus()

    def _select_icon(self, emoji: str) -> None:
        self.selected_icon = emoji
        self._sync_icons()

    def _sync_icons(self) -> None:
        for button in self.icon_buttons:
            button.setChecked(button.text() == self.selected_icon)

    def value(self) -> dict:
        data = dict(self.group)
        data.update({"name": self.name.text().strip(), "icon": self.selected_icon})
        return data


# ---------------------------------------------------------------------------
# 카드 위젯
# ---------------------------------------------------------------------------


def make_group_card(
    group: dict,
    subtitle: str,
    on_open: Callable[[], None],
    on_favorite: Callable[[dict, QWidget, QWidget], None],
    on_edit: Callable[[dict], None],
    on_delete: Callable[[dict], None],
    card_height: int = 92,
) -> QWidget:
    card = make_card(
        f"{group_icon(group)} {group.get('name', '(이름 없음)')}",
        subtitle,
        compact=True,
        card_height=card_height,
    )
    if group.get("favorite"):
        add_favorite_badge_to_card(card)
    size = QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)
    action_page = QWidget()
    action_page.setObjectName("cardActionBar")
    row = QHBoxLayout(action_page)
    row.setContentsMargins(3, 0, 3, 0)
    row.setSpacing(2)
    row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    pin_btn = make_icon_button(
        "pin", "즐겨찾기",
        lambda checked=False: on_favorite(group, card, pin_btn),
        size=size,
    )
    style_group_favorite_button(pin_btn, group)
    row.addWidget(pin_btn)
    row.addWidget(make_icon_button("📂", "그룹 열기 (더블클릭도 가능)", lambda checked=False: on_open(), size=size))
    row.addWidget(make_icon_button("edit", "수정", lambda checked=False: on_edit(group), size=size))
    row.addWidget(make_icon_button("delete", "삭제", lambda checked=False: on_delete(group), True, size=size))
    set_card_action_widget(card, action_page)
    card.mouseDoubleClickEvent = lambda event: on_open()
    return card


def style_group_favorite_button(button, group: dict) -> None:
    color = "#F5B301" if group.get("favorite") else "#A3A8B3"
    button.setText("★")
    button.setStyleSheet(
        f'QToolButton#iconButton {{ color: {color}; font-family: "Segoe UI Symbol", "Malgun Gothic"; '
        "font-size: 13pt; font-weight: 900; padding: 0 0 2px 0; "
        "min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }"
        f"QToolButton#iconButton:hover {{ color: {color}; background: transparent; }}"
    )


def toggle_group_favorite(group: dict, card: QWidget, button) -> None:
    group["favorite"] = not bool(group.get("favorite"))
    style_group_favorite_button(button, group)
    if group.get("favorite"):
        add_favorite_badge_to_card(card)
    else:
        remove_favorite_badge_from_card(card)


def make_back_card(on_back: Callable[[], None], card_height: int = 92) -> QWidget:
    """그룹 안 첫 번째 자리에 놓는 '이전으로 돌아가기' 카드."""
    card = make_card("⬅️ 돌아가기", "상위 경로로 이동", compact=True, card_height=card_height)
    card.setCursor(Qt.CursorShape.PointingHandCursor)

    def _release(event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            on_back()

    card.mouseReleaseEvent = _release
    card.mouseDoubleClickEvent = lambda event: None
    return card


# ---------------------------------------------------------------------------
# 브레드크럼 (현재 그룹 경로 표시 + 클릭 이동)
# ---------------------------------------------------------------------------


def make_breadcrumb_label(on_navigate: Callable[[str], None]) -> QLabel:
    """탭(메뉴 줄) 바로 아래에 놓는 그룹 경로 라벨.

    배경은 투명으로 두어 놓인 화면의 배경색과 자연스럽게 일치한다.
    각 조각을 클릭하면 on_navigate(그룹 id)가 호출된다. (최상위는 "")
    """
    label = QLabel()
    label.setObjectName("groupBreadcrumb")
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
    label.setOpenExternalLinks(False)
    label.setStyleSheet(
        "QLabel#groupBreadcrumb { font-weight: 800; font-size: 9.5pt;"
        " padding: 6px 12px 0 12px; background: transparent; border: 0; }"
    )
    label.linkActivated.connect(
        lambda href: on_navigate("" if href == "__root__" else str(href))
    )
    label.hide()
    return label


def update_breadcrumb_label(label: QLabel, data: dict, gid: str) -> None:
    chain = group_path(data, gid)
    if not chain:
        label.clear()
        label.hide()
        return
    parts = ['<a href="__root__" style="color:#94A3B8;text-decoration:none;">🏠 전체</a>']
    for group in chain:
        href = escape(str(group.get("id") or ""), quote=True)
        name = escape(str(group.get("name") or ""))
        parts.append(
            f'<a href="{href}" style="color:#3B6CF5;text-decoration:none;">{group_icon(group)} {name}</a>'
        )
    label.setText(' <span style="color:#94A3B8;">›</span> '.join(parts))
    label.show()


# ---------------------------------------------------------------------------
# 저장위치(그룹) 선택 콤보
# ---------------------------------------------------------------------------


def build_group_combo(data: dict, scope: str, selected_gid: str = "") -> QComboBox:
    """항목 등록/수정 다이얼로그에 넣는 저장위치(그룹) 선택 콤보.

    최상위를 포함해 scope에 속한 모든 그룹을 트리 들여쓰기로 나열한다.
    """
    combo = QComboBox()
    combo.addItem("🏠 최상위", "")

    def add_options(parent_id: str, depth: int) -> None:
        for group in groups_in(data, scope, parent_id):
            gid = group_id(group)
            label = ("    " * depth) + f"{group_icon(group)} {group.get('name', '')}"
            combo.addItem(label, gid)
            add_options(gid, depth + 1)

    add_options("", 0)
    index = combo.findData(selected_gid)
    combo.setCurrentIndex(index if index >= 0 else 0)
    return combo


# ---------------------------------------------------------------------------
# "그룹으로 이동" 메뉴
# ---------------------------------------------------------------------------


def show_move_to_group_menu(
    parent: QWidget,
    data: dict,
    scope: str,
    item: dict,
    on_done: Callable[[], None],
) -> None:
    """항목 카드의 📂 버튼: 항목을 옮길 그룹을 트리 형태 메뉴로 고른다."""
    menu = QMenu(parent)
    current = item_group_id(item)

    def move_to(gid: str) -> None:
        item["group_id"] = gid
        on_done()

    root_action = menu.addAction("🏠 최상위로 이동")
    root_action.setEnabled(bool(current))
    root_action.triggered.connect(lambda checked=False: move_to(""))
    menu.addSeparator()

    def add_actions(parent_id: str, depth: int) -> None:
        for group in groups_in(data, scope, parent_id):
            gid = group_id(group)
            label = ("    " * depth) + f"{group_icon(group)} {group.get('name', '')}"
            action = menu.addAction(label)
            action.setEnabled(gid != current)
            action.triggered.connect(lambda checked=False, value=gid: move_to(value))
            add_actions(gid, depth + 1)

    add_actions("", 0)
    menu.exec(QCursor.pos())
