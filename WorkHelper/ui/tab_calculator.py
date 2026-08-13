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
from app.number_format import format_calc_result
from app.practical_calc import (
    BASE_OPTIONS,
    COMPOUND_FREQUENCIES,
    LENGTH_UNITS,
    TEMPERATURE_UNITS,
    WEIGHT_UNITS,
    apply_percent_change,
    compound_interest,
    convert_base,
    convert_length,
    convert_temperature,
    convert_weight,
    exchange_convert,
    percent_change,
    percent_of,
    percent_ratio,
    simple_interest,
    tax_from_supply,
    tax_from_total,
)
from ui.common import GRID_PANEL_MARGINS, dialog_palette, style_list_selection


def _fmt_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{round(value):,}"
    return f"{value:,.2f}"


def _fmt_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{_fmt_number(value)}%"


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
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        style_list_selection(self.history_list, dialog_palette(self))
        self.history_list.itemClicked.connect(self.use_history_item)
        layout.addWidget(QLabel("계산 내역"))
        layout.addWidget(self.history_list, 1)

    def refresh(self) -> None:
        expression = self.expression.text().strip()
        if not expression:
            self.result.setText("")
            self.raw_result = ""
            self.status.setText("")
            return
        try:
            display, raw = format_calc_result(SafeCalculator.eval(expression))
            self.raw_result = raw
            self.result.setText(display)
            self.status.setText("")
        except Exception:
            # 입력 중인 수식은 아직 계산할 수 없으므로 조용히 비워둔다.
            self.result.setText("")
            self.raw_result = ""
            self.status.setText("")

    def copy_result(self) -> None:
        text = self.raw_result
        expression = self.expression.text().strip()
        if not text:
            return
        # 화면에는 1,000 · 한글·백분율을 함께 보여주지만 복사는 항상 원본 숫자만.
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
        expression, sep, _display = item.text().partition(" = ")
        if not sep:
            return
        self.expression.setText(expression)
        self.refresh()  # 표시용 문자열 대신 다시 계산한 원본 값을 복사한다.
        if self.raw_result:
            self.main.app.clipboard().setText(self.raw_result)

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


