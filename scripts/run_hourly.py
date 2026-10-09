import argparse
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.handler import lambda_handler


def main():
    parser = argparse.ArgumentParser(description="Refresh forecasts. Runs hourly until stopped, or once with --once.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()
    while True:
        try:
            print(lambda_handler({}, None))
        except Exception:
            traceback.print_exc()
        if args.once:
            return
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    main()
