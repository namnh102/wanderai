import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

enum UserLocationStatus { unknown, requesting, granted, denied, unavailable }

enum LocationPermissionState { granted, denied, deniedForever }

/// Thin seam over the platform geolocation API (browser geolocation on web,
/// OS location services on mobile/desktop) so behaviour can be tested.
abstract class LocationService {
  Future<LocationPermissionState> checkPermission();
  Future<LocationPermissionState> requestPermission();
  Future<bool> isServiceEnabled();
  Future<LatLng> currentPosition();
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
  Future<LatLng> currentPosition() async {
    final p = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 10),
      ),
    );
    return LatLng(p.latitude, p.longitude);
  }
}

class UserLocationState {
  final UserLocationStatus status;

  /// The device's real position. `null` unless a fix was actually obtained;
  /// never defaulted or guessed.
  final LatLng? position;

  const UserLocationState({
    this.status = UserLocationStatus.unknown,
    this.position,
  });

  bool get hasPosition => position != null;

  /// Honest, user-facing description of the current state.
  String? get label {
    switch (status) {
      case UserLocationStatus.unknown:
        return null;
      case UserLocationStatus.requesting:
        return 'Đang xác định vị trí của bạn...';
      case UserLocationStatus.granted:
        return 'Đã xác định vị trí của bạn';
      case UserLocationStatus.denied:
        return 'Quyền vị trí bị từ chối';
      case UserLocationStatus.unavailable:
        return 'Không xác định được vị trí';
    }
  }
}

class UserLocationNotifier extends StateNotifier<UserLocationState> {
  final LocationService _service;
  UserLocationNotifier(this._service) : super(const UserLocationState());

  /// Silent refresh: never prompts. Only fetches a fix if permission was
  /// already granted earlier.
  Future<void> refreshIfPermitted() async {
    try {
      if (await _service.checkPermission() != LocationPermissionState.granted) {
        return;
      }
      await _fetch();
    } catch (_) {
      // Stay "unknown"; the user can tap "Vị trí của tôi".
    }
  }

  /// Explicit request (from the "Vị trí của tôi" action). Prompts for
  /// permission if needed. Returns the real position or `null`.
  Future<LatLng?> request() async {
    state = UserLocationState(
        status: UserLocationStatus.requesting, position: state.position);
    try {
      var perm = await _service.checkPermission();
      if (perm == LocationPermissionState.denied) {
        perm = await _service.requestPermission();
      }
      if (perm != LocationPermissionState.granted) {
        state = const UserLocationState(status: UserLocationStatus.denied);
        return null;
      }
      if (!await _service.isServiceEnabled()) {
        state = const UserLocationState(status: UserLocationStatus.unavailable);
        return null;
      }
      return await _fetch();
    } catch (_) {
      state = const UserLocationState(status: UserLocationStatus.unavailable);
      return null;
    }
  }

  Future<LatLng?> _fetch() async {
    final pos = await _service.currentPosition();
    state = UserLocationState(status: UserLocationStatus.granted, position: pos);
    return pos;
  }
}

final locationServiceProvider =
    Provider<LocationService>((ref) => const GeolocatorLocationService());

final userLocationProvider =
    StateNotifierProvider<UserLocationNotifier, UserLocationState>((ref) {
  return UserLocationNotifier(ref.watch(locationServiceProvider));
});
