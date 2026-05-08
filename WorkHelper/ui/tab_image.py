from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QPainter, QPixmap
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
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import display_hotkey, new_id, now_iso, resolve_image_path
from ui.common import GridPanel, HotkeyFields, SortControls, add_card_actions, apply_manual_reorder, bump_usage, confirm_shift_digit_hotkey, make_card


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
    def __init__(self, image_path: str, title: str, scale: int = 100) -> None:
        super().__init__()
        self.setWindowTitle(title)
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


class ImageTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("+ 이미지")
        add_btn.clicked.connect(self.edit_image)
        top = QHBoxLayout()
        self.sort_controls = SortControls(self.refresh)
        top.addStretch(1)
        top.addWidget(self.sort_controls)
        layout.addLayout(top)
        self.list = GridPanel(columns=3)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(add_btn)
        layout.addLayout(row)

    def refresh(self) -> None:
        cards = []
        source_items = self.main.data.get("images", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name") or value.get("path", ""))
        for item in visible_items:
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

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def view_image(self, item: dict) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "이미지 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        bump_usage(item)
        self.main.save_data()
        ImageViewerDialog(path, item.get("name", "이미지"), int(item.get("display_scale", 100))).exec()

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
