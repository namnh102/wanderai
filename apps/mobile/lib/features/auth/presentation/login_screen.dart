import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/router/app_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../data/auth_social_port.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  final String? redirectPath;

  const LoginScreen({super.key, this.redirectPath});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _loading = false;
  SocialAuthProvider? _socialLoading;
  String? _inlineError;
  AppStateBannerTone _inlineTone = AppStateBannerTone.error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  bool get _isBusy => _loading || _socialLoading != null;

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _inlineError = null;
    });

    if (widget.redirectPath != null) {
      ref.read(postLoginRedirectProvider.notifier).state = widget.redirectPath;
    }

    final ok = await ref.read(authProvider.notifier).login(
          _emailCtrl.text.trim(),
          _passCtrl.text,
        );

    if (!mounted) return;
    setState(() {
      _loading = false;
      if (!ok) {
        final errorMsg =
            ref.read(authProvider).errorMessage ?? 'Đăng nhập thất bại.';
        _inlineError = errorMsg;
        _inlineTone = errorMsg.contains('kết nối mạng') ||
                errorMsg.contains('kết nối máy chủ')
            ? AppStateBannerTone.warning
            : AppStateBannerTone.error;
      }
    });
  }

  Future<void> _socialLogin(SocialAuthProvider provider) async {
    setState(() {
      _socialLoading = provider;
      _inlineError = null;
    });

    if (widget.redirectPath != null) {
      ref.read(postLoginRedirectProvider.notifier).state = widget.redirectPath;
    }

    final result = provider == SocialAuthProvider.google
        ? await ref.read(authProvider.notifier).signInWithGoogle()
        : await ref.read(authProvider.notifier).signInWithFacebook();

    if (!mounted) return;
    setState(() {
      _socialLoading = null;
      if (result.isError) {
        _inlineError = result.message ?? 'Đăng nhập thất bại.';
        _inlineTone = result.isNetworkError
            ? AppStateBannerTone.warning
            : AppStateBannerTone.error;
      }
      // On AuthActionOutcome.cancelled, stay clean with no error banner.
    });
  }

  void _cancelLogin(String redirectPath) {
    ref.read(postLoginRedirectProvider.notifier).state = null;
    ref.read(guestBrowseModeProvider.notifier).state = true;
    context.go(redirectPath);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final effectiveRedirect =
        widget.redirectPath ?? ref.watch(postLoginRedirectProvider);
    final authError = ref.watch(authProvider.select((s) => s.errorMessage));
    final displayedError = _inlineError ?? authError;

    return Scaffold(
      body: SafeArea(
        child: ResponsiveWrapper(
          maxWidth: 520,
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.auto_awesome, size: 64, color: cs.primary),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      'GoMate',
                      style:
                          Theme.of(context).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: cs.primary,
                              ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Khám phá Việt Nam cùng AI',
                      style: AppTypography.bodyM
                          .copyWith(color: AppColors.textSecondary),
                    ),
                    if (effectiveRedirect != null &&
                        effectiveRedirect.startsWith('/places/')) ...[
                      const SizedBox(height: AppSpacing.md),
                      const AppStateBanner(
                        key: Key('login_redirect_notice'),
                        icon: Icons.bookmark_added_outlined,
                        tone: AppStateBannerTone.info,
                        message:
                            'Đăng nhập để lưu địa điểm và quay lại ngay nơi bạn đang xem.',
                      ),
                    ],
                    if (displayedError != null && displayedError.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.md),
                      AppStateBanner(
                        key: const Key('login_error_banner'),
                        message: displayedError,
                        tone: _inlineTone,
                      ),
                    ],
                    const SizedBox(height: AppSpacing.lg),
                    AppTextField(
                      key: const Key('login_email_input'),
                      controller: _emailCtrl,
                      enabled: !_isBusy,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      labelText: 'Email',
                      prefixIcon: const Icon(Icons.email_outlined),
                      validator: (v) => (v == null || !v.contains('@'))
                          ? 'Email không hợp lệ'
                          : null,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      key: const Key('login_password_input'),
                      controller: _passCtrl,
                      enabled: !_isBusy,
                      obscureText: true,
                      showPasswordToggle: true,
                      textInputAction: TextInputAction.done,
                      labelText: 'Mật khẩu',
                      prefixIcon: const Icon(Icons.lock_outlined),
                      onSubmitted: (_) => _isBusy ? null : _login(),
                      validator: (v) => (v == null || v.length < 6)
                          ? 'Mật khẩu ít nhất 6 ký tự'
                          : null,
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        key: const Key('login_forgot_password_button'),
                        onPressed: _isBusy
                            ? null
                            : () => context.push('/forgot-password'),
                        child: const Text('Quên mật khẩu?'),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    AppButton(
                      key: const Key('login_submit_button'),
                      text: 'Đăng nhập',
                      isLoading: _loading,
                      onPressed: _isBusy ? null : _login,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    const Row(
                      children: [
                        Expanded(child: Divider()),
                        Padding(
                          padding: EdgeInsets.symmetric(
                            horizontal: AppSpacing.sm,
                          ),
                          child: Text(
                            'Hoặc tiếp tục với',
                            style: AppTypography.caption,
                          ),
                        ),
                        Expanded(child: Divider()),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      children: [
                        Expanded(
                          child: AppButton(
                            key: const Key('login_google_button'),
                            text: 'Google',
                            icon: Icons.g_mobiledata_rounded,
                            variant: AppButtonVariant.secondary,
                            isLoading:
                                _socialLoading == SocialAuthProvider.google,
                            onPressed: _isBusy
                                ? null
                                : () => _socialLogin(SocialAuthProvider.google),
                          ),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: AppButton(
                            key: const Key('login_facebook_button'),
                            text: 'Facebook',
                            icon: Icons.facebook_rounded,
                            variant: AppButtonVariant.secondary,
                            isLoading:
                                _socialLoading == SocialAuthProvider.facebook,
                            onPressed: _isBusy
                                ? null
                                : () =>
                                    _socialLogin(SocialAuthProvider.facebook),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    TextButton(
                      key: const Key('login_go_register_button'),
                      onPressed: _isBusy
                          ? null
                          : () {
                              final target = effectiveRedirect != null
                                  ? '/register?redirect=${Uri.encodeComponent(effectiveRedirect)}'
                                  : '/register';
                              context.go(target);
                            },
                      child: const Text('Chưa có tài khoản? Đăng ký'),
                    ),
                    if (effectiveRedirect != null)
                      TextButton.icon(
                        key: const Key('login_cancel_button'),
                        onPressed: _isBusy
                            ? null
                            : () => _cancelLogin(effectiveRedirect),
                        icon: const Icon(Icons.arrow_back_rounded, size: 18),
                        label: const Text('Hủy đăng nhập · Quay lại'),
                      ),
                    TextButton.icon(
                      key: const Key('login_guest_explore_button'),
                      onPressed: _isBusy
                          ? null
                          : () {
                              ref.read(postLoginRedirectProvider.notifier).state =
                                  null;
                              ref.read(guestBrowseModeProvider.notifier).state =
                                  true;
                              context.go('/');
                            },
                      icon: const Icon(Icons.explore_outlined, size: 18),
                      label: const Text('Khám phá trước khi đăng nhập'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
