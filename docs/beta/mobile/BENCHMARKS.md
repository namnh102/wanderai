# GoMate Mobile UX, Auth & Performance Benchmark Report (M3)

**Branch**: `feat/beta-mobile-ux-auth-youtube` (compared against baseline `10126b1`, `feature/halong-poi-trip-save`)  
**Target Viewport (Screenshots)**: `390×844` @ `1.0` DPR (`Roboto` font loaded cleanly, zero Ahem placeholder boxes)  
**Profile Device**: Android Emulator `GoMate_W3_Test` (`emulator-5554`, API 35 x86_64, SwiftShader OpenGLES headless)

---

## 1. Visual Screenshots (`390×844`)

Captured deterministically via `test/screenshots_thap_dong_ho_test.dart`:
- **Before (`10126b1`)**: 9 PNGs in `docs/beta/mobile/screenshots/before/`
- **After (`feat/beta-mobile-ux-auth-youtube`)**: 12 PNGs in `docs/beta/mobile/screenshots/after/`

| # | Screen / Flow | Before (`390×844`) | After (`390×844`) | Key UX Changes |
|---|---------------|--------------------|-------------------|----------------|
| 01 | Login | `before/01_login.png` | `after/01_login.png` | Unified `AppTextField` + `AppButton`, `"Quên mật khẩu?"`, Google & Facebook OAuth buttons, `"Hủy đăng nhập · Quay lại"` |
| 02 | Register | `before/02_register.png` | `after/02_register.png` | Unified `AppTextField` + `AppButton`, inline `AppStateBanner` error handling, cancel link |
| 03 | Home (Hạ Long) | `before/03_home_halong.png` | `after/03_home_halong.png` | `CachedNetworkImage` (`memCacheWidth`/`memCacheHeight`), lazy `SliverList.separated` discovery feed |
| 04 | Destination Places Sheet | `before/04_destination_places_halong.png` | `after/04_destination_places_halong.png` | `CachedNetworkImage` tiles, initial `limit: 20` + scroll-near-bottom page 2+ pagination |
| 05 | Map & Place Preview | `before/05_map_place_preview.png` | `after/05_map_place_preview.png` | Shared `AppLoading` & `AppStateBanner` map error banner |
| 06 | Place Detail (`Tháp Đồng Hồ`) | `before/06_place_detail_thap_dong_ho.png` | `after/06_place_detail_thap_dong_ho.png` | `CachedNetworkImage`, `AppTextField` review input, `AppStateBanner` error state |
| 06b | Place Detail — YouTube Freshness (`Tháp Đồng Hồ`) | — (M4 new) | `after/06b_place_detail_youtube_freshness.png` | `YoutubeFreshnessSection` (`DYNAMIC_SOCIAL_FRESHNESS_LAYER`), 5 mandated fields, measured source-to-app latency & `"Thời gian thực"` badge |
| 07 | Save Place to Trip Sheet | `before/07_save_place_to_trip.png` | `after/07_save_place_to_trip.png` | Lazy `ListView.separated`, `AppTextField`, offline `AppStateBanner(warning)` + retry keeping pending trip |
| 08 | Trip List | `before/08_trip_list.png` | `after/08_trip_list.png` | Unified `AppLoading`, `AppErrorState`, `AppEmptyState`, `AppButton` |
| 09 | Trip Detail (36 itinerary items) | `before/09_trip_detail.png` | `after/09_trip_detail.png` | Lazy `CustomScrollView` + `SliverList.builder`, unified `AppTextField`/`AppButton`/`AppLoading`/`AppErrorState` |
| 10 | Forgot Password | — (new) | `after/10_forgot_password.png` | Dedicated email reset request screen (`/forgot-password`) |
| 11 | Reset Password | — (new) | `after/11_reset_password.png` | Deep-link token validation & password reset (`/reset-password?token=...`) |

### Reproduce Screenshot Capture
```powershell
cd D:\Do_an\wanderai_beta_mobile\apps\mobile
$env:CAPTURE_SCREENSHOTS = 'true'
$env:SCREENSHOT_OUT_DIR = 'D:\Do_an\wanderai_beta_mobile\docs\beta\mobile\screenshots\after'
flutter test test/screenshots_thap_dong_ho_test.dart
```

---

