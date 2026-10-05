# TASK 08.1.1 — Location Accuracy, Permission & Navigation UX Hardening

**Date:** 2026-10-04  
**Branch:** `feature/location-reliability-hardening`  
**Base Commit:** `3c50b52` (TASK 08.1 merge)  
**Status:** Verification Complete — Ready for Review  

---

## 1. Executive Summary & Root Cause Analysis

### User Problem Statement
Users reported critical UX and reliability issues with location:
1. *"sao vị trí sai hiện tại của tôi sai lung tung vậy"* (My current location is all over the place / completely wrong)
2. *"lâu vậy vẫn sai là sao cứ chạy lung tung hết"* (Why is it taking so long, still wrong, and jumping all over the place)

### Root Cause Analysis

1. **Desktop/Browser Geolocation Fallback (IP/Wi-Fi vs GPS):**
   - **Root Cause:** Standard laptops and desktop PCs running Chrome/Edge do NOT have dedicated hardware GPS receivers. The browser relies on the OS/Google Geolocation API using Wi-Fi BSSID triangulation or public ISP IP address routing.
   - On desktop in Vietnam (e.g. Hanoi), Wi-Fi/ISP routing often reports a fix with an accuracy radius of 500m – 50,000m (frequently defaulting to central ISP gateways in Hoan Kiem or Cau Giay even when the user is in Ha Dong/Van Quan).
   - In contrast, Google Maps in the browser may leverage signed-in user location history, Google account synchronization from smartphones, and cached network profiles.
   - **Fix:** Never pretend an approximate location is exact. Explicitly disclose accuracy in meters (`±X m`), render an accuracy circle corresponding to `accuracyMeters`, and clearly differentiate good GPS fixes ($\le 50\text{m}$) from approximate network fixes ($50\text{m} - 200\text{m}$) and poor fixes ($> 200\text{m}$).

2. **Excessive Latency on Web ("lâu vậy"):**
   - **Root Cause:** The initial implementation attempted `LocationAccuracy.high` and multiple sequential retries on desktop Chrome. Chrome's Geolocation service would wait 10+ seconds searching for Wi-Fi scans before falling back, causing a 20–30s freeze.
   - **Fix:** On `kIsWeb`, configure `LocationAccuracy.medium` with a 5-second timeout and 1 single attempt (`maxQualityRetries = 1`). Geolocation now resolves in $< 1$ second on web browsers.

3. **POI List Disappearance and Camera Jumping ("cứ chạy lung tung hết"):**
   - **Root Cause 1:** In `MapScreen`, tapping "Vị trí của tôi" previously invoked `ref.read(mapProvider.notifier).moveCenter(pos)`. Because `moveCenter` re-queries PostGIS nearby places centered on the user's coordinates, whenever a user outside central Hanoi (e.g. Ha Dong) clicked the button, the query center moved away from Hanoi, causing all 357 Hanoi places to vanish with "Không tìm thấy địa điểm".
   - **Root Cause 2:** In `_buildMarker`, every POI marker tap was triggering `_mapController.move(placeLatLng, currentZoom)`. This caused violent camera jerks whenever a user simply clicked a marker to view its preview sheet.
   - **Fix:** Removed `moveCenter(pos)` from "Vị trí của tôi" so POIs are never discarded or re-queried when finding user location. Removed `_mapController.move` from marker taps. Camera moves smoothly only on explicit user intent via "Vị trí của tôi".

4. **Distance Formatting Artifacts:**
   - **Root Cause:** Values such as `0.9996 km` could render as `1000m` or `1 km` inconsistently.
   - **Fix:** Boundary-safe integer meters below 1 km (`(km * 1000).round() < 1000` => `Xm`) and one-decimal km (`>= 1000` => `X.X km`).

---

## 2. Accuracy Quality Gate & Architecture

### 2.1 Quality Gate Classification
In `apps/mobile/lib/features/location/providers/user_location_provider.dart`:
- **`good` ($\le 50\text{m}$):** High-confidence GPS or low-noise fix. Pill label: `Đã xác định vị trí · ±X m`. Button state: `success`.
- **`approximate` ($50\text{m} < \text{accuracy} \le 200\text{m}$):** Medium-confidence network/Wi-Fi fix. Pill label: `Vị trí ước lượng · ±X m`. Button state: `approximate`.
- **`poor` ($> 200\text{m}$):** Coarse IP/cellular fix. Pill label: `Vị trí chưa chính xác`. Button state: `approximate`.

### 2.2 Quality Gate & Retry Strategy
```dart
Future<void> _fetchWithQualityGate({int maxQualityRetries = 3}) async {
  // On web, maxQualityRetries is capped to 1 to avoid browser hang
  LocationFix? bestFix;
  for (int attempt = 0; attempt < maxQualityRetries; attempt++) {
    final fix = await _service.currentFix();
    if (fix != null) {
      if (bestFix == null || fix.accuracyMeters < bestFix.accuracyMeters) {
        bestFix = fix;
      }
      if (fix.quality == LocationAccuracyQuality.good) break;
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }
  }
  // Store bestFix with honest quality disclosure
}
```

