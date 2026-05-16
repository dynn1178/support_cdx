from __future__ import annotations

import ast
import operator
from datetime import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.date_tools import apply_offset, format_date
from ui.common import GRID_PANEL_MARGINS


def highlight_today(date_edit: QDateEdit) -> None:
    calendar = date_edit.calendarWidget()
    today_format = QTextCharFormat()
    today_format.setBackground(QColor("#FFF3B0"))
    today_format.setForeground(QColor("#111827"))
    today_format.setFontWeight(700)
    calendar.setDateTextFormat(QDate.currentDate(), today_format)


class SafeCalculator:
    OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    @classmethod
    def eval(cls, expression: str) -> float | int:
        tree = ast.parse(expression, mode="eval")
        return cls._eval_node(tree.body)

    @classmethod
    def _eval_node(cls, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in cls.OPS:
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ValueError("지수가 너무 큽니다.")
            return cls.OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in cls.OPS:
            return cls.OPS[type(node.op)](cls._eval_node(node.operand))
        raise ValueError("숫자와 + - * / // % ** 괄호만 사용할 수 있습니다.")


class ArithmeticTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.history: list[str] = []
        self.raw_result = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(12)

        # 계산기 패널 (중앙 정렬)
        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(800)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(10)

        self.expression = QLineEdit()
        self.expression.setPlaceholderText("예: 1231231 * 23 - 23")
        self.expression.textChanged.connect(self.refresh)
        self.expression.returnPressed.connect(self.copy_result)
        self.result = QLabel("")
        self.result.setObjectName("cardTitle")
        self.status = QLabel("")
        self.status.setObjectName("mutedText")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.addRow("수식", self.expression)
        form.addRow("결과", self.result)
        form.addRow("", self.status)
        panel_layout.addLayout(form)

        btn_row = QHBoxLayout()
        copy = QPushButton("결과 복사")
        copy.clicked.connect(self.copy_result)
        clear = QPushButton("내역 지우기")
        clear.clicked.connect(self.clear_history)
        btn_row.addStretch(1)
        btn_row.addWidget(copy)
        btn_row.addWidget(clear)
        panel_layout.addLayout(btn_row)

        layout.addWidget(panel)

        self.history_list = QListWidget()
        self.history_list.setSpacing(0)
        self.history_list.setUniformItemSizes(True)
        self.history_list.setStyleSheet("QListWidget::item { padding: 2px 6px; min-height: 20px; color: palette(WindowText); }")
        self.history_list.itemClicked.connect(self.use_history_item)
        layout.addWidget(QLabel("계산 내역"))
        layout.addWidget(self.history_list, 1)

    def refresh(self) -> None:
        expression = self.expression.text().strip()
        if not expression:
            self.result.setText("")
            self.status.setText("")
            return
        try:
            value = SafeCalculator.eval(expression)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            self.raw_result = str(value)
            self.result.setText(f"{value:,}")
            self.status.setText("")
        except SyntaxError:
            self.result.setText("")
            self.raw_result = ""
            self.status.setText("")
        except Exception:
            self.result.setText("")
            self.raw_result = ""
            self.status.setText("")

    def copy_result(self) -> None:
        text = self.raw_result
        expression = self.expression.text().strip()
        if not text:
            return
        self.main.app.clipboard().setText(text)
        self.status.setText("클립보드로 복사되었습니다.")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1200, self.status.clear)
        entry = f"{expression} = {self.result.text().strip()}"
        if entry not in self.history:
            self.history.insert(0, entry)
            self.history = self.history[:20]
            self.history_list.clear()
            self.history_list.addItems(self.history)

    def use_history_item(self, item: QListWidgetItem) -> None:
        expression, sep, result = item.text().partition(" = ")
        if not sep:
            return
        self.expression.setText(expression)
        self.main.app.clipboard().setText(result.replace(",", "").strip())

    def clear_history(self) -> None:
        self.history.clear()
        self.history_list.clear()


class DateCalcTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(0)

        # 날짜계산 패널 (중앙 정렬, card 스타일)
        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(800)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.base_date = QDateEdit()
        self.base_date.setCalendarPopup(True)
        self.base_date.setDate(QDate.currentDate())
        highlight_today(self.base_date)
        self.base_date.setMinimumWidth(220)
        self.amount = QSpinBox()
        self.amount.setRange(-9999, 9999)
        self.amount.setValue(1)
        self.unit = QComboBox()
        self.unit.addItems(["일", "주", "개월", "분기", "년"])
        self.unit.setMinimumWidth(140)
        calc_row = QHBoxLayout()
        calc_row.setContentsMargins(0, 0, 0, 0)
        calc_row.setSpacing(8)
        calc_row.addWidget(self.amount)
        calc_row.addWidget(self.unit)
        calc_row.addStretch(1)
        calc_widget = QWidget()
        calc_widget.setObjectName("calcWidget")
        calc_widget.setLayout(calc_row)
        calc_widget.setStyleSheet("QWidget#calcWidget { background: transparent; border: 0; }")
        self.business_days = QCheckBox("일 단위 계산 시 영업일 기준")
        self.format = QComboBox()
        self.format.setEditable(True)
        self.format.setMinimumWidth(300)
        self.format.addItems(["yyyy-mm-dd", "yyyy년 m월 d일", "yyyy년 qq", "yy.mm.dd(aaa)", "dddd", "aaaa"])
        self.result = QLabel("")
        self.result.setObjectName("cardTitle")
        form.addRow("기준 날짜", self.base_date)
        form.addRow("계산값", calc_widget)
        form.addRow("옵션", self.business_days)
        form.addRow("표시 형식", self.format)
        form.addRow("결과", self.result)
        panel_layout.addLayout(form)

        btn_row = QHBoxLayout()
        calc_btn = QPushButton("계산")
        copy = QPushButton("결과 복사")
        calc_btn.clicked.connect(self.refresh)
        copy.clicked.connect(self.copy_result)
        btn_row.addStretch(1)
        btn_row.addWidget(calc_btn)
        btn_row.addWidget(copy)
        panel_layout.addLayout(btn_row)

        layout.addWidget(panel)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        qdate = self.base_date.date()
        base = datetime(qdate.year(), qdate.month(), qdate.day()).date()
        unit_map = {"일": "D", "주": "W", "개월": "M", "분기": "Q", "년": "Y"}
        expression = f"{self.amount.value():+d}{unit_map[self.unit.currentText()]}"
        value = apply_offset(base, expression, self.business_days.isChecked())
        self.result.setText(format_date(value, self.format.currentText()))

    def copy_result(self) -> None:
        self.main.app.clipboard().setText(self.result.text())


class CalculatorTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(ArithmeticTab(main), "연산 계산")
        tabs.addTab(DateCalcTab(main), "날짜 계산")
        layout.addWidget(tabs, 1)
