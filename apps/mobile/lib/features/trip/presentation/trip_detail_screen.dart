import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';

// Provider load trip detail
final tripDetailProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, id) async {
  try {
    final r = await apiClient.get('/trips/$id');
    if (r.data['success'] == true) return r.data['data'] as Map<String, dynamic>;
    return {};
  } catch (_) {
    return {};
  }
});

class TripDetailScreen extends ConsumerStatefulWidget {
  final String id;
  const TripDetailScreen({super.key, required this.id});
  @override
  ConsumerState<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends ConsumerState<TripDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabs;

  // Mock itinerary data (real data would come from API)
  final List<Map<String, dynamic>> _days = [
    {
      'day': 1,
      'title': 'Ngay 1 — Kham pha noi thanh',
      'cost': 650000,
      'activities': [
        {'time': '07:00', 'name': 'An sang pho truyen thong', 'type': 'food',
         'address': '49 Bat Dan, Hoan Kiem', 'cost': 45000, 'done': true},
        {'time': '09:00', 'name': 'Tham quan Ho Hoan Kiem', 'type': 'attraction',
         'address': 'Hoan Kiem, Ha Noi', 'cost': 0, 'done': true},
        {'time': '11:00', 'name': 'Pho co 36 pho phuong', 'type': 'attraction',
         'address': 'Hang Dao, Hoan Kiem', 'cost': 0, 'done': false},
        {'time': '13:00', 'name': 'Com bun cha Obama', 'type': 'food',
         'address': '24 Le Van Huu, Hai Ba Trung', 'cost': 65000, 'done': false},
        {'time': '15:00', 'name': 'Bao tang Lich su', 'type': 'attraction',
         'address': '1 Trang Tien, Hoan Kiem', 'cost': 40000, 'done': false},
        {'time': '19:00', 'name': 'Pho di bo Ho Tay', 'type': 'attraction',
         'address': 'Tay Ho, Ha Noi', 'cost': 0, 'done': false},
      ],
    },
    {
      'day': 2,
      'title': 'Ngay 2 — Lang que ngoai o',
      'cost': 450000,
      'activities': [
        {'time': '06:30', 'name': 'Banh mi buoi sang', 'type': 'food',
         'address': 'Near hotel', 'cost': 25000, 'done': false},
        {'time': '08:00', 'name': 'Lang gom su Bat Trang', 'type': 'attraction',
         'address': 'Bat Trang, Gia Lam', 'cost': 50000, 'done': false},
        {'time': '12:00', 'name': 'An trua dac san', 'type': 'food',
         'address': 'Bat Trang', 'cost': 80000, 'done': false},
        {'time': '14:00', 'name': 'Gom thu cong', 'type': 'attraction',
         'address': 'Bat Trang', 'cost': 200000, 'done': false},
        {'time': '17:00', 'name': 'Ve khach san nghi ngoi', 'type': 'transport',
         'address': 'Ha Noi', 'cost': 50000, 'done': false},
      ],
    },
    {
      'day': 3,
      'title': 'Ngay 3 — Am thuc & mua sam',
      'cost': 720000,
      'activities': [
        {'time': '08:00', 'name': 'Cho dong Dong Xuan', 'type': 'attraction',
         'address': 'Dong Xuan, Hoan Kiem', 'cost': 0, 'done': false},
        {'time': '10:00', 'name': 'Mua qua luu niem', 'type': 'attraction',
         'address': 'Hang Gai, Hoan Kiem', 'cost': 300000, 'done': false},
        {'time': '12:30', 'name': 'Bun cha o pho co', 'type': 'food',
         'address': 'Hang Manh, Hoan Kiem', 'cost': 55000, 'done': false},
        {'time': '15:00', 'name': 'Ca phe trung Ha Noi', 'type': 'food',
         'address': 'Dinh Tien Hoang, Hoan Kiem', 'cost': 45000, 'done': false},
        {'time': '18:00', 'name': 'An toi dem cuoi', 'type': 'food',
         'address': 'La Terasse, Ba Dinh', 'cost': 280000, 'done': false},
      ],
    },
  ];

