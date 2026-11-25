import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/router/app_router.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../providers/auth_provider.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  final String? redirectPath;

  const RegisterScreen({super.key, this.redirectPath});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _loading = false;
  String? _inlineError;
  AppStateBannerTone _inlineTone = AppStateBannerTone.error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _passCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _inlineError = null;
    });

    if (widget.redirectPath != null) {
      ref.read(postLoginRedirectProvider.notifier).state = widget.redirectPath;
    }

    final ok = await ref.read(authProvider.notifier).register(
          _nameCtrl.text.trim(),
          _emailCtrl.text.trim(),
          _passCtrl.text,
        );

    if (!mounted) return;
    setState(() {
      _loading = false;
      if (!ok) {
        final errorMsg =
            ref.read(authProvider).errorMessage ?? 'Đăng ký thất bại.';
        _inlineError = errorMsg;
        _inlineTone = errorMsg.contains('kết nối mạng') ||
                errorMsg.contains('kết nối máy chủ')
            ? AppStateBannerTone.warning
            : AppStateBannerTone.error;
      }
    });
  }

  void _cancelRegister(String redirectPath) {
    ref.read(authProvider.notifier).clearError();
    ref.read(postLoginRedirectProvider.notifier).state = null;
    ref.read(guestBrowseModeProvider.notifier).state = true;
    context.go(redirectPath);
  }

  @override
  Widget build(BuildContext context) {
    final effectiveRedirect =
        widget.redirectPath ?? ref.watch(postLoginRedirectProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Tạo tài khoản')),
      body: SafeArea(
        child: ResponsiveWrapper(
          maxWidth: 520,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  if (_inlineError != null) ...[
                    AppStateBanner(
                      key: const Key('register_error_banner'),
                      message: _inlineError!,
                      tone: _inlineTone,
                    ),
                    const SizedBox(height: AppSpacing.md),
                  ],
                  AppTextField(
                    key: const Key('register_name_input'),
                    controller: _nameCtrl,
                    enabled: !_loading,
                    labelText: 'Họ và tên',
                    prefixIcon: const Icon(Icons.person_outlined),
                    validator: (v) => (v == null || v.trim().isEmpty)
                        ? 'Vui lòng nhập tên'
                        : null,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  AppTextField(
                    key: const Key('register_email_input'),
                    controller: _emailCtrl,
                    enabled: !_loading,
                    keyboardType: TextInputType.emailAddress,
                    labelText: 'Email',
                    prefixIcon: const Icon(Icons.email_outlined),
                    validator: (v) => (v == null || !v.contains('@'))
                        ? 'Email không hợp lệ'
                        : null,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  AppTextField(
                    key: const Key('register_password_input'),
                    controller: _passCtrl,
                    enabled: !_loading,
                    obscureText: true,
                    showPasswordToggle: true,
                    labelText: 'Mật khẩu',
                    prefixIcon: const Icon(Icons.lock_outlined),
                    validator: (v) => (v == null || v.length < 6)
                        ? 'Mật khẩu ít nhất 6 ký tự'
                        : null,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  AppTextField(
                    key: const Key('register_confirm_password_input'),
                    controller: _confirmCtrl,
                    enabled: !_loading,
                    obscureText: true,
                    showPasswordToggle: true,
                    labelText: 'Xác nhận mật khẩu',
                    prefixIcon: const Icon(Icons.lock_outlined),
                    onSubmitted: (_) => _loading ? null : _register(),
                    validator: (v) =>
                        v != _passCtrl.text ? 'Mật khẩu không khớp' : null,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  AppButton(
                    key: const Key('register_submit_button'),
                    text: 'Đăng ký',
                    isLoading: _loading,
                    onPressed: _loading ? null : _register,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextButton(
                    onPressed: _loading
                        ? null
                        : () {
                            ref.read(authProvider.notifier).clearError();
                            final target = effectiveRedirect != null
                                ? '/login?redirect=${Uri.encodeComponent(effectiveRedirect)}'
                                : '/login';
                            context.go(target);
                          },
                    child: const Text('Đã có tài khoản? Đăng nhập'),
                  ),
                  if (effectiveRedirect != null)
                    TextButton.icon(
                      key: const Key('register_cancel_button'),
                      onPressed: _loading
                          ? null
                          : () => _cancelRegister(effectiveRedirect),
                      icon: const Icon(Icons.arrow_back_rounded, size: 18),
                      label: const Text('Hủy đăng nhập · Quay lại'),
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
