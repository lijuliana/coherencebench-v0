"""Example: emit a random-coin (P=0.5) baseline forecast CSV.

Run from inside benchmark/coherencebench_v0/:
    python examples/random_baseline.py > random_baseline.csv
    python scripts/audit.py --forecasts random_baseline.csv --out random_report.json

The random baseline is interesting because the *pair* axis is satisfied by
construction (0.5 + 0.5 = 1) but the *chain* and *Frechet* axes are routinely
violated by Gaussian noise around 0.5.
"""
from __future__ import annotations
import json, random, sys
from pathlib import Path

EVENTS = Path(__file__).resolve().parent.parent / "events" / "events.jsonl"

def main(noise: float = 0.05, seed: int = 0) -> int:
    random.seed(seed)
    print("model,event_id,forecast_mean")
    with EVENTS.open() as f:
        for line in f:
            e = json.loads(line)
            p = max(0.0, min(1.0, 0.5 + random.gauss(0, noise)))
            print(f"random_p0.5_n{noise},{e['event_id']},{p:.4f}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
