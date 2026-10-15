"""Conservative Deterministic OSM opening_hours Parser & Evaluator for W06 (W06-INSTRUMENT-01C).

Grounded in:
- W06-MEASUREMENT-CONTRACT-01 v1.1.0 (data/evaluation/w06/w06_measurement_contract_v1.json)
- Frozen REC-A-CORE-V2 catalog (data/curated/gomate_places_freeze_v2.json, 622 core POIs, 101 with opening_hours)

Strict scientific rules:
- Conservative parser: never guesses; if syntax cannot be interpreted with 100% deterministic confidence,
  returns supported=False and opening_hours_state="UNKNOWN".
- Parser failure / unsupported syntax is NEVER interpreted as VIOLATION and NEVER interpreted as COMPLIANT.
- Cross-midnight / overnight ranges (where end <= start or end == "00:00", e.g., 18:00-02:00, 18:00-00:00)
  are classified as UNKNOWN with reason_code="UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX".
- Explicit "24:00" as an opening-hours end boundary (e.g., 11:00-24:00) is supported as 1440 minutes.
  (Itinerary activity start_time/end_time remain strict 00:00..23:59 with start < end.)
"""
from collections import Counter
import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.prompts.planner_benchmark_prompt import DEFAULT_CATALOG_PATH

OPENING_HOURS_PARSER_VERSION: str = "W06-OPENING-HOURS-PARSER-01C-V1.0.0"

WEEKDAY_NAME_TO_INDEX: Dict[str, int] = {
    "mo": 0,
    "tu": 1,
    "we": 2,
    "th": 3,
    "fr": 4,
    "sa": 5,
    "su": 6,
}

STRICT_ACTIVITY_HHMM_RE = re.compile(r"^(\d{2}):(\d{2})$")
OPENING_HOURS_TIME_RANGE_RE = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")
SUBCLAUSE_SPLIT_RE = re.compile(r"(?<=\d),\s*(?=[A-Za-z]{2}\b)")
CLAUSE_HEAD_RE = re.compile(
    r"^(?:([A-Za-z]{2}(?:-[A-Za-z]{2})?(?:,[A-Za-z]{2}(?:-[A-Za-z]{2})?)*)\s+)?(.+)$"
)
HOLIDAY_TOKEN_RE = re.compile(r"\b(PH|SH)\b")
MONTH_OR_DATE_TOKEN_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|week)\b",
    re.IGNORECASE,
)
SOLAR_TOKEN_RE = re.compile(r"\b(sunrise|sunset|dawn|dusk)\b", re.IGNORECASE)


class ParsedOpeningHoursSchedule(BaseModel):
    """Result of conservatively parsing an OSM opening_hours string."""

    model_config = ConfigDict(extra="forbid")

    raw_value: Optional[str] = None
    supported: bool
    reason_code: str
    is_24_7: bool = False
    syntax_features: List[str] = Field(default_factory=list)
    intervals_by_weekday: Dict[int, List[Tuple[int, int]]] = Field(default_factory=dict)


class OpeningHoursItemEvaluation(BaseModel):
    """Per-item opening-hours evaluation record for a POI_VISIT itinerary item."""

    model_config = ConfigDict(extra="forbid")

    day_number: int
    date: Optional[str] = None
    order_index: int
    place_id: Optional[str] = None
    opening_hours_raw: Optional[str] = None
    start_time: str
    end_time: str
    opening_hours_state: str  # "COMPLIANT" | "VIOLATION" | "UNKNOWN"
    reason_code: str