### 2.3 Visual Representation on Map
- **Translucent Accuracy Disk:** Rendered via `CircleLayer` below POI markers:
  - `radius`: `accuracyMeters`
  - `useRadiusInMeter`: `true`
  - `color`: `AppColors.info.withValues(alpha: 0.12)`
  - `borderColor`: `AppColors.info.withValues(alpha: 0.35)`
- **Blue User Marker:** Wrapped in `IgnorePointer` to ensure accuracy circle and user marker never intercept or block POI taps.
- **Interactive Status Pill:**
  - Auto-dismisses after 5 seconds on success.
  - Interactive tap-to-dismiss gesture.

---

## 3. Distance & Navigation Validation

### 3.1 Device-Side Haversine Formula
```dart
double haversineKm(LatLng p1, LatLng p2) {
  const r = 6371.0; // Earth radius in km
  final dLat = _degToRad(p2.latitude - p1.latitude);
  final dLon = _degToRad(p2.longitude - p1.longitude);
  final a = sin(dLat / 2) * sin(dLat / 2) +
      cos(_degToRad(p1.latitude)) *
          cos(_degToRad(p2.latitude)) *
          sin(dLon / 2) *
          sin(dLon / 2);
  final c = 2 * atan2(sqrt(a), sqrt(1 - a));
  return r * c;
}
```

### 3.2 Distance Display Rules
- Distance is computed strictly from the device's realtime fix to the destination coordinates.
- Backend map-center distance is completely ignored.
- When location is null/denied/unavailable: `Khoảng cách chưa xác định`.
- Distance formatting:
  - $0\text{m} - 999\text{m}$: integer meters (e.g., `191m`, `850m`).
  - $\ge 1000\text{m}$: one decimal kilometer (e.g., `1.0 km`, `2.4 km`).

### 3.3 Navigation URL Generation
External navigation URL contract:
- Target: `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>[&origin=<lat>,<lng>]&travelmode=driving`
- Origin is included **only** when a valid fix exists.
- Lat/Lng ordering is strictly `latitude,longitude`.

---

## 4. Camera Policy
- **On Map Open:** Camera remains fixed at the default Hanoi center (`21.0285, 105.8542`). No automatic recentering.
- **On POI Tap:** Opens preview sheet without camera animation or jumping.
- **On Returning from Place Detail:** Camera maintains its exact previous viewport.
- **On Explicit "Vị trí của tôi" Tap:** Smoothly animates camera to user location fix using 250ms cubic easing (`Curves.easeInOutCubic`). Preserves zoom level if already zoomed in ($\ge 14.0$), or zooms to $15.0$ if zoomed out.

---

## 5. Automated Verification Matrix

| Test Category | Suite / Command | Result | Details |
| :--- | :--- | :---: | :--- |
| **Flutter Mobile Tests** | `flutter test` | **152 / 152 PASSED** | All 52 location & navigation tests pass |
| **Flutter Analysis** | `flutter analyze` | **0 issues** | Clean static analysis |
| **Backend Nest Build** | `npm run build` | **Exit 0** | Clean TypeScript compilation |
| **Backend Lint** | `npm run lint` | **0 errors** (52 warnings) | Clean linting |
| **Backend Jest E2E** | `npm run test:e2e` | **76 / 76 PASSED** | 10 suites passed |
| **AI Pytest Suite** | `pytest tests/ -q` | **87 passed, 2 skipped** | All AI tools and grounding contracts clean |

---

## 6. Browser Verification Evidence (Flutter Web)

Browser audit performed on `http://127.0.0.1:5000` with emulated geolocation:
- **01_map_initial.png:** Map loads at Hanoi center with clean HOT tiles; "Vị trí của tôi" in idle state; no user marker.
- **02_location_fixed.png:** Tapped "Vị trí của tôi"; location resolved in $< 1\text{s}$; blue marker and translucent accuracy disk rendered; status pill displays `Đã xác định vị trí · ±25 m`.
- **03_preview_distance.png:** Tapped POI "Chùa Trấn Quốc"; preview sheet displayed `2.4 km` (independent Haversine verification: 2.418 km); accuracy disk did not block POI tap.
- **04_dismiss_pill.png:** Status pill dismissed cleanly on tap; camera view and markers remained stable.

*Note on Testing Environment:*
- Web: Verified via Flutter Web on Chrome.
- Android: Native location intents and Android geolocator not executed in this environment.
- iOS: Apple Maps integration and CoreLocation not executed in this environment.
