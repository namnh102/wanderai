# Contribution Evidence — W1

> Audit date: 2026-10-05. Source: `git log --all` (whole history), `git shortlog -sne --all`, `gh issue/pr list`.

## 1. Raw facts
| Fact | Value | Source |
|---|---|---|
| Distinct git authors in whole repository | 1: `namnh102 <namkaz1234@gmail.com>` (82 commits) | `git shortlog -sne --all` |
| Commits in W1 window (all branches) | 31 (20 non-merge), all by `namnh102` | `git-log-W01.txt` |
| Commits matching `--author="Nam"`, `"Khanh"`, `"Khánh"` | 0, 0, 0 (author name is `namnh102`, which matches none of these strings; the `Nam` pattern does not match the lowercase handle) | `git log --all --author=...` |
| GitHub Issues / PRs authored | none exist | `gh issue list`, `gh pr list` |
| Code review between members | none recorded | no PR |

## 2. Contribution table
| Member | Work | Evidence | Quantified contribution |
|---|---|---|---|
| Ngô Hoàng Nam | Probable owner of the `namnh102` account: all W1-window commits (data pipeline, ADRs, docs, apps) | 31 commits `git-log-W01.txt` | 31 commits (20 non-merge) under the `namnh102` account. **Identity mapping Nam ↔ `namnh102` is an assumption from the handle; not confirmed by any repository file.** |
| Nguyễn Duy Khánh | No attributable work found | none | **Not fully traceable** — 0 commits, 0 issues, 0 PRs, no named document |

## 3. Statement
Evidence does not show contribution by the second member in W1. It is possible that work was done outside Git (research, discussion, shared account), but it is **not verifiable from the repository** and no 50/50 split is claimed. The proposal (§10, §12) requires quantifiable contributions through Issues/PR/commits and cross-review from both members; this requirement was **not met in W1** and should be corrected from W2 (separate commits per member, Issues, PRs).
