"""Reliability analysis and judgment aggregation tooling for W5 human evaluation.

Operationalizes frozen R7 human-validation methodology:
- Standalone Ordinal Krippendorff's Alpha calculation (no external dependency)
- 95% bootstrap confidence interval tooling (10,000 unit-level resamples)
- 3-judge aggregation:
    - Non-severe numeric (range < 2): RESOLVED_BY_MEDIAN with final_relevance = median
    - Severe disagreement (range == 2): PENDING_ADJUDICATION with final_relevance = None
    - Any NA / None: PENDING_EVIDENCE_ADJUDICATION with final_relevance = None
- Strict raw judgment validation: rejects booleans, floats, malformed strings, out-of-range ints
- Operational reliability gate interpretations:
    alpha >= 0.80: GOOD
    0.67 <= alpha < 0.80: USABLE_WITH_QUALIFICATION
    alpha < 0.67: STOP_REVIEW_RUBRIC
"""

from __future__ import annotations

import random
from typing import Any

W5_RELIABILITY_BOOTSTRAP_SEED: int = 20261013
BOOTSTRAP_REPLICATES: int = 10000


def validate_judgment_label(val: Any) -> int | None:
    """Strict validator for raw human judgment labels.

    Permitted numeric relevance labels:
        type(val) is int (NOT bool) AND val in {0, 1, 2} -> returns int in {0, 1, 2}
    Permitted missing values:
        val == "NA" or val is None -> returns None
    All other values:
        raise ValueError (no implicit int coercion, no booleans, no floats, no malformed strings)
    """
    if isinstance(val, bool):
        raise ValueError(f"Boolean values are not permitted as judgment labels: {val!r}")
    if val is None or val == "NA":
        return None
    if type(val) is int and val in {0, 1, 2}:
        return val
    raise ValueError(
        f"Invalid raw judgment label {val!r} of type {type(val).__name__}: "
        "must be int in {0, 1, 2} or missing ('NA' / None)"
    )


def calculate_krippendorff_alpha_ordinal(matrix: list[list[Any]]) -> float:
    """Calculate Krippendorff's alpha for ordinal data.

    Args:
        matrix: A list of units (rows), where each row is a list of ratings
            from coders. Missing values can be represented as None or 'NA'.
            Malformed values raise ValueError immediately (no silent dropping).

    Returns:
        alpha value as a float rounded to 4 decimal places.
    """
    # 1. Extract valid ordinal numeric ratings
    units: list[list[int]] = []
    for row in matrix:
        valid_ratings: list[int] = []
        for r in row:
            v = validate_judgment_label(r)
            if v is not None:
                valid_ratings.append(v)
        if len(valid_ratings) >= 2:
            units.append(valid_ratings)

    if not units:
        return 0.0

    # 2. Extract unique ordered values
    all_values = sorted(list(set(v for u in units for v in u)))
    if len(all_values) <= 1:
        # Zero variance in ratings across units
        return 1.0

    val_idx = {v: i for i, v in enumerate(all_values)}
    num_vals = len(all_values)

    # 3. Calculate marginal frequencies n_c and per-unit counts
    n_c = [0] * num_vals
    unit_data: list[tuple[int, list[int]]] = []
    n_total = 0

    for u in units:
        m_u = len(u)
        n_total += m_u
        counts = [0] * num_vals
        for v in u:
            idx = val_idx[v]
            counts[idx] += 1
            n_c[idx] += 1
        unit_data.append((m_u, counts))

    if n_total <= 1:
        return 0.0

    # 4. Ordinal difference function delta(c, k)^2
    delta_sq = [[0.0] * num_vals for _ in range(num_vals)]
    for i in range(num_vals):
        for j in range(i, num_vals):
            if i == j:
                d = 0.0
            else:
                sum_ng = sum(n_c[g] for g in range(i, j + 1))
                d = sum_ng - (n_c[i] + n_c[j]) / 2.0
            delta_sq[i][j] = d * d
            delta_sq[j][i] = d * d

    # 5. Observed disagreement D_o
    sum_do = 0.0
    for m_u, counts in unit_data:
        for c in range(num_vals):
            if counts[c] == 0:
                continue
            for k in range(num_vals):
                if counts[k] == 0:
                    continue
                sum_do += (counts[c] * counts[k] / (m_u - 1.0)) * delta_sq[c][k]
    d_observed = sum_do / n_total

    # 6. Expected disagreement D_e
    sum_de = 0.0
    for c in range(num_vals):
        for k in range(num_vals):
            sum_de += n_c[c] * n_c[k] * delta_sq[c][k]
    d_expected = sum_de / (n_total * (n_total - 1.0))

    if d_expected == 0.0:
        return 1.0 if d_observed == 0.0 else 0.0

    alpha = 1.0 - (d_observed / d_expected)
    return round(alpha, 4)


