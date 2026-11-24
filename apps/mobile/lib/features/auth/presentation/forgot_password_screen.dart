import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../providers/auth_provider.dart';

class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() =>
      _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  bool _loading = false;
  String? _bannerMessage;
  AppStateBannerTone _bannerTone = AppStateBannerTone.info;

  @override
  void dispose() {
    _emailCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _bannerMessage = null;
    });

    final result = await ref
        .read(authProvider.notifier)
        .requestPasswordReset(_emailCtrl.text.trim());

    if (!mounted) return;
    setState(() {
      _loading = false;
      _bannerMessage = result.message ??
          (result.isSuccess
              ? 'Nếu email tồn tại trong hệ thống, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu.'
              : 'Không thể gửi yêu cầu khôi phục mật khẩu.');
      _bannerTone = result.isSuccess
          ? AppStateBannerTone.info
          : (result.isNetworkError
              ? AppStateBannerTone.warning
              : AppStateBannerTone.error);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quên mật khẩu')),
      body: SafeArea(
        child: ResponsiveWrapper(
          maxWidth: 520,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(
                    Icons.lock_reset_rounded,
                    size: 52,
                    color: AppColors.primary,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  const Text(
                    'Khôi phục mật khẩu',
                    style: AppTypography.h2,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Nhập email đã đăng ký để nhận liên kết đặt lại mật khẩu (hiệu lực 30 phút).',
                    style: AppTypography.bodyM
                        .copyWith(color: AppColors.textSecondary),
                    textAlign: TextAlign.center,
                  ),
                  if (_bannerMessage != null) ...[
                    const SizedBox(height: AppSpacing.md),
                    AppStateBanner(
                      key: const Key('forgot_result_banner'),
                      message: _bannerMessage!,
                      tone: _bannerTone,
                    ),
                  ],
                  const SizedBox(height: AppSpacing.lg),
                  AppTextField(
                    key: const Key('forgot_email_input'),
                    controller: _emailCtrl,
                    enabled: !_loading,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.done,
                    labelText: 'Email',
                    prefixIcon: const Icon(Icons.email_outlined),
                    onSubmitted: (_) => _loading ? null : _submit(),
                    validator: (v) => (v == null || !v.contains('@'))
                        ? 'Email không hợp lệ'
                        : null,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  AppButton(
                    key: const Key('forgot_submit_button'),
                    text: 'Gửi liên kết đặt lại',
                    isLoading: _loading,
                    onPressed: _loading ? null : _submit,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextButton(
                    key: const Key('forgot_go_reset_button'),
                    onPressed: () => context.push('/reset-password'),
                    child: const Text('Đã có mã đặt lại? Nhập mã ngay'),
                  ),
                  TextButton(
                    key: const Key('forgot_back_login_button'),
                    onPressed: () => context.go('/login'),
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
