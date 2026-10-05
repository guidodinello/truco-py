"""Exp 009 analysis, exactly as pre-registered (docs/experiments/009-retrain-mixed-pool.md).

Reads results/009/*.json (n=4000, seed 20261002, seat-rotated) and writes
results/009/analysis.json. No choices are made here beyond the pre-registered rules; the one
unspecified detail (the CI method for the M - C difference) is the unpooled normal interval,
with the Newcombe (Wilson-based) interval reported alongside as a sensitivity check.
"""

import argparse
import json
import math
from itertools import combinations
from pathlib import Path

from gamekit.mc import benjamini_hochberg, two_proportion_test, wilson_interval

from log import get_logger

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parent.parent
Z95 = 1.959963984540054
ALPHA = 0.05  # H2 and "Control better", tested alone
BH_Q = 0.05  # the M-trend secondary family
NONINFERIORITY_PP = -0.05
H1_FLOOR = 0.5


def load(results: Path, name: str, role: str) -> tuple[int, int, dict]:
    d = json.loads((results / f"{name}.json").read_text())
    r = d["by_role"][role]
    return int(r["wins"]), int(r["n_seat_occupancies"]), d


def rate(k: int, n: int) -> dict:
    ci = wilson_interval(k, n)
    return {"wins": k, "n": n, "rate": k / n, "wilson95": [ci.lower, ci.upper]}


def diff_ci(k1: int, n1: int, k2: int, n2: int) -> dict:
    p1, p2 = k1 / n1, k2 / n2
    d = p1 - p2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    l1, u1 = wilson_interval(k1, n1)
    l2, u2 = wilson_interval(k2, n2)
    newcombe = (
        d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
        d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2),
    )
    return {
        "diff": d,
        "ci95_unpooled": [d - Z95 * se, d + Z95 * se],
        "ci95_newcombe": list(newcombe),
    }


def compare(a: tuple[int, int], b: tuple[int, int]) -> dict:
    t = two_proportion_test(a[0], a[1], b[0], b[1])
    return {"z": t.z, "p_value": t.p_value, **diff_ci(a[0], a[1], b[0], b[1])}


def detector_fired(runs: Path, arm: str) -> bool:
    return any((runs / arm / "ckpt").glob("freeze_*.zip"))


def analyze(results: Path, runs: Path) -> dict:
    rl = {}  # (arm, opp) -> (k, n)
    stamps: dict[str, dict] = {}
    for arm, tag in (("M", "M20M"), ("C", "C20M"), ("bc", "bc"), ("M10", "M10M"), ("M5", "M5M")):
        for opp, short in (("threshold", "thr"), ("von_neumann", "vn"), ("random", "rnd")):
            f = results / f"{tag}_vs_{short}.json"
            if f.exists():
                k, n, d = load(results, f"{tag}_vs_{short}", "rl")
                rl[(arm, opp)] = (k, n)
                stamps[f.stem] = {
                    "checkpoint_sha256_12": d.get("checkpoint_sha256_12"),
                    "voided_hands": d.get("voided_hands"),
                    "git_commit": d.get("git_commit"),
                    "seed": d.get("seed"),
                }
    base_rnd = load(results, "baseline_thr_vs_rnd", "threshold")[:2]
    base_vn = load(results, "baseline_thr_vs_vn", "threshold")[:2]  # Threshold vs VonNeumann

    out: dict = {"results": {}, "tests": {}}
    for (arm, opp), (k, n) in sorted(rl.items()):
        out["results"][f"{arm}_vs_{opp}"] = rate(k, n)
    out["results"]["baseline_threshold_vs_random"] = rate(*base_rnd)
    out["results"]["baseline_threshold_vs_von_neumann"] = rate(*base_vn)
    out["stamps"] = stamps

    m_thr, c_thr = rl[("M", "threshold")], rl[("C", "threshold")]
    m_vn, c_vn = rl[("M", "von_neumann")], rl[("C", "von_neumann")]

    h1_lb = wilson_interval(*m_thr).lower
    out["tests"]["H1"] = {"M_vs_threshold_wilson_lower": h1_lb, "holds": h1_lb > H1_FLOOR}

    h2 = compare(m_vn, c_vn)
    h2["M_beats_C"] = h2["p_value"] < ALPHA and h2["diff"] > 0
    h2["C_beats_M"] = h2["p_value"] < ALPHA and h2["diff"] < 0
    out["tests"]["H2_M_vs_C_against_von_neumann"] = h2

    ni = compare(m_thr, c_thr)
    ni["lower_bound_gt_minus5pp"] = ni["ci95_unpooled"][0] > NONINFERIORITY_PP
    ni["lower_bound_gt_minus5pp_newcombe"] = ni["ci95_newcombe"][0] > NONINFERIORITY_PP
    out["tests"]["noninferiority_M_minus_C_vs_threshold"] = ni

    pts = {"5M": rl[("M5", "threshold")], "10M": rl[("M10", "threshold")], "20M": m_thr}
    pairs = list(combinations(pts, 2))
    cmps = [compare(pts[b], pts[a]) for a, b in pairs]  # later minus earlier
    rejected = benjamini_hochberg([c["p_value"] for c in cmps], q=BH_Q)
    out["tests"]["M_trend_vs_threshold_BH"] = [
        {"later_minus_earlier": f"{b} - {a}", **c, "bh_rejected_q05": r}
        for (a, b), c, r in zip(pairs, cmps, rejected, strict=True)
    ]

    fired = {arm: detector_fired(runs, arm) for arm in ("M", "C")}
    out["detector_fired"] = fired
    if any(fired.values()):
        verdict = "1. Collapsed"
    elif h2["M_beats_C"] and ni["lower_bound_gt_minus5pp"]:
        verdict = "2. Generalises"
    elif h2["M_beats_C"]:
        verdict = "3. Generalises with trade-off"
    elif h2["C_beats_M"]:
        verdict = "4. Control better"
    else:
        verdict = "5. Inconclusive"
    out["verdict"] = verdict
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=ROOT / "results" / "009")
    p.add_argument("--runs", type=Path, default=ROOT / "runs" / "009")
    args = p.parse_args()
    out = analyze(args.results, args.runs)
    (args.results / "analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    logger.info("verdict: %s", out["verdict"])
    print(json.dumps(out, indent=2, sort_keys=True))  # primary product of this script


if __name__ == "__main__":
    main()
