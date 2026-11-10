import 'package:flutter/foundation.dart';

/// Application-wide constants and environment-aware API endpoint resolution.
///
/// Security boundary:
/// - All Flutter traffic (including `/ai/chat` and `/ai/planner`) MUST route
///   exclusively through the JWT-guarded NestJS backend (`API_BASE_URL`).
/// - Flutter MUST NEVER connect directly to the internal FastAPI service (`:8000`).
class AppConstants {
  /// Compile-time API base URL supplied via `--dart-define=API_BASE_URL=...`.
  static const String configuredApiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );

  /// Default base URL for local desktop/web debug sessions only.
  static const String debugDefaultApiBaseUrl = 'http://localhost:3000';

  /// Reference example for standard Android Emulator host loopback (not auto-selected).
  static const String androidEmulatorExampleApiBaseUrl = 'http://10.0.2.2:3000';

  static const String appName = 'WanderAI';
  static const int pageSize = 20;

  static const Set<String> _disallowedReleaseHosts = {
    'localhost',
    '127.0.0.1',
    '::1',
    '[::1]',
    '0.0.0.0',
    '10.0.2.2',
  };

  /// Resolved NestJS API base URL for the current build mode.
  static String get apiBaseUrl => resolveApiBaseUrl();

  /// Resolves and validates the NestJS API base URL.
  ///
  /// - In release/profile builds (`isReleaseMode || isProfileMode`), an explicit
  ///   `https://` URL is required and loopback/emulator hosts are rejected.
  /// - In debug builds, falls back to [debugDefaultApiBaseUrl] when omitted,
  ///   while still validating any `--dart-define=API_BASE_URL=...` value.
  static String resolveApiBaseUrl({
    String? rawUrl,
    bool isReleaseMode = kReleaseMode,
    bool isProfileMode = kProfileMode,
  }) {
    final bool requireProductionHttps = isReleaseMode || isProfileMode;
    final String candidate = (rawUrl ?? configuredApiBaseUrl).trim();

    if (candidate.isEmpty) {
      if (requireProductionHttps) {
        throw StateError(
          'Missing API_BASE_URL in release/profile build. '
          'Pass --dart-define=API_BASE_URL=https://<your-backend-host> at build time.',
        );
      }
      return debugDefaultApiBaseUrl;
    }

    return validateAndNormalizeApiBaseUrl(
      candidate,
      requireHttps: requireProductionHttps,
    );
  }

  /// Validates a candidate API base URL and strips trailing slashes.
  static String validateAndNormalizeApiBaseUrl(
    String rawUrl, {
    bool requireHttps = false,
  }) {
    final String trimmed = rawUrl.trim();
    if (trimmed.isEmpty) {
      throw const FormatException('API_BASE_URL must not be empty.');
    }

    final Uri? uri = Uri.tryParse(trimmed);
    if (uri == null || !uri.hasScheme || !uri.hasAuthority || uri.host.isEmpty) {
      throw FormatException(
        'Invalid API_BASE_URL "$rawUrl": must be an absolute http(s) URL with a host.',
      );
    }

    final String scheme = uri.scheme.toLowerCase();
    if (scheme != 'http' && scheme != 'https') {
      throw FormatException(
        'Invalid API_BASE_URL "$rawUrl": scheme must be http or https.',
      );
    }

    if (uri.userInfo.isNotEmpty) {
      throw FormatException(
        'Invalid API_BASE_URL "$rawUrl": credentials in URL userInfo are forbidden.',
      );
    }

    if (uri.hasQuery || uri.hasFragment) {
      throw FormatException(
        'Invalid API_BASE_URL "$rawUrl": query parameters and fragments are not allowed.',
      );
    }

    if (uri.hasPort && (uri.port < 1 || uri.port > 65535)) {
      throw FormatException(
        'Invalid API_BASE_URL "$rawUrl": port must be between 1 and 65535.',
      );
    }

    final String normalizedHost = uri.host.toLowerCase();
    if (requireHttps) {
      if (scheme != 'https') {
        throw FormatException(
          'Insecure API_BASE_URL "$rawUrl": release and profile builds require https://.',
        );
      }
      if (_disallowedReleaseHosts.contains(normalizedHost)) {
        throw FormatException(
          'Invalid API_BASE_URL "$rawUrl": loopback or emulator host "$normalizedHost" is forbidden in release/profile builds.',
        );
      }
    }

    String normalizedPath = uri.path;
    while (normalizedPath.endsWith('/')) {
      normalizedPath = normalizedPath.substring(0, normalizedPath.length - 1);
    }

    final Uri normalizedUri = Uri(
      scheme: scheme,
      host: uri.host,
      port: uri.hasPort ? uri.port : null,
      path: normalizedPath.isEmpty ? null : normalizedPath,
    );

    return normalizedUri.toString();
  }
}
