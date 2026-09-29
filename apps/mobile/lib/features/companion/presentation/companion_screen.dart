import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../core/theme/app_theme.dart';

class CompanionScreen extends StatefulWidget {
  const CompanionScreen({super.key});
  @override
  State<CompanionScreen> createState() => _CompanionScreenState();
}

class _CompanionScreenState extends State<CompanionScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  int _filterIndex = 0;

  final List<String> _filters = [
    'Tat ca', 'Cung tuyen', 'Cuoi tuan', 'Phuot', 'Nghi duong',
  ];

  final List<Map<String, dynamic>> _companions = [
    {
      'name': 'Nguyen Linh',
      'age': 24,
      'hometown': 'Ha Noi',
      'bio': 'Me phuot, thich kham pha vung cao. Da di 15 tinh.',
      'match': 98,
      'rating': 4.9,
      'trips': 23,
      'avatar': 'https://i.pravatar.cc/150?img=47',
      'destination': 'Ha Giang',
      'date': '15-20/10',
      'style': 'Phuot',
      'verified': true,
    },
    {
      'name': 'Tran Minh Duc',
      'age': 27,
      'hometown': 'TP.HCM',
      'bio': 'Luot song, leo nui, an uong. Tim ban di Da Nang.',
      'match': 94,
      'rating': 4.7,
      'trips': 18,
      'avatar': 'https://i.pravatar.cc/150?img=12',
      'destination': 'Da Nang',
      'date': '5-8/10',
      'style': 'Bien',
      'verified': true,
    },
    {
      'name': 'Le Thi Thu',
      'age': 22,
      'hometown': 'Da Nang',
      'bio': 'Yeu thien nhien, photography. Tim nhom 3-4 nguoi.',
      'match': 91,
      'rating': 4.8,
      'trips': 12,
      'avatar': 'https://i.pravatar.cc/150?img=38',
      'destination': 'Sapa',
      'date': '20-25/10',
      'style': 'Trekking',
      'verified': false,
    },
    {
      'name': 'Pham Quoc Bao',
      'age': 29,
      'hometown': 'Can Tho',
      'bio': 'Biker, thich di xe may xuyen Viet. 50.000km da di.',
      'match': 88,
      'rating': 4.6,
      'trips': 41,
      'avatar': 'https://i.pravatar.cc/150?img=33',
      'destination': 'Ca Mau',
      'date': '1-7/11',
      'style': 'Biker',
      'verified': true,
    },
    {
      'name': 'Hoang Phuong Anh',
      'age': 25,
      'hometown': 'Hue',
      'bio': 'Thich van hoa dia phuong, am thuc. Di cham, cam nhan sau.',
      'match': 85,
      'rating': 4.5,
      'trips': 9,
      'avatar': 'https://i.pravatar.cc/150?img=52',
      'destination': 'Hoi An',
      'date': '10-14/10',
      'style': 'Van hoa',
      'verified': true,
    },
  ];

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: NestedScrollView(
        headerSliverBuilder: (_, __) => [
          _buildHeader(),
          _buildFilterBar(),
        ],
        body: _buildCompanionList(),
      ),
    );
  }

  // ── HEADER ──────────────────────────────────────────────
  Widget _buildHeader() {
    return SliverToBoxAdapter(
      child: Container(
        padding: EdgeInsets.only(
          top: MediaQuery.of(context).padding.top + 12,
          left: 20,
          right: 20,
          bottom: 16,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Tim Ban Dong Hanh',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 22, fontWeight: FontWeight.w800,
                              color: AppTheme.onSurface)),
                      Text('AI ghep ban theo phong cach du lich',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 13, color: AppTheme.onSurfaceVariant)),
                    ],
                  ),
                ),
                // Post trip button
                GestureDetector(
                  onTap: () => _showPostTripSheet(context),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppTheme.primary,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.add_rounded,
                            size: 16, color: Colors.white),
                        const SizedBox(width: 4),
                        Text('Dang lich',
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 12, fontWeight: FontWeight.w700,
                                color: Colors.white)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            // AI match banner
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    AppTheme.primary.withValues(alpha: 0.08),
                    AppTheme.secondary.withValues(alpha: 0.06),
                  ],
                ),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                    color: AppTheme.primary.withValues(alpha: 0.15)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AppTheme.primary,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.auto_awesome_rounded,
                        color: Colors.white, size: 18),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('AI dang phan tich phong cach du lich cua ban',
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 12, fontWeight: FontWeight.w700,
                                color: AppTheme.onSurface)),
                        Text('Tim thay 5 ban dong hanh phu hop nhat hom nay',
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 11, color: AppTheme.primary)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── FILTER BAR ───────────────────────────────────────────
  Widget _buildFilterBar() {
    return SliverToBoxAdapter(
      child: SizedBox(
        height: 44,
        child: ListView.builder(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: _filters.length,
          itemBuilder: (_, i) {
            final selected = _filterIndex == i;
            return GestureDetector(
              onTap: () => setState(() => _filterIndex = i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                margin: const EdgeInsets.only(right: 8, bottom: 8),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: selected ? AppTheme.primary : Colors.white,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: selected
                        ? AppTheme.primary
                        : AppTheme.outlineVariant.withValues(alpha: 0.5),
                  ),
                ),
                child: Center(
                  child: Text(
                    _filters[i],
                    style: GoogleFonts.plusJakartaSans(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: selected ? Colors.white : AppTheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  // ── COMPANION LIST ───────────────────────────────────────
  Widget _buildCompanionList() {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      itemCount: _companions.length,
      itemBuilder: (_, i) => _buildCompanionCard(_companions[i]),
    );
  }

  Widget _buildCompanionCard(Map<String, dynamic> c) {
    final match = c['match'] as int;
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primary.withValues(alpha: 0.07),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Row 1: Avatar + Info + Match badge
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Avatar
                Stack(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(14),
                      child: CachedNetworkImage(
                        imageUrl: c['avatar'] as String,
                        width: 60,
                        height: 60,
                        fit: BoxFit.cover,
                        placeholder: (_, __) => Container(
                          color: AppTheme.surfaceContainerLow,
                          child: const Icon(Icons.person_rounded,
                              color: AppTheme.onSurfaceVariant),
                        ),
                        errorWidget: (_, __, ___) => Container(
                          color: AppTheme.primaryFixed,
                          child: Center(
                            child: Text(
                              (c['name'] as String)[0],
                              style: GoogleFonts.plusJakartaSans(
                                  fontSize: 22, fontWeight: FontWeight.w800,
                                  color: AppTheme.primary),
                            ),
                          ),
                        ),
                      ),
                    ),
                    if (c['verified'] == true)
                      Positioned(
                        bottom: 0, right: 0,
                        child: Container(
                          width: 18, height: 18,
                          decoration: BoxDecoration(
                            color: AppTheme.primary,
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 1.5),
                          ),
                          child: const Icon(Icons.verified_rounded,
                              color: Colors.white, size: 10),
                        ),
                      ),
                  ],
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(c['name'] as String,
                              style: GoogleFonts.plusJakartaSans(
                                  fontSize: 15, fontWeight: FontWeight.w700,
                                  color: AppTheme.onSurface)),
                          const SizedBox(width: 5),
                          Text('${c['age']}t',
                              style: GoogleFonts.plusJakartaSans(
                                  fontSize: 12, color: AppTheme.onSurfaceVariant)),
                        ],
                      ),
                      Text(c['hometown'] as String,
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 11, color: AppTheme.onSurfaceVariant)),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.star_rounded,
                              size: 12, color: Color(0xFFF59E0B)),
                          const SizedBox(width: 2),
                          Text('${c['rating']}',
                              style: GoogleFonts.plusJakartaSans(
                                  fontSize: 11, fontWeight: FontWeight.w700,
                                  color: AppTheme.onSurface)),
                          const SizedBox(width: 8),
                          const Icon(Icons.luggage_rounded,
                              size: 11, color: AppTheme.onSurfaceVariant),
                          const SizedBox(width: 2),
                          Text('${c['trips']} chuyen',
                              style: GoogleFonts.plusJakartaSans(
                                  fontSize: 11, color: AppTheme.onSurfaceVariant)),
                        ],
                      ),
                    ],
                  ),
                ),
                // Match badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                  decoration: BoxDecoration(
                    color: match >= 95
                        ? AppTheme.primary
                        : AppTheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    children: [
                      Text('$match%',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 14, fontWeight: FontWeight.w900,
                              color: match >= 95 ? Colors.white : AppTheme.primary)),
                      Text('Hop',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 9,
                              color: match >= 95
                                  ? Colors.white.withValues(alpha: 0.85)
                                  : AppTheme.primary)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            // Bio
            Text(c['bio'] as String,
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 12, color: AppTheme.onSurfaceVariant,
                    height: 1.4),
                maxLines: 2,
                overflow: TextOverflow.ellipsis),
            const SizedBox(height: 10),
            // Trip info chips
            Row(
              children: [
                _infoChip(Icons.location_on_rounded, c['destination'] as String),
                const SizedBox(width: 6),
                _infoChip(Icons.calendar_today_rounded, c['date'] as String),
                const SizedBox(width: 6),
                _infoChip(Icons.style_rounded, c['style'] as String),
              ],
            ),
            const SizedBox(height: 12),
            // Action buttons
            Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: () => _showConnectDialog(context, c['name'] as String),
                    child: Container(
                      height: 38,
                      decoration: BoxDecoration(
                        color: AppTheme.primary,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Center(
                        child: Text('Ket noi',
                            style: GoogleFonts.plusJakartaSans(
                                fontSize: 13, fontWeight: FontWeight.w700,
                                color: Colors.white)),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                _iconActionBtn(Icons.chat_bubble_outline_rounded, () {}),
                const SizedBox(width: 8),
                _iconActionBtn(Icons.bookmark_border_rounded, () {}),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: AppTheme.primary),
          const SizedBox(width: 3),
          Text(label,
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 10, fontWeight: FontWeight.w600,
                  color: AppTheme.onSurfaceVariant)),
        ],
      ),
    );
  }

  Widget _iconActionBtn(IconData icon, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: AppTheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
              color: AppTheme.outlineVariant.withValues(alpha: 0.4)),
        ),
        child: Icon(icon, size: 18, color: AppTheme.onSurfaceVariant),
      ),
    );
  }

  void _showConnectDialog(BuildContext ctx, String name) {
    showDialog(
      context: ctx,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Gui loi ket noi',
            style: GoogleFonts.plusJakartaSans(fontWeight: FontWeight.w800)),
        content: Text(
          'Ban muon gui loi ket noi den $name?\n'
          'Ho se nhan duoc thong bao va co the chap nhan.',
          style: GoogleFonts.plusJakartaSans(fontSize: 13, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Huy', style: GoogleFonts.plusJakartaSans()),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primary,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Da gui loi ket noi den $name!',
                      style: GoogleFonts.plusJakartaSans(color: Colors.white)),
                  backgroundColor: AppTheme.primary,
                ),
              );
            },
            child: Text('Gui',
                style: GoogleFonts.plusJakartaSans(
                    color: Colors.white, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }

  void _showPostTripSheet(BuildContext ctx) {
    showModalBottomSheet(
      context: ctx,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        height: MediaQuery.of(ctx).size.height * 0.5,
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                    color: AppTheme.outlineVariant,
                    borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),
            Text('Dang tim ban dong hanh',
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 16),
            _sheetField('Diem den', 'VD: Ha Giang, Sapa...'),
            const SizedBox(height: 10),
            _sheetField('Ngay di', 'VD: 15-20/10/2026'),
            const SizedBox(height: 10),
            _sheetField('So nguoi tim', 'VD: 2-3 nguoi'),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () => Navigator.pop(ctx),
                child: Text('Dang lich trinh',
                    style: GoogleFonts.plusJakartaSans(
                        fontWeight: FontWeight.w700, color: Colors.white)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sheetField(String label, String hint) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: GoogleFonts.plusJakartaSans(
                fontSize: 12, fontWeight: FontWeight.w600,
                color: AppTheme.onSurfaceVariant)),
        const SizedBox(height: 6),
        TextField(
          decoration: InputDecoration(
            hintText: hint,
            filled: true,
            fillColor: AppTheme.surfaceContainerLow,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          ),
          style: GoogleFonts.plusJakartaSans(fontSize: 13),
        ),
      ],
    );
  }
}
