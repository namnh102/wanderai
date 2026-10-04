import 'package:flutter/foundation.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

/// Hint shown before external navigation opens.
const String navigationHintText = 'Điều hướng sẽ mở ứng dụng bản đồ';

enum NavPlatform { web, android, ios, desktop }

NavPlatform currentNavPlatform() {
  if (kIsWeb) return NavPlatform.web;
  switch (defaultTargetPlatform) {
    case TargetPlatform.android:
      return NavPlatform.android;
    case TargetPlatform.iOS:
      return NavPlatform.ios;
    default:
      return NavPlatform.desktop;
  }
}

String _fmt(double v) => v.toStringAsFixed(6);

/// Standard Google Maps Directions URL (no API key). Destination is the
/// selected place; the origin is included only when the user's real position
/// is known, otherwise the service determines it from the device/browser.
Uri googleDirectionsUri({
  required double destLat,
  required double destLng,
  LatLng? origin,
}) =>
    Uri.https('www.google.com', '/maps/dir/', {
      'api': '1',
      'destination': '${_fmt(destLat)},${_fmt(destLng)}',
      if (origin != null)
        'origin': '${_fmt(origin.latitude)},${_fmt(origin.longitude)}',
      'travelmode': 'driving',
    });

/// Apple Maps directions URL (iOS native handling).
Uri appleDirectionsUri({
  required double destLat,
  required double destLng,
  LatLng? origin,
}) =>
    Uri.https('maps.apple.com', '/', {
      'daddr': '${_fmt(destLat)},${_fmt(destLng)}',
      if (origin != null)
        'saddr': '${_fmt(origin.latitude)},${_fmt(origin.longitude)}',
      'dirflg': 'd',
    });

/// Android `geo:` intent, handled natively by the installed map app.
Uri androidGeoUri({required double destLat, required double destLng}) =>
    Uri.parse('geo:0,0?q=${_fmt(destLat)},${_fmt(destLng)}');

/// Ordered candidate URIs for a platform. The app never computes a route and
/// never falls back to the openstreetmap.org website.
List<Uri> directionsCandidates({
  required double destLat,
  required double destLng,
  LatLng? origin,
  required NavPlatform platform,
}) {
  final google = googleDirectionsUri(
      destLat: destLat, destLng: destLng, origin: origin);
  switch (platform) {
    case NavPlatform.android:
      return [androidGeoUri(destLat: destLat, destLng: destLng), google];
    case NavPlatform.ios:
      return [
        appleDirectionsUri(destLat: destLat, destLng: destLng, origin: origin),
        google,
      ];
    case NavPlatform.web:
    case NavPlatform.desktop:
      return [google];
  }
}

typedef UriOpener = Future<bool> Function(Uri uri);

Future<bool> _defaultOpen(Uri uri) async {
  try {
    if (!await canLaunchUrl(uri)) return false;
    return await launchUrl(uri, mode: LaunchMode.externalApplication);
  } catch (_) {
    return false;
  }
}

/// Unified "Chỉ đường" handler: hands the first openable candidate to the
/// platform. Returns the URI opened, or `null` if none could be opened.
Future<Uri?> openDirections({
  required double destLat,
  required double destLng,
  LatLng? origin,
  NavPlatform? platform,
  UriOpener? opener,
}) async {
  final open = opener ?? _defaultOpen;
  for (final uri in directionsCandidates(
    destLat: destLat,
    destLng: destLng,
    origin: origin,
    platform: platform ?? currentNavPlatform(),
  )) {
    if (await open(uri)) return uri;
  }
  return null;
}
