# Scoring prototype

Deterministic scorer for proposals A-E. Python 3 standard library only; no API calls.

## Run

```
python3 prototype/score.py
```

It reads `facts.json` (extracted facts per proposal) and `criteria.json` (weights, budget ceiling, max weeks, version) from this folder, writes `../ranking.json`, and prints a per-criterion breakdown.

## Rules, in order

1. **Mandatory gate:** missing licence, WSIB or $5M insurance makes a proposal `ineligible`.
2. **Limits:** price over the budget ceiling or weeks over the max makes it `ineligible`.
3. **Flags:** injection detected, no timeline, or unverified recent installs makes it `flagged`. Flagged proposals get no rank, but the reason line includes a provisional score for the reviewer.
4. Everything else is `ranked` by score.

Scores are normalized across every proposal that isn't ineligible, so flagged ones count. A criterion that can't be scored, such as a missing timeline, counts as 0.

To change weights or limits, edit `criteria.json` and bump `version`.

## Reasons

Each reason line is built from the data, so it stays correct when facts or weights change. Ranked proposals list the criteria they lead on and compare against their neighbour in the ranking. Flagged and ineligible ones state the specific issue. Optional coded fields in `facts.json` (`licence_holder`, `installs_counted_since`, `injection_goal`) add detail; their wording lives in `score.py`, not copied from proposals.
