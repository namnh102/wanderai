import 'dart:async';
import 'package:flutter/services.dart';
import 'package:flutter_facebook_auth/flutter_facebook_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';

enum SocialAuthProvider { google, facebook }

sealed class SocialAuthResult {
  const SocialAuthResult();
}

class SocialAuthSuccess extends SocialAuthResult {
  final String token;
  final String? email;
  final String? displayName;

  const SocialAuthSuccess(
    this.token, {
    this.email,
    this.displayName,
  });
}

class SocialAuthCancelled extends SocialAuthResult {
  const SocialAuthCancelled();
}

class SocialAuthFailure extends SocialAuthResult {
  final String message;
  final String? errorCode;

  const SocialAuthFailure(this.message, {this.errorCode});
}

/// Mockable boundary around native Google Sign-In and Facebook Login SDKs.
abstract class AuthSocialPort {
  Future<SocialAuthResult> signInWithGoogle();
  Future<SocialAuthResult> signInWithFacebook();
  Future<void> signOutAll();
}

class SdkAuthSocialPort implements AuthSocialPort {
  static const String _googleServerClientId = String.fromEnvironment(
    'GOOGLE_SERVER_CLIENT_ID',
    defaultValue: '',
  );

  Future<void>? _googleInitFuture;

  Future<void> _ensureGoogleInitialized() {
    return _googleInitFuture ??= GoogleSignIn.instance.initialize(
      serverClientId:
          _googleServerClientId.trim().isEmpty ? null : _googleServerClientId,
    );
  }

  @override
  Future<SocialAuthResult> signInWithGoogle() async {
    try {
      await _ensureGoogleInitialized();
      if (!GoogleSignIn.instance.supportsAuthenticate()) {
        return const SocialAuthFailure(
          'Thiết bị hiện tại chưa hỗ trợ đăng nhập Google.',
          errorCode: 'OAUTH_PROVIDER_ERROR',
        );
      }
      final account = await GoogleSignIn.instance.authenticate();
      final idToken = account.authentication.idToken?.trim();
      if (idToken == null || idToken.isEmpty) {
        return const SocialAuthFailure(
          'Không nhận được mã xác thực từ Google. Vui lòng kiểm tra cấu hình Google OAuth.',
          errorCode: 'OAUTH_TOKEN_INVALID',
        );
      }
      return SocialAuthSuccess(
        idToken,
        email: account.email,
        displayName: account.displayName,
      );
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled ||
          e.code == GoogleSignInExceptionCode.interrupted) {
        return const SocialAuthCancelled();
      }
      return SocialAuthFailure(
        e.description?.trim().isNotEmpty == true
            ? e.description!.trim()
            : 'Đăng nhập Google thất bại. Vui lòng thử lại.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    } on MissingPluginException {
      return const SocialAuthFailure(
        'Đăng nhập Google chưa sẵn sàng trên nền tảng này.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    } on PlatformException catch (e) {
      if (e.code.toLowerCase().contains('cancel')) {
        return const SocialAuthCancelled();
      }
      return SocialAuthFailure(
        e.message?.trim().isNotEmpty == true
            ? e.message!.trim()
            : 'Đăng nhập Google thất bại. Vui lòng thử lại.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    } catch (_) {
      return const SocialAuthFailure(
        'Không thể kết nối tới Google. Vui lòng thử lại.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    }
  }

  @override
  Future<SocialAuthResult> signInWithFacebook() async {
    try {
      final result = await FacebookAuth.instance.login(
        permissions: const ['email', 'public_profile'],
      );
      switch (result.status) {
        case LoginStatus.success:
          final token = result.accessToken?.tokenString.trim();
          if (token == null || token.isEmpty) {
            return const SocialAuthFailure(
              'Không nhận được mã truy cập từ Facebook.',
              errorCode: 'OAUTH_TOKEN_INVALID',
            );
          }
          return SocialAuthSuccess(token);
        case LoginStatus.cancelled:
          return const SocialAuthCancelled();
        case LoginStatus.operationInProgress:
          return const SocialAuthFailure(
            'Phiên đăng nhập Facebook đang được xử lý.',
            errorCode: 'OAUTH_PROVIDER_ERROR',
          );
        case LoginStatus.failed:
          return SocialAuthFailure(
            result.message?.trim().isNotEmpty == true
                ? result.message!.trim()
                : 'Đăng nhập Facebook thất bại. Vui lòng thử lại.',
            errorCode: 'OAUTH_PROVIDER_ERROR',
          );
      }
    } on MissingPluginException {
      return const SocialAuthFailure(
        'Đăng nhập Facebook chưa sẵn sàng trên nền tảng này.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    } on PlatformException catch (e) {
      if (e.code.toLowerCase().contains('cancel')) {
        return const SocialAuthCancelled();
      }
      return SocialAuthFailure(
        e.message?.trim().isNotEmpty == true
            ? e.message!.trim()
            : 'Đăng nhập Facebook thất bại. Vui lòng thử lại.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    } catch (_) {
      return const SocialAuthFailure(
        'Không thể kết nối tới Facebook. Vui lòng thử lại.',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
    }
  }

  @override
  Future<void> signOutAll() async {
    try {
      await GoogleSignIn.instance.signOut();
    } catch (_) {}
    try {
      await FacebookAuth.instance.logOut();
    } catch (_) {}
  }
}

final authSocialPortProvider = Provider<AuthSocialPort>((ref) {
  return SdkAuthSocialPort();
});
