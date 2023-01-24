import os
import sys
from datetime import datetime

DEBUG = os.environ.get("OONO_DEBUG") in {"1", "ON"}


def log(s: str, debug: bool = False):
    if not debug or debug and DEBUG:
        print(f"[{datetime.now().isoformat()}] {s}", file=sys.stderr)