def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Sort and merge contiguous or overlapping half-open intervals [start, end)."""
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: List[Tuple[int, int]] = [sorted_iv[0]]
    for cur_start, cur_end in sorted_iv[1:]:
        prev_start, prev_end = merged[-1]
        if cur_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, cur_end))
        else:
            merged.append((cur_start, cur_end))
    return merged


def _expand_weekday_selector(selector_str: str) -> Optional[ Tuple[List[int], List[str]] ]:
    """Expand a weekday selector string (e.g. 'Mo-Fr', 'Tu-Th,Sa-Su', 'Th-Tu') into weekday indices 0..6."""
    weekdays: List[int] = []
    features: List[str] = ["weekday_names"]
    parts = [p.strip() for p in selector_str.split(",")]
    if len(parts) > 1:
        features.append("weekday_lists")

    for part in parts:
        if not part:
            return None
        if "-" in part:
            features.append("weekday_ranges")
            endpoints = part.split("-")
            if len(endpoints) != 2:
                return None
            start_code = endpoints[0].strip().lower()
            end_code = endpoints[1].strip().lower()
            if start_code not in WEEKDAY_NAME_TO_INDEX or end_code not in WEEKDAY_NAME_TO_INDEX:
                return None
            start_idx = WEEKDAY_NAME_TO_INDEX[start_code]
            end_idx = WEEKDAY_NAME_TO_INDEX[end_code]
            if start_idx <= end_idx:
                span = list(range(start_idx, end_idx + 1))
            else:
                features.append("wraparound_weekday_ranges")
                span = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
            for d in span:
                if d not in weekdays:
                    weekdays.append(d)
        else:
            code = part.strip().lower()
            if code not in WEEKDAY_NAME_TO_INDEX:
                return None
            d = WEEKDAY_NAME_TO_INDEX[code]
            if d not in weekdays:
                weekdays.append(d)

    if any(c.islower() for c in selector_str if c.isalpha() and c not in "o u e h a"):
        features.append("lowercase_weekday_tokens")

    return weekdays, sorted(set(features))


def classify_opening_hours_syntax_features(raw_value: str) -> List[str]:
    """Identify syntax features present in a raw opening_hours string for inventory reporting."""
    s = raw_value.strip()
    features: List[str] = []
    if s == "24/7":
        features.append("24/7")
        return features

    if re.search(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)\b", s, re.IGNORECASE):
        features.append("weekday_names")
    if re.search(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)-(Mo|Tu|We|Th|Fr|Sa|Su)\b", s, re.IGNORECASE):
        features.append("weekday_ranges")
    if re.search(
        r"\b(Mo|Tu|We|Th|Fr|Sa|Su)(?:-(Mo|Tu|We|Th|Fr|Sa|Su))?,(Mo|Tu|We|Th|Fr|Sa|Su|PH|SH)\b",
        s,
        re.IGNORECASE,
    ):
        features.append("weekday_lists")
    if re.search(r"\d{1,2}:\d{2}-\d{1,2}:\d{2}", s):
        features.append("hhmm_to_hhmm_ranges")
    if ";" in s:
        features.append("semicolon_separated_rules")
    if re.search(r"\boff\b", s, re.IGNORECASE):
        features.append("explicit_off_rules")
    if "+" in s:
        features.append("open_ended_plus")
    if HOLIDAY_TOKEN_RE.search(s):
        features.append("public_or_school_holiday_selectors")
    if MONTH_OR_DATE_TOKEN_RE.search(s):
        features.append("month_or_date_selectors")
    if SOLAR_TOKEN_RE.search(s):
        features.append("sunrise_or_sunset")
    if "24:00" in s:
        features.append("end_of_day_24_00")

    # Check multiple time ranges or cross-midnight ranges
    time_matches = re.findall(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", s)
    if len(time_matches) > 1 and ";" not in s:
        features.append("multiple_same_day_time_ranges")
    elif ";" in s:
        for semi_part in s.split(";"):
            if len(re.findall(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", semi_part)) > 1:
                features.append("multiple_same_day_time_ranges")
                break

    for sh_s, sm_s, eh_s, em_s in time_matches:
        sh, sm, eh, em = int(sh_s), int(sm_s), int(eh_s), int(em_s)
        if not (eh == 24 and em == 0) and (eh * 60 + em <= sh * 60 + sm):
            features.append("cross_midnight_ranges")
            break

    if not re.search(r"[A-Za-z]", s) and time_matches:
        features.append("time_range_only_daily")

    return sorted(set(features))


def parse_osm_opening_hours(raw_value: Optional[str]) -> ParsedOpeningHoursSchedule:
    """Conservatively parse an OSM opening_hours string into per-weekday open intervals [start, end).

    Never guesses on unsupported or ambiguous syntax: returns supported=False with an explicit
    deterministic reason_code.
    """
    if raw_value is None or not isinstance(raw_value, str) or not raw_value.strip():
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=False,
            reason_code="MISSING_OPENING_HOURS",
            is_24_7=False,
            syntax_features=[],
            intervals_by_weekday={},
        )

    s = raw_value.strip()
    features = classify_opening_hours_syntax_features(s)

    if s == "24/7":
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=True,
            reason_code="SUPPORTED_24_7",
            is_24_7=True,
            syntax_features=features,
            intervals_by_weekday={d: [(0, 1440)] for d in range(7)},
        )

    if "+" in s:
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=False,
            reason_code="UNSUPPORTED_OPEN_ENDED_PLUS",
            syntax_features=features,
        )

    if HOLIDAY_TOKEN_RE.search(s):
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=False,
            reason_code="UNSUPPORTED_HOLIDAY_SELECTOR",
            syntax_features=features,
        )

    if MONTH_OR_DATE_TOKEN_RE.search(s):
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=False,
            reason_code="UNSUPPORTED_DATE_OR_MONTH_SELECTOR",
            syntax_features=features,
        )

    if SOLAR_TOKEN_RE.search(s):
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=False,
            reason_code="UNSUPPORTED_SOLAR_EVENT_SYNTAX",
            syntax_features=features,
        )

    schedule: Dict[int, List[Tuple[int, int]]] = {d: [] for d in range(7)}

    semi_rules = [part.strip() for part in s.split(";")]
    if any(not part for part in semi_rules):
        return ParsedOpeningHoursSchedule(
            raw_value=raw_value,
            supported=False,
            reason_code="UNSUPPORTED_SYNTAX",
            syntax_features=features,
        )

    for semi_rule in semi_rules:
        subclauses = [sc.strip() for sc in SUBCLAUSE_SPLIT_RE.split(semi_rule)]
        overridden_days_in_semi_rule: set[int] = set()

        for subclause in subclauses:
            if not subclause:
                return ParsedOpeningHoursSchedule(
                    raw_value=raw_value,
                    supported=False,
                    reason_code="UNSUPPORTED_SYNTAX",
                    syntax_features=features,
                )

            head_match = CLAUSE_HEAD_RE.match(subclause)
            if not head_match:
                return ParsedOpeningHoursSchedule(
                    raw_value=raw_value,
                    supported=False,
                    reason_code="UNSUPPORTED_SYNTAX",
                    syntax_features=features,
                )

            weekday_selector_str, action_str = head_match.group(1), head_match.group(2).strip()
            if weekday_selector_str is not None:
                expanded = _expand_weekday_selector(weekday_selector_str)
                if expanded is None:
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_SYNTAX",
                        syntax_features=features,
                    )
                target_weekdays, _ = expanded
            else:
                # Without a weekday selector, only pure HH:MM-HH:MM time lists are allowed (no unknown alpha tokens)
                if re.search(r"[A-Za-z]", action_str):
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_SYNTAX",
                        syntax_features=features,
                    )
                target_weekdays = [0, 1, 2, 3, 4, 5, 6]

            if action_str.lower() == "off":
                for d in target_weekdays:
                    schedule[d] = []
                    overridden_days_in_semi_rule.add(d)
                continue

            time_specs = [t.strip() for t in action_str.split(",")]
            parsed_intervals: List[Tuple[int, int]] = []
            for ts in time_specs:
                tm = OPENING_HOURS_TIME_RANGE_RE.match(ts)
                if not tm:
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_SYNTAX",
                        syntax_features=features,
                    )
                sh_s, sm_s, eh_s, em_s = tm.group(1), tm.group(2), tm.group(3), tm.group(4)
                sh, sm, eh, em = int(sh_s), int(sm_s), int(eh_s), int(em_s)

                if not (0 <= sh <= 23 and 0 <= sm <= 59):
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_SYNTAX",
                        syntax_features=features,
                    )
                if not ((0 <= eh <= 23 and 0 <= em <= 59) or (eh == 24 and em == 0)):
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_SYNTAX",
                        syntax_features=features,
                    )

                start_min = sh * 60 + sm
                end_min = eh * 60 + em

                if end_min <= start_min:
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX",
                        syntax_features=features,
                    )

                if len(sh_s) != 2 or len(eh_s) != 2:
                    return ParsedOpeningHoursSchedule(
                        raw_value=raw_value,
                        supported=False,
                        reason_code="UNSUPPORTED_SYNTAX",
                        syntax_features=features,
                    )

                parsed_intervals.append((start_min, end_min))

            for d in target_weekdays:
                if d not in overridden_days_in_semi_rule:
                    schedule[d] = list(parsed_intervals)
                    overridden_days_in_semi_rule.add(d)
                else:
                    schedule[d].extend(parsed_intervals)
                schedule[d] = _merge_intervals(schedule[d])

    return ParsedOpeningHoursSchedule(
        raw_value=raw_value,
        supported=True,
        reason_code="SUPPORTED_STANDARD_OPENING_HOURS",
        is_24_7=False,
        syntax_features=features,
        intervals_by_weekday=schedule,
    )


def _parse_activity_hhmm(value: Any) -> Optional[int]:
    """Strictly parse an itinerary activity 24-hour HH:MM string (00:00..23:59) into minutes."""
    if not isinstance(value, str):
        return None
    m = STRICT_ACTIVITY_HHMM_RE.match(value)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def evaluate_poi_visit_opening_hours(
    *,
    day_number: int,
    date_str: Optional[str],
    date_context_trusted: bool,
    order_index: int,
    place_id: Optional[str],
    is_grounded: bool,
    opening_hours_raw: Optional[str],
    start_time: str,
    end_time: str,
) -> OpeningHoursItemEvaluation:
    """Deterministically evaluate a single POI_VISIT item against catalog opening_hours.

    Returns one of:
    - COMPLIANT
    - VIOLATION
    - UNKNOWN
    with an explicit reason_code.
    """
    if not is_grounded or not place_id:
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="UNKNOWN",
            reason_code="UNGROUNDED_POI_VISIT",
        )

    if opening_hours_raw is None or not str(opening_hours_raw).strip():
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="UNKNOWN",
            reason_code="MISSING_OPENING_HOURS",
        )

    parsed_schedule = parse_osm_opening_hours(opening_hours_raw)
    if not parsed_schedule.supported:
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="UNKNOWN",
            reason_code=parsed_schedule.reason_code,
        )

    if not date_context_trusted or not date_str:
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="UNKNOWN",
            reason_code="UNKNOWN_DATE_CONTEXT",
        )

    try:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise ValueError("Not strict YYYY-MM-DD")
        visit_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="UNKNOWN",
            reason_code="UNKNOWN_DATE_CONTEXT",
        )

    start_min = _parse_activity_hhmm(start_time)
    end_min = _parse_activity_hhmm(end_time)
    if start_min is None or end_min is None or start_min >= end_min:
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="UNKNOWN",
            reason_code="INVALID_VISIT_INTERVAL_FOR_OPENING_HOURS",
        )

    weekday_idx = visit_date.weekday()
    open_windows = parsed_schedule.intervals_by_weekday.get(weekday_idx, [])
    if not open_windows:
        return OpeningHoursItemEvaluation(
            day_number=day_number,
            date=date_str,
            order_index=order_index,
            place_id=place_id,
            opening_hours_raw=opening_hours_raw,
            start_time=start_time,
            end_time=end_time,
            opening_hours_state="VIOLATION",
            reason_code="CLOSED_ON_WEEKDAY",
        )

    for open_start, open_end in open_windows:
        if open_start <= start_min and end_min <= open_end:
            return OpeningHoursItemEvaluation(
                day_number=day_number,
                date=date_str,
                order_index=order_index,
                place_id=place_id,
                opening_hours_raw=opening_hours_raw,
                start_time=start_time,
                end_time=end_time,
                opening_hours_state="COMPLIANT",
                reason_code="WITHIN_OPENING_HOURS",
            )

    return OpeningHoursItemEvaluation(
        day_number=day_number,
        date=date_str,
        order_index=order_index,
        place_id=place_id,
        opening_hours_raw=opening_hours_raw,
        start_time=start_time,
        end_time=end_time,
        opening_hours_state="VIOLATION",
        reason_code="OUTSIDE_OPENING_HOURS_WINDOW",
    )


def build_opening_hours_parser_coverage_report(
    catalog_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the deterministic parser coverage inventory over the 622 REC-A-CORE-V2 POIs (Section 3 & 20).

    Measures parser capability over the frozen catalog only, NOT planner performance.
    """
    target = catalog_path or DEFAULT_CATALOG_PATH
    raw_places: List[Dict[str, Any]] = json.loads(target.read_text(encoding="utf-8"))
    core_places = [p for p in raw_places if p.get("is_rec_a_core_v2") is True]
    core_with_oh = [
        p
        for p in core_places
        if p.get("opening_hours") is not None and str(p.get("opening_hours")).strip()
    ]

    unique_strings = sorted({str(p["opening_hours"]).strip() for p in core_with_oh})
    syntax_family_record_counts: Counter[str] = Counter()
    unsupported_reason_counts: Counter[str] = Counter()
    supported_reason_counts: Counter[str] = Counter()

    supported_count = 0
    unsupported_count = 0
    unsupported_records: List[Dict[str, str]] = []
    per_destination_coverage: Dict[str, Dict[str, int]] = {
        "ha-noi": {"total_core": 0, "with_opening_hours": 0, "parser_supported": 0, "parser_unsupported": 0},
        "da-nang": {"total_core": 0, "with_opening_hours": 0, "parser_supported": 0, "parser_unsupported": 0},
        "ha-long": {"total_core": 0, "with_opening_hours": 0, "parser_supported": 0, "parser_unsupported": 0},
    }

    for p in core_places:
        dest = str(p["destination_slug"])
        if dest in per_destination_coverage:
            per_destination_coverage[dest]["total_core"] += 1

    for p in core_with_oh:
        dest = str(p["destination_slug"])
        raw_oh = str(p["opening_hours"])
        parsed = parse_osm_opening_hours(raw_oh)

        for feat in parsed.syntax_features:
            syntax_family_record_counts[feat] += 1

        if dest in per_destination_coverage:
            per_destination_coverage[dest]["with_opening_hours"] += 1

        if parsed.supported:
            supported_count += 1
            supported_reason_counts[parsed.reason_code] += 1
            if dest in per_destination_coverage:
                per_destination_coverage[dest]["parser_supported"] += 1
        else:
            unsupported_count += 1
            unsupported_reason_counts[parsed.reason_code] += 1
            if dest in per_destination_coverage:
                per_destination_coverage[dest]["parser_unsupported"] += 1
            unsupported_records.append(
                {
                    "destination_slug": dest,
                    "opening_hours": raw_oh,
                    "place_id": str(p["place_id"]),
                    "reason_code": parsed.reason_code,
                }
            )

    unsupported_records.sort(key=lambda r: (r["reason_code"], r["destination_slug"], r["place_id"]))

    total_oh = len(core_with_oh)
    supported_ratio = round(supported_count / total_oh, 6) if total_oh > 0 else 0.0

    return {
        "artifact_id": "W06-OPENING-HOURS-PARSER-COVERAGE-V1",
        "claims_planner_performance": False,
        "core_opening_hours_records": total_oh,
        "core_with_opening_hours": total_oh,
        "evidence_scope": "INSTRUMENT_PARSER_CAPABILITY_ONLY_NOT_PLANNER_COMPLIANCE",
        "observed_syntax_family_presence": {
            "24/7": syntax_family_record_counts.get("24/7", 0) > 0,
            "comments_or_unsupported_tokens": False,
            "cross_midnight_ranges": syntax_family_record_counts.get("cross_midnight_ranges", 0) > 0,
            "end_of_day_24_00": syntax_family_record_counts.get("end_of_day_24_00", 0) > 0,
            "explicit_off_rules": syntax_family_record_counts.get("explicit_off_rules", 0) > 0,
            "hhmm_to_hhmm_ranges": syntax_family_record_counts.get("hhmm_to_hhmm_ranges", 0) > 0,
            "month_or_date_selectors": syntax_family_record_counts.get("month_or_date_selectors", 0) > 0,
            "multiple_same_day_time_ranges": syntax_family_record_counts.get("multiple_same_day_time_ranges", 0) > 0,
            "open_ended_plus": syntax_family_record_counts.get("open_ended_plus", 0) > 0,
            "public_or_school_holiday_selectors": syntax_family_record_counts.get("public_or_school_holiday_selectors", 0) > 0,
            "semicolon_separated_rules": syntax_family_record_counts.get("semicolon_separated_rules", 0) > 0,
            "sunrise_or_sunset": syntax_family_record_counts.get("sunrise_or_sunset", 0) > 0,
            "time_range_only_daily": syntax_family_record_counts.get("time_range_only_daily", 0) > 0,
            "weekday_lists": syntax_family_record_counts.get("weekday_lists", 0) > 0,
            "weekday_names": syntax_family_record_counts.get("weekday_names", 0) > 0,
            "weekday_ranges": syntax_family_record_counts.get("weekday_ranges", 0) > 0,
        },
        "observed_syntax_family_record_counts": dict(sorted(syntax_family_record_counts.items())),
        "opening_hours_parser_version": OPENING_HOURS_PARSER_VERSION,
        "parser_supported_ratio": supported_ratio,
        "parser_supported_record_count": supported_count,
        "parser_unsupported_record_count": unsupported_count,
        "per_destination_coverage": per_destination_coverage,
        "source_catalog_file": "data/curated/gomate_places_freeze_v2.json",
        "source_catalog_scope": "REC-A-CORE-V2",
        "supported_grammar": [
            "24/7",
            "HH:MM-HH:MM daily same-day ranges without weekday selector",
            "weekday selectors (Mo, Tu, We, Th, Fr, Sa, Su; case-insensitive)",
            "weekday lists (e.g. Sa,Su)",
            "weekday ranges including cyclical ranges (e.g. Mo-Fr, Mo-Su, Tu-Su, Th-Tu, We-Mo)",
            "multiple same-day HH:MM-HH:MM time ranges (including comma-separated repeated weekday clauses)",
            "semicolon-separated rules with deterministic later-rule weekday override",
            "explicit off rules (e.g. Mo off, Fr off)",
            "24:00 as explicit end-of-day opening-hours boundary (1440 minutes)"
        ],
        "supported_reason_counts": dict(sorted(supported_reason_counts.items())),
        "total_core_pois": len(core_places),
        "unique_opening_hours_string_count": len(unique_strings),
        "unsupported_grammar": [
            "cross-midnight / overnight ranges where end <= start or end == 00:00 (UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX)",
            "open-ended '+' syntax such as 05:30+ (UNSUPPORTED_OPEN_ENDED_PLUS)",
            "public/school holiday selectors PH / SH (UNSUPPORTED_HOLIDAY_SELECTOR)",
            "month/date/week selectors (UNSUPPORTED_DATE_OR_MONTH_SELECTOR)",
            "solar event tokens sunrise/sunset/dawn/dusk (UNSUPPORTED_SOLAR_EVENT_SYNTAX)",
            "non-2-digit hour tokens or free-text comments (UNSUPPORTED_SYNTAX)"
        ],
        "unsupported_reason_counts": dict(sorted(unsupported_reason_counts.items())),
        "unsupported_records": unsupported_records,
    }
