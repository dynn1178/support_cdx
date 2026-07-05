from __future__ import annotations

"""설정/프리셋 자동 백업.

backups/ 아래에 타임스탬프 zip으로 settings.json, 템플릿, 클립보드 이력을
보관한다. 시작 시 auto_backup_if_due()가 주기를 확인해 새 백업을 만들고,
오래된 백업은 MAX_BACKUPS개까지만 남긴다.
"""

import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from . import config
from .logger import get_logger

log = get_logger("backup")

BACKUP_DIR = config.BASE_DIR / "backups"
MAX_BACKUPS = 10
AUTO_BACKUP_INTERVAL_HOURS = 24

_BACKUP_TARGETS = ("settings.json", "clipboard_history.json")


def list_backups() -> list[Path]:
    """최신순으로 정렬된 백업 zip 목록."""
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)


def create_backup() -> Path | None:
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"backup_{timestamp}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in _BACKUP_TARGETS:
                path = config.DATA_DIR / name
                if path.exists():
                    archive.write(path, name)
            if config.TEMPLATE_DIR.exists():
                for template in sorted(config.TEMPLATE_DIR.glob("template_*.json")):
                    archive.write(template, f"templates/{template.name}")
        _prune_old_backups()
        log.info("backup created: %s", target.name)
        return target
    except Exception:
        log.error("backup failed", exc_info=True)
        return None


def _prune_old_backups() -> None:
    for stale in list_backups()[MAX_BACKUPS:]:
        try:
            stale.unlink()
        except Exception:
            log.debug("failed to prune backup %s", stale, exc_info=True)


def auto_backup_if_due(interval_hours: int = AUTO_BACKUP_INTERVAL_HOURS) -> Path | None:
    """마지막 백업이 interval보다 오래됐으면 새 백업을 만든다."""
    backups = list_backups()
    if backups:
        try:
            newest = datetime.fromtimestamp(backups[0].stat().st_mtime)
            if datetime.now() - newest < timedelta(hours=interval_hours):
                return None
        except OSError:
            pass
    return create_backup()


def restore_backup(backup_path: str | Path) -> None:
    """백업 zip의 내용으로 data/를 되돌린다.

    복원 직전 현재 상태를 임시 디렉터리에 복사해 두고, 압축 해제에 실패하면
    되돌린다. 호출자는 복원 후 앱 재시작(또는 데이터 리로드)을 안내해야 한다.
    """
    backup_path = Path(backup_path)
    with zipfile.ZipFile(backup_path) as archive:
        names = archive.namelist()
        safety = Path(tempfile.mkdtemp(prefix="6pma_restore_undo_"))
        for name in _BACKUP_TARGETS:
            src = config.DATA_DIR / name
            if src.exists():
                shutil.copy2(src, safety / name)
        if config.TEMPLATE_DIR.exists():
            shutil.copytree(config.TEMPLATE_DIR, safety / "templates", dirs_exist_ok=True)
        try:
            for name in names:
                # zip 경로 탈출 방지
                destination = (config.DATA_DIR / name).resolve()
                if not str(destination).startswith(str(config.DATA_DIR.resolve())):
                    raise ValueError(f"잘못된 백업 항목: {name}")
            archive.extractall(config.DATA_DIR)
            log.info("backup restored: %s", backup_path.name)
        except Exception:
            # 실패 시 원상 복구
            for name in _BACKUP_TARGETS:
                saved = safety / name
                if saved.exists():
                    shutil.copy2(saved, config.DATA_DIR / name)
            saved_templates = safety / "templates"
            if saved_templates.exists():
                shutil.copytree(saved_templates, config.TEMPLATE_DIR, dirs_exist_ok=True)
            log.error("restore failed — rolled back", exc_info=True)
            raise
