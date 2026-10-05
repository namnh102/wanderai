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

## Realtime location & navigation (TASK 08.1 & TASK 08.1.1)

- **Location Data Model & Quality Gate** (`features/location/providers/user_location_provider.dart`):
  - State machine: `unknown`, `requesting`, `granted`, `denied`, `unavailable`.
  - Fix representation: `LocationFix` with `position` (`LatLng`), `accuracyMeters` (`double`), `timestamp` (`DateTime`), and `quality` (`LocationAccuracyQuality`).
  - Quality classification: `good` ($\le 50\text{m}$), `approximate` ($50–200\text{m}$), `poor` ($> 200\text{m}$).
  - Quality Gate: Automatically retries up to 3 times on poor accuracy fixes (capped to 1 attempt on `kIsWeb` to prevent browser timeouts), selecting the best available fix. Good fixes complete immediately.
  - Position remains strictly `null` unless a real fix exists; approximate fixes are never presented as exact.
- **Platforms:** Web = browser geolocation (Geolocator web plugin, medium accuracy, 5s timeout); Android/iOS = OS location services; Desktop = platform location where available, else `unavailable`.
- **Map Visuals & Accuracy Circle:**
  - Blue user dot with halo (`user_location_marker`), wrapped in `IgnorePointer` to prevent intercepting POI taps.
  - Translucent accuracy disk (`CircleLayer`) rendered below POIs with radius equal to `accuracyMeters` in meters.
  - Multi-state location button (`idle`, `requesting`, `success`, `approximate`, `denied`, `unavailable`) using GoMate design tokens.
  - Compact status pill with honest feedback (`Đã xác định vị trí · ±X m`, `Vị trí ước lượng · ±X m`, `Vị trí chưa chính xác`, `Quyền vị trí bị từ chối`) with 5-second auto-dismiss and tap-to-dismiss.
- **Camera Policy:**
  - On map open: Camera remains fixed at default center; does NOT automatically recenter.
  - On POI tap: Does NOT move camera; opens preview sheet smoothly.
  - On returning from Place Detail: Camera position and zoom are preserved.
  - On explicit "Vị trí của tôi" tap: Smoothly animates camera to user location fix using 250ms cubic easing (`Curves.easeInOutCubic`). Preserves zoom level if $\ge 14.0$, or zooms to $15.0$ if zoomed out.
- **Distance:** Device-side `haversineKm` in `features/location/domain/geo_distance.dart`. Shared formatter:
  - $< 1\text{ km}$ ($< 1000\text{m}$): integer meters (e.g. `191m`, `850m`).
  - $\ge 1\text{ km}$: one decimal kilometer (e.g. `1.0 km`, `2.4 km`).
  - Unknown location => `Khoảng cách chưa xác định`. Backend map-center distance is completely ignored.
- **Navigation** (`features/places/data/navigation_service.dart`):
  - `Chỉ đường` opens external service without internal routing.
  - Web/Desktop: `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>[&origin=<lat>,<lng>]&travelmode=driving`.
  - Origin is included only when a valid fix exists. Lat/Lng ordering is strictly `lat,lng`.
- **Tests:** `test/location_navigation_test.dart` (52 tests covering accuracy thresholds, quality gate retry, camera behavior, distance formatting, and edge cases).

