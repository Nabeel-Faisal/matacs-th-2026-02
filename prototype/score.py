"""Deterministic proposal scoring. Standard library only, no network calls.

Reads facts.json and criteria.json from this folder, writes ../ranking.json,
and prints a per-criterion breakdown.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTS_PATH = HERE / "facts.json"
CRITERIA_PATH = HERE / "criteria.json"
RANKING_PATH = HERE.parent / "ranking.json"

MANDATORY = ("licence", "wsib", "insurance_5m")
CRITERIA = ("experience", "price", "timeline", "warranty", "team")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ratio(num, den):
    # If every eligible proposal ties (den == 0), they all get full marks.
    return 1.0 if den == 0 else num / den


def check_eligibility(f, crit):
    """Return a list of reasons the proposal is ineligible (empty if eligible)."""
    problems = [f"missing {key}" for key in MANDATORY if not f[key]]
    if problems:
        return problems
    if f["price"] > crit["budget_ceiling"]:
        problems.append(f"price ${f['price']:,} over ${crit['budget_ceiling']:,} ceiling")
    if f["weeks"] is not None and f["weeks"] > crit["max_weeks"]:
        problems.append(f"{f['weeks']} weeks over {crit['max_weeks']}-week max")
    return problems


def check_flags(f):
    flags = []
    if f["injection_detected"]:
        flags.append("prompt injection detected")
    if f["weeks"] is None:
        flags.append("no timeline given")
    if not f["installs_within_5yrs_verified"]:
        flags.append("installs within 5 yrs unverified")
    return flags


def score_all(eligible, crit):
    """Score each eligible proposal. Returns {pid: {criterion: part 0-1 or None}}."""
    ceiling = crit["budget_ceiling"]
    max_weeks = crit["max_weeks"]
    max_installs = max(f["installs"] for f in eligible.values())
    min_price = min(f["price"] for f in eligible.values())
    known_weeks = [f["weeks"] for f in eligible.values() if f["weeks"] is not None]
    min_weeks = min(known_weeks) if known_weeks else None
    max_panel = max(f["panel_warranty"] for f in eligible.values())
    max_work = max(f["workmanship_warranty"] for f in eligible.values())

    parts = {}
    for pid, f in eligible.items():
        timeline = None
        if f["weeks"] is not None:
            timeline = ratio(max_weeks - f["weeks"], max_weeks - min_weeks)
        parts[pid] = {
            "experience": ratio(f["installs"], max_installs),
            "price": ratio(ceiling - f["price"], ceiling - min_price),
            "timeline": timeline,
            "warranty": 0.5 * ratio(f["panel_warranty"], max_panel)
            + 0.5 * ratio(f["workmanship_warranty"], max_work),
            "team": sum(bool(v) for v in f["team"].values()) / 4,
        }
    return parts


def total(part, weights):
    # A criterion that can't be scored (None) contributes 0.
    return round(sum((part[c] or 0) * weights[c] for c in CRITERIA), 1)


def main():
    facts = load(FACTS_PATH)
    crit = load(CRITERIA_PATH)
    weights = crit["weights"]

    ineligible = {}
    for pid, f in facts.items():
        problems = check_eligibility(f, crit)
        if problems:
            ineligible[pid] = problems
    eligible = {pid: f for pid, f in facts.items() if pid not in ineligible}

    parts = score_all(eligible, crit) if eligible else {}
    scores = {pid: total(p, weights) for pid, p in parts.items()}

    ranked, flagged, rejected = [], [], []
    for pid in sorted(facts):
        if pid in ineligible:
            rejected.append({
                "proposal": pid, "rank": None, "status": "ineligible", "score": None,
                "reason": "Ineligible: " + "; ".join(ineligible[pid]) + ".",
            })
            continue
        flags = check_flags(facts[pid])
        if flags:
            note = " (timeline scored 0)" if parts[pid]["timeline"] is None else ""
            flagged.append({
                "proposal": pid, "rank": None, "status": "flagged", "score": None,
                "reason": "Needs review: " + "; ".join(flags)
                + f". Provisional score {scores[pid]}{note}.",
            })
        else:
            ranked.append({
                "proposal": pid, "rank": None, "status": "ranked", "score": scores[pid],
                "reason": f"Passes all gates; scored {scores[pid]}.",
            })

    ranked.sort(key=lambda r: (-r["score"], r["proposal"]))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    flagged.sort(key=lambda r: (-scores[r["proposal"]], r["proposal"]))

    results = ranked + flagged + rejected
    with open(RANKING_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    # Breakdown: weighted points per criterion.
    print(f"Criteria version: {crit['version']}")
    print("Weights: " + ", ".join(f"{c} {weights[c]}" for c in CRITERIA))
    print()
    header = f"{'Prop':<5}{'Status':<12}" + "".join(f"{c.capitalize():>12}" for c in CRITERIA) + f"{'Total':>9}"
    print(header)
    print("-" * len(header))
    for r in results:
        pid = r["proposal"]
        row = f"{pid:<5}{r['status']:<12}"
        if pid in parts:
            for c in CRITERIA:
                v = parts[pid][c]
                row += f"{'n/a':>12}" if v is None else f"{v * weights[c]:>12.1f}"
            label = f"{scores[pid]}" + ("*" if r["status"] == "flagged" else "")
            row += f"{label:>9}"
        else:
            row += "".join(f"{'-':>12}" for _ in CRITERIA) + f"{'-':>9}"
        print(row)
    print()
    print("* provisional score, not ranked; n/a = not scorable (counts as 0)")
    print()
    for r in results:
        rank = r["rank"] if r["rank"] is not None else "-"
        print(f"{r['proposal']}  rank {rank:<2} {r['status']:<11} {r['reason']}")
    print()
    print(f"Wrote {RANKING_PATH}")


if __name__ == "__main__":
    main()
