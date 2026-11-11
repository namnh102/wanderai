import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

/// Hint shown before external navigation opens.
const String navigationHintText = 'Điều hướng sẽ mở ứng dụng bản đồ';

/// Vietnamese error feedback shown when external link or map handoff fails.
const String directionsOpenFailedText =
    'Không thể mở ứng dụng bản đồ để chỉ đường.';
const String externalLinkOpenFailedText =
    'Không thể mở liên kết ngoài ứng dụng.';
const String citationLinkOpenFailedText =
    'Không thể mở liên kết nguồn tham khảo.';

/// Scoped external URI schemes permitted by GoMate and declared in Android `<queries>`.
const Set<String> allowedExternalSchemes = {'https', 'http', 'geo', 'tel'};

bool isAllowedExternalUri(Uri uri) {
  final scheme = uri.scheme.toLowerCase();
  if (!allowedExternalSchemes.contains(scheme)) return false;
  if ((scheme == 'https' || scheme == 'http') && uri.host.trim().isEmpty) {
    return false;
  }
  if ((scheme == 'geo' || scheme == 'tel') &&
      uri.path.trim().isEmpty &&
      uri.query.trim().isEmpty) {
    return false;
  }
  return true;
}

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

/// Opens an external [uri] only if its scheme is in [allowedExternalSchemes].
/// For `geo:` URIs, checks `canLaunchUrl` first so `openDirections` can fall
/// back cleanly to Google Maps HTTPS when no native map app is installed.
/// For `https`/`http`/`tel`, prefers `LaunchMode.externalApplication` and falls
/// back to `LaunchMode.platformDefault` (e.g. Custom Tabs / system dialer).
Future<bool> defaultOpenExternalUri(Uri uri) async {
  if (!isAllowedExternalUri(uri)) return false;
  try {
    final scheme = uri.scheme.toLowerCase();
    if (scheme == 'geo') {
      if (!await canLaunchUrl(uri)) return false;
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
    if (await canLaunchUrl(uri)) {
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (opened) return true;
    }
    if (scheme == 'https' || scheme == 'http' || scheme == 'tel') {
      return await launchUrl(uri, mode: LaunchMode.platformDefault);
    }
    return false;
  } catch (_) {
    return false;
  }
}

/// Parses and opens a raw external URL string using [opener] (or
/// [defaultOpenExternalUri]). Returns `false` on malformed, disallowed, or
/// unlaunchable URLs without throwing.
Future<bool> openExternalUrlString(
  String rawUrl, {
  UriOpener? opener,
}) async {
  final trimmed = rawUrl.trim();
  if (trimmed.isEmpty) return false;
  final uri = Uri.tryParse(trimmed);
  if (uri == null || !isAllowedExternalUri(uri)) return false;
  return (opener ?? defaultOpenExternalUri)(uri);
}

/// Riverpod seam for external URI launching so screens can be deterministically
/// tested for both success and failure states.
final externalUriOpenerProvider =
    Provider<UriOpener>((ref) => defaultOpenExternalUri);

/// Unified "Chỉ đường" handler: hands the first openable candidate to the
/// platform. Returns the URI opened, or `null` if none could be opened.
Future<Uri?> openDirections({
  required double destLat,
  required double destLng,
  LatLng? origin,
  NavPlatform? platform,
  UriOpener? opener,
}) async {
  final open = opener ?? defaultOpenExternalUri;
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
