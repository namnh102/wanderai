# TASK 08.1.1 — Location Reliability & UX Hardening Closure Audit

**Date:** 2026-10-04  
**Branch:** `feature/location-reliability-hardening`  
**Base Commit:** `3c50b52` (TASK 08.1 merge)  
**Status:** Verification Complete — Ready for Review  

---

## 1. Executive Summary & Problem Statement

During real-world browser usage on desktop/web, geolocation fixes can suffer from high inaccuracy (e.g. ISP/IP-based routing resolving to hundreds of meters or kilometers away). Users reported:
> *"sao vị trí sai hiện tại của tôi sai lung tung vậy"*

TASK 08.1.1 hardens location reliability and user feedback across the entire mobile application without compromising the honest data integrity principle:
1. **Never present poor accuracy as exact location.**
2. **Expose location accuracy transparently** (`±X m`).
3. **Accuracy Quality Gate with Retry:** When an initial fix is poor (`> 200m`), automatically retry up to 2–3 times to obtain a better fix before accepting.
4. **Visual Accuracy Feedback on Map:** Render a translucent accuracy disk (`CircleLayer`) matching `accuracyMeters` under POIs.
5. **Location Button Visual States:** Multi-state visual indicator (`idle`, `requesting`, `success`, `approximate`, `denied`, `unavailable`) using GoMate design system tokens.
6. **Smooth Camera Animation:** Smooth cubic-bezier glide with zoom policy preservation (zooms to 15.0 if overview, preserves zoom if already zoomed in).
7. **Unified Distance Formatter:** Consistent integer meters below 1 km (`< 1 km` => `Xm`) and one-decimal km (`>= 1 km` => `X.X km`), eliminating rounding artifacts near 1000m.
8. **Actionable Permission Recovery:** Direct "Mở cài đặt" actions in SnackBars invoking `openAppSettings()` / `openLocationSettings()`.

---

## 2. Architecture & Component Changes

### 2.1 Location Data Model & Quality Gate (`user_location_provider.dart`)
- **`LocationAccuracyQuality` Enum:**
  - `good`: `<= 50m`
  - `approximate`: `50m < accuracy <= 200m`
  - `poor`: `> 200m`
- **`LocationFix` Value Object:**
  - Holds `position` (`LatLng`), `accuracyMeters` (`double`), `timestamp` (`DateTime`).
  - Computes `quality` according to defined thresholds.
- **`UserLocationNotifier._fetchWithQualityGate()`:**
  - Queries `currentFix()`. If accuracy is `<= 50m` (good), completes immediately without delay.
  - If accuracy is poor (`> 200m`), retries up to 3 attempts with short delay.
  - Always selects the fix with minimum `accuracyMeters` among attempts.
  - If accuracy remains poor or approximate, transparently stores it with quality flag — never faking coordinates.
  - Direct exceptions (e.g. GPS hardware failure) fail immediately without retry delay.

### 2.2 Shared Distance Formatter (`geo_distance.dart`)
- Updated `formatDistanceKm`:
  ```dart
  String formatDistanceKm(double km) {
    if (km <= 0) return '0m';
    final meters = (km * 1000).round();
    if (meters < 1000) {
      return '${meters}m';
    }
    return '${km.toStringAsFixed(1)} km';
  }
  ```
- Prevents boundary artifacts where `0.9996 km` could render as `1000m`. Now consistently outputs `1.0 km`.

### 2.3 Map Screen & Visual Polish (`map_screen.dart`)
- **Accuracy Disk (`CircleLayer`):**
  - Renders translucent circle with radius `accuracyMeters` (`useRadiusInMeter: true`, `alpha: 0.12`, border `alpha: 0.35`).
  - Placed before POI layer so POI taps are never blocked.
- **User Marker:** Blue dot with white border and halo, wrapped in `IgnorePointer`.
- **Location Button States:**
  - `idle`: grey `my_location` icon
  - `requesting`: small `CircularProgressIndicator` inside button
  - `success` (good): info blue `my_location` icon
  - `approximate`: warning amber `location_searching` icon
  - `denied`: error red `location_disabled` icon
  - `unavailable`: text tertiary `location_off` icon
- **Status Pill UX:**
  - Compact pill with icon and honest label:
    - `Đã xác định vị trí · ±X m` (good)
    - `Vị trí ước lượng · ±X m` (approximate)
    - `Vị trí chưa chính xác` (poor)
    - `Quyền vị trí bị từ chối` (denied)
  - Auto-dismisses after 5 seconds on success.
  - Tap-to-dismiss interactive gesture.
- **Smooth Camera Animation:**
  - 250ms `Curves.easeInOutCubic` smooth interpolation.
  - Preserves user zoom when `>= 14.0`, zooms to `15.0` when overviewing.

---

## 3. Automated Test Verification Summary

| Test Suite | Commands Executed | Tests Passed | Tests Failed | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Flutter Mobile Tests** | `flutter test` | **152** | 0 | **PASS** |
| **Flutter Analysis** | `flutter analyze` | **0 issues** | 0 | **PASS** |
| **Backend Nest Build** | `npm run build` | **Exit 0** | 0 | **PASS** |
| **Backend Lint** | `npm run lint` | **0 errors** (52 warnings) | 0 | **PASS** |
| **Backend Jest E2E** | `npm run test:e2e` | **76 (10 suites)** | 0 | **PASS** |
| **AI Pytest Suite** | `python -m pytest tests/ -q` | **87 passed, 2 skipped** | 0 | **PASS** |

---

## 4. Verification Evidence Matrix

1. **Accuracy Quality Gate Tests:**
   - `thresholds: good (<= 50m), approximate (50-200m), poor (> 200m)`: PASS
   - `retry logic: retries up to 3 times on poor accuracy and selects best fix`: PASS
   - `retry logic: picks the lowest accuracyMeters even if all attempts are poor`: PASS
   - `immediate return: good fix on first attempt does not retry`: PASS

2. **Map Screen Location Hardening Tests:**
   - `renders accuracy circle with useRadiusInMeter below POI markers`: PASS
   - `denied tap shows SnackBar with "Mở cài đặt" action calling openAppSettings`: PASS
   - `unavailable service shows SnackBar with "Mở cài đặt" action calling openLocationSettings`: PASS
   - `status pill can be dismissed by tap`: PASS

3. **Camera & Distance Tests:**
   - `tapping "Vị trí của tôi" DOES recenter on the fix`: PASS
   - `a changed fix updates the marker; the camera moves only on tap`: PASS
   - `Shared Distance Formatter Edge Cases`: PASS
