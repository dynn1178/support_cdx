from __future__ import annotations

import shutil
import subprocess
import sys
import time


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: updater.py <old_path> <new_path> <restart_path>")
        return 2
    old_path, new_path, restart_path = sys.argv[1], sys.argv[2], sys.argv[3]
    time.sleep(1)
    shutil.move(new_path, old_path)
    subprocess.Popen([restart_path])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

