export type ItineraryViolationCode =
  | 'TIME_INTERVAL_INVALID'
  | 'SCHEDULE_OVERLAP'
  | 'OPENING_HOURS_CLOSED';

export type OpeningHoursItemStatus = 'COMPLIANT' | 'VIOLATION' | 'UNKNOWN';

export interface VerifiedPlaceConstraintInfo {
  id: string;
  name: string;
  nameEn?: string | null;
  openingHours?: string | null;
}

export interface EvaluableItineraryItemInput {
  orderIndex: number;
  activity: string;
  placeId?: string | null;
  placeName?: string | null;
  startTime?: string | null;
  endTime?: string | null;
}

export interface EvaluableItineraryDayInput {
  dayNumber: number;
  date?: string | Date | null;
  items: EvaluableItineraryItemInput[];
}

export interface ItineraryScheduleViolation {
  code: ItineraryViolationCode;
  reasonCode: string;
  dayNumber: number;
  orderIndex: number;
  conflictingOrderIndex: number | null;
  activity: string;
  placeId: string | null;
  placeName: string | null;
  startTime: string | null;
  endTime: string | null;
  openingHours: string | null;
  effectiveDate: string | null;
  message: string;
}

export interface EvaluatedItemConstraintResult {
  openingHoursStatus: OpeningHoursItemStatus;
  openingHoursReasonCode: string;
  violations: ItineraryScheduleViolation[];
}

export interface EvaluatedItineraryResult {
  violations: ItineraryScheduleViolation[];
  perDayItemResults: Map<string, EvaluatedItemConstraintResult>;
}

const STRICT_HHMM_RE = /^(\d{2}):(\d{2})$/;
const ISO_DATE_PREFIX_RE = /^(\d{4})-(\d{2})-(\d{2})(?:$|T|\s)/;

const WEEKDAY_MAP: Record<string, number> = {
  mo: 0,
  tu: 1,
  we: 2,
  th: 3,
  fr: 4,
  sa: 5,
  su: 6,
};

const WEEKDAY_VI_LABELS: Record<number, string> = {
  0: 'Thứ Hai',
  1: 'Thứ Ba',
  2: 'Thứ Tư',
  3: 'Thứ Năm',
  4: 'Thứ Sáu',
  5: 'Thứ Bảy',
  6: 'Chủ nhật',
};

const MONTH_OR_SOLAR_TOKENS = new Set([
  'jan',
  'feb',
  'mar',
  'apr',
  'may',
  'jun',
  'jul',
  'aug',
  'sep',
  'oct',
  'nov',
  'dec',
  'ph',
  'sh',
  'sunrise',
  'sunset',
  'dawn',
  'dusk',
]);

const SELECTOR_GROUP_RE =
  /^(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*-\s*(?:Mo|Tu|We|Th|Fr|Sa|Su))?(?:\s*,\s*(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*-\s*(?:Mo|Tu|We|Th|Fr|Sa|Su))?)*\s+/i;
const STRICT_TIME_RANGE_RE = /^(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})$/;
const ANY_TIME_RANGE_RE = /^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$/;

interface ParsedOsmOpeningHours {
  supported: boolean;
  reasonCode: string;
  windowsByWeekday: Record<number, Array<[number, number]>>;
}

export function parseStrictHhmm(raw?: string | null): number | null {
  if (typeof raw !== 'string') return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const m = STRICT_HHMM_RE.exec(trimmed);
  if (!m) return null;
  const hh = Number(m[1]);
  const mm = Number(m[2]);
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return null;
  return hh * 60 + mm;
}

