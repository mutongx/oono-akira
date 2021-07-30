from datetime import datetime
import sys

def log(s: str):
    print(f"[{datetime.now().isoformat()}] {s}", file=sys.stderr)
