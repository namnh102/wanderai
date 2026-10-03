import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_colors.dart';
import '../widgets/responsive_wrapper.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/ai_chat/presentation/ai_chat_screen.dart';
import '../../features/trips/presentation/trip_list_screen.dart';
import '../../features/trips/presentation/trip_form_screen.dart';
import '../../features/trips/presentation/trip_detail_screen.dart';
import '../../features/map/presentation/map_screen.dart';

// Placeholder screens for tabs not yet implemented
class _PlaceholderScreen extends StatelessWidget {
  final String title;
  final IconData icon;
  const _PlaceholderScreen({required this.title, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: AppColors.primary),
            const SizedBox(height: 16),
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text(
              'Tính năng đang phát triển...',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppColors.textSecondary,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

/// RouterNotifier listens to AuthState changes and triggers GoRouter redirect
/// without recreating the GoRouter or its Navigator GlobalKeys.
/// This completely resolves the "Multiple widgets used the same GlobalKey" exception.
class RouterNotifier extends ChangeNotifier {
  final Ref _ref;

  RouterNotifier(this._ref) {
    _ref.listen<AuthState>(
      authProvider,
      (_, __) => notifyListeners(),
    );
  }

  String? redirect(BuildContext context, GoRouterState state) {
    final authState = _ref.read(authProvider);
    final isAuth = authState.status == AuthStatus.authenticated;
    final isLoading = authState.status == AuthStatus.unknown;
    final location = state.uri.toString();
    final isLoginRoute = location == '/login' || location == '/register';

    // While loading auth state, don't redirect
    if (isLoading) return null;

    // Not authenticated → force login (unless already there)
    if (!isAuth && !isLoginRoute) return '/login';

    // Authenticated but on login/register → go home
    if (isAuth && isLoginRoute) return '/';

    return null;
  }
}

final routerNotifierProvider = Provider<RouterNotifier>((ref) => RouterNotifier(ref));

final _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'rootNav');
final _shellNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'shellNav');

final appRouterProvider = Provider<GoRouter>((ref) {
  final notifier = ref.watch(routerNotifierProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    refreshListenable: notifier,
    redirect: notifier.redirect,
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        builder: (context, state) => const RegisterScreen(),
      ),
      GoRoute(
        path: '/trips/create',
        builder: (context, state) => const TripFormScreen(),
      ),
      GoRoute(
        path: '/trips/:id',
        builder: (context, state) => TripDetailScreen(
          tripId: state.pathParameters['id']!,
        ),
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => _MainScaffold(child: child),
        routes: [
          GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
          GoRoute(path: '/map', builder: (_, __) => const MapScreen()),
          GoRoute(path: '/ai', builder: (_, __) => const AiChatScreen()),
          GoRoute(path: '/safety', builder: (_, __) => const _PlaceholderScreen(title: 'An toàn', icon: Icons.shield)),
          GoRoute(path: '/trips', builder: (_, __) => const TripListScreen()),
        ],
      ),
    ],
  );
});

class _MainScaffold extends StatelessWidget {
  final Widget child;
  const _MainScaffold({required this.child});

  static const _tabs = ['/', '/map', '/ai', '/safety', '/trips'];

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.toString();
    final currentIndex = _tabs.indexOf(location).clamp(0, 4);

    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
        color: Theme.of(context).colorScheme.surface,
        child: SafeArea(
          top: false,
          child: ResponsiveWrapper(
            maxWidth: 720.0,
            fillHeight: false,
            child: NavigationBar(
          selectedIndex: currentIndex,
          onDestinationSelected: (index) => context.go(_tabs[index]),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.explore_outlined),
              selectedIcon: Icon(Icons.explore),
              label: 'Trang chủ',
            ),
            NavigationDestination(
              icon: Icon(Icons.map_outlined),
              selectedIcon: Icon(Icons.map),
              label: 'Bản đồ',
            ),
            NavigationDestination(
              icon: Icon(Icons.auto_awesome_outlined),
              selectedIcon: Icon(Icons.auto_awesome),
              label: 'Wandy AI',
            ),
            NavigationDestination(
              icon: Icon(Icons.shield_outlined),
              selectedIcon: Icon(Icons.shield),
              label: 'An toàn',
            ),
            NavigationDestination(
              icon: Icon(Icons.luggage_outlined),
              selectedIcon: Icon(Icons.luggage),
              label: 'Chuyến đi',
            ),
          ],
        ),
      ),
    ),
  ),
);
  }
}
