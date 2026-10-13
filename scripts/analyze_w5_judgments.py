"""Reliability analysis and judgment aggregation tooling for W5 human evaluation.

Operationalizes frozen R7 human-validation methodology:
- Standalone Ordinal Krippendorff's Alpha calculation (no external dependency)
- 3-judge aggregation: median rule, severe-disagreement flags (range == 2)
- Explicit NA handling: never converted to 0, flags INSUFFICIENT_JUDGMENT_EVIDENCE
- Operational reliability gate interpretations:
    alpha >= 0.80: GOOD
    0.67 <= alpha < 0.80: USABLE_WITH_QUALIFICATION
    alpha < 0.67: STOP_REVIEW_RUBRIC
"""

from __future__ import annotations

from typing import Any


def calculate_krippendorff_alpha_ordinal(matrix: list[list[Any]]) -> float:
    """Calculate Krippendorff's alpha for ordinal data.

    Args:
        matrix: A list of units (rows), where each row is a list of ratings
            from coders. Missing values can be represented as None or 'NA'.

    Returns:
        alpha value as a float rounded to 4 decimal places.
    """
    # 1. Extract valid ordinal numeric ratings
    units: list[list[int]] = []
    for row in matrix:
        valid_ratings: list[int] = []
        for r in row:
            if r is None or r == "NA":
                continue
            try:
                valid_ratings.append(int(r))
            except (ValueError, TypeError):
                continue
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

    Rules:
    - If any judge returned 'NA' or None:
        - NA is NEVER converted to 0.
        - judgment_status = 'INSUFFICIENT_JUDGMENT_EVIDENCE'
        - final_relevance = None
        - adjudication_required = True
    - For numeric labels {0, 1, 2}:
        - agreement_range = max - min
        - severe_disagreement = (agreement_range == 2)
        - If severe_disagreement:
            - adjudication_required = True
            - judgment_status = 'PENDING_ADJUDICATION'
            - final_relevance = median (default provisional value)
        - If not severe:
            - adjudication_required = False
            - judgment_status = 'CONSENSUS'
            - final_relevance = median
    """
    raw_labels = [j1, j2, j3]

    # Check for NA or missing
    if any(label is None or label == "NA" or label == "INSUFFICIENT_EVIDENCE" for label in raw_labels):
        return {
            "judge_1_label": j1,
            "judge_2_label": j2,
            "judge_3_label": j3,
            "agreement_range": None,
            "severe_disagreement": False,
            "adjudication_required": True,
            "judgment_status": "INSUFFICIENT_JUDGMENT_EVIDENCE",
            "final_relevance": None,
        }

    # Parse numeric labels
    try:
        numeric = [int(x) for x in raw_labels]
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid judgment labels {raw_labels}: must be 0, 1, 2, or 'NA'") from exc

    for val in numeric:
        if val not in {0, 1, 2}:
            raise ValueError(f"Label {val} outside permitted set {{0, 1, 2, 'NA'}}")

    sorted_vals = sorted(numeric)
    min_val = sorted_vals[0]
    median_val = sorted_vals[1]
    max_val = sorted_vals[2]
    agreement_range = max_val - min_val

    is_severe = (agreement_range == 2)

    if is_severe:
        return {
            "judge_1_label": numeric[0],
            "judge_2_label": numeric[1],
            "judge_3_label": numeric[2],
            "agreement_range": agreement_range,
            "severe_disagreement": True,
            "adjudication_required": True,
            "judgment_status": "PENDING_ADJUDICATION",
            "final_relevance": median_val,
        }
    else:
        return {
            "judge_1_label": numeric[0],
            "judge_2_label": numeric[1],
            "judge_3_label": numeric[2],
            "agreement_range": agreement_range,
            "severe_disagreement": False,
            "adjudication_required": False,
            "judgment_status": "CONSENSUS",
            "final_relevance": median_val,
        }


def compute_agreement_statistics(records: list[tuple[Any, Any, Any]]) -> dict[str, Any]:
    """Compute agreement breakdown from a list of (j1, j2, j3) judgment triples."""
    total = len(records)
    if total == 0:
        return {
            "total_records": 0,
            "exact_agreement_pct": 0.0,
            "adjacent_disagreement_pct": 0.0,
            "severe_disagreement_pct": 0.0,
            "na_records_pct": 0.0,
        }

    exact = 0
    adjacent = 0
    severe = 0
    na_count = 0

    matrix_for_alpha: list[list[Any]] = []

    for j1, j2, j3 in records:
        matrix_for_alpha.append([j1, j2, j3])
        if any(x is None or x == "NA" for x in (j1, j2, j3)):
            na_count += 1
            continue
        vals = sorted([int(j1), int(j2), int(j3)])
        rng = vals[2] - vals[0]
        if rng == 0:
            exact += 1
        elif rng == 1:
            adjacent += 1
        elif rng == 2:
            severe += 1

    alpha = calculate_krippendorff_alpha_ordinal(matrix_for_alpha)

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
        "operational_gate": interpret_reliability_gate(alpha),
    }
