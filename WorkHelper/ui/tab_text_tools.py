from __future__ import annotations

import re
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget


class PlainTextEdit(QTextEdit):
    def insertFromMimeData(self, source) -> None:
        self.insertPlainText(source.text())


class UrlCodecTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        self.input = PlainTextEdit()
        self.output = PlainTextEdit()
        row = QHBoxLayout()
        encode = QPushButton("URL 인코딩")
        decode = QPushButton("URL 디코딩")
        copy = QPushButton("결과 복사")
        encode.clicked.connect(lambda: self.convert(True))
        decode.clicked.connect(lambda: self.convert(False))
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.output.toPlainText()))
        row.addStretch(1)
        row.addWidget(encode)
        row.addWidget(decode)
        row.addWidget(copy)
        layout.addWidget(QLabel("입력"))
        layout.addWidget(self.input, 1)
        layout.addLayout(row)
        layout.addWidget(QLabel("결과"))
        layout.addWidget(self.output, 1)

    def convert(self, encode: bool) -> None:
        text = self.input.toPlainText()
        self.output.setPlainText(quote(text, safe="") if encode else unquote(text))


class UtmTab(QWidget):
    UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.url = QLineEdit()
        self.fields = {key: QLineEdit() for key in self.UTM_KEYS}
        form.addRow("URL", self.url)
        for key, field in self.fields.items():
            form.addRow(key, field)
        layout.addLayout(form)
        row = QHBoxLayout()
        split = QPushButton("분해")
        build = QPushButton("조합")
        copy = QPushButton("URL 복사")
        split.clicked.connect(self.split_url)
        build.clicked.connect(self.build_url)
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.url.text()))
        row.addStretch(1)
        row.addWidget(split)
        row.addWidget(build)
        row.addWidget(copy)
        layout.addLayout(row)
        layout.addStretch(1)

    def split_url(self) -> None:
        parts = urlsplit(self.url.text().strip())
        params = dict(parse_qsl(parts.query, keep_blank_values=True))
        for key, field in self.fields.items():
            field.setText(params.get(key, ""))

    def build_url(self) -> None:
        raw = self.url.text().strip()
        parts = urlsplit(raw)
        params = dict(parse_qsl(parts.query, keep_blank_values=True))
        for key, field in self.fields.items():
            value = field.text().strip()
            if value:
                params[key] = value
            else:
                params.pop(key, None)
        query = urlencode(params)
        self.url.setText(urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment)))


class LineBreakTab(QWidget):
    EXAMPLES = {
        "줄바꿈 → 쉼표": ("hello\nworld", "hello, world"),
        "공백 → 줄바꿈": ("hello world foo", "hello\nworld\nfoo"),
        "줄바꿈 → 따옴표 목록": ("hello\nworld", "('hello', 'world')"),
        "공백 → 따옴표 목록": ("hello world foo", "('hello', 'world', 'foo')"),
    }

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        self.mode = QComboBox()
        self.mode.addItems(list(self.EXAMPLES))
        self.mode.currentTextChanged.connect(self.update_example)
        self.before_example = QLabel()
        self.after_example = QLabel()
        for label in [self.before_example, self.after_example]:
            label.setObjectName("mutedText")
            label.setWordWrap(True)
            label.setFixedHeight(38)
            label.setStyleSheet("QLabel#mutedText { padding: 2px 6px; border: 1px solid rgba(107,114,128,0.28); border-radius: 6px; line-height: 90%; }")
        self.input = PlainTextEdit()
        self.output = PlainTextEdit()
        for editor in [self.input, self.output]:
            editor.setStyleSheet("QTextEdit { line-height: 100%; }")
        convert = QPushButton("변환")
        copy = QPushButton("결과 복사")
        convert.clicked.connect(self.convert)
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.output.toPlainText()))
        row = QHBoxLayout()
        row.addWidget(self.mode)
        examples = QGridLayout()
        examples.setContentsMargins(0, 0, 0, 0)
        examples.setHorizontalSpacing(6)
        examples.setVerticalSpacing(2)
        examples.addWidget(QLabel("전"), 0, 0)
        examples.addWidget(QLabel("후"), 0, 1)
        examples.addWidget(self.before_example, 1, 0)
        examples.addWidget(self.after_example, 1, 1)
        row.addLayout(examples, 1)
        row.addWidget(convert)
        row.addWidget(copy)
        layout.addLayout(row)
        layout.addWidget(QLabel("입력"))
        layout.addWidget(self.input, 1)
        layout.addWidget(QLabel("결과"))
        layout.addWidget(self.output, 1)
        self.update_example(self.mode.currentText())

    def update_example(self, mode: str) -> None:
        before, after = self.EXAMPLES.get(mode, ("", ""))
        self.before_example.setText(before)
        self.after_example.setText(after)

    def convert(self) -> None:
        mode = self.mode.currentText()
        text = self.input.toPlainText().strip()
        if mode.startswith("줄바꿈"):
            items = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            items = [part.strip() for part in text.split() if part.strip()]
        if "쉼표" in mode:
            result = ", ".join(items)
        elif mode == "공백 → 줄바꿈":
            result = "\n".join(items)
        else:
            result = "(" + ", ".join(f"'{item}'" for item in items) + ")"
        self.output.setPlainText(result)


class CaseCycleTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        hint = QLabel("SER_ID ↔ userId ↔ UserId 형식을 순환 변환합니다. 단축키: Ctrl+Shift+U")
        hint.setObjectName("mutedText")
        layout.addWidget(hint)
        self.input = PlainTextEdit()
        self.output = PlainTextEdit()
        row = QHBoxLayout()
        convert = QPushButton("순환 변환")
        copy = QPushButton("결과 복사")
        convert.clicked.connect(self.convert)
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.output.toPlainText()))
        row.addStretch(1)
        row.addWidget(convert)
        row.addWidget(copy)
        layout.addWidget(QLabel("입력"))
        layout.addWidget(self.input, 1)
        layout.addLayout(row)
        layout.addWidget(QLabel("결과"))
        layout.addWidget(self.output, 1)
        QShortcut(QKeySequence("Ctrl+Shift+U"), self, activated=self.convert)

    def words(self, text: str) -> list[str]:
        if "_" in text:
            return [part.lower() for part in text.split("_") if part]
        return [part.lower() for part in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z]|$)", text)]

    def cycle_token(self, token: str) -> str:
        parts = self.words(token)
        if not parts:
            return token
        if "_" in token and token.upper() == token:
            return parts[0] + "".join(part.capitalize() for part in parts[1:])
        if token[:1].islower() and "_" not in token:
            return "".join(part.capitalize() for part in parts)
        return "_".join(part.upper() for part in parts)

    def convert(self) -> None:
        text = self.input.toPlainText()
        result = re.sub(r"[A-Za-z][A-Za-z0-9_]*", lambda match: self.cycle_token(match.group(0)), text)
        self.output.setPlainText(result)


class TextToolsTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(UrlCodecTab(main), "URL 인코딩")
        tabs.addTab(UtmTab(main), "UTM")
        tabs.addTab(LineBreakTab(main), "줄바꿈/따옴표")
        tabs.addTab(CaseCycleTab(main), "대소문자 변환")
        layout.addWidget(tabs, 1)
