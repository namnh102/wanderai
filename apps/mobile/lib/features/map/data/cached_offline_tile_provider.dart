import 'dart:async';
import 'dart:ui' as ui;
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/painting.dart';
import 'package:flutter_map/flutter_map.dart';
import 'offline_tile_downloader.dart';
import 'offline_tile_store.dart';

/// Thrown when a tile is missing from the local offline cache (and either
/// offline-only mode is active or network fallback failed).
class OfflineTileUnavailableException implements Exception {
  final TileCoordinates coordinates;
  final String message;

  const OfflineTileUnavailableException(
    this.coordinates, [
    this.message = 'Tile chưa được tải ngoại tuyến.',
  ]);

  @override
  String toString() =>
      'OfflineTileUnavailableException(${coordinates.z}/${coordinates.x}/${coordinates.y}): $message';
}

/// Persistent disk-first [TileProvider] for `flutter_map` 7.0.2.
///
/// 1. Checks [OfflineTileStore] asynchronously on disk first.
/// 2. If missing and [isOfflineOnly] is true, fails cleanly with
///    [OfflineTileUnavailableException] and evicts from Flutter's [ImageCache].
/// 3. If online, fetches primary URL then fallback URL with ADR-006 headers.
///
/// Leaves [headers] mutable via `super.headers` so [TileLayer] can inject its
/// `User-Agent` header without throwing on a `const {}` map.
class CachedOfflineTileProvider extends TileProvider {
  final OfflineTileStore store;
  final Dio dio;
  final bool Function() isOfflineOnly;
  final VoidCallback? onNetworkTileLoaded;
  int cacheEpoch;

  CachedOfflineTileProvider({
    required this.store,
    Dio? dio,
    bool Function()? isOfflineOnly,
    this.onNetworkTileLoaded,
    this.cacheEpoch = 0,
    super.headers,
  })  : dio = dio ??
            Dio(
              BaseOptions(
                connectTimeout: const Duration(seconds: 10),
                receiveTimeout: const Duration(seconds: 15),
              ),
            ),
        isOfflineOnly = isOfflineOnly ?? (() => false);

  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) {
    final primaryUrl = getTileUrl(coordinates, options);
    final fallbackUrl = getTileFallbackUrl(coordinates, options);
    final mergedHeaders = <String, String>{
      'User-Agent': OfflineTileDownloader.defaultUserAgent,
      ...headers,
    };

    return _CachedTileImageProvider(
      coordinates: coordinates,
      primaryUrl: primaryUrl,
      fallbackUrl: fallbackUrl,
      headers: mergedHeaders,
      store: store,
      dio: dio,
      offlineOnly: isOfflineOnly(),
      cacheEpoch: cacheEpoch,
      onNetworkTileLoaded: onNetworkTileLoaded,
    );
  }
}

@immutable
class _CachedTileImageProvider extends ImageProvider<_CachedTileImageProvider> {
  final TileCoordinates coordinates;
  final String primaryUrl;
  final String? fallbackUrl;
  final Map<String, String> headers;
  final OfflineTileStore store;
  final Dio dio;
  final bool offlineOnly;
  final int cacheEpoch;
  final VoidCallback? onNetworkTileLoaded;

  const _CachedTileImageProvider({
    required this.coordinates,
    required this.primaryUrl,
    required this.fallbackUrl,
    required this.headers,
    required this.store,
    required this.dio,
    required this.offlineOnly,
    required this.cacheEpoch,
    this.onNetworkTileLoaded,
  });

  @override
  SynchronousFuture<_CachedTileImageProvider> obtainKey(
    ImageConfiguration configuration,
  ) =>
      SynchronousFuture(this);

  @override
  ImageStreamCompleter loadImage(
    _CachedTileImageProvider key,
    ImageDecoderCallback decode,
  ) {
    return MultiFrameImageStreamCompleter(
      codec: _load(key, decode),
      scale: 1.0,
      debugLabel: 'tile:${coordinates.z}/${coordinates.x}/${coordinates.y}',
      informationCollector: () => [
        DiagnosticsProperty('URL', primaryUrl),
        DiagnosticsProperty('Fallback URL', fallbackUrl),
        DiagnosticsProperty('Offline only', offlineOnly),
      ],
    );
  }

  Future<ui.Codec> _decodeBytes(
    Uint8List bytes,
    ImageDecoderCallback decode,
  ) async {
    final buffer = await ui.ImmutableBuffer.fromUint8List(bytes);
    return await decode(buffer);
  }

  Future<ui.Codec> _load(
    _CachedTileImageProvider key,
    ImageDecoderCallback decode,
  ) async {
    final cached = await store.readTileBytes(
      coordinates.z,
      coordinates.x,
      coordinates.y,
    );
    if (cached != null && OfflineTileStore.isValidPng(cached)) {
      try {
        return await _decodeBytes(cached, decode);
      } catch (_) {
        scheduleMicrotask(() => PaintingBinding.instance.imageCache.evict(key));
        if (offlineOnly) {
          throw OfflineTileUnavailableException(coordinates);
        }
      }
    }

    if (offlineOnly) {
      scheduleMicrotask(() => PaintingBinding.instance.imageCache.evict(key));
      throw OfflineTileUnavailableException(coordinates);
    }

    final primaryBytes = await _fetchBytes(primaryUrl);
    if (primaryBytes != null) {
      try {
        final codec = await _decodeBytes(primaryBytes, decode);
        onNetworkTileLoaded?.call();
        return codec;
      } catch (_) {
        // Fall through to fallback URL if primary bytes fail decoding.
      }
    }

    if (fallbackUrl != null && fallbackUrl!.isNotEmpty) {
      final fallbackBytes = await _fetchBytes(fallbackUrl!);
      if (fallbackBytes != null) {
        try {
          final codec = await _decodeBytes(fallbackBytes, decode);
          onNetworkTileLoaded?.call();
          return codec;
        } catch (_) {
          // Fall through to OfflineTileUnavailableException.
        }
      }
    }

    scheduleMicrotask(() => PaintingBinding.instance.imageCache.evict(key));
    throw OfflineTileUnavailableException(
      coordinates,
      'Không thể tải mảnh bản đồ (${coordinates.z}/${coordinates.x}/${coordinates.y}).',
    );
  }

  Future<Uint8List?> _fetchBytes(String url) async {
    try {
      final response = await dio.get<List<int>>(
        url,
        options: Options(
          responseType: ResponseType.bytes,
          headers: headers,
        ),
      );
      if (response.statusCode != 200 || response.data == null) return null;
      final bytes = Uint8List.fromList(response.data!);
      if (!OfflineTileStore.isValidPng(bytes)) return null;
      return bytes;
    } catch (_) {
      return null;
    }
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is _CachedTileImageProvider &&
          coordinates.z == other.coordinates.z &&
          coordinates.x == other.coordinates.x &&
          coordinates.y == other.coordinates.y &&
          primaryUrl == other.primaryUrl &&
          offlineOnly == other.offlineOnly &&
          cacheEpoch == other.cacheEpoch);

  @override
  int get hashCode => Object.hash(
        coordinates.z,
        coordinates.x,
        coordinates.y,
        primaryUrl,
        offlineOnly,
        cacheEpoch,
      );
}
