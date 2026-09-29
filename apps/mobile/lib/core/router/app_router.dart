import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/ai_chat/presentation/ai_chat_screen.dart';
import '../../features/trip/presentation/trip_screen.dart';
import '../../features/trip/presentation/trip_detail_screen.dart';
import '../../features/map/presentation/map_screen.dart';
import '../../features/companion/presentation/companion_screen.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../theme/app_theme.dart';
import 'package:google_fonts/google_fonts.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      final isLoading = authState.status == AuthStatus.initial;
      if (isLoading) return null;

      final isAuthed = authState.status == AuthStatus.authenticated;
      final isAuthRoute =
          state.uri.path == '/login' || state.uri.path == '/register';

      if (!isAuthed && !isAuthRoute) return '/login';
      if (isAuthed && isAuthRoute) return '/';
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
        builder: (context, state, child) => MainScaffold(child: child),
        routes: [
          GoRoute(
              path: '/', builder: (context, state) => const HomeScreen()),
          GoRoute(
              path: '/companions',
              builder: (context, state) => const CompanionScreen()),
          GoRoute(
              path: '/chat',
              builder: (context, state) => const AiChatScreen()),
          GoRoute(
              path: '/safety',
              builder: (context, state) => const SafetyScreen()),
          GoRoute(
              path: '/trips',
              builder: (context, state) => const TripScreen()),
          GoRoute(
              path: '/trips/:id',
              builder: (context, state) => TripDetailScreen(
                    id: state.pathParameters['id'] ?? '',
                  )),
        ],
      ),
    ],
  );
});

// Placeholder screen cho tính năng chưa làm
class _ComingSoonScreen extends StatelessWidget {
  final IconData icon;
  final String label;
  const _ComingSoonScreen({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppTheme.primaryFixed,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Icon(icon, size: 40, color: AppTheme.primary),
            ),
            const SizedBox(height: 16),
            Text(label,
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.onSurface)),
            const SizedBox(height: 8),
            Text('Tinh nang dang phat trien',
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 14, color: AppTheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}

// Main shell scaffold với bottom nav bar
class MainScaffold extends ConsumerStatefulWidget {
  final Widget child;
  const MainScaffold({super.key, required this.child});

  @override
  ConsumerState<MainScaffold> createState() => _MainScaffoldState();
}

class _MainScaffoldState extends ConsumerState<MainScaffold> {
  final List<String> _routes = ['/', '/companions', '/chat', '/safety', '/trips'];

  void _onTabTapped(int index) {
    context.go(_routes[index]);
  }

  int _getIndexFromRoute(String path) {
    if (path == '/') return 0;
    if (path.startsWith('/companions')) return 1;
    if (path.startsWith('/chat')) return 2;
    if (path.startsWith('/safety')) return 3;
    if (path.startsWith('/trips')) return 4;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final currentIndex = _getIndexFromRoute(location);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: widget.child,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          boxShadow: [
            BoxShadow(
              color: AppTheme.onSurface.withValues(alpha: 0.06),
              blurRadius: 20,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: SafeArea(
          child: SizedBox(
            height: 72,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _NavItem(
                  icon: Icons.explore_outlined,
                  activeIcon: Icons.explore,
                  label: 'Kham pha',
                  isSelected: currentIndex == 0,
                  onTap: () => _onTabTapped(0),
                ),
                _NavItem(
                  icon: Icons.diversity_1_outlined,
                  activeIcon: Icons.diversity_1,
                  label: 'Dong hanh',
                  isSelected: currentIndex == 1,
                  onTap: () => _onTabTapped(1),
                ),
                // AI Agent - center FAB
                GestureDetector(
                  onTap: () => _onTabTapped(2),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: currentIndex == 2
                                ? [AppTheme.primary, AppTheme.primaryContainer]
                                : [AppTheme.primary, AppTheme.primaryContainer],
                          ),
                          borderRadius: BorderRadius.circular(18),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.primary.withValues(alpha: 0.35),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: const Icon(Icons.auto_awesome,
                            color: Colors.white, size: 26),
                      ),
                      const SizedBox(height: 4),
                      Text('AI Agent',
                          style: GoogleFonts.plusJakartaSans(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: currentIndex == 2
                                ? AppTheme.primary
                                : AppTheme.onSurfaceVariant,
                          )),
                    ],
                  ),
                ),
                _NavItem(
                  icon: Icons.shield_outlined,
                  activeIcon: Icons.shield,
                  label: 'An toan',
                  isSelected: currentIndex == 3,
                  onTap: () => _onTabTapped(3),
                ),
                _NavItem(
                  icon: Icons.luggage_outlined,
                  activeIcon: Icons.luggage,
                  label: 'Chuyen di',
                  isSelected: currentIndex == 4,
                  onTap: () => _onTabTapped(4),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        width: 60,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 40,
              height: 28,
              decoration: BoxDecoration(
                color: isSelected
                    ? AppTheme.primaryFixed
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(
                isSelected ? activeIcon : icon,
                size: 20,
                color:
                    isSelected ? AppTheme.primary : AppTheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 10,
                fontWeight:
                    isSelected ? FontWeight.w700 : FontWeight.w500,
                color:
                    isSelected ? AppTheme.primary : AppTheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}