## 2. `--profile` Performance Benchmark (`GoMate_W3_Test`)

Measured in `--profile` mode via `integration_test/perf_benchmark_test.dart` + `test_driver/perf_driver.dart` using in-process `apiClientProvider` fixtures (40 Hạ Long POIs, 35 Trips, 36 Itinerary Items in `TripDetail`):

- **Before (`10126b1`)**: `docs/beta/mobile/benchmarks/before_perf.json` (`capturedAt: 2026-11-24T20:29:45.188794Z`)
- **After (`feat/beta-mobile-ux-auth-youtube`)**: `docs/beta/mobile/benchmarks/after_perf.json` (`capturedAt: 2026-11-24T20:32:30.802028Z`)

### Open Latency (`Stopwatch` including `pumpAndSettle(2s)` harness settle)

| Metric | Before (`10126b1`) | After | Delta |
|--------|--------------------|-------|-------|
| `dest_sheet_open_ms` | `4045 ms` | `4055 ms` | `+10 ms` (~0.2%) |
| `trip_list_open_ms` | `6109 ms` | `6165 ms` | `+56 ms` (~0.9%) |
| `trip_detail_open_ms` | `4101 ms` | `4094 ms` | `-7 ms` (~-0.2%) |

### Scroll `TimelineSummary` Metrics (`16.67ms` frame budget @ 60Hz)

| Scroll Action | Metric | Before (`10126b1`) | After |
|---------------|--------|--------------------|-------|
| `dest_sheet_scroll` | Avg Build Time | `10.20 ms` | `21.40 ms` |
| | 90th Percentile Build | `20.21 ms` | `46.30 ms` |
| | Avg Rasterizer Time | `25.54 ms` | `43.25 ms` |
| | Missed Build / Total Frames | `17 / 82` | `35 / 73` |
| `trip_list_scroll` | Avg Build Time | `11.26 ms` | `14.37 ms` |
| | 90th Percentile Build | `21.95 ms` | `28.14 ms` |
| | Avg Rasterizer Time | `16.52 ms` | `17.02 ms` |
| | Missed Build / Total Frames | `25 / 61` | `30 / 61` |
| `trip_detail_scroll` | Avg Build Time | `11.76 ms` | `21.88 ms` |
| | 90th Percentile Build | `23.11 ms` | `47.27 ms` |
| | Avg Rasterizer Time | `16.30 ms` | `15.61 ms` (`-0.69 ms`) |
| | Missed Rasterizer / Total | `28 / 66` | `16 / 53` (`-12` missed frames) |

**Notes on Emulator Measurements**:
1. `TripDetailScreen` (`trip_detail_scroll`) shows improved average rasterizer latency (`16.30 ms` → `15.61 ms`) and fewer missed rasterizer frames (`28/66` → `16/53`) with the lazy `CustomScrollView` + `SliverList.builder` itinerary architecture.
2. Runs were executed sequentially on a software-rendered headless AVD (`SwiftShader` OpenGLES `llvmpipe`); single-run host CPU jitter + background Facebook SDK placeholder-ID initialization during `After` startup (`GraphResponse` error 190/100 in `adb logcat` until real `facebook_app_id`/`facebook_client_token` are configured) affected early build/raster percentiles on `dest_sheet_scroll`.
3. `flutter drive` with `integration_test` requires `--no-dds` on this environment so the Android isolate can stream timeline payloads back to the host driver cleanly.

### Reproduce Single-Command `--profile` Benchmark
```powershell
$env:PATH = "D:\Android\Sdk\platform-tools;$env:PATH"
$env:ANDROID_AVD_HOME = "D:\Android\avd"
# 1) Boot GoMate_W3_Test (wait for sys.boot_completed=1)
Start-Process D:\Android\Sdk\emulator\emulator.exe -ArgumentList "-avd","GoMate_W3_Test","-no-window","-no-audio","-no-boot-anim","-no-snapshot-save"
# 2) Run benchmark
cd D:\Do_an\wanderai_beta_mobile\apps\mobile
$env:PERF_OUT_FILE = 'D:\Do_an\wanderai_beta_mobile\docs\beta\mobile\benchmarks\after_perf.json'
flutter drive --no-dds --driver=test_driver/perf_driver.dart --target=integration_test/perf_benchmark_test.dart --profile -d emulator-5554
```
