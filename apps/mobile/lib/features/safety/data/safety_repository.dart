import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_error.dart';
import 'safety_models.dart';

const String _accessTokenKey = 'access_token';
const String _safetyLastUserIdKey = 'safety_last_user_id';
const String _safetyStorePrefix = 'safety_store_v1_';
const String _emergencyDirectoryAssetPath =
    'assets/data/emergency_directory.json';

class SafetyNetworkResult {
  final SafetyNetworkSendStatus status;
  final String message;
  final String? serverId;
  final bool isOfflineError;

  const SafetyNetworkResult({
    required this.status,
    required this.message,
    this.serverId,
    this.isOfflineError = false,
  });

  bool get isSentOnline => status == SafetyNetworkSendStatus.sentOnline;
}

/// Network transport port for safety operations, backed by [Dio] and easily
/// overridable in tests via [safetyNetworkClientProvider].
abstract class SafetyNetworkClient {
  Future<bool> checkReachability();

  Future<SafetyNetworkResult> createContact({
    required String name,
    required String phone,
    required String relation,
    required bool isAuthenticated,
  });

  Future<SafetyNetworkResult> deleteContact({
    required String serverId,
    required bool isAuthenticated,
  });

  Future<SafetyNetworkResult> createCheckin({
    required double latitude,
    required double longitude,
    String? note,
    required bool isAuthenticated,
  });

  Future<SafetyNetworkResult> createEmergencyEvent({
    required double latitude,
    required double longitude,
    String? message,
    required bool isSandbox,
    required bool isAuthenticated,
  });
}

class DioSafetyNetworkClient implements SafetyNetworkClient {
  final Dio _dio;

  DioSafetyNetworkClient(this._dio);

  static const String _guestLocalMessage =
      'Đã lưu cục bộ trên thiết bị (chưa đồng bộ máy chủ do chưa đăng nhập)';
  static const String _offlineNotSentMessage =
      'Chưa gửi được lên máy chủ do mất mạng — đã lưu cục bộ trên thiết bị';
  static const String _serverRejectedLocalMessage =
      'Đã lưu cục bộ trên thiết bị (chưa đồng bộ được lên máy chủ)';

