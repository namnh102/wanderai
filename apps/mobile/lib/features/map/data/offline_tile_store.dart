import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'offline_map_models.dart';
import 'place_model.dart';

/// Persistent disk store for downloaded raster PNG tiles and region manifests:
/// `<appSupportDir>/offline_tiles/<regionId>/<z>/<x>/<y>.png`
/// `<appSupportDir>/offline_tiles/<regionId>/manifest.json`
class OfflineTileStore {
  static const _rootFolderName = 'offline_tiles';
  static const _manifestFileName = 'manifest.json';
  static const List<int> _pngSignature = [
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
  ];
  static const List<int> _pngIendChunk = [
    0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
  ];

  final Future<Directory?> Function() _baseDirProvider;

  /// Cached set of region IDs known to exist under `<root>`.
  Set<String>? _knownRegionIds;
  Future<Set<String>>? _resolvingRegionIds;
  final Map<String, Future<void>> _regionLocks = {};
  int _tempSeq = 0;

  OfflineTileStore({
    Future<Directory?> Function()? baseDirProvider,
  }) : _baseDirProvider = baseDirProvider ?? _defaultBaseDirProvider;

  static Future<Directory?> _defaultBaseDirProvider() async {
    try {
      return await getApplicationSupportDirectory();
    } on MissingPluginException {
      return null;
    } on UnimplementedError {
      return null;
    } catch (_) {
      return null;
    }
  }

  /// Validates the PNG 8-byte signature, minimum PNG structure length
  /// (signature + IHDR + IEND >= 33 bytes), and trailing 12-byte IEND chunk
  /// so HTML/error responses and truncated PNG files are rejected.
  static bool isValidPng(Uint8List bytes) {
    if (bytes.length < 33) return false;
    for (var i = 0; i < _pngSignature.length; i++) {
      if (bytes[i] != _pngSignature[i]) return false;
    }
    final iendOffset = bytes.length - _pngIendChunk.length;
    for (var i = 0; i < _pngIendChunk.length; i++) {
      if (bytes[iendOffset + i] != _pngIendChunk[i]) return false;
    }
    return true;
  }

  Future<T> _withRegionLock<T>(
    String regionId,
    Future<T> Function() action,
  ) async {
    final prev = _regionLocks[regionId] ?? Future<void>.value();
    final completer = Completer<void>();
    _regionLocks[regionId] = completer.future;
    try {
      await prev.catchError((_) {});
      return await action();
    } finally {
      completer.complete();
      if (identical(_regionLocks[regionId], completer.future)) {
        _regionLocks.remove(regionId);
      }
    }
  }

  Future<Directory?> _getRootDir({bool create = false}) async {
    final base = await _baseDirProvider();
    if (base == null) return null;
    final root = Directory('${base.path}${Platform.pathSeparator}$_rootFolderName');
    if (create && !await root.exists()) {
      await root.create(recursive: true);
    }
    return root;
  }

  Future<Directory?> getRegionDir(
    String regionId, {
    bool create = false,
  }) async {
    final root = await _getRootDir(create: create);
    if (root == null) return null;
    final dir = Directory('${root.path}${Platform.pathSeparator}$regionId');
    if (create && !await dir.exists()) {
      await dir.create(recursive: true);
      _knownRegionIds?.add(regionId);
    }
    return dir;
  }

  Future<File?> getTileFile(String regionId, int z, int x, int y) async {
    final regionDir = await getRegionDir(regionId);
    if (regionDir == null) return null;
    final sep = Platform.pathSeparator;
    return File('${regionDir.path}$sep$z$sep$x$sep$y.png');
  }

  Future<bool> hasValidTile(String regionId, int z, int x, int y) async {
    final file = await getTileFile(regionId, z, x, y);
    if (file == null || !await file.exists()) return false;
    try {
      final bytes = await file.readAsBytes();
      return isValidPng(bytes);
    } catch (_) {
      return false;
    }
  }

  Future<Uint8List?> readTileBytesForRegion(
    String regionId,
    int z,
    int x,
    int y,
  ) async {
    final file = await getTileFile(regionId, z, x, y);
    if (file == null || !await file.exists()) return null;
    try {
      final bytes = await file.readAsBytes();
      if (!isValidPng(bytes)) return null;
      return bytes;
    } catch (_) {
      return null;
    }
  }

  Future<Set<String>> _resolveKnownRegionIds() async {
    if (_knownRegionIds != null) return _knownRegionIds!;
    if (_resolvingRegionIds != null) return _resolvingRegionIds!;
    final future = _scanKnownRegionIds();
    _resolvingRegionIds = future;
    try {
      return await future;
    } finally {
      if (identical(_resolvingRegionIds, future)) {
        _resolvingRegionIds = null;
      }
    }
  }

  Future<Set<String>> _scanKnownRegionIds() async {
    final root = await _getRootDir();
    if (root == null || !await root.exists()) {
      _knownRegionIds = <String>{};
      return _knownRegionIds!;
    }
    final ids = <String>{};
    await for (final entity in root.list(followLinks: false)) {
      if (entity is Directory) {
        final name = entity.path
            .split(Platform.pathSeparator)
            .where((s) => s.isNotEmpty)
            .lastOrNull;
        if (name != null && name.isNotEmpty) {
          ids.add(name);
        }
      }
    }
    _knownRegionIds = ids;
    return ids;
  }

