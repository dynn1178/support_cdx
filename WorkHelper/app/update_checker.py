from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from app import config

JUST_UPDATED_FLAG = Path(tempfile.gettempdir()) / "6pma_just_updated.txt"


@dataclass
class UpdateInfo:
    latest_version: str
    download_url: str
    release_url: str
    body: str = ""
    asset_name: str = ""


def normalize_version(version: str) -> str:
    return version.strip().lstrip("\ufeff").strip().lstrip("vV").strip()


def parse_version(version: str) -> tuple[int, ...]:
    normalized = re.split(r"[-+_ ]", normalize_version(version), maxsplit=1)[0]
    parts = []
    for chunk in normalized.split("."):
        match = re.match(r"\d+", chunk)
        parts.append(int(match.group(0)) if match else 0)
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts) if parts else (0,)


def check_just_updated() -> str | None:
    """업데이트 완료 플래그 확인. 새 버전 문자열 반환 후 파일 삭제."""
    if JUST_UPDATED_FLAG.exists():
        try:
            version = JUST_UPDATED_FLAG.read_text(encoding="utf-8").strip()
            JUST_UPDATED_FLAG.unlink(missing_ok=True)
            return version or "최신"
        except Exception:
            pass
    return None


def _build_update_info(payload: dict, current_version: str) -> UpdateInfo | None:
    latest = normalize_version(str(payload.get("tag_name", "")))
    if not latest or parse_version(latest) <= parse_version(current_version):
        return None
    assets = payload.get("assets", [])
    zip_asset = next(
        (a for a in assets if str(a.get("name", "")).lower().endswith(".zip")),
        None,
    )
    exe_asset = next(
        (a for a in assets if str(a.get("name", "")).lower().endswith(".exe") and "updater" not in str(a.get("name", "")).lower()),
        None,
    )
    asset = zip_asset or exe_asset or (assets[0] if assets else {})
    download_url = asset.get("browser_download_url", "") if asset else payload.get("html_url", "")
    return UpdateInfo(
        latest_version=latest,
        download_url=download_url,
        release_url=payload.get("html_url", ""),
        body=payload.get("body", "") or "",
        asset_name=asset.get("name", "") if asset else "",
    )


def _fetch_release_payload(repo: str | None = None, token: str | None = None) -> dict | None:
    repo_name = repo or os.getenv("WORKHELPER_GITHUB_REPO", "").strip() or config.GITHUB_REPO
    if not repo_name:
        return None
    headers = {"Accept": "application/vnd.github+json"}
    token_value = token or os.getenv("WORKHELPER_GITHUB_TOKEN", "").strip()
    if token_value:
        headers["Authorization"] = f"Bearer {token_value}"
    response = requests.get(f"https://api.github.com/repos/{repo_name}/releases/latest", headers=headers, timeout=8)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def fetch_latest_update(current_version: str, repo: str | None = None, token: str | None = None) -> UpdateInfo | None:
    payload = _fetch_release_payload(repo, token)
    if not payload:
        return None
    return _build_update_info(payload, current_version)


def fetch_latest_info(current_version: str, repo: str | None = None, token: str | None = None) -> tuple[str | None, UpdateInfo | None]:
    """(최신버전 문자열, 업데이트 정보) 반환. 업데이트 없으면 update_info=None."""
    payload = _fetch_release_payload(repo, token)
    if not payload:
        return None, None
    latest = payload.get("tag_name", "").lstrip("v") or None
    update = _build_update_info(payload, current_version)
    return latest, update


def _resolve_updater() -> Path | None:
    side_by_side = config.BASE_DIR / "updater.exe"
    if side_by_side.exists():
        return side_by_side
    return None


def can_self_update(update: UpdateInfo) -> bool:
    if not getattr(sys, "frozen", False):
        return False
    if not update.download_url or not update.asset_name.lower().endswith((".exe", ".zip")):
        return False
    return _resolve_updater() is not None


def _download_suffix(update: UpdateInfo) -> str:
    name = update.asset_name.lower()
    if name.endswith(".zip"):
        return ".zip"
    return ".exe"


def _prepare_downloaded_update(path: Path) -> Path:
    if path.suffix.lower() != ".zip":
        return path

    extract_dir = Path(tempfile.gettempdir()) / f"6pma_update_extract_{path.stem}"
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path) as archive:
        archive.extractall(extract_dir)

    new_exe = extract_dir / "6PM Assistant.exe"
    if not new_exe.exists():
        candidates = [candidate for candidate in extract_dir.rglob("*.exe") if candidate.name.lower() != "updater.exe"]
        if candidates:
            new_exe = candidates[0]
    if not new_exe.exists():
        raise FileNotFoundError("zip 안에서 6PM Assistant.exe를 찾을 수 없습니다.")

    new_updater = extract_dir / "updater.exe"
    current_updater = _resolve_updater()
    if new_updater.exists() and current_updater:
        shutil.copy2(new_updater, current_updater)

    return new_exe


# ── 다운로드 스레드 ──────────────────────────────────────────────────────────

