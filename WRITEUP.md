# Write-up: AI-assisted proposal triage

## Summary

AI reads, code decides, a person awards. The AI turns each proposal into facts, each backed by a quote. Plain code applies the rules and scores, and a reviewer makes the final call.

On the sample set: **A ranks 1st (92.7), E 2nd (73.5), C and D are flagged for review, and B is ineligible.** See [ranking.json](ranking.json) and the flow in [diagram/flow.png](diagram/flow.png).

## 1. AI vs rules

**AI is used only for:**
- Reading messy, varied wording and pulling out facts, each with an exact quote as evidence ([PROMPTS.md](PROMPTS.md)).
- Optionally drafting a clarification question for a flagged proposal. A reviewer edits it before it is sent.

**Rules (plain code) do everything else:**
- Getting text out of the PDF, with OCR (reading text from a scanned image) when needed.
- Checking that every quote really appears in the PDF.
- Mandatory gates and thresholds, such as insurance ≥ $5M and price ≤ ceiling.
- Flags, scoring, ranking and the reason lines ([prototype/score.py](prototype/score.py)).

**Why the line sits there:** understanding different ways of saying the same thing is what AI is good at. Pass/fail decisions and arithmetic must be exact, repeatable and auditable, which is what code is good at. The AI never sees the weights, so it can't lean toward a result.

## 2. Consistency and explainability

- **Same facts + same criteria version = identical scores.** The scoring code has no randomness.
- **The AI step is kept as steady as possible.** It runs with temperature 0 (the setting that makes the model least random), a pinned model version and a versioned prompt. Its facts are cached, so re-ranking never calls the AI again.
- **Every number traces back to the PDF.** Each fact carries a quote, and each reason line explains the position. For example, A's reason says it leads on installs, timeline and team, which outweighs E's longer workmanship warranty.

**Honest trade-off:** scores are relative. The best proposal on each criterion sets the benchmark, so adding or removing a proposal can shift everyone's numbers. In a close race it can even swap two proposals. Fixed benchmarks set by the admin (for example, "15+ installs = full marks") would avoid this, at the cost of choosing those numbers up front.

## 3. Human in the loop

- **The admin** owns the criteria, weights and thresholds.
- **The reviewer** checks the evidence and resolves flags. They can override any score or status, but must write a reason.
- **A person always makes the final award.** The tool only produces a ranked shortlist.
- **Flagged does not mean rejected.** Once a flag is resolved, the proposal goes back into scoring and gets a rank.

**The audit log records:**
- who uploaded what, and when
- a file hash (a fingerprint that proves the file hasn't changed)
- the extracted text
- the prompt, model and criteria versions
- the raw AI output and the result of each evidence check
- scores and flags
- every override, with who, when and why

## 4. Changing criteria

- **Every edit creates a new criteria version.** Old results stay tied to the version they were scored under and are never silently changed.
- **Weight or threshold change:** re-score instantly from the cached facts, with no AI call.
- **New field to extract:** re-run the AI for that field only.
- **The reviewer sees** "scored under v1, criteria now v2", with a before/after comparison of ranks.

## 5. Risks and safeguards

| Risk | Example from sample set | Safeguard |
|---|---|---|
| Wrong or made-up facts | Any extracted value | The quote must exist in the PDF text; if not, the value is flagged |
| Missing information | D gives no timeline | Recorded as empty, not guessed; flagged; draft question to contractor |
| Who holds the licence | B relies on an unconfirmed subcontractor | A "holder" field; the gate requires the bidder to hold it |
| Manipulation (prompt injection: hidden text telling the AI what to do) | C | Proposal treated as data only; injected text reported and auto-flagged; never auto-ranked |
| Stale experience | C counts installs from 2020 | An "earliest year counted" field; flagged when the 5-year window can't be confirmed |
| Bias toward big names or polished writing | All | The AI extracts facts, not impressions; same formula and checklist for everyone |
| Close calls | A small weight change could swap ranks | Close-call warning before the reviewer decides |
| Cost | Every upload | One AI call per proposal, cached; re-scoring is free; OCR only for scanned files |
| Over-trust in the tool | Any ranking | The tool ranks, a person awards; overrides are logged |

## Assumptions

- "Last 5 years" is counted back from the review date (2026).
- Flagged proposals have rank and score left empty in [ranking.json](ranking.json). Their provisional score appears only in the reason line.
- B fails the licence gate because the licence must be held by the bidder.
- The prototype covers scoring and ranking only. Extraction, the evidence check, versioning, the close-call warning and the audit log are designed in [PROMPTS.md](PROMPTS.md) and [diagram/flow.png](diagram/flow.png), but not built.
- **Scoring formulas**, from [prototype/score.py](prototype/score.py), compared across all non-ineligible proposals:
  - Experience = installs ÷ most installs
  - Price = (ceiling − price) ÷ (ceiling − lowest price)
  - Timeline = (16 − weeks) ÷ (16 − shortest weeks); a missing timeline scores 0
  - Warranty = half panel years ÷ best + half workmanship years ÷ best
  - Team = checklist items present ÷ 4
  - Final = sum of each part × its weight (30/25/15/15/15), out of 100
