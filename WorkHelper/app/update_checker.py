from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import requests
from PyQt6.QtWidgets import QMessageBox, QWidget

from app import config


@dataclass
class UpdateInfo:
    latest_version: str
    download_url: str
    release_url: str
    body: str = ""
    asset_name: str = ""


def parse_version(version: str) -> tuple[int, ...]:
    parts = []
    for chunk in version.lstrip("v").split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def fetch_latest_update(current_version: str, repo: str | None = None, token: str | None = None) -> UpdateInfo | None:
    repo_name = repo or os.getenv("WORKHELPER_GITHUB_REPO", "").strip() or config.GITHUB_REPO
    if not repo_name:
        return None
    headers = {"Accept": "application/vnd.github+json"}
    token_value = token or os.getenv("WORKHELPER_GITHUB_TOKEN", "").strip()
    if token_value:
        headers["Authorization"] = f"Bearer {token_value}"

    response = requests.get(f"https://api.github.com/repos/{repo_name}/releases/latest", headers=headers, timeout=8)
    response.raise_for_status()
    payload = response.json()
    latest = payload.get("tag_name", "").lstrip("v")
    if not latest or parse_version(latest) <= parse_version(current_version):
        return None

    assets = payload.get("assets", [])
    exe_asset = next(
        (
            asset
            for asset in assets
            if str(asset.get("name", "")).lower().endswith(".exe") and "updater" not in str(asset.get("name", "")).lower()
        ),
        None,
    )
    asset = exe_asset or (assets[0] if assets else {})
    download_url = asset.get("browser_download_url", "") if asset else payload.get("html_url", "")
    return UpdateInfo(
        latest_version=latest,
        download_url=download_url,
        release_url=payload.get("html_url", ""),
        body=payload.get("body", "") or "",
        asset_name=asset.get("name", "") if asset else "",
    )


def can_self_update(update: UpdateInfo) -> bool:
    updater = config.BASE_DIR / "updater.exe"
    return bool(getattr(sys, "frozen", False) and updater.exists() and update.download_url and update.asset_name.lower().endswith(".exe"))


def download_update(update: UpdateInfo, token: str | None = None) -> Path:
    headers = {}
    token_value = token or os.getenv("WORKHELPER_GITHUB_TOKEN", "").strip()
    if token_value:
        headers["Authorization"] = f"Bearer {token_value}"
    response = requests.get(update.download_url, headers=headers, timeout=60)
    response.raise_for_status()
    target = Path(tempfile.gettempdir()) / f"workhelper_update_{update.latest_version}.exe"
    target.write_bytes(response.content)
    return target


def install_update(update: UpdateInfo, token: str | None = None) -> None:
    new_path = download_update(update, token)
    current_exe = Path(sys.executable)
    updater = config.BASE_DIR / "updater.exe"
    if not updater.exists():
        raise FileNotFoundError("updater.exe 파일을 찾을 수 없습니다.")
    subprocess.Popen([str(updater), str(current_exe), str(new_path), str(current_exe)])
    sys.exit(0)


def update_message(update: UpdateInfo, auto_install: bool) -> str:
    action = "지금 업데이트를 설치할까요?" if auto_install and can_self_update(update) else "다운로드 페이지를 열까요?"
    body = update.body.strip()
    if len(body) > 1200:
        body = body[:1200].rstrip() + "\n..."
    notes = f"\n\n업데이트 내용\n{body}" if body else ""
    return f"새 버전 {update.latest_version}이 사용 가능합니다.\n{action}{notes}"


def check_update_dialog(
    parent: QWidget,
    current_version: str,
    repo: str | None = None,
    auto_install: bool = False,
    silent_no_update: bool = True,
    token: str | None = None,
) -> bool:
    try:
        update = fetch_latest_update(current_version, repo=repo, token=token)
    except Exception as exc:
        if not silent_no_update:
            QMessageBox.warning(parent, "업데이트 확인 실패", str(exc))
        return False

    if not update:
        if not silent_no_update:
            QMessageBox.information(parent, "업데이트 확인", "현재 최신 버전을 사용 중입니다.")
        return False

    choice = QMessageBox.question(parent, "업데이트 확인", update_message(update, auto_install))
    if choice == QMessageBox.StandardButton.Yes:
        if auto_install and can_self_update(update):
            try:
                install_update(update, token=token)
            except Exception as exc:
                QMessageBox.warning(parent, "업데이트 설치 실패", str(exc))
                if update.release_url or update.download_url:
                    webbrowser.open(update.release_url or update.download_url)
        elif update.release_url or update.download_url:
            webbrowser.open(update.release_url or update.download_url)
    return True
