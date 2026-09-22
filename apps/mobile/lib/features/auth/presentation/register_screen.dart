import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    ref.listen(authProvider, (previous, next) {
      if (next.status == AuthStateStatus.error) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(next.errorMessage ?? 'Lỗi')));
      } else if (next.status == AuthStateStatus.unauthenticated && previous?.status == AuthStateStatus.loading) {
        // Success
        ref.read(authProvider.notifier).login(_emailCtrl.text, _passCtrl.text);
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Đăng ký')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Họ tên', border: OutlineInputBorder())),
            const SizedBox(height: 16),
            TextField(controller: _emailCtrl, decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder())),
            const SizedBox(height: 16),
            TextField(controller: _passCtrl, decoration: const InputDecoration(labelText: 'Mật khẩu', border: OutlineInputBorder()), obscureText: true),
            const SizedBox(height: 16),
            TextField(controller: _confirmCtrl, decoration: const InputDecoration(labelText: 'Xác nhận mật khẩu', border: OutlineInputBorder()), obscureText: true),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(backgroundColor: Colors.teal),
                onPressed: authState.status == AuthStateStatus.loading
                    ? null
                    : () {
                        if (_passCtrl.text == _confirmCtrl.text) {
                          ref.read(authProvider.notifier).register(_nameCtrl.text, _emailCtrl.text, _passCtrl.text);
                        }
                      },
                child: authState.status == AuthStateStatus.loading 
                    ? const CircularProgressIndicator(color: Colors.white) 
                    : const Text('Đăng ký'),
              ),
            ),
            TextButton(
              onPressed: () => context.pop(),
              child: const Text('Đã có tài khoản? Đăng nhập'),
            )
          ],
        ),
      ),
    );
  }
}