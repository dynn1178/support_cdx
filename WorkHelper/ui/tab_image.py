from __future__ import annotations

import ctypes
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import display_hotkey, new_id, now_iso, resolve_image_path
from ui.common import GridPanel, HotkeyFields, SortControls, add_card_actions, apply_manual_reorder, bump_usage, confirm_shift_digit_hotkey, make_card, make_icon_button


def active_window_title() -> str:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


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

    def relative_asset_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(config.BASE_DIR.resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

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
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        for screen in screens:
            intersected = rect.intersected(screen.geometry())
            if intersected.isEmpty():
                continue
            local = intersected.translated(-screen.geometry().topLeft())
            part = screen.grabWindow(0, local.x(), local.y(), local.width(), local.height())
            painter.drawPixmap(intersected.topLeft() - rect.topLeft(), part)
        painter.end()
        percent = int(self.capture_scale.currentText().replace("%", ""))
        if percent != 100:
            pixmap = pixmap.scaled(
                max(1, pixmap.width() * percent // 100),
                max(1, pixmap.height() * percent // 100),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        target = self.image_dir() / f"{new_id('capture')}.png"
        if not pixmap.save(str(target), "PNG"):
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
        row.addWidget(add_btn)
        page_layout.addLayout(row)
        self.tabs.addTab(page, "컨닝페이퍼")
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
        steel_layout.addWidget(self.steel_cut_list, 1)
        self.tabs.addTab(steel_page, "스틸 컷")
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
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("window_title") or value.get("created_at", ""))
        cards = []
        for item in visible_items:
            haystack = f"{item.get('window_title', '')} {item.get('created_at', '')}".lower()
            if q and q not in haystack:
                continue
            cards.append(self.make_steel_cut_card(item))
        callback = (lambda old, new: self.reorder_items(source_items, visible_items, old, new)) if self.sort_controls.is_manual() else None
        self.steel_cut_list.add_cards(cards, on_reorder=callback)

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
        items = self.main.data.setdefault("steel_cuts", [])
        cutoff = datetime.now() - timedelta(days=7)
        kept = []
        changed = False
        for item in items:
            raw = item.get("last_used_at") or item.get("created_at") or now_iso()
            try:
                used_at = datetime.fromisoformat(raw)
            except ValueError:
                used_at = datetime.now()
            if used_at < cutoff:
                self.delete_steel_cut_file(item)
                changed = True
                continue
            kept.append(item)
        if changed:
            self.main.data["steel_cuts"] = kept
            self.main.save_data()

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def image_dir(self) -> Path:
        path = config.BASE_DIR / "assets" / "images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_asset_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(config.BASE_DIR.resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

    def capture_selection(self, rect: QRect) -> QPixmap:
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        for screen in QApplication.screens():
            intersected = rect.intersected(screen.geometry())
            if intersected.isEmpty():
                continue
            local = intersected.translated(-screen.geometry().topLeft())
            part = screen.grabWindow(0, local.x(), local.y(), local.width(), local.height())
            painter.drawPixmap(intersected.topLeft() - rect.topLeft(), part)
        painter.end()
        return pixmap

    def capture_steel_cut(self) -> None:
        title = active_window_title()
        capture = ScreenCaptureDialog()
        if capture.exec() != capture.DialogCode.Accepted or capture.selection.width() < 3 or capture.selection.height() < 3:
            return
        pixmap = self.capture_selection(capture.selection)
        target = self.image_dir() / f"{new_id('steel')}.png"
        if not pixmap.save(str(target), "PNG"):
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
        self.tabs.setCurrentIndex(1)
        self.view_steel_cut(value)

    def view_image(self, item: dict) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "이미지 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        bump_usage(item)
        self.main.save_usage_data()
        ImageViewerDialog(path, item.get("name", "이미지"), int(item.get("display_scale", 100))).exec()

    def view_steel_cut(self, item: dict) -> None:
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

    def delete_steel_cut_file(self, item: dict) -> None:
        try:
            path = Path(resolve_image_path(item.get("path", ""), config.BASE_DIR))
            if path.exists() and config.BASE_DIR.resolve() in path.resolve().parents:
                path.unlink()
        except Exception:
            pass

    def delete_steel_cut(self, item: dict) -> None:
        if QMessageBox.question(self, "삭제", "선택한 스틸 컷을 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        items = self.main.data.get("steel_cuts", [])
        if item in items:
            items.remove(item)
        self.delete_steel_cut_file(item)
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
        if QMessageBox.question(self, "삭제", "선택한 이미지를 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.main.data.get("images", []).remove(item)
        self.main.save_data()