class _DownloadThread(QThread):
    progress = pyqtSignal(int)      # 0-100
    finished = pyqtSignal(object)   # Path
    failed = pyqtSignal(str)

    def __init__(self, update: UpdateInfo, token: str | None = None) -> None:
        super().__init__()
        self.update = update
        self.token = token

    def run(self) -> None:
        try:
            headers: dict = {}
            token_value = self.token or os.getenv("WORKHELPER_GITHUB_TOKEN", "").strip()
            if token_value:
                headers["Authorization"] = f"Bearer {token_value}"
            with requests.get(self.update.download_url, headers=headers, timeout=120, stream=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                target = Path(tempfile.gettempdir()) / f"6pma_update_{self.update.latest_version}{_download_suffix(self.update)}"
                downloaded = 0
                with target.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self.progress.emit(int(downloaded * 100 / total))
            self.progress.emit(100)
            self.finished.emit(target)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── 다운로드 진행 다이얼로그 ─────────────────────────────────────────────────

class DownloadProgressDialog(QDialog):
    def __init__(self, parent: QWidget, update: UpdateInfo, token: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("업데이트 다운로드")
        self.setModal(True)
        self.setFixedSize(400, 130)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._path: Path | None = None
        self._error: str | None = None

        # 스타일 (dialog_palette 지연 import)
        try:
            from ui.common import dialog_palette
            colors = dialog_palette(parent)
        except Exception:
            colors = {"panel": "#ffffff", "border": "#dddddd", "text": "#222222",
                      "accent": "#3B6CF5", "field": "#f5f5f5"}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        self._label = QLabel(f"v{update.latest_version} 다운로드 중...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(18)

        layout.addWidget(self._label)
        layout.addWidget(self._bar)

        self.setStyleSheet(f"""
            QDialog {{
                background: {colors["panel"]};
                border: 1px solid {colors["border"]};
                border-radius: 10px;
            }}
            QLabel {{
                color: {colors["text"]};
                font-size: 10pt;
            }}
            QProgressBar {{
                border: 1px solid {colors["border"]};
                border-radius: 6px;
                background: {colors["field"]};
                text-align: center;
                color: {colors["text"]};
            }}
            QProgressBar::chunk {{
                background: {colors["accent"]};
                border-radius: 5px;
            }}
        """)

        self._thread = _DownloadThread(update, token)
        self._thread.progress.connect(self._bar.setValue)
        self._thread.finished.connect(self._on_finished)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_finished(self, path: Path) -> None:
        self._path = path
        self._label.setText("다운로드 완료! 설치를 시작합니다...")
        self.accept()

    def _on_failed(self, error: str) -> None:
        self._error = error
        self.reject()

    @property
    def result_path(self) -> Path | None:
        return self._path

    @property
    def error(self) -> str | None:
        return self._error


# ── 설치 / 다이얼로그 함수 ────────────────────────────────────────────────────

def install_update(parent: QWidget, update: UpdateInfo, token: str | None = None) -> None:
    """진행 바를 보여주면서 다운로드 후 updater 실행."""
    dlg = DownloadProgressDialog(parent, update, token)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        if dlg.error:
            raise RuntimeError(dlg.error)
        return

    downloaded_path = dlg.result_path
    new_path = _prepare_downloaded_update(downloaded_path) if downloaded_path else None
    if not new_path:
        raise RuntimeError("다운로드된 파일을 찾을 수 없습니다.")

    current_exe = Path(sys.executable)
    updater = _resolve_updater()
    if not updater:
        raise FileNotFoundError("updater.exe를 찾을 수 없습니다.")

    subprocess.Popen([str(updater), str(current_exe), str(new_path), str(current_exe), update.latest_version])
    sys.exit(0)


class _UpdateStatusDialog(QDialog):
    """버전 정보 + 업데이트 상태를 통합 표시하는 다이얼로그."""

    def __init__(self, parent: QWidget, current_version: str, latest_version: str | None, update: UpdateInfo | None) -> None:
        super().__init__(parent)
        self.setWindowTitle("업데이트 확인")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.confirmed = False

        try:
            from ui.common import dialog_palette
            colors = dialog_palette(parent)
        except Exception:
            colors = {"panel": "#ffffff", "border": "#dddddd", "text": "#222222",
                      "accent": "#3B6CF5", "field": "#f5f5f5", "danger": "#E05353", "bg": "#F0F2F5"}

        has_update = update is not None
        self_install = has_update and can_self_update(update)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)

        title_lbl = QLabel("업데이트 확인")
        title_lbl.setObjectName("usd_title")
        layout.addWidget(title_lbl)

        # 버전 정보 그리드
        info_widget = QWidget()
        info_widget.setObjectName("usd_info_box")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        def info_row(label: str, value: str, value_object_name: str = "") -> None:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setObjectName("usd_key")
            lbl.setFixedWidth(72)
            val = QLabel(value)
            if value_object_name:
                val.setObjectName(value_object_name)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            info_layout.addLayout(row)

        info_row("현재 버전", f"v{current_version}")
        if latest_version:
            info_row("최신 버전", f"v{latest_version}")
        if has_update:
            info_row("상태", "새 버전이 출시되었습니다", "usd_status_update")
        else:
            info_row("상태", "최신 버전을 사용 중입니다  ✓", "usd_status_ok")

        layout.addWidget(info_widget)

        # 릴리즈 노트 (업데이트 있을 때만)
        body = (update.body or "").strip() if update else ""
        if body:
            if len(body) > 800:
                body = body[:800].rstrip() + "\n..."
            notes_label = QLabel("업데이트 내용")
            notes_label.setObjectName("usd_notes_title")
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(110)
            inner = QLabel(body)
            inner.setWordWrap(True)
            inner.setContentsMargins(6, 4, 6, 4)
            inner.setAlignment(Qt.AlignmentFlag.AlignTop)
            scroll.setWidget(inner)
            layout.addWidget(notes_label)
            layout.addWidget(scroll)

        if has_update:
            manual_hint = QLabel("자동 업데이트가 실패할 경우 홈페이지에서 직접 다운로드를 통해 수동으로 진행해주세요.")
            manual_hint.setObjectName("usd_manual_hint")
            manual_hint.setWordWrap(True)
            layout.addWidget(manual_hint)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if has_update:
            cancel_btn = QToolButton()
            cancel_btn.setText("나중에")
            cancel_btn.setFixedHeight(32)
            cancel_btn.setObjectName("usd_btn_secondary")
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)
            confirm_btn = QToolButton()
            confirm_btn.setText("지금 업데이트" if self_install else "업데이트 불가")
            confirm_btn.setFixedHeight(32)
            confirm_btn.setEnabled(self_install)
            confirm_btn.clicked.connect(self._on_confirm)
            btn_row.addWidget(confirm_btn)
        else:
            ok_btn = QToolButton()
            ok_btn.setText("확인")
            ok_btn.setFixedHeight(32)
            ok_btn.clicked.connect(self.accept)
            btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        accent = colors.get("accent", "#3B6CF5")
        ok_color = "#2BA05A"
        update_color = colors.get("danger", "#E05353")
        self.setStyleSheet(f"""
            QDialog {{
                background: {colors["panel"]};
                border: 1px solid {colors["border"]};
                border-radius: 10px;
            }}
            QLabel {{ color: {colors["text"]}; font-size: 10pt; }}
            QLabel#usd_title {{
                color: {accent};
                font-size: 14pt;
                font-weight: 900;
            }}
            QWidget#usd_info_box {{
                background: {colors.get("field", colors.get("bg", "#F0F2F5"))};
                border: 1px solid {colors["border"]};
                border-radius: 7px;
            }}
            QLabel#usd_key {{
                color: {colors["text"]};
                font-size: 9pt;
                opacity: 0.7;
            }}
            QLabel#usd_status_ok {{ color: {ok_color}; font-weight: 700; }}
            QLabel#usd_status_update {{ color: {update_color}; font-weight: 700; }}
            QLabel#usd_notes_title {{
                color: {colors["text"]};
                font-weight: 700;
                font-size: 9pt;
            }}
            QLabel#usd_manual_hint {{
                color: {colors.get("muted", colors["text"])};
                font-size: 9pt;
                background: transparent;
            }}
            QScrollArea {{
                border: 1px solid {colors["border"]};
                border-radius: 6px;
                background: {colors.get("field", "#f5f5f5")};
            }}
            QScrollArea QLabel {{
                background: {colors.get("field", "#f5f5f5")};
                font-size: 9pt;
            }}
            QToolButton {{
                background: {accent};
                color: white;
                border: 0;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 800;
            }}
            QToolButton#usd_btn_secondary {{
                background: {colors["border"]};
                color: {colors["text"]};
            }}
        """)
        base_height = 220
        if body:
            base_height += 140
        if has_update:
            base_height += 34
        self.resize(400, base_height)

    def _on_confirm(self) -> None:
        self.confirmed = True
        self.accept()


def check_update_dialog(
    parent: QWidget,
    current_version: str,
    repo: str | None = None,
    auto_install: bool = False,
    silent_no_update: bool = True,
    token: str | None = None,
) -> bool:
    try:
        if silent_no_update:
            update = fetch_latest_update(current_version, repo=repo, token=token)
            latest_version = update.latest_version if update else None
        else:
            latest_version, update = fetch_latest_info(current_version, repo=repo, token=token)
    except Exception as exc:
        if not silent_no_update:
            QMessageBox.warning(parent, "업데이트 확인 실패", str(exc))
        return False

    if silent_no_update and not update:
        return False

    dlg = _UpdateStatusDialog(parent, current_version, latest_version, update)
    dlg.exec()
    if dlg.confirmed and update:
        if can_self_update(update):
            try:
                install_update(parent, update, token=token)
            except Exception as exc:
                QMessageBox.warning(parent, "업데이트 설치 실패", str(exc))
        else:
            QMessageBox.warning(
                parent,
                "업데이트 설치 불가",
                "현재 실행 환경에서는 자동 업데이트를 진행할 수 없습니다.\n"
                "배포된 exe에서 다시 시도해주세요.",
            )
    return update is not None
