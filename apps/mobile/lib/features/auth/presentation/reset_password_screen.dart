import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../providers/auth_provider.dart';

class ResetPasswordScreen extends ConsumerStatefulWidget {
  final String? initialToken;

  const ResetPasswordScreen({super.key, this.initialToken});

  @override
  ConsumerState<ResetPasswordScreen> createState() =>
      _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends ConsumerState<ResetPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _tokenCtrl;
  final _passCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  bool _validating = false;
  bool _tokenInvalid = false;
  bool _validationTransientError = false;
  bool _submitting = false;
  bool _resetDone = false;
  String? _bannerMessage;
  AppStateBannerTone _bannerTone = AppStateBannerTone.info;

  bool get _hasInitialToken =>
      widget.initialToken != null && widget.initialToken!.trim().isNotEmpty;

  @override
  void initState() {
    super.initState();
    _tokenCtrl = TextEditingController(text: widget.initialToken?.trim() ?? '');
    if (_hasInitialToken) {
      _validateToken(_tokenCtrl.text);
    }
  }

  @override
  void didUpdateWidget(covariant ResetPasswordScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final nextToken = widget.initialToken?.trim() ?? '';
    if (nextToken != (oldWidget.initialToken?.trim() ?? '') &&
        nextToken.isNotEmpty) {
      _tokenCtrl.text = nextToken;
      _resetDone = false;
      _tokenInvalid = false;
      _validationTransientError = false;
      _bannerMessage = null;
      _validateToken(nextToken);
    }
  }

  @override
  void dispose() {
    _tokenCtrl.dispose();
    _passCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _validateToken(String token) async {
    setState(() {
      _validating = true;
      _tokenInvalid = false;
      _validationTransientError = false;
      _bannerMessage = null;
    });

    final result =
        await ref.read(authProvider.notifier).validateResetToken(token);
    if (!mounted) return;
    setState(() {
      _validating = false;
      if (!result.valid) {
        final isTransient = (result.isNetworkError || result.isTransientError) &&
            result.errorCode == null;
        if (isTransient) {
          _validationTransientError = true;
          _tokenInvalid = false;
          _bannerTone = AppStateBannerTone.warning;
          _bannerMessage = result.message ??
              'Không thể kiểm tra liên kết đặt lại mật khẩu lúc này.';
        } else {
          _tokenInvalid = true;
          _validationTransientError = false;
          _bannerTone = AppStateBannerTone.error;
          _bannerMessage =
              result.message ?? 'Liên kết đặt lại mật khẩu không hợp lệ.';
        }
      }
    });
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _bannerMessage = null;
    });

    final res = await ref.read(authProvider.notifier).resetPassword(
          token: _tokenCtrl.text.trim(),
          newPassword: _passCtrl.text,
        );
    if (!mounted) return;