  /// Reads a cached tile across any installed region on disk.
  Future<Uint8List?> readTileBytes(int z, int x, int y) async {
    final regionIds = (await _resolveKnownRegionIds()).toList(growable: false);
    if (regionIds.isEmpty) return null;
    for (final regionId in regionIds) {
      final bytes = await readTileBytesForRegion(regionId, z, x, y);
      if (bytes != null) return bytes;
    }
    return null;
  }

  Future<void> writeTileBytes(
    String regionId,
    int z,
    int x,
    int y,
    Uint8List bytes,
  ) async {
    if (!isValidPng(bytes)) {
      throw const FormatException('Invalid PNG tile payload.');
    }
    final regionDir = await getRegionDir(regionId, create: true);
    if (regionDir == null) {
      throw StateError('Offline tile storage directory is unavailable.');
    }
    final sep = Platform.pathSeparator;
    final tileFile = File('${regionDir.path}$sep$z$sep$x$sep$y.png');
    if (!await tileFile.parent.exists()) {
      await tileFile.parent.create(recursive: true);
    }
    await tileFile.writeAsBytes(bytes, flush: true);
    (_knownRegionIds ??= <String>{}).add(regionId);
  }

  /// Computes exact tile count and byte sum across all valid PNG tiles in [regionId].
  Future<({int tileCount, int totalBytes})> measureRegionTiles(
    String regionId,
  ) async {
    final regionDir = await getRegionDir(regionId);
    if (regionDir == null || !await regionDir.exists()) {
      return (tileCount: 0, totalBytes: 0);
    }
    var count = 0;
    var bytes = 0;
    await for (final entity in regionDir.list(recursive: true, followLinks: false)) {
      if (entity is File && entity.path.toLowerCase().endsWith('.png')) {
        try {
          final fileBytes = await entity.readAsBytes();
          if (isValidPng(fileBytes)) {
            count++;
            bytes += fileBytes.length;
          }
        } catch (_) {
          // Ignore unreadable or transient tile files.
        }
      }
    }
    return (tileCount: count, totalBytes: bytes);
  }

  Future<int> computeRegionBytes(String regionId) async {
    final measured = await measureRegionTiles(regionId);
    return measured.totalBytes;
  }

  Future<void> saveManifest(OfflineRegionManifest manifest) {
    return _withRegionLock(manifest.regionId, () async {
      final regionDir = await getRegionDir(manifest.regionId, create: true);
      if (regionDir == null) {
        throw StateError('Offline tile storage directory is unavailable.');
      }
      final sep = Platform.pathSeparator;
      final target = File('${regionDir.path}$sep$_manifestFileName');
      final tmp = File(
        '${regionDir.path}$sep$_manifestFileName.${DateTime.now().microsecondsSinceEpoch}.${_tempSeq++}.tmp',
      );
      final encoded =
          const JsonEncoder.withIndent('  ').convert(manifest.toJson());
      try {
        await tmp.writeAsString(encoded, flush: true);
        if (await target.exists()) {
          await target.delete();
        }
        await tmp.rename(target.path);
        (_knownRegionIds ??= <String>{}).add(manifest.regionId);
      } finally {
        if (await tmp.exists()) {
          try {
            await tmp.delete();
          } catch (_) {
            // Best-effort temp cleanup.
          }
        }
      }
    });
  }

  Future<OfflineRegionManifest?> loadManifest(String regionId) async {
    final regionDir = await getRegionDir(regionId);
    if (regionDir == null) return null;
    final file = File('${regionDir.path}${Platform.pathSeparator}$_manifestFileName');
    if (!file.existsSync()) return null;
    try {
      final raw = file.readAsStringSync();
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return null;
      (_knownRegionIds ??= <String>{}).add(regionId);
      return OfflineRegionManifest.fromJson(Map<String, dynamic>.from(decoded));
    } catch (_) {
      return null;
    }
  }

  Future<List<OfflineRegionManifest>> listManifests() async {
    final root = await _getRootDir();
    if (root == null || !await root.exists()) return const [];
    final manifests = <OfflineRegionManifest>[];
    final ids = <String>{};
    await for (final entity in root.list(followLinks: false)) {
      if (entity is Directory) {
        final name = entity.path
            .split(Platform.pathSeparator)
            .where((s) => s.isNotEmpty)
            .lastOrNull;
        if (name != null && name.isNotEmpty) {
          ids.add(name);
          final m = await loadManifest(name);
          if (m != null) manifests.add(m);
        }
      }
    }
    _knownRegionIds = ids;
    return manifests;
  }

  Future<PlaceModel?> findCachedPlaceById(String placeId) async {
    final manifests = await listManifests();
    for (final manifest in manifests) {
      for (final place in manifest.places) {
        if (place.id == placeId) return place;
      }
    }
    return null;
  }

  Future<void> deleteRegion(String regionId) {
    return _withRegionLock(regionId, () async {
      _knownRegionIds?.remove(regionId);
      final regionDir = await getRegionDir(regionId);
      if (regionDir == null || !await regionDir.exists()) return;

      final manifestFile =
          File('${regionDir.path}${Platform.pathSeparator}$_manifestFileName');
      if (await manifestFile.exists()) {
        await manifestFile.delete();
      }

      try {
        await regionDir.delete(recursive: true);
      } on FileSystemException {
        // Allow any in-flight tile read handle (especially on Windows) to close.
        await Future<void>.delayed(const Duration(milliseconds: 80));
        if (await regionDir.exists()) {
          try {
            await regionDir.delete(recursive: true);
          } on FileSystemException {
            // Best-effort cleanup of remaining files.
          }
        }
      }
    });
  }
}