  final List<Map<String, dynamic>> _expenses = [
    {'category': 'An uong', 'amount': 650000, 'color': Color(0xFFFF5A5F), 'icon': Icons.restaurant_rounded},
    {'category': 'Di chuyen', 'amount': 350000, 'color': Color(0xFF3B82F6), 'icon': Icons.directions_car_rounded},
    {'category': 'Tham quan', 'amount': 290000, 'color': Color(0xFF00685F), 'icon': Icons.camera_alt_rounded},
    {'category': 'Luu tru', 'amount': 480000, 'color': Color(0xFFF59E0B), 'icon': Icons.hotel_rounded},
    {'category': 'Mua sam', 'amount': 500000, 'color': Color(0xFF8B5CF6), 'icon': Icons.shopping_bag_rounded},
  ];

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  int get _totalCost => _expenses.fold(0, (s, e) => s + (e['amount'] as int));

  @override
  Widget build(BuildContext context) {
    final tripAsync = ref.watch(tripDetailProvider(widget.id));

    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: tripAsync.when(
        loading: () => const Center(
            child: CircularProgressIndicator(color: AppTheme.primary)),
        error: (_, __) => _buildBody(null),
        data: (trip) => _buildBody(trip.isEmpty ? null : trip),
      ),
    );
  }

  Widget _buildBody(Map<String, dynamic>? trip) {
    final title = trip?['title'] as String? ?? 'Hanh trinh cua toi';
    final status = trip?['status'] as String? ?? 'DRAFT';

    return NestedScrollView(
      headerSliverBuilder: (_, __) => [
        _buildSliverHeader(title, status),
        _buildTabBar(),
      ],
      body: TabBarView(
        controller: _tabs,
        children: [
          _buildItineraryTab(),
          _buildExpenseTab(),
          _buildMembersTab(),
        ],
      ),
    );
  }

  // ── SLIVER HEADER ────────────────────────────────────────
  Widget _buildSliverHeader(String title, String status) {
    return SliverAppBar(
      expandedHeight: 200,
      pinned: true,
      backgroundColor: AppTheme.primary,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
        onPressed: () => Navigator.pop(context),
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.share_rounded, color: Colors.white),
          onPressed: () {},
        ),
        IconButton(
          icon: const Icon(Icons.more_vert_rounded, color: Colors.white),
          onPressed: () {},
        ),
      ],
      flexibleSpace: FlexibleSpaceBar(
        background: Stack(
          fit: StackFit.expand,
          children: [
            CachedNetworkImage(
              imageUrl:
                  'https://images.unsplash.com/photo-1509030450996-dd1a26dda07a?w=600',
              fit: BoxFit.cover,
              placeholder: (_, __) =>
                  Container(color: AppTheme.primaryFixed),
              errorWidget: (_, __, ___) =>
                  Container(color: AppTheme.primaryFixed),
            ),
            Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Colors.transparent,
                    Colors.black.withValues(alpha: 0.7),
                  ],
                ),
              ),
            ),
            Positioned(
              left: 16,
              right: 16,
              bottom: 16,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: _statusColor(status),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      _statusLabel(status),
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Colors.white),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(title,
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: Colors.white)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.calendar_today_rounded,
                          size: 12, color: Colors.white70),
                      const SizedBox(width: 4),
                      Text('3 ngay 2 dem  •  Ha Noi',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 12, color: Colors.white70)),
                      const Spacer(),
                      Text(
                          '${(_totalCost / 1000).round()}k VND',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: Colors.white)),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabBar() {
    return SliverToBoxAdapter(
      child: Container(
        color: Colors.white,
        child: TabBar(
          controller: _tabs,
          labelColor: AppTheme.primary,
          unselectedLabelColor: AppTheme.onSurfaceVariant,
          indicatorColor: AppTheme.primary,
          indicatorWeight: 3,
          labelStyle: GoogleFonts.plusJakartaSans(
              fontWeight: FontWeight.w700, fontSize: 13),
          unselectedLabelStyle: GoogleFonts.plusJakartaSans(fontSize: 13),
          tabs: const [
            Tab(text: 'Lich trinh'),
            Tab(text: 'Chi tieu'),
            Tab(text: 'Thanh vien'),
          ],
        ),
      ),
    );
  }

  // ── ITINERARY TAB ────────────────────────────────────────
  Widget _buildItineraryTab() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _days.length,
      itemBuilder: (_, i) {
        final day = _days[i];
        final activities =
            (day['activities'] as List).cast<Map<String, dynamic>>();
        final dayCost = day['cost'] as int;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Day header
            Container(
              margin: EdgeInsets.only(bottom: 12, top: i == 0 ? 0 : 16),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: AppTheme.primary,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(
                      child: Text('${day['day']}',
                          style: GoogleFonts.plusJakartaSans(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              fontSize: 13)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(day['title'] as String,
                        style: GoogleFonts.plusJakartaSans(
                            fontWeight: FontWeight.w700,
                            fontSize: 13,
                            color: AppTheme.onSurface)),
                  ),
                  Text(
                    '${(dayCost / 1000).round()}k',
                    style: GoogleFonts.plusJakartaSans(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.secondary),
                  ),
                ],
              ),
            ),
            // Activities timeline
            ...activities.asMap().entries.map((e) {
              final idx = e.key;
              final act = e.value;
              final isDone = act['done'] as bool;
              final isLast = idx == activities.length - 1;
              return _timelineItem(act, isDone, isLast);
            }),
          ],
        );
      },
    );
  }

  Widget _timelineItem(Map<String, dynamic> act, bool isDone, bool isLast) {
    final typeColors = {
      'food': const Color(0xFFFF5A5F),
      'attraction': AppTheme.primary,
      'transport': const Color(0xFF3B82F6),
      'accommodation': const Color(0xFFF59E0B),
      'shopping': const Color(0xFF8B5CF6),
    };
    final typeIcons = {
      'food': Icons.restaurant_rounded,
      'attraction': Icons.camera_alt_rounded,
      'transport': Icons.directions_car_rounded,
      'accommodation': Icons.hotel_rounded,
      'shopping': Icons.shopping_bag_rounded,
    };
    final color = typeColors[act['type']] ?? AppTheme.primary;
    final icon = typeIcons[act['type']] ?? Icons.place_rounded;
    final cost = act['cost'] as int;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Timeline column
          SizedBox(
            width: 40,
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: isDone ? color : color.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                    border: Border.all(color: color, width: 2),
                  ),
                  child: Icon(
                    isDone ? Icons.check_rounded : icon,
                    color: isDone ? Colors.white : color,
                    size: 13,
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      color: AppTheme.outlineVariant.withValues(alpha: 0.4),
                    ),
                  ),
              ],
            ),
          ),
          // Content
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(left: 8, bottom: isLast ? 0 : 16),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: isDone
                          ? color.withValues(alpha: 0.3)
                          : AppTheme.outlineVariant.withValues(alpha: 0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(act['time'] as String,
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: color)),
                        const Spacer(),
                        if (cost > 0)
                          Text('${(cost / 1000).round()}k',
                              style: GoogleFonts.plusJakartaSans(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.secondary)),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(act['name'] as String,
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: isDone
                                ? AppTheme.onSurfaceVariant
                                : AppTheme.onSurface,
                            decoration: isDone
                                ? TextDecoration.lineThrough
                                : null)),
                    const SizedBox(height: 2),
                    Text(act['address'] as String,
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 11,
                            color: AppTheme.onSurfaceVariant)),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── EXPENSE TAB ─────────────────────────────────────────
  Widget _buildExpenseTab() {
    final total = _totalCost;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Pie chart
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primary.withValues(alpha: 0.07),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              children: [
                Text('Tong chi tieu: ${(total / 1000).round()}k VND',
                    style: GoogleFonts.plusJakartaSans(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.onSurface)),
                const SizedBox(height: 16),
                SizedBox(
                  height: 200,
                  child: PieChart(
                    PieChartData(
                      sections: _expenses.map((e) {
                        final pct =
                            (e['amount'] as int) / total * 100;
                        return PieChartSectionData(
                          value: (e['amount'] as int).toDouble(),
                          color: e['color'] as Color,
                          title: '${pct.round()}%',
                          radius: 70,
                          titleStyle: GoogleFonts.plusJakartaSans(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              color: Colors.white),
                        );
                      }).toList(),
                      sectionsSpace: 2,
                      centerSpaceRadius: 40,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                // Legend
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: _expenses.map((e) {
                    return Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            color: e['color'] as Color,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Text(e['category'] as String,
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 11,
                                color: AppTheme.onSurfaceVariant)),
                      ],
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Expense list
          ..._expenses.map((e) {
            final pct = (e['amount'] as int) / total;
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: (e['color'] as Color).withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(e['icon'] as IconData,
                        color: e['color'] as Color, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(e['category'] as String,
                            style: GoogleFonts.plusJakartaSans(
                                fontWeight: FontWeight.w700, fontSize: 13)),
                        const SizedBox(height: 4),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: pct,
                            backgroundColor: (e['color'] as Color)
                                .withValues(alpha: 0.12),
                            valueColor: AlwaysStoppedAnimation(
                                e['color'] as Color),
                            minHeight: 6,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    '${((e['amount'] as int) / 1000).round()}k',
                    style: GoogleFonts.plusJakartaSans(
                        fontWeight: FontWeight.w800,
                        fontSize: 14,
                        color: AppTheme.onSurface),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── MEMBERS TAB ─────────────────────────────────────────
  Widget _buildMembersTab() {
    final members = [
      {'name': 'Ban (toi)', 'role': 'Truong nhom', 'avatar': 'T', 'paid': 1200000},
      {'name': 'Nguyen Van A', 'role': 'Thanh vien', 'avatar': 'A', 'paid': 850000},
      {'name': 'Le Thi B', 'role': 'Thanh vien', 'avatar': 'B', 'paid': 770000},
    ];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ...members.map((m) => Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            children: [
              Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.primaryFixed,
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(m['avatar'] as String,
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 18, fontWeight: FontWeight.w800,
                          color: AppTheme.primary)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(m['name'] as String,
                        style: GoogleFonts.plusJakartaSans(
                            fontWeight: FontWeight.w700, fontSize: 14)),
                    Text(m['role'] as String,
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 11, color: AppTheme.onSurfaceVariant)),
                  ],
                ),
              ),
              Text('${((m['paid'] as int) / 1000).round()}k',
                  style: GoogleFonts.plusJakartaSans(
                      fontWeight: FontWeight.w800, fontSize: 14,
                      color: AppTheme.primary)),
            ],
          ),
        )),
        const SizedBox(height: 16),
        ElevatedButton.icon(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.primaryFixed,
            foregroundColor: AppTheme.primary,
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12)),
          ),
          icon: const Icon(Icons.person_add_rounded),
          label: Text('Moi thanh vien',
              style: GoogleFonts.plusJakartaSans(fontWeight: FontWeight.w700)),
          onPressed: () {},
        ),
      ],
    );
  }

  Color _statusColor(String s) {
    switch (s) {
      case 'PLANNED': return const Color(0xFF3B82F6);
      case 'ONGOING': return const Color(0xFF22C55E);
      case 'COMPLETED': return const Color(0xFF6B7280);
      default: return AppTheme.secondary;
    }
  }

  String _statusLabel(String s) {
    switch (s) {
      case 'PLANNED': return 'Da len ke hoach';
      case 'ONGOING': return 'Dang di';
      case 'COMPLETED': return 'Da hoan thanh';
      default: return 'Nhap';
    }
  }
}
