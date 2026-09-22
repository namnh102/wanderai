import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/ai_chat/presentation/ai_chat_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    redirect: (context, state) {
      final isAuth = authState.status == AuthStateStatus.authenticated;
      final isLoginRoute = state.matchedLocation == '/login' || state.matchedLocation == '/register';

      if (!isAuth && !isLoginRoute) return '/login';
      if (isAuth && isLoginRoute) return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(path: '/register', builder: (context, state) => const RegisterScreen()),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => Scaffold(
          body: child,
          bottomNavigationBar: BottomNavigationBar(
            currentIndex: _calculateSelectedIndex(state.matchedLocation),
            onTap: (idx) => _onItemTapped(idx, context),
            selectedItemColor: Colors.teal,
            unselectedItemColor: Colors.grey,
            items: const [
              BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
              BottomNavigationBarItem(icon: Icon(Icons.chat), label: 'Wandy'),
              BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Profile'),
            ],
          ),
        ),
        routes: [
          GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
          GoRoute(path: '/chat', builder: (context, state) => const AiChatScreen()),
          GoRoute(path: '/profile', builder: (context, state) => const ProfileScreen()),
        ],
      ),
    ],
  );
});

int _calculateSelectedIndex(String location) {
  if (location.startsWith('/chat')) return 1;
  if (location.startsWith('/profile')) return 2;
  return 0;
}

void _onItemTapped(int index, BuildContext context) {
  switch (index) {
    case 0: context.go('/'); break;
    case 1: context.go('/chat'); break;
    case 2: context.go('/profile'); break;
  }
}