def calculate_krippendorff_alpha_ci(
    matrix: list[list[Any]],
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = W5_RELIABILITY_BOOTSTRAP_SEED,
) -> list[float]:
    """Calculate 95% bootstrap confidence interval for ordinal Krippendorff alpha.

    Resampling unit: one scenario-POI judgment unit (row of J1, J2, J3 ratings).
    Sampling with replacement of N units, preserving all ratings inside each unit.
    Malformed values raise ValueError immediately (no silent dropping).

    Returns:
        alpha_ci_95 as [lower_2_5th_percentile, upper_97_5th_percentile]
    """
    # Filter valid units with at least 2 ratings
    valid_units: list[list[int]] = []
    for row in matrix:
        valid_ratings: list[int] = []
        for r in row:
            v = validate_judgment_label(r)
            if v is not None:
                valid_ratings.append(v)
        if len(valid_ratings) >= 2:
            valid_units.append(valid_ratings)

    num_units = len(valid_units)
    if num_units < 2:
        val = calculate_krippendorff_alpha_ordinal(matrix)
        return [val, val]

    # Precompute unit properties for fast exact evaluation
    # Check if all ratings belong to standard {0, 1, 2}
    all_ratings = [r for u in valid_units for r in u]
    is_standard_012 = all(r in {0, 1, 2} for r in all_ratings)

    rng = random.Random(seed)
    bootstrap_alphas: list[float] = []

    if is_standard_012:
        # Precomputed fast exact 3-class statistics
        precomputed: list[tuple[int, int, int, float, float, float, int]] = []
        for u in valid_units:
            c0 = u.count(0)
            c1 = u.count(1)
            c2 = u.count(2)
            m = len(u)
            denom = m - 1.0
            p01 = c0 * c1 / denom
            p12 = c1 * c2 / denom
            p02 = c0 * c2 / denom
            precomputed.append((c0, c1, c2, p01, p12, p02, m))

        for _ in range(replicates):
            sampled = [precomputed[rng.randint(0, num_units - 1)] for _ in range(num_units)]
            s0 = sum(x[0] for x in sampled)
            s1 = sum(x[1] for x in sampled)
            s2 = sum(x[2] for x in sampled)
            sp01 = sum(x[3] for x in sampled)
            sp12 = sum(x[4] for x in sampled)
            sp02 = sum(x[5] for x in sampled)
            n_tot = sum(x[6] for x in sampled)

            nonzero = sum(1 for c in [s0, s1, s2] if c > 0)
            if nonzero <= 1:
                bootstrap_alphas.append(1.0)
                continue

            d01_sq = ((s0 + s1) / 2.0) ** 2
            d12_sq = ((s1 + s2) / 2.0) ** 2
            d02_sq = (s1 + (s0 + s2) / 2.0) ** 2

            sum_do = 2.0 * (sp01 * d01_sq + sp12 * d12_sq + sp02 * d02_sq)
            d_obs = sum_do / n_tot

            sum_de = 2.0 * (s0 * s1 * d01_sq + s1 * s2 * d12_sq + s0 * s2 * d02_sq)
            d_exp = sum_de / (n_tot * (n_tot - 1.0))

            if d_exp == 0.0:
                a = 1.0 if d_obs == 0.0 else 0.0
            else:
                a = 1.0 - (d_obs / d_exp)
            bootstrap_alphas.append(a)
    else:
        # Fallback to general formula
        for _ in range(replicates):
            sampled_units = [valid_units[rng.randint(0, num_units - 1)] for _ in range(num_units)]
            bootstrap_alphas.append(calculate_krippendorff_alpha_ordinal(sampled_units))

    bootstrap_alphas.sort()
    lower_idx = int(replicates * 0.025)
    upper_idx = int(replicates * 0.975)
    ci_lower = round(bootstrap_alphas[lower_idx], 4)
    ci_upper = round(bootstrap_alphas[upper_idx], 4)

    return [ci_lower, ci_upper]


def interpret_reliability_gate(alpha: float) -> str:
    """Interpret Krippendorff's alpha according to R7 operational gate."""
    if alpha >= 0.80:
        return "GOOD"
    elif alpha >= 0.67:
        return "USABLE_WITH_QUALIFICATION"
    else:
        return "STOP_REVIEW_RUBRIC"


