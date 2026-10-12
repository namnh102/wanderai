/**
 * Destination rating trust boundary (W3-04 / PDG-003).
 *
 * `destinations.rating` is seeded from `data/seed/synthetic_destinations.json` (non-zero value, zero
 * reviews). It is NOT a traveler rating and must never be presented publicly as factual.
 * A destination rating is only exposed when it is backed by real reviews (`reviewCount > 0`);
 * otherwise the public value is `null`. No replacement rating is invented.
 */
export function trustedDestinationRating(
  rating: number | null | undefined,
  reviewCount: number | null | undefined,
): number | null {
  return typeof rating === 'number' && rating > 0 && typeof reviewCount === 'number' && reviewCount > 0
    ? rating
    : null;
}

/** Returns a copy of a destination-shaped object whose `rating` is trust-checked. Null-safe. */
export function sanitizeDestination<T extends { rating?: number | null; reviewCount?: number | null }>(
  dest: T,
): T;
export function sanitizeDestination<T extends { rating?: number | null; reviewCount?: number | null }>(
  dest: T | null | undefined,
): T | null;
export function sanitizeDestination<T extends { rating?: number | null; reviewCount?: number | null }>(
  dest: T | null | undefined,
): T | null {
  if (!dest) return null;
  return { ...dest, rating: trustedDestinationRating(dest.rating, dest.reviewCount) };
}
