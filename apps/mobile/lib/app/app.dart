import 'dart:async';
import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/router/app_router.dart';
import '../core/theme/app_theme.dart';

const _allowedResetHosts = <String>{
  'app.gomate.vn',
  'gomate.vn',
  'www.gomate.vn',
};

/// Normalizes incoming custom-scheme or HTTPS deep links into in-app GoRouter
/// locations (for example `wanderai://reset-password?token=abc` ->
/// `/reset-password?token=abc`). Returns `null` for unsupported links.
String? normalizeAuthDeepLink(Uri uri) {
  final scheme = uri.scheme.toLowerCase();
  final host = uri.host.toLowerCase();
  final path = uri.path;
  final normalizedPath = path.length > 1 && path.endsWith('/')
      ? path.substring(0, path.length - 1)
      : path;

  final isCustomReset = scheme == 'wanderai' &&
      ((host == 'reset-password' && (path.isEmpty || path == '/')) ||
          (host == 'app' && normalizedPath == '/reset-password'));
  final isHttpsReset = scheme == 'https' &&
      _allowedResetHosts.contains(host) &&
      normalizedPath == '/reset-password';

  if (isCustomReset || isHttpsReset) {
    final token = uri.queryParameters['token']?.trim();
    return Uri(
      path: '/reset-password',
      queryParameters: (token != null && token.isNotEmpty)
          ? {'token': token}
          : null,
    ).toString();
  }
  return null;
}

class WanderApp extends ConsumerStatefulWidget {
  const WanderApp({super.key});

  @override
  ConsumerState<WanderApp> createState() => _WanderAppState();
}

class _WanderAppState extends ConsumerState<WanderApp> {
  StreamSubscription<Uri>? _linkSub;

  @override
  void initState() {
    super.initState();
    _initDeepLinks();
  }

  Future<void> _initDeepLinks() async {
    try {
      final appLinks = AppLinks();
      final initialUri = await appLinks.getInitialLink();
      if (initialUri != null && mounted) {
        _handleIncomingUri(initialUri);
      }
      _linkSub = appLinks.uriLinkStream.listen(
        _handleIncomingUri,
        onError: (_) {},
      );
    } on MissingPluginException {
      // Widget tests without native platform channel ignore deep-link init.
    } on PlatformException {
      // Safe fallback if native deep-link channel is unavailable.
    } catch (_) {
      // Never block app startup on deep-link plugin errors.
    }
  }

  void _handleIncomingUri(Uri uri) {
    if (!mounted) return;
    final target = normalizeAuthDeepLink(uri);
    if (target != null) {
      ref.read(appRouterProvider).go(target);
    }
  }

  @override
  void dispose() {
    _linkSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'GoMate',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      routerConfig: router,
    );
  }
}