export function formatMinutesHhmm(minutes: number): string {
  const hh = Math.floor(minutes / 60)
    .toString()
    .padStart(2, '0');
  const mm = (minutes % 60).toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

function parseOsmTimeToken(hhStr: string, mmStr: string, allow24End: boolean): number | null {
  const hh = Number(hhStr);
  const mm = Number(mmStr);
  if (hh === 24 && mm === 0 && allow24End) return 1440;
  if (hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59) return hh * 60 + mm;
  return null;
}

function parseWeekdaySelectorGroup(selectorText: string): number[] | null {
  const cleaned = selectorText.trim();
  if (!cleaned) return null;
  const weekdays: number[] = [];
  const seen = new Set<number>();

  for (const rawPart of cleaned.split(',')) {
    const part = rawPart.trim();
    if (!part) return null;
    if (part.includes('-')) {
      const pieces = part.split('-').map((p) => p.trim().toLowerCase());
      if (pieces.length !== 2) return null;
      const [startTok, endTok] = pieces;
      if (!(startTok in WEEKDAY_MAP) || !(endTok in WEEKDAY_MAP)) return null;
      const startIdx = WEEKDAY_MAP[startTok];
      const endIdx = WEEKDAY_MAP[endTok];
      const span =
        startIdx <= endIdx
          ? Array.from({ length: endIdx - startIdx + 1 }, (_, k) => startIdx + k)
          : [
              ...Array.from({ length: 7 - startIdx }, (_, k) => startIdx + k),
              ...Array.from({ length: endIdx + 1 }, (_, k) => k),
            ];
      for (const wd of span) {
        if (!seen.has(wd)) {
          seen.add(wd);
          weekdays.push(wd);
        }
      }
    } else {
      const tok = part.toLowerCase();
      if (!(tok in WEEKDAY_MAP)) return null;
      const wd = WEEKDAY_MAP[tok];
      if (!seen.has(wd)) {
        seen.add(wd);
        weekdays.push(wd);
      }
    }
  }
  return weekdays;
}

function mergeWindows(windows: Array<[number, number]>): Array<[number, number]> {
  if (windows.length === 0) return [];
  const sorted = [...windows].sort((a, b) => (a[0] !== b[0] ? a[0] - b[0] : a[1] - b[1]));
  const merged: Array<[number, number]> = [sorted[0]];
  for (let i = 1; i < sorted.length; i++) {
    const [curS, curE] = sorted[i];
    const last = merged[merged.length - 1];
    if (curS <= last[1]) {
      last[1] = Math.max(last[1], curE);
    } else {
      merged.push([curS, curE]);
    }
  }
  return merged;
}

/**
 * Deterministic OSM opening_hours parser aligned with W06-OPENING-HOURS-PARSER-01C.
 * Conservatively returns `{ supported: false }` on null/empty or unsupported syntax
 * so unknown opening hours are NEVER falsely rejected as closed.
 */
export function parseOsmOpeningHours(raw?: string | null): ParsedOsmOpeningHours {
  const emptySchedule: Record<number, Array<[number, number]>> = {
    0: [],
    1: [],
    2: [],
    3: [],
    4: [],
    5: [],
    6: [],
  };

  if (typeof raw !== 'string' || raw.trim().length === 0) {
    return { supported: false, reasonCode: 'NULL_OR_EMPTY', windowsByWeekday: emptySchedule };
  }

  const trimmed = raw.trim();
  if (trimmed === '24/7') {
    return {
      supported: true,
      reasonCode: 'SUPPORTED_24_7',
      windowsByWeekday: {
        0: [[0, 1440]],
        1: [[0, 1440]],
        2: [[0, 1440]],
        3: [[0, 1440]],
        4: [[0, 1440]],
        5: [[0, 1440]],
        6: [[0, 1440]],
      },
    };
  }

  if (trimmed.includes('+')) {
    return { supported: false, reasonCode: 'UNSUPPORTED_OPEN_END_PLUS', windowsByWeekday: emptySchedule };
  }
  if (trimmed.includes('"')) {
    return { supported: false, reasonCode: 'UNSUPPORTED_COMMENT_SYNTAX', windowsByWeekday: emptySchedule };
  }

  const wordTokens = trimmed.toLowerCase().match(/[a-z]+/g) ?? [];
  for (const tok of wordTokens) {
    if (MONTH_OR_SOLAR_TOKENS.has(tok)) {
      return {
        supported: false,
        reasonCode: 'UNSUPPORTED_HOLIDAY_MONTH_OR_SOLAR',
        windowsByWeekday: emptySchedule,
      };
    }
  }

  const rules = trimmed
    .split(';')
    .map((r) => r.trim())
    .filter((r) => r.length > 0);
  if (rules.length === 0) {
    return { supported: false, reasonCode: 'NULL_OR_EMPTY', windowsByWeekday: emptySchedule };
  }

  const schedule: Record<number, Array<[number, number]>> = {
    0: [],
    1: [],
    2: [],
    3: [],
    4: [],
    5: [],
    6: [],
  };

  for (const rule of rules) {
    let targetWeekdays: number[];
    let body: string;

    const mSel = SELECTOR_GROUP_RE.exec(rule);
    if (mSel) {
      const parsedWeekdays = parseWeekdaySelectorGroup(mSel[0]);
      if (!parsedWeekdays || parsedWeekdays.length === 0) {
        return { supported: false, reasonCode: 'UNSUPPORTED_WEEKDAY_SELECTOR', windowsByWeekday: emptySchedule };
      }
      targetWeekdays = parsedWeekdays;
      body = rule.slice(mSel[0].length).trim();
    } else {
      targetWeekdays = [0, 1, 2, 3, 4, 5, 6];
      body = rule;
    }

    if (!body) {
      return { supported: false, reasonCode: 'UNSUPPORTED_EMPTY_RULE_BODY', windowsByWeekday: emptySchedule };
    }

    const bodyLower = body.toLowerCase();
    if (bodyLower === 'off' || bodyLower === 'closed') {
      for (const wd of targetWeekdays) {
        schedule[wd] = [];
      }
      continue;
    }

    if (body === '24/7') {
      for (const wd of targetWeekdays) {
        schedule[wd] = [[0, 1440]];
      }
      continue;
    }

    const parsedWindows: Array<[number, number]> = [];
    const rangeParts = body.split(',').map((p) => p.trim());
    for (const rPart of rangeParts) {
      const mRange = STRICT_TIME_RANGE_RE.exec(rPart);
      if (!mRange) {
        if (ANY_TIME_RANGE_RE.test(rPart)) {
          return { supported: false, reasonCode: 'UNSUPPORTED_NON_TWO_DIGIT_TIME', windowsByWeekday: emptySchedule };
        }
        return { supported: false, reasonCode: 'UNSUPPORTED_RULE_BODY', windowsByWeekday: emptySchedule };
      }

      const startMin = parseOsmTimeToken(mRange[1], mRange[2], false);
      const endMin = parseOsmTimeToken(mRange[3], mRange[4], true);
      if (startMin === null || endMin === null) {
        return { supported: false, reasonCode: 'INVALID_CLOCK_VALUE', windowsByWeekday: emptySchedule };
      }
      if (endMin <= startMin) {
        return { supported: false, reasonCode: 'UNSUPPORTED_CROSS_MIDNIGHT', windowsByWeekday: emptySchedule };
      }
      parsedWindows.push([startMin, endMin]);
    }

    const merged = mergeWindows(parsedWindows);
    for (const wd of targetWeekdays) {
      schedule[wd] = [...merged];
    }
  }

  return {
    supported: true,
    reasonCode: 'SUPPORTED_OSM_STANDARD',
    windowsByWeekday: schedule,
  };
}

function extractValidIsoDate(val?: string | Date | null): string | null {
  if (!val) return null;
  if (val instanceof Date) {
    if (Number.isNaN(val.getTime())) return null;
    return val.toISOString().slice(0, 10);
  }
  if (typeof val === 'string') {
    const trimmed = val.trim();
    const m = ISO_DATE_PREFIX_RE.exec(trimmed);
    if (!m) return null;
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const d = Number(m[3]);
    const dt = new Date(Date.UTC(y, mo - 1, d));
    if (
      dt.getUTCFullYear() !== y ||
      dt.getUTCMonth() + 1 !== mo ||
      dt.getUTCDate() !== d
    ) {
      return null;
    }
    return `${m[1]}-${m[2]}-${m[3]}`;
  }
  return null;
}

export function resolveEffectiveDayDateIso(
  dayDate?: string | Date | null,
  tripStartDate?: string | Date | null,
  dayNumber = 1,
): string | null {
  const direct = extractValidIsoDate(dayDate);
  if (direct) return direct;

  const baseIso = extractValidIsoDate(tripStartDate);
  if (!baseIso || dayNumber < 1) return null;

  const [y, mo, d] = baseIso.split('-').map(Number);
  const dt = new Date(Date.UTC(y, mo - 1, d + (dayNumber - 1)));
  return dt.toISOString().slice(0, 10);
}

function isoDateToMondayZeroWeekday(isoDate: string): number {
  const [y, mo, d] = isoDate.split('-').map(Number);
  const utcDay = new Date(Date.UTC(y, mo - 1, d)).getUTCDay(); // 0=Sun..6=Sat
  return (utcDay + 6) % 7; // 0=Mon..6=Sun
}

function itemResultKey(dayNumber: number, itemIdx: number): string {
  return `${dayNumber}:${itemIdx}`;
}

export function evaluateItineraryDays(
  days: EvaluableItineraryDayInput[],
  placesById: Map<string, VerifiedPlaceConstraintInfo>,
  tripStartDate?: string | Date | null,
): EvaluatedItineraryResult {
  const summaryViolations: ItineraryScheduleViolation[] = [];
  const perDayItemResults = new Map<string, EvaluatedItemConstraintResult>();

  for (const day of days) {
    const effectiveDate = resolveEffectiveDayDateIso(
      day.date,
      tripStartDate,
      day.dayNumber,
    );
    const validIntervals: Array<{
      itemIdx: number;
      item: EvaluableItineraryItemInput;
      startMin: number;
      endMin: number;
      place: VerifiedPlaceConstraintInfo | null;
    }> = [];

    for (let itemIdx = 0; itemIdx < (day.items?.length ?? 0); itemIdx++) {
      const item = day.items[itemIdx];
      const key = itemResultKey(day.dayNumber, itemIdx);
      const itemRes: EvaluatedItemConstraintResult = {
        openingHoursStatus: 'UNKNOWN',
        openingHoursReasonCode: 'NOT_EVALUATED',
        violations: [],
      };
      perDayItemResults.set(key, itemRes);

      const place =
        item.placeId && placesById.has(item.placeId)
          ? (placesById.get(item.placeId) ?? null)
          : null;
      const displayPlaceName = place?.name ?? item.placeName ?? null;
      const startRaw =
        typeof item.startTime === 'string' && item.startTime.trim().length > 0
          ? item.startTime.trim()
          : null;
      const endRaw =
        typeof item.endTime === 'string' && item.endTime.trim().length > 0
          ? item.endTime.trim()
          : null;

      const startMin = startRaw !== null ? parseStrictHhmm(startRaw) : null;
      const endMin = endRaw !== null ? parseStrictHhmm(endRaw) : null;

      if (
        (startRaw !== null && startMin === null) ||
        (endRaw !== null && endMin === null)
      ) {
        const v: ItineraryScheduleViolation = {
          code: 'TIME_INTERVAL_INVALID',
          reasonCode: 'MALFORMED_HHMM',
          dayNumber: day.dayNumber,
          orderIndex: item.orderIndex,
          conflictingOrderIndex: null,
          activity: item.activity,
          placeId: item.placeId ?? null,
          placeName: displayPlaceName,
          startTime: startRaw,
          endTime: endRaw,
          openingHours: place?.openingHours ?? null,
          effectiveDate,
          message: `Ngày ${day.dayNumber} • Mục #${item.orderIndex} "${item.activity}": định dạng giờ không hợp lệ (${startRaw ?? '?'} - ${endRaw ?? '?'}).`,
        };
        itemRes.openingHoursReasonCode = 'INVALID_VISIT_TIME';
        itemRes.violations.push(v);
        summaryViolations.push(v);
        continue;
      }

      if (startMin !== null && endMin !== null && endMin <= startMin) {
        const v: ItineraryScheduleViolation = {
          code: 'TIME_INTERVAL_INVALID',
          reasonCode: 'END_NOT_AFTER_START',
          dayNumber: day.dayNumber,
          orderIndex: item.orderIndex,
          conflictingOrderIndex: null,
          activity: item.activity,
          placeId: item.placeId ?? null,
          placeName: displayPlaceName,
          startTime: startRaw,
          endTime: endRaw,
          openingHours: place?.openingHours ?? null,
          effectiveDate,
          message: `Ngày ${day.dayNumber} • Mục #${item.orderIndex} "${item.activity}": giờ kết thúc (${endRaw}) phải sau giờ bắt đầu (${startRaw}).`,
        };
        itemRes.openingHoursReasonCode = 'INVALID_VISIT_TIME';
        itemRes.violations.push(v);
        summaryViolations.push(v);
        continue;
      }

      if (startMin !== null && endMin !== null) {
        validIntervals.push({
          itemIdx,
          item,
          startMin,
          endMin,
          place,
        });
      }

      // Opening-hours deterministic check (only when place has supported OSM openingHours, valid date, and visit time)
      if (!place) {
        itemRes.openingHoursStatus = 'UNKNOWN';
        itemRes.openingHoursReasonCode = 'UNMATCHED_OR_NON_POI';
        continue;
      }
      const parsedOh = parseOsmOpeningHours(place.openingHours);
      if (!parsedOh.supported) {
        itemRes.openingHoursStatus = 'UNKNOWN';
        itemRes.openingHoursReasonCode = parsedOh.reasonCode;
        continue;
      }
      if (!effectiveDate) {
        itemRes.openingHoursStatus = 'UNKNOWN';
        itemRes.openingHoursReasonCode = 'MISSING_VISIT_DATE';
        continue;
      }
      if (startMin === null) {
        itemRes.openingHoursStatus = 'UNKNOWN';
        itemRes.openingHoursReasonCode = 'MISSING_VISIT_TIME';
        continue;
      }

      const checkEndMin = endMin ?? Math.min(1440, startMin + 1);
      const weekday = isoDateToMondayZeroWeekday(effectiveDate);
      const dayWindows = parsedOh.windowsByWeekday[weekday] ?? [];
      const weekdayLabel = WEEKDAY_VI_LABELS[weekday] ?? effectiveDate;

      if (dayWindows.length === 0) {
        const v: ItineraryScheduleViolation = {
          code: 'OPENING_HOURS_CLOSED',
          reasonCode: 'CLOSED_ON_WEEKDAY',
          dayNumber: day.dayNumber,
          orderIndex: item.orderIndex,
          conflictingOrderIndex: null,
          activity: item.activity,
          placeId: place.id,
          placeName: place.name,
          startTime: startRaw,
          endTime: endRaw,
          openingHours: place.openingHours ?? null,
          effectiveDate,
          message: `Ngày ${day.dayNumber} (${effectiveDate}, ${weekdayLabel}) • Mục #${item.orderIndex} "${place.name}" đóng cửa vào ${weekdayLabel} (giờ mở cửa: ${place.openingHours}).`,
        };
        itemRes.openingHoursStatus = 'VIOLATION';
        itemRes.openingHoursReasonCode = 'CLOSED_ON_WEEKDAY';
        itemRes.violations.push(v);
        summaryViolations.push(v);
        continue;
      }

      const fitsWindow = dayWindows.some(
        ([wStart, wEnd]) => wStart <= startMin && checkEndMin <= wEnd,
      );
      if (!fitsWindow) {
        const windowsLabel = dayWindows
          .map(([ws, we]) => `${formatMinutesHhmm(ws)}-${formatMinutesHhmm(we)}`)
          .join(', ');
        const visitLabel =
          endRaw !== null ? `${startRaw} - ${endRaw}` : `${startRaw}`;
        const v: ItineraryScheduleViolation = {
          code: 'OPENING_HOURS_CLOSED',
          reasonCode: 'OUTSIDE_OPENING_HOURS_WINDOW',
          dayNumber: day.dayNumber,
          orderIndex: item.orderIndex,
          conflictingOrderIndex: null,
          activity: item.activity,
          placeId: place.id,
          placeName: place.name,
          startTime: startRaw,
          endTime: endRaw,
          openingHours: place.openingHours ?? null,
          effectiveDate,
          message: `Ngày ${day.dayNumber} (${effectiveDate}) • Mục #${item.orderIndex} "${place.name}" (${visitLabel}) nằm ngoài khung giờ mở cửa hôm đó (${windowsLabel}; quy tắc: ${place.openingHours}).`,
        };
        itemRes.openingHoursStatus = 'VIOLATION';
        itemRes.openingHoursReasonCode = 'OUTSIDE_OPENING_HOURS_WINDOW';
        itemRes.violations.push(v);
        summaryViolations.push(v);
        continue;
      }

      itemRes.openingHoursStatus = 'COMPLIANT';
      itemRes.openingHoursReasonCode = 'WITHIN_OPENING_HOURS_WINDOW';
    }

    // Pairwise overlap detection within the day
    for (let i = 0; i < validIntervals.length; i++) {
      const a = validIntervals[i];
      for (let j = i + 1; j < validIntervals.length; j++) {
        const b = validIntervals[j];
        const ovStart = Math.max(a.startMin, b.startMin);
        const ovEnd = Math.min(a.endMin, b.endMin);
        if (ovStart < ovEnd) {
          const ovLabel = `${formatMinutesHhmm(ovStart)} - ${formatMinutesHhmm(ovEnd)}`;
          const aStartStr = formatMinutesHhmm(a.startMin);
          const aEndStr = formatMinutesHhmm(a.endMin);
          const bStartStr = formatMinutesHhmm(b.startMin);
          const bEndStr = formatMinutesHhmm(b.endMin);

          const vForA: ItineraryScheduleViolation = {
            code: 'SCHEDULE_OVERLAP',
            reasonCode: 'OVERLAPPING_TIME_WINDOW',
            dayNumber: day.dayNumber,
            orderIndex: a.item.orderIndex,
            conflictingOrderIndex: b.item.orderIndex,
            activity: a.item.activity,
            placeId: a.item.placeId ?? null,
            placeName: a.place?.name ?? a.item.placeName ?? null,
            startTime: aStartStr,
            endTime: aEndStr,
            openingHours: a.place?.openingHours ?? null,
            effectiveDate,
            message: `Chồng giờ khoảng ${ovLabel} với mục #${b.item.orderIndex} "${b.item.activity}" (${bStartStr} - ${bEndStr}).`,
          };
          const vForB: ItineraryScheduleViolation = {
            code: 'SCHEDULE_OVERLAP',
            reasonCode: 'OVERLAPPING_TIME_WINDOW',
            dayNumber: day.dayNumber,
            orderIndex: b.item.orderIndex,
            conflictingOrderIndex: a.item.orderIndex,
            activity: b.item.activity,
            placeId: b.item.placeId ?? null,
            placeName: b.place?.name ?? b.item.placeName ?? null,
            startTime: bStartStr,
            endTime: bEndStr,
            openingHours: b.place?.openingHours ?? null,
            effectiveDate,
            message: `Chồng giờ khoảng ${ovLabel} với mục #${a.item.orderIndex} "${a.item.activity}" (${aStartStr} - ${aEndStr}).`,
          };

          perDayItemResults.get(itemResultKey(day.dayNumber, a.itemIdx))?.violations.push(vForA);
          perDayItemResults.get(itemResultKey(day.dayNumber, b.itemIdx))?.violations.push(vForB);

          summaryViolations.push({
            code: 'SCHEDULE_OVERLAP',
            reasonCode: 'OVERLAPPING_TIME_WINDOW',
            dayNumber: day.dayNumber,
            orderIndex: b.item.orderIndex,
            conflictingOrderIndex: a.item.orderIndex,
            activity: b.item.activity,
            placeId: b.item.placeId ?? null,
            placeName: b.place?.name ?? b.item.placeName ?? null,
            startTime: bStartStr,
            endTime: bEndStr,
            openingHours: b.place?.openingHours ?? null,
            effectiveDate,
            message: `Ngày ${day.dayNumber}: Mục #${a.item.orderIndex} "${a.item.activity}" (${aStartStr} - ${aEndStr}) và mục #${b.item.orderIndex} "${b.item.activity}" (${bStartStr} - ${bEndStr}) bị chồng giờ (${ovLabel}).`,
          });
        }
      }
    }
  }

  return {
    violations: summaryViolations,
    perDayItemResults,
  };
}
