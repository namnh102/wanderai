import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

enum UserLocationStatus { unknown, requesting, granted, denied, unavailable }

enum LocationPermissionState { granted, denied, deniedForever }

/// Quality gate for location accuracy in meters:
/// - good: <= 50m
/// - approximate: 50–200m
/// - poor: > 200m
enum LocationAccuracyQuality {
  good,
  approximate,
  poor,
}

/// Rich value object representing a platform geolocation fix.
class LocationFix {
  final LatLng position;
  final double accuracyMeters;
  final DateTime timestamp;

  const LocationFix({
    required this.position,
    required this.accuracyMeters,
    required this.timestamp,
  });

  double get latitude => position.latitude;
  double get longitude => position.longitude;

  LocationAccuracyQuality get quality {
    if (accuracyMeters <= 50.0) return LocationAccuracyQuality.good;
    if (accuracyMeters <= 200.0) return LocationAccuracyQuality.approximate;
    return LocationAccuracyQuality.poor;
  }
}

/// Thin seam over the platform geolocation API (browser geolocation on web,
/// OS location services on mobile/desktop) so behaviour can be tested.
abstract class LocationService {
  Future<LocationPermissionState> checkPermission();
  Future<LocationPermissionState> requestPermission();
  Future<bool> isServiceEnabled();
  Future<LocationFix> currentFix();
  Future<LatLng> currentPosition() async => (await currentFix()).position;
  Future<bool> openAppSettings() async => true;
  Future<bool> openLocationSettings() async => true;
}

class GeolocatorLocationService implements LocationService {
  const GeolocatorLocationService();

  static LocationPermissionState _map(LocationPermission p) {
    switch (p) {
      case LocationPermission.always:
      case LocationPermission.whileInUse:
        return LocationPermissionState.granted;
      case LocationPermission.deniedForever:
        return LocationPermissionState.deniedForever;
      case LocationPermission.denied:
      case LocationPermission.unableToDetermine:
        return LocationPermissionState.denied;
    }
  }

  @override
  Future<LocationPermissionState> checkPermission() async =>
      _map(await Geolocator.checkPermission());

  @override
  Future<LocationPermissionState> requestPermission() async =>
      _map(await Geolocator.requestPermission());

  @override
  Future<bool> isServiceEnabled() => Geolocator.isLocationServiceEnabled();

  @override
  Future<LocationFix> currentFix() async {
    final p = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: kIsWeb ? LocationAccuracy.medium : LocationAccuracy.high,
        timeLimit: Duration(seconds: 5),
      ),
    );
    return LocationFix(
      position: LatLng(p.latitude, p.longitude),
      accuracyMeters: p.accuracy,
      timestamp: p.timestamp,
    );
  }

  @override
  Future<LatLng> currentPosition() async => (await currentFix()).position;

  @override
  Future<bool> openAppSettings() => Geolocator.openAppSettings();

  @override
  Future<bool> openLocationSettings() => Geolocator.openLocationSettings();
}

class UserLocationState {
  final UserLocationStatus status;
  final LocationFix? fix;
  final LocationPermissionState permissionState;

  UserLocationState({
    this.status = UserLocationStatus.unknown,
    LocationFix? fix,
    LatLng? position,
    double? accuracyMeters,
    DateTime? timestamp,
    this.permissionState = LocationPermissionState.denied,
  }) : fix = fix ??
            (position != null
                ? LocationFix(
                    position: position,
                    accuracyMeters: accuracyMeters ?? 15.0,
                    timestamp: timestamp ?? DateTime.now(),
                  )
                : null);

  /// The device's real position. `null` unless a fix was actually obtained;
  /// never defaulted or guessed.
  LatLng? get position => fix?.position;
  double? get accuracyMeters => fix?.accuracyMeters;
  DateTime? get timestamp => fix?.timestamp;
  LocationAccuracyQuality? get quality => fix?.quality;

  bool get hasPosition => position != null;

  /// Honest, user-facing description of the current state including accuracy.
  String? get label {
    switch (status) {
      case UserLocationStatus.unknown:
        return null;
      case UserLocationStatus.requesting:
        return 'Đang xác định vị trí của bạn...';
      case UserLocationStatus.denied:
        return 'Quyền vị trí bị từ chối';
      case UserLocationStatus.unavailable:
        return 'Không xác định được vị trí';
      case UserLocationStatus.granted:
        if (fix == null) return 'Đã xác định vị trí';
        final acc = fix!.accuracyMeters.round();
        if (quality == LocationAccuracyQuality.good) {
          return 'Đã xác định vị trí · ±$acc m';
        } else if (quality == LocationAccuracyQuality.approximate) {
          return 'Vị trí ước lượng · ±$acc m';
        } else {
          return 'Vị trí chưa chính xác';
        }
    }
  }
}

