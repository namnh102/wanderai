import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _obscure = true;

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    ref.listen(authProvider, (previous, next) {
      if (next.status == AuthStateStatus.error) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(next.errorMessage ?? 'Lỗi')));
      } else if (next.status == AuthStateStatus.authenticated) {
        context.go('/');
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('WanderAI', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.teal)),
              const SizedBox(height: 32),
              TextField(
                controller: _emailCtrl,
                decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passCtrl,
                decoration: InputDecoration(
                  labelText: 'Mật khẩu',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                ),
                obscureText: _obscure,
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: Colors.teal),
                  onPressed: authState.status == AuthStateStatus.loading
                      ? null
                      : () => ref.read(authProvider.notifier).login(_emailCtrl.text, _passCtrl.text),
                  child: authState.status == AuthStateStatus.loading 
                      ? const CircularProgressIndicator(color: Colors.white) 
                      : const Text('Đăng nhập'),
                ),
              ),
              TextButton(
                onPressed: () => context.push('/register'),
                child: const Text('Chưa có tài khoản? Đăng ký'),
              )
            ],
          ),
        ),
      ),
    );
  }
}