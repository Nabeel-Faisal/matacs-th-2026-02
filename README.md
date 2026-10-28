# AI-Assisted Proposal Triage — Design

**AI reads. Code decides. A person awards.**

| Name | Reference | Role | Time spent |
|---|---|---|---|
| Nabeel Faisal | MATACS-TH-2026-02 | Associate Software Developer | About 1 hour 15 minutes (including reading the brief and planning) |

## Result at a glance

| Rank | Proposal | Status | Score | Score bar | Why (short) |
|:---:|:---:|---|---:|---|---|
| 1 | **A** | ✅ Ranked | **92.7** | `███████████████████` | Most installs, fastest timeline, full team checklist |
| 2 | **E** | ✅ Ranked | **73.5** | `███████████████` | Best warranty, but fewer installs and higher price than A |
| — | **D** | 🚩 Flagged | *69.8 provisional* | `██████████████` | No completion timeline given; ask the contractor before ranking |
| — | **C** | 🚩 Flagged | *61.8 provisional* | `████████████` | Contains text aimed at AI reviewers; experience may be older than 5 years |
| — | **B** | ❌ Ineligible | — | | Licence not held by the bidder |

One block = 5 points. Full reason lines are in [ranking.json](ranking.json).

## Score breakdown

| Proposal | Experience /30 | Price /25 | Timeline /15 | Warranty /15 | Team /15 | **Total** |
|---|---:|---:|---:|---:|---:|---:|
| A | 30.0 | 19.0 | 15.0 | 13.8 | 15.0 | **92.7** |
| E | 17.1 | 15.1 | 11.2 | 15.0 | 15.0 | **73.5** |
| D* | 23.6 | 25.0 | n/a | 13.8 | 7.5 | *69.8* |
| C* | 19.3 | 13.8 | 7.5 | 13.8 | 7.5 | *61.8* |

\* Provisional score for the reviewer only, not ranked. Parts are rounded, so a row can differ from its total by 0.1.

## How it works

```mermaid
flowchart LR
    U["Upload PDFs"]:::human --> T["Extract text"]:::rule
    T --> AI["AI extracts facts + quotes"]:::ai
    AI --> EV["Evidence check"]:::rule
    EV --> G["Mandatory gates"]:::rule
    G --> F["Flags"]:::rule
    F --> S["Scoring + reasons"]:::rule
    S --> R["Reviewer"]:::human
    R --> W["Final award"]:::human

    classDef ai fill:#DCEBFF,stroke:#1F5FBF,stroke-width:2px,color:#0B2A55
    classDef rule fill:#DFF3E1,stroke:#2E8B3E,stroke-width:2px,color:#123D1A
    classDef human fill:#FFE7CC,stroke:#D9730D,stroke-width:2px,color:#5A2E00
```

Blue = AI · Green = rules / plain code · Orange = human checkpoint

Full diagram: [diagram/flow.png](diagram/flow.png)

## Key design decisions

- **The AI never scores, ranks or sees the weights.** It only extracts facts, so it can't lean toward a result.
- **Every fact needs a quote, and the quote must exist in the PDF.** If it doesn't, the fact is flagged as possibly made up.
- **Flagged is not rejected.** A reviewer resolves the issue and the proposal goes back into scoring.
- **Criteria are versioned.** Changing weights re-scores from cached facts with no new AI call, and old results stay under the old version.
- **A person always makes the award.** Every override needs a written reason and is logged.

## Repository contents

| File | What it contains |
|---|---|
| [WRITEUP.md](WRITEUP.md) | Answers to the five assessment questions, risks and assumptions |
| [PROMPTS.md](PROMPTS.md) | System prompt, user prompt template, output schema and validation checks |
| [ranking.json](ranking.json) | Final ranking of proposals A–E with status, score and reason |
| [diagram/flow.png](diagram/flow.png) | Full process-flow diagram, colour-coded |
| [diagram/flow.mmd](diagram/flow.mmd) | Mermaid source for the diagram |
| [prototype/](prototype/) | Deterministic scoring script, extracted facts and criteria config |

### Run the prototype

```
python3 prototype/score.py
```

Python 3 standard library only, with no API calls. It rewrites `ranking.json` and prints the score breakdown.

## How I used AI tools

I used Claude in chat to break down the brief and plan the design decisions (e.g. flagging C and D instead of scoring them), and Claude Code to write the files, the scoring prototype and the diagram, reviewing each output before committing. I corrected the AI when its first ranking reasons only repeated the score ("scored 92.7") instead of explaining why a proposal sat in its position, and had them rewritten to compare against neighbouring proposals. I also had it restructure the extraction criteria from 12 entries back to the admin's 7 criteria, so the prompt clearly reflects admin-defined, not hard-coded, criteria.