class UserLocationNotifier extends StateNotifier<UserLocationState> {
  final LocationService _service;
  final Duration retryDelay;
  final int maxQualityRetries;

  UserLocationNotifier(
    this._service, {
    this.retryDelay = const Duration(milliseconds: 250),
    int? maxQualityRetries,
  })  : maxQualityRetries = maxQualityRetries ?? (kIsWeb ? 1 : 3),
        super(UserLocationState());

  /// Open system app settings (for permission recovery).
  Future<bool> openAppSettings() => _service.openAppSettings();

  /// Open system location service settings.
  Future<bool> openLocationSettings() => _service.openLocationSettings();

  /// Silent refresh: never prompts. Only fetches a fix if permission was
  /// already granted earlier.
  Future<void> refreshIfPermitted() async {
    try {
      if (await _service.checkPermission() != LocationPermissionState.granted) {
        return;
      }
      if (!await _service.isServiceEnabled()) {
        return;
      }
      await _fetchWithQualityGate();
    } catch (_) {
      // Stay "unknown"; the user can tap "Vị trí của tôi".
    }
  }

  /// Explicit request (from the "Vị trí của tôi" action). Prompts for
  /// permission if needed. Returns the real position or `null`.
  Future<LatLng?> request() async {
    state = UserLocationState(
      status: UserLocationStatus.requesting,
      fix: state.fix,
      permissionState: state.permissionState,
    );
    try {
      var perm = await _service.checkPermission();
      if (perm == LocationPermissionState.denied) {
        perm = await _service.requestPermission();
      }
      if (perm != LocationPermissionState.granted) {
        state = UserLocationState(
          status: UserLocationStatus.denied,
          permissionState: perm,
        );
        return null;
      }
      if (!await _service.isServiceEnabled()) {
        state = UserLocationState(
          status: UserLocationStatus.unavailable,
          permissionState: LocationPermissionState.granted,
        );
        return null;
      }
      return await _fetchWithQualityGate();
    } catch (_) {
      state = UserLocationState(
        status: UserLocationStatus.unavailable,
        permissionState: LocationPermissionState.denied,
      );
      return null;
    }
  }

  /// Fetches a location fix through the accuracy quality gate:
  /// 1. Tries up to `maxQualityRetries` (2–3 times) if the fix is poor (> 200m).
  /// 2. If a good fix (<= 50m) is obtained, stops retrying immediately.
  /// 3. Keeps the fix with the smallest accuracy radius among attempts.
  /// 4. If still poor or approximate, stores it with proper quality flag —
  ///    never presenting poor accuracy as exact.
  Future<LatLng?> _fetchWithQualityGate() async {
    LocationFix? bestFix;

    for (int attempt = 1; attempt <= maxQualityRetries; attempt++) {
      final LocationFix fix;
      try {
        fix = await _service.currentFix();
      } catch (e) {
        if (bestFix != null) {
          break;
        }
        state = UserLocationState(
          status: UserLocationStatus.unavailable,
          permissionState: LocationPermissionState.granted,
        );
        return null;
      }

      if (bestFix == null || fix.accuracyMeters < bestFix.accuracyMeters) {
        bestFix = fix;
      }
      if (fix.quality == LocationAccuracyQuality.good) {
        break;
      }

      if (attempt < maxQualityRetries &&
          bestFix.quality == LocationAccuracyQuality.poor) {
        if (retryDelay > Duration.zero) {
          await Future.delayed(retryDelay);
        }
      } else {
        break;
      }
    }

    if (bestFix == null) {
      state = UserLocationState(
        status: UserLocationStatus.unavailable,
        permissionState: LocationPermissionState.granted,
      );
      return null;
    }

    state = UserLocationState(
      status: UserLocationStatus.granted,
      fix: bestFix,
      permissionState: LocationPermissionState.granted,
    );
    return bestFix.position;
  }
}

final locationServiceProvider =
    Provider<LocationService>((ref) => const GeolocatorLocationService());

final userLocationProvider =
    StateNotifierProvider<UserLocationNotifier, UserLocationState>((ref) {
  return UserLocationNotifier(ref.watch(locationServiceProvider));
});
