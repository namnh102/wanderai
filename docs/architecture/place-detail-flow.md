# Place Detail Flow (TASK 08)

```
Map marker tap
  → mapProvider.selectPlace(place)           (list data: name, category, rating?, distance)
  → PlacePreviewSheet
      "Xem chi tiết"  → context.push('/places/:id')
  → PlaceDetailScreen(placeId)
      placeDetailProvider(id)  → PlaceRepository.getPlaceById → GET /places/:id
  → Back (AppBar arrow / system back) → context.pop() → MapScreen (unchanged state)
```

## Navigation decisions

- `/places/:id` is a top-level `GoRoute` (like `/trips/:id`), **outside** the `ShellRoute`. It is reached with `push`, so `MapScreen` stays mounted beneath it: camera, markers, selected category, search and radius are preserved on back.
- No new `GoRouter` is created and no navigator key is added (`RouterNotifier` + persistent root/shell keys from TASK 07.6 are untouched), so no duplicate `GlobalKey`.
- Deep link / refresh on `/places/:id`: no back stack → back falls back to `context.go('/map')`.

## Screen composition (GoMate tokens only)

| Section | Rule |
|---------|------|
| Hero | name, optional English name, category label, **verified badge only when `isVerified`**, destination |
| Rating | `RatingView`: real rating, else `Chưa có đánh giá` (☆) |
| Address | text, else `Chưa có thông tin địa chỉ.` |
| Opening hours | text, else `Chưa có thông tin giờ mở cửa.` |
| Contact | section **omitted** unless website and/or phone exist |
| Description | omitted unless stored for a verified place |
| Location | coordinates + non-interactive mini map (OSM HOT tiles, attribution) |
| Provenance | `Nguồn: OpenStreetMap`, clickable canonical URL, ODbL / attribution; unverified → "chưa được xác minh nguồn dữ liệu" |
| CTA | `Chỉ đường` (fixed bottom bar) when coordinates exist |

States: loading (`AppLoading`), error with retry (`AppErrorState`), 400/404 → empty state (`AppEmptyState`, "Về bản đồ").

## "Chỉ đường" — coordinates only

No routing provider is invented. The CTA hands the OS a neutral `geo:<lat>,<lng>?q=<lat>,<lng>` URI. Where no handler exists (e.g. Flutter Web / desktop) it opens the OpenStreetMap *location* of the same coordinates (`https://www.openstreetmap.org/?mlat=..&mlon=..#map=17/lat/lon`) — a location view, not turn-by-turn routing.

## Data integrity

- Facts originate from `place_sources.raw_data` (OSM tags) / `places`; the backend returns `null` otherwise and Flutter renders an honest unavailable state.
- Verified status derives from genuine `place_sources`; unverified records get no badge, no source and no descriptive facts.
- Only `trusted` reviews can be returned; ratings are never defaulted.

## Files

- Backend: `places.service.ts` (`findById`), `places.controller.ts` (`ParseUUIDPipe`), `test/place-detail.e2e-spec.ts`
- Flutter: `features/places/presentation/place_detail_screen.dart`, `widgets/place_mini_map.dart`, `features/places/providers/place_detail_provider.dart`, `place_model.dart` (+`PlaceSourceInfo`), `place_preview_sheet.dart` (`onViewDetail`), `app_router.dart`, `test/place_detail_test.dart`
