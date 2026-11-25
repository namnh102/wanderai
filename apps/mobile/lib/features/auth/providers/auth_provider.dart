import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_error.dart';
import '../data/auth_models.dart';
import '../data/auth_repository.dart';
import '../data/auth_social_port.dart';

/// Authentication states.
enum AuthStatus { unknown, authenticated, unauthenticated }

enum AuthActionOutcome { success, cancelled, error }

class AuthActionResult {
  final AuthActionOutcome outcome;
  final String? message;
  final String? errorCode;
  final bool isNetworkError;

  const AuthActionResult({
    required this.outcome,
    this.message,
    this.errorCode,
    this.isNetworkError = false,
  });

  const AuthActionResult.success({this.message})
      : outcome = AuthActionOutcome.success,
        errorCode = null,
        isNetworkError = false;

  const AuthActionResult.cancelled({this.message})
      : outcome = AuthActionOutcome.cancelled,
        errorCode = null,
        isNetworkError = false;

  const AuthActionResult.error({
    required String this.message,
    this.errorCode,
    this.isNetworkError = false,
  }) : outcome = AuthActionOutcome.error;

  bool get isSuccess => outcome == AuthActionOutcome.success;
  bool get isCancelled => outcome == AuthActionOutcome.cancelled;
  bool get isError => outcome == AuthActionOutcome.error;
}

class AuthState {
  final AuthStatus status;
  final String? errorMessage;

  const AuthState({required this.status, this.errorMessage});

  const AuthState.unknown()
      : status = AuthStatus.unknown,
        errorMessage = null;
  const AuthState.authenticated()
      : status = AuthStatus.authenticated,
        errorMessage = null;
  const AuthState.unauthenticated({this.errorMessage})
      : status = AuthStatus.unauthenticated;
}