def aggregate_three_judgments(
    j1: Any, j2: Any, j3: Any
) -> dict[str, Any]:
    """Aggregate judgments from three independent judges (J1, J2, J3).

    Strict rules:
    - All inputs must be valid raw judgment labels (int in {0, 1, 2}, "NA", or None).
      Malformed inputs raise ValueError.
    - If any judge returned 'NA' or None:
        - NA is NEVER converted to 0.
        - judgment_status = 'PENDING_EVIDENCE_ADJUDICATION'
        - final_relevance = None
        - provisional_median = None
        - adjudication_required = True
        - severe_disagreement = False
    - For three numeric labels in {0, 1, 2}:
        - agreement_range = max - min
        - If severe_disagreement (agreement_range == 2):
            - judgment_status = 'PENDING_ADJUDICATION'
            - final_relevance = None (MUST NOT store provisional median as final GT)
            - provisional_median = median_val
            - adjudication_required = True
            - severe_disagreement = True
        - If not severe (agreement_range < 2):
            - judgment_status = 'RESOLVED_BY_MEDIAN'
            - final_relevance = median_val
            - provisional_median = median_val
            - adjudication_required = False
            - severe_disagreement = False
    """
    v1 = validate_judgment_label(j1)
    v2 = validate_judgment_label(j2)
    v3 = validate_judgment_label(j3)

    # Check for NA or missing
    if v1 is None or v2 is None or v3 is None:
        return {
            "judge_1_label": j1,
            "judge_2_label": j2,
            "judge_3_label": j3,
            "agreement_range": None,
            "severe_disagreement": False,
            "adjudication_required": True,
            "judgment_status": "PENDING_EVIDENCE_ADJUDICATION",
            "final_relevance": None,
            "provisional_median": None,
        }

    # All three labels are valid numeric ints in {0, 1, 2}
    sorted_vals = sorted([v1, v2, v3])
    min_val = sorted_vals[0]
    median_val = sorted_vals[1]
    max_val = sorted_vals[2]
    agreement_range = max_val - min_val

    is_severe = (agreement_range == 2)

    if is_severe:
        return {
            "judge_1_label": v1,
            "judge_2_label": v2,
            "judge_3_label": v3,
            "agreement_range": agreement_range,
            "severe_disagreement": True,
            "adjudication_required": True,
            "judgment_status": "PENDING_ADJUDICATION",
            "final_relevance": None,
            "provisional_median": median_val,
        }
    else:
        return {
            "judge_1_label": v1,
            "judge_2_label": v2,
            "judge_3_label": v3,
            "agreement_range": agreement_range,
            "severe_disagreement": False,
            "adjudication_required": False,
            "judgment_status": "RESOLVED_BY_MEDIAN",
            "final_relevance": median_val,
            "provisional_median": median_val,
        }


def compute_agreement_statistics(records: list[tuple[Any, Any, Any]]) -> dict[str, Any]:
    """Compute agreement breakdown from a list of (j1, j2, j3) judgment triples.

    Strict rules:
    - All inputs must be valid raw judgment labels (int in {0, 1, 2}, 'NA', or None).
      Malformed inputs raise ValueError immediately (no silent dropping).
    """
    total = len(records)
    if total == 0:
        return {
            "total_records": 0,
            "exact_agreement_count": 0,
            "exact_agreement_pct": 0.0,
            "adjacent_disagreement_count": 0,
            "adjacent_disagreement_pct": 0.0,
            "severe_disagreement_count": 0,
            "severe_disagreement_pct": 0.0,
            "na_count": 0,
            "na_pct": 0.0,
            "ordinal_krippendorff_alpha": 0.0,
            "ordinal_krippendorff_alpha_ci_95": [0.0, 0.0],
            "operational_gate": "STOP_REVIEW_RUBRIC",
        }

    exact = 0
    adjacent = 0
    severe = 0
    na_count = 0

    matrix_for_alpha: list[list[Any]] = []

    for record in records:
        if len(record) != 3:
            raise ValueError(f"Record must have exactly 3 judgments, got {len(record)}: {record}")
        j1, j2, j3 = record
        # Validate each label strictly
        v1 = validate_judgment_label(j1)
        v2 = validate_judgment_label(j2)
        v3 = validate_judgment_label(j3)

        matrix_for_alpha.append([j1, j2, j3])

        if v1 is None or v2 is None or v3 is None:
            na_count += 1
            continue

        vals = sorted([v1, v2, v3])
        rng = vals[2] - vals[0]
        if rng == 0:
            exact += 1
        elif rng == 1:
            adjacent += 1
        elif rng == 2:
            severe += 1

    alpha = calculate_krippendorff_alpha_ordinal(matrix_for_alpha)
    alpha_ci = calculate_krippendorff_alpha_ci(matrix_for_alpha)

    return {
        "total_records": total,
        "exact_agreement_count": exact,
        "exact_agreement_pct": round(exact / total * 100, 2),
        "adjacent_disagreement_count": adjacent,
        "adjacent_disagreement_pct": round(adjacent / total * 100, 2),
        "severe_disagreement_count": severe,
        "severe_disagreement_pct": round(severe / total * 100, 2),
        "na_count": na_count,
        "na_pct": round(na_count / total * 100, 2),
        "ordinal_krippendorff_alpha": alpha,
        "ordinal_krippendorff_alpha_ci_95": alpha_ci,
        "operational_gate": interpret_reliability_gate(alpha),
    }
