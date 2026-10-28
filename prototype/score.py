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
MAX_REASON = 200
ORDINALS = ("Top scorer", "Second", "Third", "Fourth", "Fifth")

# Wording for coded fields in facts.json (our own words, not proposal text).
MISSING_TEXT = {
    "licence": "bidder holds no valid licence",
    "wsib": "no WSIB clearance",
    "insurance_5m": "no $5M liability insurance",
}
LICENCE_HOLDER_TEXT = {
    "subcontractor_tbc": "licence is not held by the bidder (only an unnamed "
                         "subcontractor to be confirmed after award)",
}
INJECTION_GOAL_TEXT = {
    "rank_first": "rank it first",
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ratio(num, den):
    # If every eligible proposal ties (den == 0), they all get full marks.
    return 1.0 if den == 0 else num / den


def join_words(items):
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def team_count(f):
    return sum(bool(v) for v in f["team"].values())


def check_eligibility(f, crit):
    """Return a list of reasons the proposal is ineligible (empty if eligible)."""
    problems = []
    for key in MANDATORY:
        if f[key]:
            continue
        if key == "licence" and f.get("licence_holder") in LICENCE_HOLDER_TEXT:
            problems.append(LICENCE_HOLDER_TEXT[f["licence_holder"]])
        else:
            problems.append(MISSING_TEXT[key])
    if problems:
        return problems
    if f["price"] > crit["budget_ceiling"]:
        problems.append(f"price ${f['price']:,} is over the ${crit['budget_ceiling']:,} ceiling")
    if f["weeks"] is not None and f["weeks"] > crit["max_weeks"]:
        problems.append(f"{f['weeks']} weeks is over the {crit['max_weeks']}-week limit")
    return problems


def check_flags(f, crit):
    """Return (flag clauses, needs_human_review) for a proposal."""
    flags = []
    human = False
    if f["injection_detected"]:
        goal = INJECTION_GOAL_TEXT.get(f.get("injection_goal"), "change the outcome")
        flags.append(f"contains text instructing automated reviewers to {goal}")
        human = True
    if f["weeks"] is None:
        flags.append(f"no completion timeline given, so the {crit['max_weeks']}-week "
                     "limit can't be checked")
    if not f["installs_within_5yrs_verified"]:
        since = f.get("installs_counted_since")
        if since:
            flags.append(f"experience counted since {since} may fall outside the 5-year window")
        else:
            flags.append("installs within the 5-year window are unverified")
        human = True
    return flags, human


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
            "team": team_count(f) / 4,
        }
    return parts


def total(part, weights):
    # A criterion that can't be scored (None) contributes 0.
    return round(sum((part[c] or 0) * weights[c] for c in CRITERIA), 1)


# --- Reason wording -------------------------------------------------------

def strength_text(c, f):
    """Phrase for a criterion where this proposal is best among eligible ones."""
    if c == "experience":
        return f"most installs ({f['installs']})"
    if c == "price":
        return f"lowest price (${f['price']:,})"
    if c == "timeline":
        return f"fastest timeline ({f['weeks']} wks)"
    if c == "warranty":
        return f"best warranty ({f['panel_warranty']}-yr panel, {f['workmanship_warranty']}-yr workmanship)"
    n = team_count(f)
    return "full team checklist" if n == 4 else f"best team checklist ({n}/4)"


def compare_text(c, better, worse, from_better):
    """Phrase for where `better` beats `worse` on criterion c.

    from_better=True  -> "longer workmanship warranty (12 vs 10 yrs)"
    from_better=False -> "fewer installs (8 vs 14)"
    """
    if c == "experience":
        words, key, pre, unit = ("more installs", "fewer installs"), "installs", "", ""
    elif c == "price":
        words, key, pre, unit = ("lower price", "higher price"), "price", "$", ""
    elif c == "timeline":
        words, key, pre, unit = ("shorter timeline", "longer timeline"), "weeks", "", " wks"
    elif c == "warranty":
        kind = "workmanship" if better["workmanship_warranty"] != worse["workmanship_warranty"] else "panel"
        words = (f"longer {kind} warranty", f"shorter {kind} warranty")
        key, pre, unit = f"{kind}_warranty", "", " yrs"
    else:
        a, b = team_count(better), team_count(worse)
        words = ("fuller team checklist", "thinner team checklist")
        return f"{words[0]} ({a}/4 vs {b}/4)" if from_better else f"{words[1]} ({b}/4 vs {a}/4)"

    def fmt(v):
        return f"{pre}{v:,}"

    a, b = better[key], worse[key]
    if from_better:
        return f"{words[0]} ({fmt(a)} vs {fmt(b)}{unit})"
    return f"{words[1]} ({fmt(b)} vs {fmt(a)}{unit})"


