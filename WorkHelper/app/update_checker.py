from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass

import requests
from PyQt6.QtWidgets import QMessageBox, QWidget


@dataclass
class UpdateInfo:
    latest_version: str
    download_url: str


def parse_version(version: str) -> tuple[int, ...]:
    parts = []
    for chunk in version.lstrip("v").split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def fetch_latest_update(current_version: str, repo: str | None = None) -> UpdateInfo | None:
    repo_name = repo or os.getenv("WORKHELPER_GITHUB_REPO", "").strip()
    if not repo_name:
        return None
    url = f"https://api.github.com/repos/{repo_name}/releases/latest"
    res = requests.get(url, timeout=5)
    res.raise_for_status()
    payload = res.json()
    latest = payload.get("tag_name", "").lstrip("v")
    assets = payload.get("assets", [])
    download_url = assets[0].get("browser_download_url", "") if assets else payload.get("html_url", "")
    if latest and parse_version(latest) > parse_version(current_version):
        return UpdateInfo(latest, download_url)
    return None


def check_update_dialog(parent: QWidget, current_version: str) -> None:
    try:
        update = fetch_latest_update(current_version)
    except Exception:
        return
    if not update:
        return
    choice = QMessageBox.question(
        parent,
        "업데이트 확인",
        f"새 버전 {update.latest_version}을 사용할 수 있습니다.\n다운로드 페이지를 열까요?",
    )
    if choice == QMessageBox.StandardButton.Yes and update.download_url:
        webbrowser.open(update.download_url)

