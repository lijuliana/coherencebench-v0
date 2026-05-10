"""Stand-alone CoherenceBench audit.

Inputs: a CSV of forecasts (model, event_id, forecast_mean) and the bundled
events/*.jsonl files. Outputs: a JSON report of per-axis violation rates
plus per-model breakdown.

Usage:
    python audit.py --forecasts forecasts.csv --events ../events --out report.json

The forecasts CSV must have columns:  model, event_id, forecast_mean
(extra columns are ignored).

Definitions:
    Pair violation:      |P(A) + P(B) - 1| > tau                     (tau=0.05 default)
    Chain violation:     ∃ i<j with P(e_j) > P(e_i) + tau
                         where e_j is strictly tighter than e_i
    Conjunction (Frechet) violation:
                         P(A∩B) < max(0, P(A)+P(B)-1) - tau
                         OR  P(A∩B) > min(P(A), P(B)) + tau
    Entailment violation: P(A) > P(B) + tau   when A ⇒ B
"""
from __future__ import annotations
import argparse, csv, json
from collections import defaultdict
from pathlib import Path


def load_jsonl(p):
    with Path(p).open() as f:
        return [json.loads(l) for l in f if l.strip()]


def load_forecasts(p):
    """Return dict[(model, event_id)] -> forecast_mean (float in [0,1])."""
    out = {}
    with Path(p).open() as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                v = float(row["forecast_mean"])
            except (KeyError, ValueError):
                continue
            v = max(0.0, min(1.0, v))
            out[(row["model"], row["event_id"])] = v
    return out


def audit(forecasts, events_dir, tau=0.05):
    events_dir = Path(events_dir)
    pairs = load_jsonl(events_dir / "pairs.jsonl")
    chains = load_jsonl(events_dir / "chains.jsonl")
    conjs = load_jsonl(events_dir / "conjunctions.jsonl")
    ents = load_jsonl(events_dir / "entailments.jsonl")

    models = sorted({m for (m, _) in forecasts.keys()})
    report = {"tau": tau, "n_models": len(models),
              "structures": {"pairs": len(pairs), "chains": len(chains),
                             "conjunctions": len(conjs), "entailments": len(ents)},
              "by_model": {}}

    overall = defaultdict(lambda: {"pair_n": 0, "pair_v": 0,
                                   "chain_n": 0, "chain_v": 0,
                                   "conj_n": 0, "conj_v": 0,
                                   "ent_n": 0, "ent_v": 0})

    for m in models:
        get = lambda eid, _m=m: forecasts.get((_m, eid))

        for pair in pairs:
            a, b = get(pair["a_event"]), get(pair["b_event"])
            if a is None or b is None: continue
            overall[m]["pair_n"] += 1
            if abs(a + b - 1.0) > tau:
                overall[m]["pair_v"] += 1

        for chain in chains:
            evs = chain["events_tightening"]
            ps = [get(e) for e in evs]
            if any(p is None for p in ps): continue
            overall[m]["chain_n"] += 1
            for i in range(len(ps)):
                for j in range(i+1, len(ps)):
                    if ps[j] > ps[i] + tau:
                        overall[m]["chain_v"] += 1
                        break
                else:
                    continue
                break

        for c in conjs:
            a, b, ab = get(c["a_event"]), get(c["b_event"]), get(c["ab_event"])
            if a is None or b is None or ab is None: continue
            lo = max(0.0, a + b - 1.0)
            hi = min(a, b)
            overall[m]["conj_n"] += 1
            if ab < lo - tau or ab > hi + tau:
                overall[m]["conj_v"] += 1

        for e in ents:
            a, b = get(e["antecedent"]), get(e["consequent"])
            if a is None or b is None: continue
            overall[m]["ent_n"] += 1
            if a > b + tau:
                overall[m]["ent_v"] += 1

    for m, d in overall.items():
        d["pair_rate"]  = (d["pair_v"]/d["pair_n"])  if d["pair_n"]  else None
        d["chain_rate"] = (d["chain_v"]/d["chain_n"]) if d["chain_n"] else None
        d["conj_rate"]  = (d["conj_v"]/d["conj_n"])  if d["conj_n"]  else None
        d["ent_rate"]   = (d["ent_v"]/d["ent_n"])   if d["ent_n"]   else None
        report["by_model"][m] = d

    # Aggregate (mean across models, weighted by structure count)
    def agg(key_n, key_v):
        n = sum(d[key_n] for d in overall.values())
        v = sum(d[key_v] for d in overall.values())
        return v / n if n else None
    report["aggregate"] = {
        "pair_violation_rate":  agg("pair_n", "pair_v"),
        "chain_violation_rate": agg("chain_n", "chain_v"),
        "conj_violation_rate":  agg("conj_n", "conj_v"),
        "ent_violation_rate":   agg("ent_n", "ent_v"),
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forecasts", required=True, help="CSV with columns model,event_id,forecast_mean")
    ap.add_argument("--events", default=str(Path(__file__).resolve().parent.parent / "events"))
    ap.add_argument("--out", default="report.json")
    ap.add_argument("--tau", type=float, default=0.05, help="Slack for violation indicator")
    args = ap.parse_args()

    forecasts = load_forecasts(args.forecasts)
    print(f"loaded {len(forecasts)} forecasts across {len({m for m,_ in forecasts})} models")
    report = audit(forecasts, args.events, tau=args.tau)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"wrote {args.out}")
    print("\nAggregate violation rates:")
    for k, v in report["aggregate"].items():
        print(f"  {k:<28} {v:.3f}" if v is not None else f"  {k:<28} (no data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
