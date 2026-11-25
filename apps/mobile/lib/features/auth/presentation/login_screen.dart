import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/router/app_router.dart';
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
  bool _obscure = true;
  bool _loading = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);

    if (widget.redirectPath != null) {
      ref.read(postLoginRedirectProvider.notifier).state = widget.redirectPath;
    }

    final ok = await ref.read(authProvider.notifier).login(
          _emailCtrl.text.trim(),
          _passCtrl.text,
        );

    if (mounted) {
      setState(() => _loading = false);
      if (!ok) {
        final errorMsg =
            ref.read(authProvider).errorMessage ?? 'Đăng nhập thất bại.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(errorMsg),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
      // On success, GoRouter redirect handles navigation automatically
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final effectiveRedirect =
        widget.redirectPath ?? ref.watch(postLoginRedirectProvider);

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.auto_awesome, size: 64, color: cs.primary),
                  const SizedBox(height: 8),
                  Text('GoMate',
                      style:
                          Theme.of(context).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: cs.primary,
                              )),
                  const SizedBox(height: 4),
                  Text('Khám phá Việt Nam cùng AI',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: cs.onSurfaceVariant,
                          )),
                  if (effectiveRedirect != null &&
                      effectiveRedirect.startsWith('/places/')) ...[
                    const SizedBox(height: 16),
                    Container(
                      key: const Key('login_redirect_notice'),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                      decoration: BoxDecoration(
                        color: cs.primaryContainer.withValues(alpha: 0.45),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.bookmark_added_outlined,
                              size: 18, color: cs.primary),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Đăng nhập để lưu địa điểm và quay lại ngay nơi bạn đang xem.',
                              style: TextStyle(
                                fontSize: 12.5,
                                color: cs.onSurface,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 32),
                  TextFormField(
                    key: const Key('login_email_input'),
                    controller: _emailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      prefixIcon: Icon(Icons.email_outlined),
                    ),
                    validator: (v) => (v == null || !v.contains('@'))
                        ? 'Email không hợp lệ'
                        : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    key: const Key('login_password_input'),
                    controller: _passCtrl,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'Mật khẩu',
                      prefixIcon: const Icon(Icons.lock_outlined),
                      suffixIcon: IconButton(
                        icon: Icon(
                            _obscure ? Icons.visibility_off : Icons.visibility),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                    validator: (v) => (v == null || v.length < 6)
                        ? 'Mật khẩu ít nhất 6 ký tự'
                        : null,
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      key: const Key('login_submit_button'),
                      onPressed: _loading ? null : _login,
                      child: _loading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white))
                          : const Text('Đăng nhập'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    key: const Key('login_go_register_button'),
                    onPressed: () {
                      final target = effectiveRedirect != null
                          ? '/register?redirect=${Uri.encodeComponent(effectiveRedirect)}'
                          : '/register';
                      context.go(target);
                    },
                    child: const Text('Chưa có tài khoản? Đăng ký'),
                  ),
                  TextButton.icon(
                    key: const Key('login_guest_explore_button'),
                    onPressed: () {
                      ref.read(guestBrowseModeProvider.notifier).state = true;
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
    );
  }
}
