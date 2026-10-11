# TASK 08.1 - Closure audit (realtime location & navigation)

Branch: `feature/realtime-location-navigation`. Date: 2026-10-04.

## 1. The unknown `flutter test` exit code 1

Original symptom: a full `flutter test` run (output piped through `Select-String`) reported exit code 1 and the captured output ended at `+118` without a summary line.

Investigation (unfiltered output redirected to a file, nothing hidden):

| Run | Command | Result |
|---|---|---|
| 1 | `flutter test --reporter expanded` | exit 0, `+127: All tests passed!` |
| 2 | same | exit 0, `+127: All tests passed!` (the task wrapper still showed exit 1 because the chained trailing `git grep` found no match; harness artefact, not a test failure) |
| 3 | same, after adding camera/state-machine tests | exit 0, `+143: All tests passed!` |
| 4 | `--test-randomize-ordering-seed random` (seed 3252860629) | exit 0, `+143: All tests passed!` |

Conclusion: the failure is **not reproducible**; the current suite is clean, also under shuffled order (no order dependence). The most likely explanation for the original report is the same harness artefact: the pipeline's last command (`Select-String`/`git grep`) sets the exit status, and the output was truncated before the summary line. This is stated as a likely cause, not a proven one; no failing test was ever observed.

## 2. Camera behaviour (automated)

`MapScreen` gained an optional `mapController` parameter (null in the app) so tests can observe the camera. No production behaviour changed. Tests in `test/location_navigation_test.dart`:

- opening the map does NOT recenter even when a fix is already available (marker drawn, camera stays at the default centre, no permission prompt);
- tapping "Vị trí của tôi" DOES recenter (zoom 15) on the fix;
- a denied tap does not move the camera;
- a changed fix updates the marker only after the next tap, and the camera moves only on tap (a 2 s wait with a moved device changes nothing);
- returning from Place Detail does NOT recenter (camera stays at the user's panned centre/zoom; marker still drawn).

## 3. Location state machine (tests)

`unknown -> requesting -> granted`, `-> denied`, `-> unavailable` asserted by recording every state. Position is `null` during `requesting`, `denied` and `unavailable`; a later failure/denial clears the previous coordinates (stale coordinates are never shown as realtime); permission state and position are independent (permission granted but no fix => `unavailable`, no position).

## 4. Distance source (traced)

browser/OS fix -> `GeolocatorLocationService.currentPosition()` -> `UserLocationNotifier.state.position` -> `distanceFromUserKm()` (device-side Haversine, `geo_distance.dart`) -> `PlacePreviewSheet.distanceKm` and `PlaceDetailView.distanceKm`. The backend `distanceKm` (computed from the map centre) is still parsed into `PlaceModel` for API compatibility but is not displayed; a test asserts a server value of 99 km is never rendered. Known pair `(21.03,105.85) -> (21.0479,105.83676)` = 2.418 km (tolerance 0.02).

## 5. Latitude/longitude order (audit)

| Place | Order | Status |
|---|---|---|
| Flutter `LatLng(lat, lng)` everywhere (`PlaceMiniMap`, markers, user marker) | lat, lng | OK |
| `GeolocatorLocationService`: `LatLng(p.latitude, p.longitude)` | lat, lng | OK |
| Nearby API call: `lat: c.latitude`, `lng: c.longitude` | named params | OK |
| PostGIS (`places.service.ts`): `ST_MakePoint(p.longitude, p.latitude)` vs `ST_MakePoint(${lng}, ${lat})` | lng, lat (PostGIS x,y) | OK |
| Haversine: `dLat = b.latitude - a.latitude` | lat | OK; swapped-argument test proves a different result |
| Google destination/origin | `"lat,lng"` | OK (tested) |
| Apple Maps `daddr`/`saddr` | `"lat,lng"` | OK (tested) |

## 6. Browser evidence (Flutter Web, Chrome)

All coordinates below are **emulated browser geolocation (DevTools)**, not real GPS. Evidence: `docs/audit/evidence/task-08.1-closure/` (A1-A3 from an earlier pass, B0, B0b, B0c, B1, B2, C1) and `docs/audit/evidence/task-08.1/`.

| Check | Result |
|---|---|
| A. Permission blocked: tap "Vị trí của tôi" -> "Quyền vị trí bị từ chối" | PASS |
| A. Marker distance chip reads "Khoảng cách chưa xác định", no km | PASS |
| A. Blocked: no blue dot and no pill before tapping (D1b); after tapping only the denied pill, still no dot, map pixel-identical (D2) | PASS |`n| B. Emulated 21.03,105.85: on open the camera stays on the default view (silent read draws the pill) | PASS |
| B. After panning away, "Vị trí của tôi" centres the map on the blue dot (B1) | PASS |
| B. Chùa Trấn Quốc 2.4 km vs haversine 2.418 | PASS |
| B. Emulation changed to 21.05,105.80, then tap again: marker moves, 3.8 km vs haversine 3.822 | PASS |
| B. Emulation changed to 21.05,105.80 with no interaction for 11 s: dot and map identical (D3 vs D4); one tap on "Vị trí của tôi" then moves both (D5_after_retap) | PASS |`n| C. Detail distance 3.8 km equals preview; OSM source shown; hint "Điều hướng sẽ mở ứng dụng bản đồ" | PASS |
| C. `Chỉ đường` URL (window.open log): `https://www.google.com/maps/dir/?api=1&destination=21.047900%2C105.836760&origin=21.050000%2C105.800000&travelmode=driving` | PASS (destination = place, origin = emulated fix; host not openstreetmap.org) |
| C. Back to map: view kept, sheet kept, blue dot still visible (C1) | PASS |
| D. Console | no messages; GlobalKey 0, RenderFlex 0, other app errors 0 (page reloaded twice, so only post-reload messages were visible) |

Real (non-emulated) geolocation: on an earlier run, before emulation was applied, the app received the machine's actual Chrome location (about 20.98, 105.79, matching Google Maps in the user's own browser), showing the app uses a genuine fix and no default. Desktop Chrome positions come from Wi-Fi/IP and can be off by hundreds of metres to kilometres.

Incident: while the audit ran, the audit browser's emulation (21.05,105.80) was visible in the user's Chrome and looked like a wrong location (the user's real position was near Văn Quán, Hà Đông). Emulation has been cleared and the site's location permission reset to "Ask".

## 7. Platform status

- Web: verified (emulated geolocation + one earlier real Chrome fix).
- Android: not executed.
- iOS: not executed.
- Desktop (Windows/Linux/macOS native app): not executed.

## 8. Remaining limitations

- Native handlers (`geo:`, Apple Maps) are unit-tested as URIs only.
- The external Google page was never loaded to completion; only the generated URL was verified.
- No accuracy radius is shown on the map; the blue dot is a point estimate.