    setState(() {
      _submitting = false;
      if (res.isSuccess) {
        _resetDone = true;
        _bannerTone = AppStateBannerTone.info;
        _bannerMessage = res.message ??
            'Đặt lại mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới.';
      } else {
        if (res.errorCode == 'RESET_TOKEN_EXPIRED' ||
            res.errorCode == 'RESET_TOKEN_USED' ||
            res.errorCode == 'RESET_TOKEN_INVALID') {
          _tokenInvalid = true;
        }
        _bannerTone = res.isNetworkError
            ? AppStateBannerTone.warning
            : AppStateBannerTone.error;
        _bannerMessage = res.message ?? 'Không thể đặt lại mật khẩu.';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Đặt lại mật khẩu')),
      body: SafeArea(
        child: ResponsiveWrapper(
          maxWidth: 520,
          child: _validating
              ? const AppLoading(
                  message: 'Đang kiểm tra liên kết đặt lại mật khẩu...',
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Icon(
                          Icons.password_rounded,
                          size: 52,
                          color: AppColors.primary,
                        ),
                        const SizedBox(height: AppSpacing.md),
                        const Text(
                          'Tạo mật khẩu mới',
                          style: AppTypography.h2,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          'Nhập mật khẩu mới tối thiểu 6 ký tự cho tài khoản GoMate của bạn.',
                          style: AppTypography.bodyM
                              .copyWith(color: AppColors.textSecondary),
                          textAlign: TextAlign.center,
                        ),
                        if (_bannerMessage != null) ...[
                          const SizedBox(height: AppSpacing.md),
                          AppStateBanner(
                            key: const Key('reset_status_banner'),
                            message: _bannerMessage!,
                            tone: _bannerTone,
                            actionLabel: _validationTransientError
                                ? 'Thử lại'
                                : (_tokenInvalid ? 'Gửi lại liên kết' : null),
                            onAction: _validationTransientError
                                ? () => _validateToken(_tokenCtrl.text)
                                : (_tokenInvalid
                                    ? () => context.go('/forgot-password')
                                    : null),
                          ),
                        ],
                        if (_validationTransientError) ...[
                          const SizedBox(height: AppSpacing.lg),
                          AppButton(
                            key: const Key('reset_retry_validate_button'),
                            text: 'Thử lại kiểm tra liên kết',
                            onPressed: () => _validateToken(_tokenCtrl.text),
                          ),
                        ] else if (_tokenInvalid) ...[
                          const SizedBox(height: AppSpacing.lg),
                          AppButton(
                            key: const Key('reset_request_new_button'),
                            text: 'Yêu cầu liên kết mới',
                            variant: AppButtonVariant.secondary,
                            onPressed: () => context.go('/forgot-password'),
                          ),
                        ] else if (_resetDone) ...[
                          const SizedBox(height: AppSpacing.lg),
                          AppButton(
                            key: const Key('reset_go_login_button'),
                            text: 'Đăng nhập ngay',
                            onPressed: () {
                              ref.read(authProvider.notifier).clearError();
                              context.go('/login');
                            },
                          ),
                        ] else ...[
                          const SizedBox(height: AppSpacing.lg),
                          if (!_hasInitialToken) ...[
                            AppTextField(
                              key: const Key('reset_token_input'),
                              controller: _tokenCtrl,
                              enabled: !_submitting,
                              labelText: 'Mã đặt lại mật khẩu',
                              prefixIcon: const Icon(Icons.key_outlined),
                              validator: (v) => (v == null || v.trim().isEmpty)
                                  ? 'Vui lòng nhập mã đặt lại'
                                  : null,
                            ),
                            const SizedBox(height: AppSpacing.md),
                          ],
                          AppTextField(
                            key: const Key('reset_password_input'),
                            controller: _passCtrl,
                            enabled: !_submitting,
                            obscureText: true,
                            showPasswordToggle: true,
                            labelText: 'Mật khẩu mới',
                            prefixIcon: const Icon(Icons.lock_outlined),
                            validator: (v) => (v == null || v.length < 6)
                                ? 'Mật khẩu ít nhất 6 ký tự'
                                : null,
                          ),
                          const SizedBox(height: AppSpacing.md),
                          AppTextField(
                            key: const Key('reset_confirm_password_input'),
                            controller: _confirmCtrl,
                            enabled: !_submitting,
                            obscureText: true,
                            showPasswordToggle: true,
                            labelText: 'Xác nhận mật khẩu mới',
                            prefixIcon: const Icon(Icons.lock_outlined),
                            onSubmitted: (_) => _submitting ? null : _submit(),
                            validator: (v) => v != _passCtrl.text
                                ? 'Mật khẩu không khớp'
                                : null,
                          ),
                          const SizedBox(height: AppSpacing.lg),
                          AppButton(
                            key: const Key('reset_submit_button'),
                            text: 'Đặt lại mật khẩu',
                            isLoading: _submitting,
                            onPressed: _submitting ? null : _submit,
                          ),
                        ],
                        const SizedBox(height: AppSpacing.md),
                        TextButton(
                          key: const Key('reset_back_login_button'),
                          onPressed: () {
                            ref.read(authProvider.notifier).clearError();
                            context.go('/login');
                          },
                          child: const Text('Quay lại đăng nhập'),
                        ),
                      ],
                    ),
                  ),
                ),
        ),
      ),
    );
  }
}
