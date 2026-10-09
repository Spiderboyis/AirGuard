import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import db
from ml.features import hour


def pages(table, **params):
    yield from db.select_all(table, **params)


def main():
    actual = {
        (r["station_id"], hour(r["ts"])): r["value"]
        for r in pages("measurements", select="station_id,ts,value", pollutant="eq.pm25", order="ts.asc")
    }
    errors = defaultdict(list)
    for r in pages("forecasts", select="station_id,horizon_h,target_ts,pm25_pred", horizon_h="gt.0", order="target_ts.asc"):
        observed = actual.get((r["station_id"], hour(r["target_ts"])))
        if observed is not None:
            errors[r["horizon_h"]].append(abs(observed - r["pm25_pred"]))
    if not errors:
        print("No stored forecasts overlap measured hours yet.")
        return
    for h in sorted(errors):
        print(f"+{h}h: live MAE {mean(errors[h]):.1f} over {len(errors[h])} forecasts")


if __name__ == "__main__":
    main()
