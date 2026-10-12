import { Prisma } from '@prisma/client';

/**
 * Canonical extraction of factual OSM metadata from `PlaceSource.rawData`.
 *
 * Shapes found in the database (W3-04 inspection):
 *  - canonical nested : rawData.tags[key]        (621 OSM rows)
 *  - historical flat  : rawData[key]             (~34 OSM rows)
 *
 * Priority: nested canonical first, flat fallback second. The same rule is mirrored in SQL by
 * `osmTagSql` / `osmAddressSql` and the two MUST stay equivalent.
 * `places.address` is importer-generated ("<name>, <city>") and is never used here.
 */
export type RawData = Record<string, unknown> | null | undefined;

function clean(v: unknown): string | null {
  return typeof v === 'string' && v.trim() !== '' ? v.trim() : null;
}

function nestedTags(raw: RawData): Record<string, unknown> | null {
  const t = raw?.['tags'];
  return t && typeof t === 'object' && !Array.isArray(t) ? (t as Record<string, unknown>) : null;
}

/** First non-empty value among `keys`: all keys nested first (in order), then all keys flat. */
export function osmTag(raw: RawData, ...keys: string[]): string | null {
  const nested = nestedTags(raw);
  if (nested) {
    for (const k of keys) {
      const v = clean(nested[k]);
      if (v) return v;
    }
  }
  if (raw) {
    for (const k of keys) {
      const v = clean(raw[k]);
      if (v) return v;
    }
  }
  return null;
}

/** Factual address from OSM `addr:*` tags only (null when OSM has none). */
export function osmAddress(raw: RawData): string | null {
  const parts = [
    [osmTag(raw, 'addr:housenumber'), osmTag(raw, 'addr:street')].filter(Boolean).join(' ') || null,
    osmTag(raw, 'addr:suburb', 'addr:district'),
    osmTag(raw, 'addr:city'),
  ].filter((x): x is string => !!x);
  return parts.length > 0 ? parts.join(', ') : null;
}

export const osmWebsite = (raw: RawData) => osmTag(raw, 'website', 'contact:website');
export const osmPhone = (raw: RawData) => osmTag(raw, 'phone', 'contact:phone');
export const osmOpeningHours = (raw: RawData) => osmTag(raw, 'opening_hours');

/* ---------------------------- SQL mirror ---------------------------- */

/** Keys are internal constants; inlined as quoted literals so `->>` resolves to the text operator. */
const lit = (k: string) => Prisma.raw(`'${k.replace(/'/g, "''")}'`);

/**
 * SQL: first non-empty among keys, nested first then flat (mirror of `osmTag`).
 * `col` and `keys` are trusted internal literals, never user input.
 */
export function osmTagSql(col: string, ...keys: string[]): Prisma.Sql {
  const c = Prisma.raw(col);
  const nested = keys.map((k) => Prisma.sql`NULLIF(btrim((${c}->'tags')->>${lit(k)}), '')`);
  const flat = keys.map((k) => Prisma.sql`NULLIF(btrim(${c}->>${lit(k)}), '')`);
  return Prisma.sql`COALESCE(${Prisma.join([...nested, ...flat])})`;
}

/** SQL mirror of `osmAddress`. */
export function osmAddressSql(col: string): Prisma.Sql {
  return Prisma.sql`NULLIF(concat_ws(', ',
    NULLIF(concat_ws(' ', ${osmTagSql(col, 'addr:housenumber')}, ${osmTagSql(col, 'addr:street')}), ''),
    ${osmTagSql(col, 'addr:suburb', 'addr:district')},
    ${osmTagSql(col, 'addr:city')}
  ), '')`;
}