def edges(parts, weights, pid, other):
    """Criteria where `other` beats `pid`, largest weighted gap first."""
    gaps = []
    for c in CRITERIA:
        mine, theirs = parts[pid][c], parts[other][c]
        if mine is None or theirs is None:
            continue
        gap = (theirs - mine) * weights[c]
        if gap > 1e-9:
            gaps.append((gap, c))
    return [c for _, c in sorted(gaps, key=lambda g: -g[0])]


def strengths(parts, weights, facts, pid):
    """Criteria where pid is best among eligible proposals; else its top contributors."""
    tops = []
    for c in CRITERIA:
        mine = parts[pid][c]
        best = max((p[c] for p in parts.values() if p[c] is not None), default=None)
        if mine is not None and best is not None and mine >= best - 1e-9:
            tops.append(strength_text(c, facts[pid]))
    if tops:
        return tops
    by_points = sorted(CRITERIA, key=lambda c: -((parts[pid][c] or 0) * weights[c]))
    return [f"strongest on {c}" for c in by_points[:2]]


def ranked_reason(order, i, parts, weights, facts):
    pid = order[i]
    head = ORDINALS[i] if i < len(ORDINALS) else f"Rank {i + 1}"
    good = join_words(strengths(parts, weights, facts, pid))

    if i == 0:
        if len(order) == 1:
            return f"{head}: {good}."
        nxt = order[1]
        theirs = edges(parts, weights, pid, nxt)[:2]
        if not theirs:
            return f"{head}: {good}; ahead of {nxt} on every criterion."
        why = join_words([compare_text(c, facts[nxt], facts[pid], True) for c in theirs])
        return f"{head}: {good}; outweighs {nxt}'s {why}."

    above = order[i - 1]
    weak = edges(parts, weights, pid, above)[:2]
    if not weak:
        return f"{head}: {good}; level with {above} on every criterion but scores lower overall."
    why = join_words([compare_text(c, facts[above], facts[pid], False) for c in weak])
    return f"{head}: {good}, but {why} than {above}."


def flagged_reason(f, crit, provisional):
    flags, human = check_flags(f, crit)
    action = "human review needed" if human else "ask contractor before ranking"
    return f"Flagged: {', plus '.join(flags)}; {action}. Provisional {provisional}."


def ineligible_reason(problems):
    return f"Ineligible: {'; '.join(problems)}."


# --- Main ------------------------------------------------------------------

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

    ranked_ids = [pid for pid in eligible if not check_flags(facts[pid], crit)[0]]
    flagged_ids = [pid for pid in eligible if pid not in ranked_ids]
    ranked_ids.sort(key=lambda pid: (-scores[pid], pid))
    flagged_ids.sort(key=lambda pid: (-scores[pid], pid))

    results = []
    for i, pid in enumerate(ranked_ids):
        results.append({
            "proposal": pid, "rank": i + 1, "status": "ranked", "score": scores[pid],
            "reason": ranked_reason(ranked_ids, i, parts, weights, facts),
        })
    for pid in flagged_ids:
        results.append({
            "proposal": pid, "rank": None, "status": "flagged", "score": None,
            "reason": flagged_reason(facts[pid], crit, scores[pid]),
        })
    for pid in sorted(ineligible):
        results.append({
            "proposal": pid, "rank": None, "status": "ineligible", "score": None,
            "reason": ineligible_reason(ineligible[pid]),
        })

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
        if len(r["reason"]) > MAX_REASON:
            print(f"WARNING: reason for {r['proposal']} is {len(r['reason'])} chars (> {MAX_REASON})")
    print(f"Wrote {RANKING_PATH}")


if __name__ == "__main__":
    main()
