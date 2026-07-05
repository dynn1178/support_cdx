"""pytest 루트 설정 — 프로젝트 루트를 임포트 경로에 올린다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
