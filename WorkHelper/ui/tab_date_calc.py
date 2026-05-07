from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from app.date_tools import apply_offset, format_date


class DateCalculatorTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        panel = QWidget()
        panel.setMaximumWidth(560)
        form = QFormLayout(panel)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.base_date = QDateEdit()
        self.base_date.setCalendarPopup(True)
        self.base_date.setDate(QDate.currentDate())
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
        calc_widget.setLayout(calc_row)
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
        layout.addWidget(panel)
        row = QHBoxLayout()
        row.setContentsMargins(80, 0, 0, 0)
        row.setSpacing(8)
        calc = QPushButton("계산")
        copy = QPushButton("결과 복사")
        calc.clicked.connect(self.refresh)
        copy.clicked.connect(self.copy_result)
        row.addWidget(calc)
        row.addWidget(copy)
        row.addStretch(1)
        layout.addLayout(row)
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
