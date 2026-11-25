/// Auth-related data models matching the NestJS backend API contract.
///
/// Backend response format (TransformInterceptor / HttpExceptionFilter):
///   Success: {success: true, data: {...}, timestamp: "..."}
///   Error:   {success: false, statusCode: N, errorCode: "...", message: "...", timestamp: "...", path: "..."}

class AuthTokens {
  final String accessToken;
  final String refreshToken;

  const AuthTokens({required this.accessToken, required this.refreshToken});

  factory AuthTokens.fromJson(Map<String, dynamic> json) {
    return AuthTokens(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
    );
  }
}

class LoginRequest {
  final String email;
  final String password;

  const LoginRequest({required this.email, required this.password});

  Map<String, dynamic> toJson() => {'email': email, 'password': password};
}

class RegisterRequest {
  final String email;
  final String password;
  final String name;

  const RegisterRequest({
    required this.email,
    required this.password,
    required this.name,
  });

  Map<String, dynamic> toJson() => {
        'email': email,
        'password': password,
        'name': name,
      };
}

class ForgotPasswordResult {
  final bool sent;
  final String message;
  final int expiresInMinutes;

  const ForgotPasswordResult({
    required this.sent,
    required this.message,
    this.expiresInMinutes = 30,
  });

  factory ForgotPasswordResult.fromJson(Map<String, dynamic> json) {
    return ForgotPasswordResult(
      sent: json['sent'] as bool? ?? true,
      message: (json['message'] as String?)?.trim().isNotEmpty == true
          ? (json['message'] as String).trim()
          : 'Nếu email tồn tại trong hệ thống, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu.',
      expiresInMinutes: (json['expiresInMinutes'] as num?)?.toInt() ?? 30,
    );
  }
}

class ResetTokenValidationResult {
  final bool valid;
  final DateTime? expiresAt;
  final String? errorCode;
  final String? message;
  final bool isNetworkError;
  final bool isTransientError;

  const ResetTokenValidationResult({
    required this.valid,
    this.expiresAt,
    this.errorCode,
    this.message,
    this.isNetworkError = false,
    this.isTransientError = false,
  });

  factory ResetTokenValidationResult.fromJson(Map<String, dynamic> json) {
    final rawExp = json['expiresAt'] as String?;
    return ResetTokenValidationResult(
      valid: json['valid'] as bool? ?? false,
      expiresAt: rawExp != null ? DateTime.tryParse(rawExp) : null,
      errorCode: json['errorCode'] as String?,
      message: json['message'] as String?,
    );
  }
}

class ResetPasswordResult {
  final bool reset;
  final String message;

  const ResetPasswordResult({
    required this.reset,
    required this.message,
  });

  factory ResetPasswordResult.fromJson(Map<String, dynamic> json) {
    return ResetPasswordResult(
      reset: json['reset'] as bool? ?? true,
      message: (json['message'] as String?)?.trim().isNotEmpty == true
          ? (json['message'] as String).trim()
          : 'Đặt lại mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới.',
    );
  }
}
