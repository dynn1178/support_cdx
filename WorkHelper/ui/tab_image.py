from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import new_id, resolve_image_path, short_preview
from ui.common import add_widget_item, make_card


class ImageDialog(QDialog):
    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("이미지 편집")
        self.item = item or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.item.get("name", ""))
        self.path = QLineEdit(self.item.get("path", ""))
        browse = QPushButton("찾기")
        browse.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        form.addRow("이름", self.name)
        form.addRow("경로", row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.path.setText(path)

    def value(self) -> dict:
        data = dict(self.item)
        path = self.path.text().strip()
        data.update({"name": self.name.text().strip(), "path": path, "path_type": "absolute" if Path(path).is_absolute() else "relative"})
        return data


class ImageViewerDialog(QDialog):
    def __init__(self, image_path: str, title: str) -> None:
        super().__init__()
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        label = QLabel()
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            label.setText("이미지를 불러올 수 없습니다.")
        else:
            scaled = pixmap.scaled(1200, 900, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled)
            self.resize(scaled.width() + 24, scaled.height() + 24)
        layout.addWidget(label)


class ImageTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        add_btn = QPushButton("+ 이미지")
        add_btn.clicked.connect(self.edit_image)
        layout.addWidget(add_btn)

    def refresh(self) -> None:
        self.list.clear()
        for item in self.main.data.get("images", []):
            card = make_card(item.get("name", "(이름 없음)"), short_preview(item.get("path", "")))
            row = QHBoxLayout()
            view_btn = QPushButton("보기")
            edit_btn = QPushButton("편집")
            del_btn = QPushButton("삭제")
            view_btn.clicked.connect(lambda checked=False, value=item: self.view_image(value))
            edit_btn.clicked.connect(lambda checked=False, value=item: self.edit_image(value))
            del_btn.clicked.connect(lambda checked=False, value=item: self.delete_image(value))
            row.addWidget(view_btn)
            row.addWidget(edit_btn)
            row.addWidget(del_btn)
            card.layout().addLayout(row)
            add_widget_item(self.list, card)

    def view_image(self, item: dict) -> None:
        path = resolve_image_path(item.get("path", ""), config.BASE_DIR)
        if not Path(path).exists():
            QMessageBox.warning(self, "이미지 없음", f"파일을 찾을 수 없습니다.\n{path}")
            return
        ImageViewerDialog(path, item.get("name", "이미지")).exec()

    def edit_image(self, item: dict | None = None) -> None:
        dialog = ImageDialog(item)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value.get("name"):
            QMessageBox.warning(self, "입력 확인", "이름을 입력해주세요.")
            return
        if not value.get("id"):
            value["id"] = new_id("img")
        items = self.main.data.setdefault("images", [])
        if item in items:
            items[items.index(item)] = value
        else:
            items.append(value)
        self.main.save_data()

    def delete_image(self, item: dict) -> None:
        if QMessageBox.question(self, "삭제", "선택한 이미지를 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.main.data.get("images", []).remove(item)
        self.main.save_data()

