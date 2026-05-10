from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time

JUST_UPDATED_FLAG = os.path.join(tempfile.gettempdir(), "6pma_just_updated.txt")


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: updater <old_path> <new_path> <restart_path> [version]")
        return 2

    old_path = sys.argv[1]
    new_path = sys.argv[2]
    restart_path = sys.argv[3]
    version = sys.argv[4] if len(sys.argv) >= 5 else ""

    # 앱이 완전히 종료될 때까지 대기 (최대 10초, 1초 간격 재시도)
    time.sleep(2)
    replaced = False
    for attempt in range(8):
        try:
            shutil.move(new_path, old_path)
            replaced = True
            break
        except Exception:
            time.sleep(1)

    if not replaced:
        return 1

    # 업데이트 완료 플래그 파일 기록 (앱 재시작 시 "업데이트 완료" 메시지 표시용)
    try:
        with open(JUST_UPDATED_FLAG, "w", encoding="utf-8") as f:
            f.write(version)
    except Exception:
        pass

    subprocess.Popen([restart_path])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
