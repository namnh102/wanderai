# Contribution Evidence — W1

> Audit date: 2026-10-05 (revised same day). Source: `git log --all`, `git shortlog -sne --all`, `gh issue/pr list`.

## 1. Raw facts (verified)
| Fact | Value | Source |
|---|---|---|
| Distinct git authors in the whole repository | 1: `namnh102` (82 commits) | `git shortlog -sne --all` |
| Commits in the W1 window (all branches) | 31 (20 non-merge), all by `namnh102` | `git-log-W01.txt` |
| `git log --author` for "Nam", "Khanh", "Khánh" | 0, 0, 0 | author name is `namnh102` |
| GitHub Issues / PRs | none | `gh issue list`, `gh pr list` |
| Cross-review between members | none recorded | no PR |

## 2. Declared work split (SELF-REPORTED by the group, NOT derivable from Git)
The split below was provided by the group on 2026-10-05 and is organised by W1 work item, following the proposal roles (Lead A / Lead B). Artifacts are traceable to commits, but **who authored each is not verifiable from Git** because all commits use one account.

| Member | Declared W1 work | Artifacts / commits |
|---|---|---|
| Ngô Hoàng Nam | POI source selection; OSM pipeline (collect, parse, entity resolution); ADR-002; `data-sources.md`, `data-dictionary.md`; pilot dataset | `ffe7b97`, `8592aea`, `data/pipelines/osm/`, `data/pipelines/entity_resolution/`, `places_canonical.json` |
| Nguyễn Duy Khánh | License and provenance review; data quality and reconciliation; team rules | `b5e96db`, `4944fae`, `bec83d0`, `173a573`, `2d15a64`, `9b36f9d` |

## 3. Statement
- The split is a declaration, not Git-derived evidence. Verification status: **self-reported / not independently verifiable**.
- Proposal §10 and §12 (per-member quantifiable contribution, cross-review) were **not met in W1** by Git evidence. Correction from W2: separate accounts, issue IDs in commit messages, PR cross-review.