  @override
  Future<bool> checkReachability() async {
    try {
      final response = await _dio.get<dynamic>(
        '/health',
        options: Options(
          sendTimeout: const Duration(seconds: 3),
          receiveTimeout: const Duration(seconds: 3),
        ),
      );
      final code = response.statusCode ?? 0;
      return code >= 200 && code < 300;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<SafetyNetworkResult> createContact({
    required String name,
    required String phone,
    required String relation,
    required bool isAuthenticated,
  }) async {
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _guestLocalMessage,
      );
    }

    try {
      final response = await _dio.post<dynamic>(
        '/safety/contacts',
        data: {
          'name': name,
          'phone': phone,
          'relation': relation,
        },
      );
      final id = _extractId(response.data);
      return SafetyNetworkResult(
        status: SafetyNetworkSendStatus.sentOnline,
        message: 'Đã gửi thành công lên máy chủ',
        serverId: id,
      );
    } on DioException catch (e) {
      return _mapDioFailure(e);
    } catch (_) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _serverRejectedLocalMessage,
      );
    }
  }

  @override
  Future<SafetyNetworkResult> deleteContact({
    required String serverId,
    required bool isAuthenticated,
  }) async {
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _guestLocalMessage,
      );
    }

    try {
      await _dio.delete<dynamic>('/safety/contacts/$serverId');
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.sentOnline,
        message: 'Đã đồng bộ xóa trên máy chủ',
      );
    } on DioException catch (e) {
      return _mapDioFailure(e);
    } catch (_) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _serverRejectedLocalMessage,
      );
    }
  }

  @override
  Future<SafetyNetworkResult> createCheckin({
    required double latitude,
    required double longitude,
    String? note,
    required bool isAuthenticated,
  }) async {
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _guestLocalMessage,
      );
    }

    try {
      final response = await _dio.post<dynamic>(
        '/safety/checkins',
        data: {
          'latitude': latitude,
          'longitude': longitude,
          if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
        },
      );
      final id = _extractId(response.data);
      return SafetyNetworkResult(
        status: SafetyNetworkSendStatus.sentOnline,
        message: 'Đã gửi thành công lên máy chủ',
        serverId: id,
      );
    } on DioException catch (e) {
      return _mapDioFailure(e);
    } catch (_) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _serverRejectedLocalMessage,
      );
    }
  }

  @override
  Future<SafetyNetworkResult> createEmergencyEvent({
    required double latitude,
    required double longitude,
    String? message,
    required bool isSandbox,
    required bool isAuthenticated,
  }) async {
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _guestLocalMessage,
      );
    }

    try {
      final response = await _dio.post<dynamic>(
        '/safety/emergency-events',
        data: {
          'latitude': latitude,
          'longitude': longitude,
          if (message != null && message.trim().isNotEmpty)
            'message': message.trim(),
          'isSandbox': isSandbox,
        },
      );
      final id = _extractId(response.data);
      return SafetyNetworkResult(
        status: SafetyNetworkSendStatus.sentOnline,
        message: isSandbox
            ? 'Chế độ kiểm thử (Sandbox): Đã ghi nhận kiểm thử lên máy chủ'
            : 'Đã gửi thành công lên máy chủ',
        serverId: id,
      );
    } on DioException catch (e) {
      return _mapDioFailure(e);
    } catch (_) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: _serverRejectedLocalMessage,
      );
    }
  }

  SafetyNetworkResult _mapDioFailure(DioException e) {
    final details = ApiErrorDetails.fromDioException(e);
    if (details.isOfflineOrTransient) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.notSentOffline,
        message: _offlineNotSentMessage,
        isOfflineError: true,
      );
    }
    return const SafetyNetworkResult(
      status: SafetyNetworkSendStatus.localOnly,
      message: _serverRejectedLocalMessage,
    );
  }

  String? _extractId(dynamic raw) {
    if (raw is Map) {
      final data = raw['data'];
      if (data is Map && data['id'] is String) {
        return data['id'] as String;
      }
      if (raw['id'] is String) {
        return raw['id'] as String;
      }
    }
    return null;
  }
}

/// Resolves the storage scope key without requiring a live `/users/me` response
/// when the device is offline.
class SafetyScopeResolver {
  const SafetyScopeResolver();

