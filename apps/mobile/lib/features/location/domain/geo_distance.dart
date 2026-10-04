import 'dart:math' as math;
import 'package:latlong2/latlong.dart';

/// Shown whenever the user's real position is not known. A distance is never
/// derived from the map centre, a default city or any hardcoded coordinate.
const String distanceUnavailableText = 'Khoảng cách chưa xác định';

/// Great-circle (Haversine) distance in kilometres between two coordinates.
double haversineKm(LatLng a, LatLng b) {
  const earthRadiusKm = 6371.0088;
  double rad(double d) => d * math.pi / 180.0;
  final dLat = rad(b.latitude - a.latitude);
  final dLng = rad(b.longitude - a.longitude);
  final h = math.pow(math.sin(dLat / 2), 2) +
      math.cos(rad(a.latitude)) *
          math.cos(rad(b.latitude)) *
          math.pow(math.sin(dLng / 2), 2);
  return 2 * earthRadiusKm * math.asin(math.min(1.0, math.sqrt(h.toDouble())));
}

/// Distance from the user's real position to a place, or `null` when either
/// is unknown.
double? distanceFromUserKm(LatLng? user, double? placeLat, double? placeLng) {
  if (user == null || placeLat == null || placeLng == null) return null;
  return haversineKm(user, LatLng(placeLat, placeLng));
}

/// "850m" below one kilometre, otherwise "2.8 km".
String formatDistanceKm(double km) =>
    km < 1 ? '${(km * 1000).round()}m' : '${km.toStringAsFixed(1)} km';

/// Label for a possibly-unknown distance.
String distanceLabel(double? km) =>
    km == null ? distanceUnavailableText : formatDistanceKm(km);
