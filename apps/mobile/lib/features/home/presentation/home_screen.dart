import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:go_router/go_router.dart';
import '../providers/destination_provider.dart';
import 'widgets/destination_card.dart';
import '../../../core/theme/app_theme.dart';
import '../../auth/providers/auth_provider.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});
  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _searchCtrl = TextEditingController();

  final List<Map<String, dynamic>> _quickActions = [
    {'icon': Icons.map_outlined,       'label': 'Lap lich\nAI',       'route': '/chat'},
    {'icon': Icons.cabin_outlined,     'label': 'Homestay\nview may',  'route': '/'},
    {'icon': Icons.restaurant_outlined,'label': 'Dac san\nvung cao',   'route': '/'},
    {'icon': Icons.motorcycle_outlined,'label': 'Tim xe\nghep',        'route': '/companions'},
    {'icon': Icons.shield_outlined,    'label': 'An toan\ncong dong',  'route': '/safety'},
  ];

  final List<Map<String, dynamic>> _feedPosts = [
    {
      'author': 'Linh Dan',
      'verified': true,
      'time': '2 gio truoc',
      'location': 'Y Ty, Lao Cai',
      'title': '3 ngay 2 dem san may Y Ty chi 1tr8/nguoi - full chi tiet!',
      'content':
          'Vua dap chuyen di san bien may bong benh tai Choang Then & Ngai Thau Thuong. Khong khi se lanh 16 do cuc phe, do an ban dia lau ga den nam...',
      'images': [
        'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400',
        'https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=400',
        'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=400',
        'https://images.unsplash.com/photo-1501854140801-50d01698950b?w=400',
      ],
      'extraImages': 4,
      'aiExtract': 'Trich xuat lich trinh 3N2D & du toan 1.800.000d tu bai viet cua Linh Dan.',
      'stops': 3,
      'homestays': 2,
      'likes': '1.4k',
      'comments': '256',
      'saves': '89',
    },
    {
      'author': 'Hoang Nam Phuot',
      'verified': true,
      'time': '5 gio truoc',
      'location': 'Dong Van, Ha Giang',
      'title': 'Cam nhan sau chuyen phuot xuyen Moc Chau - Ha Giang 5N4D',
      'content':
          'Hanh trinh dai nhat tu truoc den nay cua minh. Duong di qua Meo Vac dep den nao long, homestay ban dia am ap...',
      'images': [
        'https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=400',
        'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=400',
      ],
      'extraImages': 0,
      'aiExtract': 'Trich xuat lich trinh 5N4D & du toan 3.200.000d tu bai viet cua Hoang Nam.',
      'stops': 5,
      'homestays': 4,
      'likes': '892',
      'comments': '134',
      'saves': '67',
    },
  ];

  final List<Map<String, dynamic>> _aiSuggestions = [
    {
      'name': 'Deo Ma Pi Leng',
      'location': 'Huyen Meo Vac, Ha Giang',
      'image': 'https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600',
      'match': 98,
      'price': '~650.000d/ngay',
      'time': '06:30',
      'tags': ['Chua lanh', 'Phuot deo'],
      'badge': 'Tiet kiem',
    },
    {
      'name': 'Ca Phe Lo Lo Chai',
      'location': 'Dong Van, Ha Giang',
      'image': 'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=600',
      'match': 95,
      'price': '~45.000d/ly',
      'time': '07:00',
      'tags': ['Cafe ban dia', 'View nui'],
      'badge': 'Pho bien',
    },
    {
      'name': 'Hem Tu San',
      'location': 'Meo Vac, Ha Giang',
      'image': 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600',
      'match': 92,
      'price': '~150.000d/nguoi',
      'time': '08:00',
      'tags': ['Cheo thuyen', 'Kham pha'],
      'badge': 'Dac biet',
    },
  ];

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final destinations = ref.watch(filteredDestinationsProvider);
    final isLoading = ref.watch(destinationsProvider).isLoading;
    final authState = ref.watch(authProvider);
    final email = authState.email ?? '';
    final initials = email.isNotEmpty ? email[0].toUpperCase() : 'W';

    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: CustomScrollView(
        slivers: [
          // ── HEADER ──────────────────────────────────────
          SliverToBoxAdapter(
            child: _buildHeader(initials),
          ),
          // ── SEARCH BAR ──────────────────────────────────
          SliverToBoxAdapter(
            child: _buildSearchBar(),
          ),
          // ── LIVE CONTEXT BAR ────────────────────────────
          SliverToBoxAdapter(
            child: _buildLiveContextBar(),
          ),
          // ── AI SUGGESTIONS ──────────────────────────────
          SliverToBoxAdapter(
            child: _buildSectionHeader('AI Goi Y Danh Rieng Ban', 'Xem tat ca'),
          ),
          SliverToBoxAdapter(
            child: _buildAiSuggestions(),
          ),
          // ── QUICK ACTIONS ───────────────────────────────
          SliverToBoxAdapter(
            child: _buildQuickActions(),
          ),
          // ── FEED ────────────────────────────────────────
          SliverToBoxAdapter(
            child: _buildFeedHeader(),
          ),
          SliverToBoxAdapter(
            child: _buildFeedPosts(),
          ),
          // ── DESTINATION GRID ────────────────────────────
          SliverToBoxAdapter(
            child: _buildSectionHeader('Kham Pha Viet Nam', 'Xem tat ca'),
          ),
          if (isLoading)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              sliver: SliverGrid(
                delegate: SliverChildBuilderDelegate(
                  (ctx, i) => DestinationCard(destination: destinations[i]),
                  childCount: destinations.length,
                ),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  childAspectRatio: 0.72,
                ),
              ),
            ),
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
        ],
      ),
    );
  }

  // ── HEADER ──────────────────────────────────────────────
  Widget _buildHeader(String initials) {
    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        left: 16,
        right: 16,
        bottom: 12,
      ),
      color: AppTheme.surface,
      child: Row(
        children: [
          // Logo
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppTheme.primary, AppTheme.primaryContainer],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.explore_rounded, color: Colors.white, size: 18),
          ),
          const SizedBox(width: 8),
          Text(
            'WanderAI',
            style: GoogleFonts.plusJakartaSans(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: AppTheme.primary,
            ),
          ),
          const Spacer(),
          // Weather
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: AppTheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.wb_sunny_outlined, size: 14, color: AppTheme.primary),
                const SizedBox(width: 4),
                Text(
                  '24C',
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.onSurface,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // Bell
          Stack(
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined, color: AppTheme.onSurface),
                onPressed: () {},
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
              ),
              Positioned(
                top: 4,
                right: 4,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppTheme.secondary,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(width: 4),
          // Avatar
          CircleAvatar(
            radius: 18,
            backgroundColor: AppTheme.primary,
            child: Text(
              initials,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── SEARCH BAR ──────────────────────────────────────────
  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Container(
        height: 48,
        decoration: BoxDecoration(
          color: AppTheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: AppTheme.outlineVariant.withValues(alpha: 0.5),
          ),
        ),
        child: Row(
          children: [
            const SizedBox(width: 16),
            const Icon(Icons.search_rounded, color: AppTheme.onSurfaceVariant, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _searchCtrl,
                onChanged: (val) =>
                    ref.read(searchQueryProvider.notifier).state = val,
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 14,
                  color: AppTheme.onSurface,
                ),
                decoration: InputDecoration(
                  hintText: 'Tim diem den, mon an, tour AI goi y...',
                  hintStyle: GoogleFonts.plusJakartaSans(
                    fontSize: 14,
                    color: AppTheme.onSurfaceVariant,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                ),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.mic_none_rounded,
                  color: AppTheme.primary, size: 20),
              onPressed: () {},
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            ),
            IconButton(
              icon: const Icon(Icons.tune_rounded,
                  color: AppTheme.onSurfaceVariant, size: 20),
              onPressed: () {},
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            ),
            const SizedBox(width: 4),
          ],
        ),
      ),
    );
  }

  // ── LIVE CONTEXT BAR ────────────────────────────────────
  Widget _buildLiveContextBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          color: AppTheme.primary.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: AppTheme.primary.withValues(alpha: 0.15),
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(
                color: AppTheme.primary,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.location_on_rounded,
                size: 14, color: AppTheme.primary),
            const SizedBox(width: 4),
            Expanded(
              child: Text(
                'Dang o Ha Noi  •  24°C Nang nhe  •  Live AI  •',
                style: GoogleFonts.plusJakartaSans(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.primary,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── SECTION HEADER ──────────────────────────────────────
  Widget _buildSectionHeader(String title, String action) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: GoogleFonts.plusJakartaSans(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: AppTheme.onSurface,
            ),
          ),
          GestureDetector(
            onTap: () {},
            child: Text(
              '$action  >',
              style: GoogleFonts.plusJakartaSans(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.primary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── AI SUGGESTIONS (horizontal scroll) ──────────────────
  Widget _buildAiSuggestions() {
    return SizedBox(
      height: 255,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        itemCount: _aiSuggestions.length,
        itemBuilder: (ctx, i) {
          final s = _aiSuggestions[i];
          return GestureDetector(
            onTap: () {},
            child: Container(
              width: 230,
              margin: const EdgeInsets.only(right: 12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primary.withValues(alpha: 0.08),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Image section — fixed 110px
                    SizedBox(
                      height: 110,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          Image.network(
                            s['image'] as String,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              color: AppTheme.surfaceContainerLow,
                              child: const Icon(Icons.image_outlined,
                                  size: 40, color: AppTheme.onSurfaceVariant),
                            ),
                          ),
                          Positioned(
                            top: 7,
                            left: 7,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 7, vertical: 3),
                              decoration: BoxDecoration(
                                color: AppTheme.primary,
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                '${s['match']}% Hop gu',
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 9,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ),
                          Positioned(
                            top: 7,
                            right: 7,
                            child: Container(
                              width: 26,
                              height: 26,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.9),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.favorite_border,
                                  size: 13, color: AppTheme.secondary),
                            ),
                          ),
                        ],
                      ),
                    ),
                    // Info section
                    Padding(
                      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            s['name'] as String,
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.onSurface,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            s['location'] as String,
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 10,
                              color: AppTheme.onSurfaceVariant,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 5),
                          Row(
                            children: [
                              const Icon(Icons.sell_outlined,
                                  size: 10, color: AppTheme.secondary),
                              const SizedBox(width: 3),
                              Expanded(
                                child: Text(
                                  s['price'] as String,
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.secondary,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const Icon(Icons.schedule_rounded,
                                  size: 10, color: AppTheme.onSurfaceVariant),
                              const SizedBox(width: 2),
                              Text(
                                s['time'] as String,
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 10,
                                  color: AppTheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Row(
                            children: (s['tags'] as List<String>)
                                .take(2)
                                .map((tag) => Container(
                                      margin: const EdgeInsets.only(right: 4),
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 7, vertical: 3),
                                      decoration: BoxDecoration(
                                        color: AppTheme.primary
                                            .withValues(alpha: 0.08),
                                        borderRadius:
                                            BorderRadius.circular(999),
                                      ),
                                      child: Text(
                                        tag,
                                        style: GoogleFonts.plusJakartaSans(
                                          fontSize: 9,
                                          fontWeight: FontWeight.w600,
                                          color: AppTheme.primary,
                                        ),
                                      ),
                                    ))
                                .toList(),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }


  // ── QUICK ACTIONS ────────────────────────────────────────
  Widget _buildQuickActions() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 16),
      child: SizedBox(
        height: 80,
        child: ListView.builder(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: _quickActions.length,
          itemBuilder: (ctx, i) {
            final a = _quickActions[i];
            return GestureDetector(
              onTap: () => context.go(a['route'] as String),
              child: Container(
                width: 72,
                margin: const EdgeInsets.only(right: 10),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceContainerLow,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: AppTheme.outlineVariant.withValues(alpha: 0.4),
                        ),
                      ),
                      child: Icon(
                        a['icon'] as IconData,
                        color: AppTheme.primary,
                        size: 22,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      a['label'] as String,
                      style: GoogleFonts.plusJakartaSans(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.onSurfaceVariant,
                        height: 1.2,
                      ),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  // ── FEED HEADER ──────────────────────────────────────────
  Widget _buildFeedHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            'Feed Du Lich Thong Minh',
            style: GoogleFonts.plusJakartaSans(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: AppTheme.onSurface,
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(
                color: AppTheme.outlineVariant.withValues(alpha: 0.5),
              ),
            ),
            child: Row(
              children: [
                Text(
                  'Gan day nhat',
                  style: GoogleFonts.plusJakartaSans(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.onSurface,
                  ),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.keyboard_arrow_down_rounded,
                    size: 16, color: AppTheme.onSurface),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── FEED POSTS ───────────────────────────────────────────
  Widget _buildFeedPosts() {
    return Column(
      children: _feedPosts.map((post) => _buildPostCard(post)).toList(),
    );
  }

  Widget _buildPostCard(Map<String, dynamic> post) {
    final images = post['images'] as List<String>;
    final extra = post['extraImages'] as int;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primary.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Author row
            Row(
              children: [
                CircleAvatar(
                  radius: 18,
                  backgroundColor: AppTheme.primaryContainer,
                  child: Text(
                    (post['author'] as String)[0],
                    style: GoogleFonts.plusJakartaSans(
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            post['author'] as String,
                            style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.onSurface,
                            ),
                          ),
                          if (post['verified'] == true) ...[
                            const SizedBox(width: 5),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppTheme.primary.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                'Da xac thuc',
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 9,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primary,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      Text(
                        '${post['time']}  •  ${post['location']}',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 11,
                          color: AppTheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.more_horiz, color: AppTheme.onSurfaceVariant),
              ],
            ),
            const SizedBox(height: 10),
            // Title
            Text(
              post['title'] as String,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.onSurface,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 5),
            Text(
              post['content'] as String,
              style: GoogleFonts.plusJakartaSans(
                fontSize: 13,
                color: AppTheme.onSurfaceVariant,
                height: 1.5,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 10),
            // Image grid
            _buildImageGrid(images, extra),
            const SizedBox(height: 12),
            // AI Smart Extraction
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: AppTheme.primary.withValues(alpha: 0.15),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.auto_awesome_rounded,
                          size: 14, color: AppTheme.primary),
                      const SizedBox(width: 6),
                      Text(
                        'AI SMART EXTRACTION',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          color: AppTheme.primary,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    post['aiExtract'] as String,
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 12,
                      color: AppTheme.onSurface,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Icon(Icons.alt_route_rounded,
                          size: 14, color: AppTheme.onSurfaceVariant),
                      const SizedBox(width: 4),
                      Text(
                        '${post['stops']} chang check-in  •  ${post['homestays']} homestay goi y',
                        style: GoogleFonts.plusJakartaSans(
                          fontSize: 11,
                          color: AppTheme.onSurfaceVariant,
                        ),
                      ),
                      const Spacer(),
                      GestureDetector(
                        onTap: () {},
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [AppTheme.primary, AppTheme.primaryContainer],
                            ),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.bolt_rounded,
                                  size: 12, color: Colors.white),
                              const SizedBox(width: 4),
                              Text(
                                'Tao chuyen di bang AI',
                                style: GoogleFonts.plusJakartaSans(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            // Reactions
            Row(
              children: [
                _reactionItem(Icons.favorite_rounded, post['likes'] as String,
                    AppTheme.secondary),
                const SizedBox(width: 16),
                _reactionItem(Icons.chat_bubble_outline_rounded,
                    post['comments'] as String, AppTheme.onSurfaceVariant),
                const SizedBox(width: 16),
                _reactionItem(Icons.share_outlined, 'Chia se',
                    AppTheme.onSurfaceVariant),
                const Spacer(),
                _reactionItem(Icons.bookmark_border_rounded,
                    '${post['saves']} luu', AppTheme.primary),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImageGrid(List<String> images, int extra) {
    if (images.isEmpty) return const SizedBox.shrink();
    if (images.length == 1) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Image.network(images[0],
            height: 160, width: double.infinity, fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              height: 160,
              color: AppTheme.surfaceContainerLow,
            )),
      );
    }
    return SizedBox(
      height: 160,
      child: Row(
        children: [
          Expanded(
            child: ClipRRect(
              borderRadius:
                  const BorderRadius.horizontal(left: Radius.circular(10)),
              child: Image.network(images[0],
                  height: 160, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) =>
                      Container(color: AppTheme.surfaceContainerLow)),
            ),
          ),
          const SizedBox(width: 3),
          Expanded(
            child: Column(
              children: [
                Expanded(
                  child: ClipRRect(
                    borderRadius: images.length <= 2
                        ? const BorderRadius.horizontal(
                            right: Radius.circular(10))
                        : BorderRadius.zero,
                    child: Image.network(
                      images.length > 1 ? images[1] : images[0],
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) =>
                          Container(color: AppTheme.surfaceContainerLow),
                    ),
                  ),
                ),
                if (images.length > 2) ...[
                  const SizedBox(height: 3),
                  Expanded(
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        ClipRRect(
                          borderRadius: const BorderRadius.only(
                            bottomRight: Radius.circular(10),
                          ),
                          child: Image.network(
                            images[2],
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                                color: AppTheme.surfaceContainerLow),
                          ),
                        ),
                        if (extra > 0)
                          ClipRRect(
                            borderRadius: const BorderRadius.only(
                              bottomRight: Radius.circular(10),
                            ),
                            child: Container(
                              color: Colors.black.withValues(alpha: 0.45),
                              child: Center(
                                child: Text(
                                  '+$extra anh',
                                  style: GoogleFonts.plusJakartaSans(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _reactionItem(IconData icon, String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 15, color: color),
        const SizedBox(width: 4),
        Text(
          label,
          style: GoogleFonts.plusJakartaSans(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: AppTheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}