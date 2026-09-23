import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/providers/auth_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final userEmail = authState.email ?? '';
    final userName = userEmail.split('@').first;

    return Scaffold(
      appBar: AppBar(title: const Text('Hồ sơ')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          CircleAvatar(radius: 40, child: Text(userName.isNotEmpty ? userName[0].toUpperCase() : 'U', style: const TextStyle(fontSize: 32))),
          const SizedBox(height: 16),
          Text(userName, textAlign: TextAlign.center, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          Text(userEmail, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
          const SizedBox(height: 32),
          ListTile(leading: const Icon(Icons.language), title: const Text('Ngôn ngữ'), onTap: () {}),
          ListTile(leading: const Icon(Icons.notifications), title: const Text('Thông báo'), onTap: () {}),
          ListTile(leading: const Icon(Icons.dark_mode), title: const Text('Chế độ tối'), onTap: () {}),
          ListTile(leading: const Icon(Icons.info), title: const Text('Giới thiệu'), onTap: () {}),
          const SizedBox(height: 32),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => ref.read(authProvider.notifier).logout(),
            child: const Text('Đăng xuất', style: TextStyle(color: Colors.white)),
          )
        ],
      ),
    );
  }
}