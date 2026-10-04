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

## Shared address contract (TASK 08 polish)

Preview sheet, list, nearby and detail all use the same factual semantics:

- Backend: `osmAddress(tags)` in `places.service.ts` builds the address from OSM `addr:*` tags in `place_sources.raw_data`; `findAll`, `findNearby` (SQL subquery) and `findById` return it, or `null`. The importer-built `places.address` ("<name>, <city>") is never served.
- Flutter: `PlaceModel.hasAddress` / `addressDisplay` / `addressUnavailableText` (`Chưa có thông tin địa chỉ.`). `PlacePreviewSheet` (key `place_preview_address`) and `PlaceDetailScreen` both render `addressDisplay`; no address is ever composed from name + city.
- Tests: `place-detail.e2e-spec.ts` (list = nearby = detail, unverified null) and `place_detail_test.dart` (real address, null address, no fabricated text).

## Realtime location & navigation (TASK 08.1)

- **Location** (`features/location/providers/user_location_provider.dart`): states `unknown`, `requesting`, `granted`, `denied`, `unavailable`. Position is `null` unless a real fix was obtained; nothing is ever defaulted. On open the map only silently reads a fix if permission was already granted (never prompts, never moves the camera). The `Vị trí của tôi` button (`my_location_button`) requests permission/fix and recenters; later taps refresh and recenter. Passive updates never move the camera.
- **Platforms:** web = browser geolocation (Geolocator web plugin); Android/iOS = OS location services; desktop = platform location where available, else `unavailable`.
- **Marker:** blue dot with halo (`user_location_marker`), drawn below POI markers and wrapped in `IgnorePointer`; POI category markers are coloured circles with icons.
- **Distance:** `haversineKm` from the user's real fix to the place (`features/location/domain/geo_distance.dart`) on both the preview sheet and Place Detail. The server `distanceKm` (computed from the map centre) is no longer displayed. Unknown location => `Khoảng cách chưa xác định`.
- **Navigation** (`features/places/data/navigation_service.dart`): `Chỉ đường` opens an external service; GoMate never routes. Web/desktop: `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>[&origin=<lat>,<lng>]&travelmode=driving` (origin only with a real fix; no API key). Android: `geo:` intent, falling back to the Google URL. iOS: Apple Maps `daddr`/`saddr`, falling back to the Google URL. The openstreetmap.org website is no longer used for directions (source/attribution links to OSM remain). Detail shows `Điều hướng sẽ mở ứng dụng bản đồ` above the button.
- **Tests:** `test/location_navigation_test.dart` (27), plus updated `map_test.dart` and `place_detail_test.dart`.
