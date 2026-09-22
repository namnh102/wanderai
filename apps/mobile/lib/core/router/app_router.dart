import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/video_feed/presentation/video_feed_screen.dart';
import '../../features/ai_chat/presentation/ai_chat_screen.dart';
import '../../features/ai_planner/presentation/ai_planner_screen.dart';
import '../../features/trip/presentation/trip_detail_screen.dart';
import '../../features/map/presentation/map_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';
import '../../features/auth/providers/auth_provider.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>();
final GlobalKey<NavigatorState> _shellNavigatorKey = GlobalKey<NavigatorState>();

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggingIn = state.uri.path == '/login' || state.uri.path == '/register';
      
      if (!authState.isLoggedIn && !isLoggingIn) return '/login';
      if (authState.isLoggedIn && isLoggingIn) return '/';
      
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        builder: (context, state) => const RegisterScreen(),
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) {
          return Scaffold(
            body: child,
            bottomNavigationBar: BottomNavigationBar(
              currentIndex: _calculateSelectedIndex(context),
              onTap: (int idx) => _onItemTapped(idx, context),
              type: BottomNavigationBarType.fixed,
              items: const [
                BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
                BottomNavigationBarItem(icon: Icon(Icons.video_library), label: 'Feed'),
                BottomNavigationBarItem(icon: Icon(Icons.smart_toy), label: 'AI'),
                BottomNavigationBarItem(icon: Icon(Icons.card_travel), label: 'Trips'),
                BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Profile'),
              ],
            ),
          );
        },
        routes: [
          GoRoute(
            path: '/',
            redirect: (_, __) => '/home',
          ),
          GoRoute(
            path: '/home',
            builder: (context, state) => const HomeScreen(),
          ),
          GoRoute(
            path: '/feed',
            builder: (context, state) => const VideoFeedScreen(),
          ),
          GoRoute(
            path: '/ai',
            redirect: (_, __) => '/ai/chat',
          ),
          GoRoute(
            path: '/ai/chat',
            builder: (context, state) => const AiChatScreen(),
          ),
          GoRoute(
            path: '/ai/planner',
            builder: (context, state) => const AiPlannerScreen(),
          ),
          GoRoute(
            path: '/trips',
            builder: (context, state) => const Scaffold(body: Center(child: Text('Trips List Placeholder'))),
          ),
          GoRoute(
            path: '/trips/:id',
            builder: (context, state) => TripDetailScreen(id: state.pathParameters['id']!),
          ),
          GoRoute(
            path: '/map',
            builder: (context, state) => const MapScreen(),
          ),
          GoRoute(
            path: '/profile',
            builder: (context, state) => const ProfileScreen(),
          ),
        ]
      ),
    ],
  );
});

int _calculateSelectedIndex(BuildContext context) {
  final String location = GoRouterState.of(context).uri.path;
  if (location.startsWith('/home')) return 0;
  if (location.startsWith('/feed')) return 1;
  if (location.startsWith('/ai')) return 2;
  if (location.startsWith('/trips')) return 3;
  if (location.startsWith('/profile')) return 4;
  return 0;
}

void _onItemTapped(int index, BuildContext context) {
  switch (index) {
    case 0:
      context.go('/home');
      break;
    case 1:
      context.go('/feed');
      break;
    case 2:
      context.go('/ai/chat');
      break;
    case 3:
      context.go('/trips');
      break;
    case 4:
      context.go('/profile');
      break;
  }
}