/// Single source of truth for authentication.
class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;
  final AuthSocialPort? _socialPort;
  final SessionEpochController _epoch;

  AuthNotifier(
    this._repo, {
    AuthSocialPort? socialPort,
    SessionEpochController? epochController,
  })  : _socialPort = socialPort,
        _epoch = epochController ?? SessionEpochController(),
        super(const AuthState.unknown()) {
    _init();
  }

  Future<void> _init() async {
    final initEpoch = _epoch.current;
    final hasToken = await _repo.restoreSession();
    if (!mounted || _epoch.current != initEpoch) return;
    if (hasToken) {
      state = const AuthState.authenticated();
    } else {
      state = const AuthState.unauthenticated();
    }
  }

  void clearError() {
    if (state.status == AuthStatus.unauthenticated &&
        state.errorMessage != null) {
      state = const AuthState.unauthenticated();
    }
  }

  Future<bool> login(String email, String password) async {
    clearError();
    final attemptEpoch = _epoch.advance();
    try {
      await _repo.login(LoginRequest(email: email, password: password));
      if (!mounted || _epoch.current != attemptEpoch) return false;
      state = const AuthState.authenticated();
      return true;
    } on DioException catch (e) {
      if (!mounted || _epoch.current != attemptEpoch) return false;
      state = AuthState.unauthenticated(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<bool> register(String name, String email, String password) async {
    clearError();
    final attemptEpoch = _epoch.advance();
    try {
      await _repo.register(
        RegisterRequest(name: name, email: email, password: password),
      );
      if (!mounted || _epoch.current != attemptEpoch) return false;
      state = const AuthState.authenticated();
      return true;
    } on DioException catch (e) {
      if (!mounted || _epoch.current != attemptEpoch) return false;
      state = AuthState.unauthenticated(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<AuthActionResult> signInWithGoogle() =>
      _signInWithProvider(SocialAuthProvider.google);

  Future<AuthActionResult> signInWithFacebook() =>
      _signInWithProvider(SocialAuthProvider.facebook);

  Future<AuthActionResult> _signInWithProvider(
    SocialAuthProvider provider,
  ) async {
    clearError();
    final port = _socialPort;
    if (port == null) {
      return const AuthActionResult.error(
        message: 'Chưa cấu hình đăng nhập mạng xã hội.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    }

    final attemptEpoch = _epoch.advance();
    final socialResult = provider == SocialAuthProvider.google
        ? await port.signInWithGoogle()
        : await port.signInWithFacebook();

    if (!mounted || _epoch.current != attemptEpoch) {
      return const AuthActionResult.cancelled();
    }

    switch (socialResult) {
      case SocialAuthCancelled():
        state = const AuthState.unauthenticated();
        return const AuthActionResult.cancelled();
      case SocialAuthFailure(:final message, :final errorCode):
        state = AuthState.unauthenticated(errorMessage: message);
        return AuthActionResult.error(message: message, errorCode: errorCode);
      case SocialAuthSuccess(:final token):
        try {
          if (provider == SocialAuthProvider.google) {
            await _repo.loginWithGoogle(token);
          } else {
            await _repo.loginWithFacebook(token);
          }
          if (!mounted || _epoch.current != attemptEpoch) {
            return const AuthActionResult.cancelled();
          }
          state = const AuthState.authenticated();
          return const AuthActionResult.success();
        } on DioException catch (e) {
          if (!mounted || _epoch.current != attemptEpoch) {
            return const AuthActionResult.cancelled();
          }
          final details = ApiErrorDetails.fromDioException(e);
          final msg = _mapError(e);
          state = AuthState.unauthenticated(errorMessage: msg);
          return AuthActionResult.error(
            message: msg,
            errorCode: details.errorCode,
            isNetworkError: details.isNetworkError,
          );
        } catch (_) {
          if (!mounted || _epoch.current != attemptEpoch) {
            return const AuthActionResult.cancelled();
          }
          const msg = 'Không thể hoàn tất đăng nhập. Vui lòng thử lại.';
          state = const AuthState.unauthenticated(errorMessage: msg);
          return const AuthActionResult.error(message: msg);
        }
    }
  }

  Future<AuthActionResult> requestPasswordReset(String email) async {
    try {
      final res = await _repo.forgotPassword(email.trim());
      return AuthActionResult.success(message: res.message);
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      return AuthActionResult.error(
        message: _mapError(e),
        errorCode: details.errorCode,
        isNetworkError: details.isNetworkError,
      );
    } catch (_) {
      return const AuthActionResult.error(
        message: 'Không thể gửi yêu cầu khôi phục mật khẩu. Vui lòng thử lại.',
      );
    }
  }

  Future<ResetTokenValidationResult> validateResetToken(String token) async {
    try {
      return await _repo.validateResetToken(token.trim());
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      return ResetTokenValidationResult(
        valid: false,
        errorCode: details.errorCode,
        message: _mapError(e),
        isNetworkError: details.isNetworkError,
        isTransientError: details.isOfflineOrTransient,
      );
    } catch (_) {
      return const ResetTokenValidationResult(
        valid: false,
        message: 'Không thể kiểm tra liên kết đặt lại mật khẩu.',
        isTransientError: true,
      );
    }
  }

  Future<AuthActionResult> resetPassword({
    required String token,
    required String newPassword,
  }) async {
    try {
      final res = await _repo.resetPassword(
        token: token.trim(),
        newPassword: newPassword,
      );
      return AuthActionResult.success(message: res.message);
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      return AuthActionResult.error(
        message: _mapError(e),
        errorCode: details.errorCode,
        isNetworkError: details.isNetworkError,
      );
    } catch (_) {
      return const AuthActionResult.error(
        message: 'Không thể đặt lại mật khẩu. Vui lòng thử lại.',
      );
    }
  }

  Future<void> logout() async {
    final logoutEpoch = _epoch.advance();
    await _repo.logout();
    final port = _socialPort;
    if (port != null) {
      await port
          .signOutAll()
          .timeout(const Duration(seconds: 3))
          .catchError((_) {});
    }
    if (!mounted || _epoch.current != logoutEpoch) return;
    state = const AuthState.unauthenticated();
  }

  /// Syncs unauthenticated UI state after automatic 401/403 refresh failure.
  void handleSessionExpired() {
    if (state.status == AuthStatus.authenticated) {
      _epoch.advance();
      state = const AuthState.unauthenticated(
        errorMessage: 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
      );
    }
  }

  /// Map API/network errors and canonical `HttpExceptionFilter` `errorCode`s
  /// to user-friendly Vietnamese messages.
  String _mapError(DioException e) {
    final details = ApiErrorDetails.fromDioException(e);
    if (details.isNetworkError) {
      if (e.type == DioExceptionType.connectionError) {
        return 'Không có kết nối mạng.';
      }
      return 'Không thể kết nối máy chủ. Vui lòng thử lại.';
    }

    switch (details.errorCode) {
      case 'INVALID_CREDENTIALS':
        return details.message ?? 'Email hoặc mật khẩu không đúng.';
      case 'EMAIL_ALREADY_EXISTS':
        return details.message ?? 'Email đã được sử dụng.';
      case 'RESET_TOKEN_INVALID':
        return details.message ?? 'Liên kết đặt lại mật khẩu không hợp lệ.';
      case 'RESET_TOKEN_EXPIRED':
        return details.message ?? 'Liên kết đặt lại mật khẩu đã hết hạn.';
      case 'RESET_TOKEN_USED':
        return details.message ?? 'Liên kết đặt lại mật khẩu đã được sử dụng.';
      case 'OAUTH_TOKEN_INVALID':
        return details.message ?? 'Mã xác thực từ nhà cung cấp không hợp lệ.';
      case 'OAUTH_EMAIL_UNAVAILABLE':
        return details.message ??
            'Tài khoản mạng xã hội chưa chia sẻ email. Vui lòng dùng phương thức khác.';
      case 'OAUTH_PROVIDER_ERROR':
        return details.message ??
            'Không thể xác thực với nhà cung cấp lúc này. Vui lòng thử lại.';
    }

    if (details.statusCode == 401) {
      return details.message ?? 'Email hoặc mật khẩu không đúng.';
    }
    if (details.statusCode == 400 || details.statusCode == 410) {
      final msg = details.message;
      if (msg != null) {
        if (msg.contains('đã được sử dụng') || msg.contains('already')) {
          return 'Email đã được sử dụng.';
        }
        return msg;
      }
    }
    if (details.message != null) {
      return details.message!;
    }
    return 'Có lỗi xảy ra. Vui lòng thử lại.';
  }
}

/// Riverpod provider for AuthRepository.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return AuthRepository(dio);
});

/// Riverpod provider for auth state — single source of truth.
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final repo = ref.read(authRepositoryProvider);
  final socialPort = ref.read(authSocialPortProvider);
  final epochController = ref.read(sessionEpochControllerProvider);
  final notifier = AuthNotifier(
    repo,
    socialPort: socialPort,
    epochController: epochController,
  );
  ref.listen<int>(authSessionExpiredSignalProvider, (prev, next) {
    if (prev != next) {
      notifier.handleSessionExpired();
    }
  });
  return notifier;
});
