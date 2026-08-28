"""캡처 이미지 속 글자를 텍스트로 뽑아내는 창 (Windows 내장 OCR).

캡처 편집 창과 고정 이미지 창에서 호출한다. 인식은 백그라운드 스레드에서
돌리고, 결과는 편집 가능한 텍스트 상자로 보여 준다 (OCR 은 오인식이 있어
사용자가 바로 손볼 수 있어야 한다).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QBuffer, QIODevice, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import ocr
from ui.common import apply_modern_dialog_style, bottom_action_bar, show_modern_warning

UPSCALE_FACTOR = 2          # 작은 글씨 인식률을 높이려고 확대해서 넘긴다
UPSCALE_MAX_SOURCE = 1600   # 이보다 큰 캡처는 이미 글자가 커서 확대하지 않는다

# 창이 먼저 닫혀도 스레드가 안전하게 끝나도록 붙잡아 둔다.
_ACTIVE_WORKERS: list["_OcrWorker"] = []


def pixmap_to_png(pixmap: QPixmap) -> bytes:
    """OCR 엔진에 넘길 PNG 바이트 — 크기 제한 안에서 최대한 크게 만든다."""
    image = pixmap.toImage()
    if image.isNull():
        return b""
    limit = ocr.max_image_dimension()
    longest = max(image.width(), image.height())
    if longest <= 0:
        return b""
    if longest > limit:
        image = image.scaled(
            int(image.width() * limit / longest),
            int(image.height() * limit / longest),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    elif longest <= UPSCALE_MAX_SOURCE and longest * UPSCALE_FACTOR <= limit:
        image = image.scaled(
            image.width() * UPSCALE_FACTOR,
            image.height() * UPSCALE_FACTOR,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()
    return data


class _OcrWorker(QThread):
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, png_bytes: bytes, language_tag: str) -> None:
        # 부모를 두지 않는다 — 결과 창이 먼저 사라져도 스레드가 함께 삭제되지 않도록.
        super().__init__()
        self._png_bytes = png_bytes
        self._language_tag = language_tag

    def run(self) -> None:
        try:
            lines = ocr.recognize_png(self._png_bytes, self._language_tag)
        except ocr.OcrError as error:
            self.failed.emit(str(error))
        except Exception as error:  # pragma: no cover - 방어
            self.failed.emit(f"글자를 인식하지 못했습니다.\n{error}")
        else:
            self.finished_ok.emit(lines)


def _forget_worker(worker: "_OcrWorker") -> None:
    if worker in _ACTIVE_WORKERS:
        _ACTIVE_WORKERS.remove(worker)


class OcrTextDialog(QDialog):
    """인식 결과를 보여 주고 다듬어서 복사할 수 있는 창."""

    def __init__(self, png_bytes: bytes, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._png_bytes = png_bytes
        self._worker: _OcrWorker | None = None
        self.setWindowTitle("이미지 글자 복사")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(560, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.status = QLabel("글자를 인식하는 중입니다...")
        self.status.setStyleSheet("font-weight: 700;")
        header.addWidget(self.status, 1)

        self.language = QComboBox()
        self.language.setFixedWidth(150)
        languages = ocr.available_languages()
        for tag, display_name in languages:
            self.language.addItem(display_name or tag, tag)
        # 언어가 하나뿐이면 고를 이유가 없다.
        self.language.setVisible(len(languages) > 1)
        self.language.currentIndexChanged.connect(lambda _index: self.start())
        header.addWidget(self.language)
        layout.addLayout(header)

        self.text = QTextEdit()
        self.text.setPlaceholderText("인식된 글자가 여기에 표시됩니다.")
        self.text.setAcceptRichText(False)
        layout.addWidget(self.text, 1)

        hint = QLabel("인식 결과는 바로 고칠 수 있습니다. 필요한 부분만 선택해 Ctrl+C 로 복사해도 됩니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748B;")
        layout.addWidget(hint)

        self.copy_btn = QPushButton("전체 복사")
        self.copy_btn.clicked.connect(self.copy_all)
        self.retry_btn = QPushButton("다시 인식")
        self.retry_btn.clicked.connect(self.start)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.reject)
        layout.addLayout(bottom_action_bar(self.retry_btn, close_btn, self.copy_btn))

        apply_modern_dialog_style(self)

    # ── 인식 ──────────────────────────────────────────────────────

    def start(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_busy(True)
        self.status.setText("글자를 인식하는 중입니다...")
        worker = _OcrWorker(self._png_bytes, self._selected_language())
        worker.finished_ok.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_done)
        worker.finished.connect(lambda done=worker: _forget_worker(done))
        _ACTIVE_WORKERS.append(worker)
        self._worker = worker
        worker.start()

    def _selected_language(self) -> str:
        data = self.language.currentData()
        return str(data or "")

    def _set_busy(self, busy: bool) -> None:
        self.copy_btn.setEnabled(not busy)
        self.retry_btn.setEnabled(not busy)
        self.language.setEnabled(not busy)

    def _on_finished(self, lines: list) -> None:
        text = "\n".join(str(line) for line in lines).strip()
        self.text.setPlainText(text)
        if text:
            self.status.setText(f"{len(lines)}줄을 인식했습니다.")
        else:
            self.status.setText("인식된 글자가 없습니다. 캡처를 더 크게 하거나 다시 시도해 보세요.")

    def _on_failed(self, message: str) -> None:
        self.status.setText("인식하지 못했습니다.")
        show_modern_warning(self, "글자 인식 실패", message)

    def _on_worker_done(self) -> None:
        self._set_busy(False)

    def copy_all(self) -> None:
        text = self.text.toPlainText().strip()
        if not text:
            self.status.setText("복사할 글자가 없습니다.")
            return
        QApplication.clipboard().setText(text)
        self.status.setText("클립보드에 복사했습니다.")

    def closeEvent(self, event) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            # 끝날 때까지 잠깐 기다리고, 그래도 남으면 _ACTIVE_WORKERS 가 붙잡아 둔다.
            worker.wait(3000)
        self._worker = None
        super().closeEvent(event)


def extract_text_from_pixmap(parent: QWidget | None, pixmap: QPixmap) -> None:
    """캡처 이미지에서 글자를 뽑는 창을 띄운다 (사용 불가 환경이면 안내만)."""
    reason = ocr.unavailable_reason()
    if reason:
        show_modern_warning(parent, "글자 인식 불가", reason)
        return
    png_bytes = pixmap_to_png(pixmap)
    if not png_bytes:
        show_modern_warning(parent, "글자 인식 불가", "이미지를 읽지 못했습니다.")
        return
    dialog = OcrTextDialog(png_bytes, parent)
    dialog.start()
    dialog.exec()