class UnitConvertTab(QWidget):
    KIND_LENGTH = "길이"
    KIND_WEIGHT = "무게"
    KIND_TEMP = "온도"
    KIND_BASE = "진법"

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.raw_result = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(12)

        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(800)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.kind = QComboBox()
        self.kind.addItems([self.KIND_LENGTH, self.KIND_WEIGHT, self.KIND_TEMP, self.KIND_BASE])
        self.kind.currentTextChanged.connect(self.on_kind_changed)

        self.value = QLineEdit()
        self.value.textChanged.connect(self.refresh)

        self.from_unit = QComboBox()
        self.to_unit = QComboBox()
        self.from_unit.currentTextChanged.connect(self.refresh)
        self.to_unit.currentTextChanged.connect(self.refresh)
        unit_row = QHBoxLayout()
        unit_row.setSpacing(8)
        unit_row.addWidget(self.from_unit, 1)
        unit_row.addWidget(QLabel("→"))
        unit_row.addWidget(self.to_unit, 1)
        unit_widget = QWidget()
        unit_widget.setLayout(unit_row)

        self.result = QLabel("")
        self.result.setObjectName("cardTitle")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form.addRow("종류", self.kind)
        form.addRow("값", self.value)
        form.addRow("단위", unit_widget)
        form.addRow("결과", self.result)
        panel_layout.addLayout(form)

        btn_row = QHBoxLayout()
        swap = QPushButton("단위 바꾸기")
        copy = QPushButton("결과 복사")
        swap.clicked.connect(self.swap_units)
        copy.clicked.connect(self.copy_result)
        btn_row.addStretch(1)
        btn_row.addWidget(swap)
        btn_row.addWidget(copy)
        panel_layout.addLayout(btn_row)

        layout.addWidget(panel)
        layout.addStretch(1)
        self.on_kind_changed(self.kind.currentText())

    def on_kind_changed(self, kind: str) -> None:
        self.from_unit.blockSignals(True)
        self.to_unit.blockSignals(True)
        self.from_unit.clear()
        self.to_unit.clear()
        if kind == self.KIND_LENGTH:
            options = list(LENGTH_UNITS)
            self.value.setPlaceholderText("예: 100")
        elif kind == self.KIND_WEIGHT:
            options = list(WEIGHT_UNITS)
            self.value.setPlaceholderText("예: 100")
        elif kind == self.KIND_TEMP:
            options = list(TEMPERATURE_UNITS)
            self.value.setPlaceholderText("예: 36.5")
        else:
            options = [f"{base}진법" for base in BASE_OPTIONS]
            self.value.setPlaceholderText("예: FF, 1010, 255")
        self.from_unit.addItems(options)
        self.to_unit.addItems(options)
        if len(options) > 1:
            self.to_unit.setCurrentIndex(1)
        self.from_unit.blockSignals(False)
        self.to_unit.blockSignals(False)
        self.refresh()

    def swap_units(self) -> None:
        i, j = self.from_unit.currentIndex(), self.to_unit.currentIndex()
        self.from_unit.setCurrentIndex(j)
        self.to_unit.setCurrentIndex(i)

    def refresh(self) -> None:
        kind = self.kind.currentText()
        text = self.value.text().strip()
        if not text or not self.from_unit.currentText() or not self.to_unit.currentText():
            self.result.setText("")
            self.raw_result = ""
            return
        try:
            if kind == self.KIND_BASE:
                from_base = int(self.from_unit.currentText().replace("진법", ""))
                to_base = int(self.to_unit.currentText().replace("진법", ""))
                result_text = convert_base(text, from_base, to_base)
                self.raw_result = result_text
                self.result.setText(result_text)
                return
            value = float(text)
            from_unit = self.from_unit.currentText()
            to_unit = self.to_unit.currentText()
            if kind == self.KIND_LENGTH:
                result_value = convert_length(value, from_unit, to_unit)
            elif kind == self.KIND_WEIGHT:
                result_value = convert_weight(value, from_unit, to_unit)
            else:
                result_value = convert_temperature(value, from_unit, to_unit)
            self.raw_result = repr(result_value)
            self.result.setText(_fmt_number(result_value))
        except Exception:
            self.result.setText("")
            self.raw_result = ""

    def copy_result(self) -> None:
        if self.raw_result:
            self.main.app.clipboard().setText(self.raw_result)


class PercentCalcTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(12)

        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(860)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(14)

        self._build_row(
            panel_layout, "전체값", "10000", "의 비율값", "20", "%는 얼마?",
            "전체값의 비율값(%)만큼은 얼마인지 계산합니다. 예) 10000의 20% = 2,000",
            lambda base, other: _fmt_number(percent_of(base, other)),
        )
        self._build_row(
            panel_layout, "전체값", "10000", "의 일부값", "500", "은 몇%?",
            "일부값이 전체값의 몇 %인지 계산합니다. 예) 10000 중 500 = 5%",
            lambda base, other: _fmt_percent(percent_ratio(base, other)),
        )
        self._build_row(
            panel_layout, "전체값", "10000", "이/가", "25000", "으로 변하면 증감률은?",
            "전체값이 두 번째 값으로 바뀌면 증감률이 몇 %인지 계산합니다. 예) 10000 → 25000 = +150%",
            lambda base, other: _fmt_percent(percent_change(base, other)),
        )
        self._build_row(
            panel_layout, "전체값", "10000", "이/가 증감률", "25", "% 변하면 결과값은?",
            "전체값이 증감률(%)만큼 바뀌면 결과값이 얼마인지 계산합니다. 예) 10000이 25% 증가 = 12,500",
            lambda base, other: _fmt_number(apply_percent_change(base, other)),
        )

        layout.addWidget(panel)
        layout.addStretch(1)

    def _build_row(self, parent_layout, label1: str, ph1: str, label2: str, ph2: str, question: str, tooltip: str, formula) -> None:
        row = QHBoxLayout()
        row.setSpacing(6)
        input1 = QLineEdit()
        input1.setPlaceholderText(f"예){ph1}")
        input1.setMaximumWidth(120)
        input2 = QLineEdit()
        input2.setPlaceholderText(f"예){ph2}")
        input2.setMaximumWidth(120)
        question_label = QLabel(f"{question} ❓")
        question_label.setToolTip(tooltip)
        result_label = QLabel("")
        result_label.setObjectName("cardTitle")
        result_label.setMinimumWidth(110)
        result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(QLabel(label1))
        row.addWidget(input1)
        row.addWidget(QLabel(label2))
        row.addWidget(input2)
        row.addWidget(question_label)
        row.addWidget(result_label, 1)
        parent_layout.addLayout(row)

        def compute() -> None:
            try:
                v1 = float(input1.text().strip())
                v2 = float(input2.text().strip())
            except ValueError:
                result_label.setText("")
                return
            try:
                result_label.setText(formula(v1, v2))
            except ZeroDivisionError:
                result_label.setText("전체값은 0이 될 수 없어요")

        input1.textChanged.connect(compute)
        input2.textChanged.connect(compute)


class TaxCalcTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(12)

        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(800)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.mode = QComboBox()
        self.mode.addItems(["공급가액 → 합계금액", "합계금액 → 공급가액"])
        self.mode.currentTextChanged.connect(self.refresh)
        self.rate = QLineEdit("10")
        self.rate.setPlaceholderText("예: 10 (부가세 기본 세율)")
        self.rate.textChanged.connect(self.refresh)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("예: 10000")
        self.amount.textChanged.connect(self.refresh)
        self.result = QLabel("")
        self.result.setObjectName("cardTitle")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form.addRow("계산 방향", self.mode)
        form.addRow("세율(%)", self.rate)
        form.addRow("금액", self.amount)
        form.addRow("결과", self.result)
        panel_layout.addLayout(form)

        hint = QLabel("기본 세율은 한국 부가가치세(10%) 기준이며, 다른 세율도 직접 입력해 계산할 수 있습니다.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        btn_row = QHBoxLayout()
        copy = QPushButton("결과 복사")
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.result.text()))
        btn_row.addStretch(1)
        btn_row.addWidget(copy)
        panel_layout.addLayout(btn_row)

        layout.addWidget(panel)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        try:
            rate = float(self.rate.text().strip())
            amount = float(self.amount.text().strip())
        except ValueError:
            self.result.setText("")
            return
        if self.mode.currentIndex() == 0:
            tax, total = tax_from_supply(amount, rate)
            self.result.setText(f"세액 {_fmt_number(tax)}  ·  합계금액 {_fmt_number(total)}")
        else:
            supply, tax = tax_from_total(amount, rate)
            self.result.setText(f"공급가액 {_fmt_number(supply)}  ·  세액 {_fmt_number(tax)}")


class ExchangeCalcTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(12)

        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(800)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.mode = QComboBox()
        self.mode.addItems(["기준통화 → 대상통화 (금액 × 환율)", "대상통화 → 기준통화 (금액 ÷ 환율)"])
        self.mode.currentTextChanged.connect(self.refresh)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("예: 100")
        self.amount.textChanged.connect(self.refresh)
        self.rate = QLineEdit()
        self.rate.setPlaceholderText("예: 1350.50 (1기준통화당 대상통화 금액)")
        self.rate.textChanged.connect(self.refresh)
        self.result = QLabel("")
        self.result.setObjectName("cardTitle")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form.addRow("계산 방향", self.mode)
        form.addRow("금액", self.amount)
        form.addRow("환율", self.rate)
        form.addRow("결과", self.result)
        panel_layout.addLayout(form)

        hint = QLabel("실시간 환율을 자동으로 조회하지 않습니다. 오늘의 환율을 직접 입력해 계산하세요.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        btn_row = QHBoxLayout()
        copy = QPushButton("결과 복사")
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.result.text().replace(",", "")))
        btn_row.addStretch(1)
        btn_row.addWidget(copy)
        panel_layout.addLayout(btn_row)

        layout.addWidget(panel)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        try:
            amount = float(self.amount.text().strip())
            rate = float(self.rate.text().strip())
        except ValueError:
            self.result.setText("")
            return
        if rate == 0:
            self.result.setText("환율은 0이 될 수 없어요")
            return
        if self.mode.currentIndex() == 0:
            self.result.setText(_fmt_number(exchange_convert(amount, rate)))
        else:
            self.result.setText(_fmt_number(amount / rate))


class InterestCalcTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, GRID_PANEL_MARGINS[1], 16, 12)
        layout.setSpacing(12)

        panel = QWidget()
        panel.setObjectName("card")
        panel.setMaximumWidth(800)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 16)
        panel_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.mode = QComboBox()
        self.mode.addItems(["단리", "복리"])
        self.mode.currentTextChanged.connect(self.on_mode_changed)
        self.principal = QLineEdit()
        self.principal.setPlaceholderText("예: 1000000")
        self.principal.textChanged.connect(self.refresh)
        self.rate = QLineEdit()
        self.rate.setPlaceholderText("예: 5 (연이율 %)")
        self.rate.textChanged.connect(self.refresh)
        self.months = QLineEdit()
        self.months.setPlaceholderText("예: 12 (개월)")
        self.months.textChanged.connect(self.refresh)
        self.frequency = QComboBox()
        self.frequency.addItems(list(COMPOUND_FREQUENCIES))
        self.frequency.currentTextChanged.connect(self.refresh)
        self.frequency_label = QLabel("복리 주기")
        self.result = QLabel("")
        self.result.setObjectName("cardTitle")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form.addRow("방식", self.mode)
        form.addRow("원금", self.principal)
        form.addRow("연이율(%)", self.rate)
        form.addRow("기간(개월)", self.months)
        form.addRow(self.frequency_label, self.frequency)
        form.addRow("결과", self.result)
        panel_layout.addLayout(form)

        btn_row = QHBoxLayout()
        copy = QPushButton("결과 복사")
        copy.clicked.connect(lambda: self.main.app.clipboard().setText(self.result.text()))
        btn_row.addStretch(1)
        btn_row.addWidget(copy)
        panel_layout.addLayout(btn_row)

        layout.addWidget(panel)
        layout.addStretch(1)
        self.on_mode_changed(self.mode.currentText())

    def on_mode_changed(self, mode: str) -> None:
        is_compound = mode == "복리"
        self.frequency.setVisible(is_compound)
        self.frequency_label.setVisible(is_compound)
        self.refresh()

    def refresh(self) -> None:
        try:
            principal = float(self.principal.text().strip())
            rate = float(self.rate.text().strip())
            months = float(self.months.text().strip())
        except ValueError:
            self.result.setText("")
            return
        if self.mode.currentText() == "단리":
            interest, total = simple_interest(principal, rate, months)
        else:
            n = COMPOUND_FREQUENCIES.get(self.frequency.currentText(), 1)
            interest, total = compound_interest(principal, rate, months, n)
        self.result.setText(f"이자 {_fmt_number(interest)}  ·  원리금 합계 {_fmt_number(total)}")


class CalculatorTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        tabs.addTab(ArithmeticTab(main), "연산 계산")
        tabs.addTab(DateCalcTab(main), "날짜 계산")
        tabs.addTab(UnitConvertTab(main), "단위/진법 변환")
        tabs.addTab(PercentCalcTab(main), "퍼센트 계산")
        tabs.addTab(TaxCalcTab(main), "세금 계산")
        tabs.addTab(ExchangeCalcTab(main), "환율 계산")
        tabs.addTab(InterestCalcTab(main), "이자 계산")
        layout.addWidget(tabs, 1)