  static String? extractJwtUserId(String? token) {
    if (token == null) return null;
    final trimmed = token.trim();
    if (trimmed.isEmpty) return null;
    final segments = trimmed.split('.');
    if (segments.length != 3) return null;
    try {
      final normalized = base64Url.normalize(segments[1]);
      final decoded = utf8.decode(base64Url.decode(normalized));
      final payload = jsonDecode(decoded);
      if (payload is Map) {
        for (final key in const ['sub', 'userId', 'id']) {
          final val = payload[key];
          if (val is String && val.trim().isNotEmpty) {
            return val.trim();
          }
        }
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  String resolveFromValues({
    required bool isAuthenticated,
    String? loadedProfileUserId,
    String? accessToken,
    String? persistedLastUserId,
    String? overrideScope,
  }) {
    if (overrideScope != null && overrideScope.trim().isNotEmpty) {
      return overrideScope.trim();
    }
    if (!isAuthenticated) {
      return 'guest';
    }
    if (loadedProfileUserId != null && loadedProfileUserId.trim().isNotEmpty) {
      return 'user:${loadedProfileUserId.trim()}';
    }
    final jwtSub = extractJwtUserId(accessToken);
    if (jwtSub != null && jwtSub.isNotEmpty) {
      return 'user:$jwtSub';
    }
    if (persistedLastUserId != null && persistedLastUserId.trim().isNotEmpty) {
      return 'user:${persistedLastUserId.trim()}';
    }
    if (accessToken != null && accessToken.trim().isNotEmpty) {
      return 'user:token_${accessToken.trim().hashCode.toRadixString(16)}';
    }
    return 'user:authenticated';
  }
}

class SafetyRepository {
  EmergencyDirectoryBundle? _cachedDirectoryBundle;

  final SafetyScopeResolver _scopeResolver;
  final Map<String, String> _memoryFallbackStore = {};
  final AssetBundle _assetBundle;

  SafetyRepository({
    SafetyScopeResolver scopeResolver = const SafetyScopeResolver(),
    AssetBundle? assetBundle,
  })  : _scopeResolver = scopeResolver,
        _assetBundle = assetBundle ?? rootBundle;

  Future<SharedPreferences?> _tryPrefs() async {
    try {
      return await SharedPreferences.getInstance();
    } catch (_) {
      return null;
    }
  }

  Future<String?> _readKey(String key) async {
    final prefs = await _tryPrefs();
    if (prefs != null) {
      return prefs.getString(key);
    }
    return _memoryFallbackStore[key];
  }

  Future<void> _writeKey(String key, String value) async {
    _memoryFallbackStore[key] = value;
    final prefs = await _tryPrefs();
    if (prefs != null) {
      await prefs.setString(key, value);
    }
  }

  Future<void> _removeKey(String key) async {
    _memoryFallbackStore.remove(key);
    final prefs = await _tryPrefs();
    if (prefs != null) {
      await prefs.remove(key);
    }
  }

  Future<String> resolveScope({
    required bool isAuthenticated,
    String? loadedProfileUserId,
    String? overrideScope,
  }) async {
    final accessToken = await _readKey(_accessTokenKey);
    final lastUserId = await _readKey(_safetyLastUserIdKey);
    final resolved = _scopeResolver.resolveFromValues(
      isAuthenticated: isAuthenticated,
      loadedProfileUserId: loadedProfileUserId,
      accessToken: accessToken,
      persistedLastUserId: lastUserId,
      overrideScope: overrideScope,
    );

    if (isAuthenticated && resolved.startsWith('user:')) {
      final candidateId = resolved.substring('user:'.length);
      if (loadedProfileUserId != null &&
          loadedProfileUserId.trim().isNotEmpty) {
        await _writeKey(_safetyLastUserIdKey, loadedProfileUserId.trim());
      } else if (SafetyScopeResolver.extractJwtUserId(accessToken) != null) {
        await _writeKey(_safetyLastUserIdKey, candidateId);
      }
    }

    return resolved;
  }

  Future<void> clearLastUserId() async {
    await _removeKey(_safetyLastUserIdKey);
  }

  Future<EmergencyDirectoryBundle> loadEmergencyDirectory() async {
    if (_cachedDirectoryBundle != null) {
      return _cachedDirectoryBundle!;
    }
    try {
      final raw = await _assetBundle.loadString(_emergencyDirectoryAssetPath);
      final decoded = jsonDecode(raw);
      if (decoded is Map) {
        final bundle = EmergencyDirectoryBundle.fromJson(
          Map<String, dynamic>.from(decoded),
        );
        _cachedDirectoryBundle = bundle;
        return bundle;
      }
    } catch (_) {
      // Deterministic bundled fallback when asset loading is unavailable in minimal test harnesses.
    }
    return EmergencyDirectoryBundle.fallback();
  }

  Future<SafetyUserStoreSnapshot> loadUserStore(String scopeKey) async {
    final storageKey = '$_safetyStorePrefix$scopeKey';
    final raw = await _readKey(storageKey);
    if (raw == null || raw.trim().isEmpty) {
      return const SafetyUserStoreSnapshot();
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map) {
        return SafetyUserStoreSnapshot.fromJson(
          Map<String, dynamic>.from(decoded),
        );
      }
    } catch (_) {
      // Corrupt store entry safely treated as empty rather than crashing offline.
    }
    return const SafetyUserStoreSnapshot();
  }

  Future<void> saveUserStore(
    String scopeKey,
    SafetyUserStoreSnapshot snapshot,
  ) async {
    final storageKey = '$_safetyStorePrefix$scopeKey';
    await _writeKey(storageKey, jsonEncode(snapshot.toJson()));
  }
}

final safetyNetworkClientProvider = Provider<SafetyNetworkClient>((ref) {
  return DioSafetyNetworkClient(ref.watch(apiClientProvider));
});

final safetyRepositoryProvider = Provider<SafetyRepository>((ref) {
  return SafetyRepository();
});
