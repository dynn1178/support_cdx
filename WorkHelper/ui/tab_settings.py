from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.theme import THEMES


class SettingsTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.template = QComboBox()
        self.template.addItems([f"템플릿 {i}" for i in range(1, 6)])
        self.template.currentIndexChanged.connect(self.change_template)
        self.theme = QComboBox()
        self.theme.addItems(list(THEMES.keys()))
        self.font_family = QComboBox()
        self.font_family.addItems(["맑은 고딕", "Malgun Gothic", "Arial", "Consolas", "Courier New"])
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 20)
        self.always_on_top = QCheckBox("항상 위")
        self.clipboard_limit = QSpinBox()
        self.clipboard_limit.setRange(10, 500)
        form.addRow("활성 템플릿", self.template)
        form.addRow("테마", self.theme)
        form.addRow("폰트", self.font_family)
        form.addRow("폰트 크기", self.font_size)
        form.addRow("창", self.always_on_top)
        form.addRow("클립보드 최대", self.clipboard_limit)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        save_btn = QPushButton("설정 저장")
        export_btn = QPushButton("내보내기")
        import_btn = QPushButton("가져오기")
        save_btn.clicked.connect(self.save_settings)
        export_btn.clicked.connect(self.export_template)
        import_btn.clicked.connect(self.import_template)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        buttons.addWidget(export_btn)
        buttons.addWidget(import_btn)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self._refreshing = False

    def change_template(self, index: int) -> None:
        if self._refreshing:
            return
        self.main.change_template(index + 1)

    def refresh(self) -> None:
        self._refreshing = True
        settings = self.main.data.get("settings", {})
        self.template.setCurrentIndex(self.main.template_index - 1)
        self.theme.setCurrentText(settings.get("theme", "light"))
        self.font_family.setCurrentText(settings.get("font_family", "맑은 고딕"))
        self.font_size.setValue(int(settings.get("font_size", 9)))
        self.always_on_top.setChecked(bool(settings.get("window", {}).get("always_on_top", False)))
        self.clipboard_limit.setValue(int(settings.get("clipboard_history_limit", 50)))
        self._refreshing = False

    def save_settings(self) -> None:
        settings = self.main.data.setdefault("settings", {})
        window = settings.setdefault("window", {"width": 400, "height": 700, "always_on_top": False})
        settings["theme"] = self.theme.currentText()
        settings["font_family"] = self.font_family.currentText()
        settings["font_size"] = self.font_size.value()
        settings["clipboard_history_limit"] = self.clipboard_limit.value()
        settings["active_template"] = self.main.template_index
        window["always_on_top"] = self.always_on_top.isChecked()
        self.main.apply_current_settings()
        self.main.save_data()
        self.main.show()

    def export_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "템플릿 내보내기", f"template_{self.main.template_index}.json", "JSON (*.json)")
        if not path:
            return
        try:
            config.export_template(self.main.template_index, path)
            QMessageBox.information(self, "완료", "템플릿을 내보냈습니다.")
        except Exception as exc:
            QMessageBox.warning(self, "내보내기 실패", str(exc))

    def import_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "템플릿 가져오기", "", "JSON (*.json)")
        if not path:
            return
        try:
            config.import_template(path, self.main.template_index)
            self.main.change_template(self.main.template_index)
            QMessageBox.information(self, "완료", "템플릿을 가져왔습니다.")
        except Exception as exc:
            QMessageBox.warning(self, "가져오기 실패", str(exc))
