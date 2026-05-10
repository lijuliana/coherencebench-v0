"""Bundle v1+v2 events into the CoherenceBench v0 release.

Outputs to events/:
  - events.jsonl       (one event per line; superset of all atomic events)
  - pairs.jsonl        (complementary pair specs)
  - chains.jsonl       (monotonicity chain specs)
  - conjunctions.jsonl (Frechet bound triple specs: A, B, A∩B)
  - entailments.jsonl  (A ⇒ B specs)
  - manifest.json      (counts + checksums + version)

Run from repo root:  python benchmark/coherencebench_v0/build_release.py
"""
from __future__ import annotations
import dataclasses, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.extended_events_v2 import PAIRS_V2_EVENTS, PAIRS_V2
from src.chains_v2 import CHAIN_V2_EVENTS, CHAINS_V2
from src.conjunctions_v2 import CONJ_V2_NEW_EVENTS, CONJUNCTIONS_V2
from src.entailment_v2 import NEW_B_EVENTS, ENTAILMENTS_V2
from src.extended_events import ALL_PAIR_EVENTS, ALL_CHAIN_EVENTS, EXTENDED_PAIRS, EXTENDED_CHAINS
from src.conjunction_events import TRIPLES as V1_TRIPLES, AB_EVENTS as V1_AB_EVENTS

OUT = Path(__file__).resolve().parent / "events"
OUT.mkdir(parents=True, exist_ok=True)
VERSION = "0.1.0"


def to_dict(e):
    if dataclasses.is_dataclass(e):
        return dataclasses.asdict(e)
    return dict(e)


def normalize_event(e):
    d = to_dict(e)
    d.setdefault("corpus_available", True)
    d.setdefault("source_url", "")
    d.setdefault("keywords", [])
    return d


def main() -> int:
    events = {}
    for src in (PAIRS_V2_EVENTS, CHAIN_V2_EVENTS, CONJ_V2_NEW_EVENTS, NEW_B_EVENTS,
                ALL_PAIR_EVENTS, ALL_CHAIN_EVENTS, V1_AB_EVENTS):
        for e in src:
            d = normalize_event(e)
            events[d["event_id"]] = d
    ev_list = sorted(events.values(), key=lambda x: x["event_id"])

    pairs = []
    for pid, a, b in EXTENDED_PAIRS:
        pairs.append({"pair_id": pid, "a_event": a, "b_event": b, "version": "v1"})
    for pid, a, b in PAIRS_V2:
        pairs.append({"pair_id": pid, "a_event": a, "b_event": b, "version": "v2"})

    chains = []
    for cid, evs in EXTENDED_CHAINS:
        chains.append({"chain_id": cid, "events_tightening": list(evs), "version": "v1"})
    for cid, evs in CHAINS_V2:
        chains.append({"chain_id": cid, "events_tightening": list(evs), "version": "v2"})

    conjunctions = []
    for tid, a, b, ab_event_obj in V1_TRIPLES:
        ab_id = ab_event_obj.event_id if hasattr(ab_event_obj, "event_id") else ab_event_obj["event_id"]
        conjunctions.append({"triple_id": tid, "a_event": a, "b_event": b, "ab_event": ab_id, "version": "v1"})
    for tid, a, b, ab_id in CONJUNCTIONS_V2:
        conjunctions.append({"triple_id": tid, "a_event": a, "b_event": b, "ab_event": ab_id, "version": "v2"})

    entailments = []
    for eid, a, b in ENTAILMENTS_V2:
        entailments.append({"entail_id": eid, "antecedent": a, "consequent": b, "version": "v2"})

    def write_jsonl(name, rows):
        p = OUT / name
        with p.open("w") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        return p

    p_ev = write_jsonl("events.jsonl", ev_list)
    p_pa = write_jsonl("pairs.jsonl", pairs)
    p_ch = write_jsonl("chains.jsonl", chains)
    p_co = write_jsonl("conjunctions.jsonl", conjunctions)
    p_en = write_jsonl("entailments.jsonl", entailments)

    def sha256(p):
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest()

    by_domain = {}
    for e in ev_list:
        by_domain[e["domain"]] = by_domain.get(e["domain"], 0) + 1

    manifest = {
        "name": "CoherenceBench",
        "version": VERSION,
        "license": "CC-BY-4.0",
        "n_events": len(ev_list),
        "n_pairs": len(pairs),
        "n_chains": len(chains),
        "n_chain_events_total": sum(len(c["events_tightening"]) for c in chains),
        "n_conjunctions": len(conjunctions),
        "n_entailments": len(entailments),
        "events_by_domain": by_domain,
        "files": {
            "events.jsonl":       {"sha256": sha256(p_ev), "lines": len(ev_list)},
            "pairs.jsonl":        {"sha256": sha256(p_pa), "lines": len(pairs)},
            "chains.jsonl":       {"sha256": sha256(p_ch), "lines": len(chains)},
            "conjunctions.jsonl": {"sha256": sha256(p_co), "lines": len(conjunctions)},
            "entailments.jsonl":  {"sha256": sha256(p_en), "lines": len(entailments)},
        },
        "schema": {
            "event": ["event_id", "question", "question_open_date", "resolution_date",
                      "outcome", "domain", "source_url", "keywords", "corpus_available"],
            "pair": ["pair_id", "a_event", "b_event", "version"],
            "chain": ["chain_id", "events_tightening", "version"],
            "conjunction": ["triple_id", "a_event", "b_event", "ab_event", "version"],
            "entailment": ["entail_id", "antecedent", "consequent", "version"],
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
