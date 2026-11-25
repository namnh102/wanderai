"""Two-layer fail-closed R_AUDIT sanitizer S -> V and multi-interval Pi_{V -> S}."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

R_CORROBORATED_PREFIX = re.compile(r"\[CORROBORATED\b")
R_AUDIT_CANDIDATE = re.compile(r"\[CORROBORATED:[^\]\r\n]*\]")

_REF_TOKEN = (
    r"(?:"
    r"canonical_poi:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|osm:(?:node|way|relation)/\d+"
    r"|wikidata:Q\d+"
    r"|wikipedia:[a-z]{2,3}:[^\s,\[\]]+"
    r"|wikivoyage:[a-z]{2,3}:[^\s,\[\]]+"
    r"|osm_website_pointer:https?://[^\s,\[\]]+"
    r")"
)
R_AUDIT = re.compile(rf"\[CORROBORATED:\s*{_REF_TOKEN}(?:,\s*{_REF_TOKEN})*\]")

KNOWN_FAMILIES = frozenset(
    {
        "canonical_poi",
        "osm",
        "wikidata",
        "wikipedia",
        "wikivoyage",
        "osm_website_pointer",
    }
)


@dataclass(frozen=True)
class SanitizationResult:
    """Result of fail-closed S -> V sanitization with exact Pi_{V -> S} segment table."""

    canonical_S: str
    view_V: str
    segments: List[Tuple[int, int, int, int]]  # (v_start, v_end, s_start, s_end)
    removed_intervals: List[Tuple[int, int]]  # (r_start, r_end) in S
    families: List[str]


def sanitize_canonical_to_view(s: str) -> SanitizationResult:
    """Fail-closed construction of sanitized view V, segment map M(S), and deleted intervals R.

    Does NOT consume preceding/trailing whitespace or newlines.
    Raises ValueError on any unclosed, multiline, empty, or grammar-invalid [CORROBORATED:...] marker.
    """
    if not isinstance(s, str):
        raise TypeError(f"Expected str for canonical S, got {type(s).__name__}")

    prefix_hits = list(R_CORROBORATED_PREFIX.finditer(s))
    candidate_hits = list(R_AUDIT_CANDIDATE.finditer(s))
    if len(prefix_hits) != len(candidate_hits):
        raise ValueError(
            "Malformed or unclosed [CORROBORATED marker: "
            f"prefix_hits={len(prefix_hits)} != candidate_hits={len(candidate_hits)}"
        )

    segments: List[Tuple[int, int, int, int]] = []
    removed: List[Tuple[int, int]] = []
    families: List[str] = []
    v_parts: List[str] = []
    v_cursor = 0
    s_cursor = 0

    for m in candidate_hits:
        raw_tag = m.group(0)
        if R_AUDIT.fullmatch(raw_tag) is None:
            raise ValueError(
                f"Unrecognized or malformed R_AUDIT marker syntax: {raw_tag!r}"
            )
        inner = raw_tag[len("[CORROBORATED:") : -1].strip()
        for item in inner.split(","):
            fam = item.strip().split(":", 1)[0]
            if fam not in KNOWN_FAMILIES:
                raise ValueError(f"Unknown reference family {fam!r} in {raw_tag!r}")
            families.append(fam)

        r_start, r_end = m.start(), m.end()
        if r_start > s_cursor:
            seg_len = r_start - s_cursor
            segments.append((v_cursor, v_cursor + seg_len, s_cursor, r_start))
            v_parts.append(s[s_cursor:r_start])
            v_cursor += seg_len
        removed.append((r_start, r_end))
        s_cursor = r_end

    if s_cursor < len(s):
        seg_len = len(s) - s_cursor
        segments.append((v_cursor, v_cursor + seg_len, s_cursor, len(s)))
        v_parts.append(s[s_cursor:])
        v_cursor += seg_len

    v = "".join(v_parts)
    if "[CORROBORATED" in v:
        raise AssertionError("Residual [CORROBORATED leaked into V!")
    if len(v) + sum(b - a for a, b in removed) != len(s):
        raise AssertionError("Code-point conservation failed during sanitization!")

    return SanitizationResult(
        canonical_S=s,
        view_V=v,
        segments=segments,
        removed_intervals=removed,
        families=families,
    )


def project_v_span_to_s(
    v_start: int,
    v_end: int,
    segments: Sequence[Tuple[int, int, int, int]],
) -> List[Tuple[int, int]]:
    """Map half-open [v_start, v_end) in V to ordered disjoint half-open [s_start, s_end) intervals in S."""
    if not (0 <= v_start <= v_end):
        raise ValueError(f"Invalid V span [{v_start}, {v_end})")
    out: List[Tuple[int, int]] = []
    for vs, ve, ss, _se in segments:
        ov_s = max(v_start, vs)
        ov_e = min(v_end, ve)
        if ov_s < ov_e:
            s_a = ss + (ov_s - vs)
            s_b = ss + (ov_e - vs)
            if out and out[-1][1] == s_a:
                out[-1] = (out[-1][0], s_b)
            else:
                out.append((s_a, s_b))
    return out


def cp_to_utf8_byte_offsets(s: str) -> List[int]:
    """Return len(s)+1 cumulative UTF-8 byte offsets for code-point positions in s."""
    offsets = [0]
    total = 0
    for ch in s:
        total += len(ch.encode("utf-8"))
        offsets.append(total)
    return offsets


def merge_intervals(intervals: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Sort and coalesce overlapping or adjacent half-open intervals [a, b)."""
    cleaned = sorted((a, b) for a, b in intervals if a < b)
    if not cleaned:
        return []
    merged: List[Tuple[int, int]] = [cleaned[0]]
    for a, b in cleaned[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def subtract_intervals(
    base: Sequence[Tuple[int, int]],
    cut: Sequence[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    """Return base minus cut as merged half-open intervals."""
    result: List[Tuple[int, int]] = []
    for a, b in base:
        cur: List[Tuple[int, int]] = [(a, b)]
        for ca, cb in cut:
            nxt: List[Tuple[int, int]] = []
            for x, y in cur:
                if cb <= x or ca >= y:
                    nxt.append((x, y))
                else:
                    if x < ca:
                        nxt.append((x, ca))
                    if cb < y:
                        nxt.append((cb, y))
            cur = nxt
        result.extend(cur)
    return merge_intervals(result)


def intervals_contain(
    container: Sequence[Tuple[int, int]],
    target: Sequence[Tuple[int, int]],
) -> bool:
    """Return True iff every point in target is covered by container."""
    return len(subtract_intervals(target, container)) == 0
