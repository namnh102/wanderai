import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/theme/app_theme.dart';

class SafetyScreen extends StatefulWidget {
  const SafetyScreen({super.key});
  @override
  State<SafetyScreen> createState() => _SafetyScreenState();
}

class _SafetyScreenState extends State<SafetyScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseCtrl;
  bool _sosPressed = false;

  // Vi tri mac dinh: Ha Noi
  static const _defaultPos = LatLng(21.0285, 105.8542);

  final List<Map<String, dynamic>> _hotlines = [
    {'name': 'Canh sat 113',   'number': '113', 'icon': Icons.local_police_rounded,   'color': Color(0xFF1D4ED8)},
    {'name': 'Cap cuu 115',    'number': '115', 'icon': Icons.local_hospital_rounded,  'color': Color(0xFFDC2626)},
    {'name': 'Phong chay 114', 'number': '114', 'icon': Icons.local_fire_department_rounded, 'color': Color(0xFFEA580C)},
    {'name': 'CSGT 1800 599 906','number': '1800599906','icon': Icons.directions_car_rounded,'color': Color(0xFF7C3AED)},
  ];

  final List<Map<String, String>> _safetyTips = [
    {'icon': 'shield',  'tip': 'Luu so lien lac khan cap truoc khi di'},
    {'icon': 'pin',     'tip': 'Chia se vi tri voi nguoi than khi di xa'},
    {'icon': 'bag',     'tip': 'Mang thuoc ca nhan va bo so cuu'},
    {'icon': 'phone',   'tip': 'Tai app offline ban do truoc khi mat mang'},
  ];

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    super.dispose();
  }

  Future<void> _callNumber(String number) async {
    final uri = Uri.parse('tel:$number');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Goi so: $number'),
            backgroundColor: AppTheme.primary,
          ),
        );
      }
    }
  }

  void _shareLocation() {
    const location = 'https://maps.google.com/?q=21.0285,105.8542';
    Clipboard.setData(const ClipboardData(text: location));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Da sao chep link vi tri!',
          style: GoogleFonts.plusJakartaSans(color: Colors.white),
        ),
        backgroundColor: AppTheme.primary,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _onSOSPressed() {
    setState(() => _sosPressed = true);
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.warning_rounded, color: Colors.red, size: 20),
            ),
            const SizedBox(width: 10),
            Text('Xac nhan SOS',
                style: GoogleFonts.plusJakartaSans(
                    fontWeight: FontWeight.w800, fontSize: 17)),
          ],
        ),
        content: Text(
          'Ban dang gui tin hieu khan cap?\n'
          'He thong se lien he Canh sat 113 va chia se vi tri cua ban.',
          style: GoogleFonts.plusJakartaSans(fontSize: 14, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () {
              setState(() => _sosPressed = false);
              Navigator.pop(context);
            },
            child: Text('Huy', style: GoogleFonts.plusJakartaSans(color: AppTheme.onSurfaceVariant)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(context);
              _callNumber('113');
            },
            child: Text('Goi 113 ngay',
                style: GoogleFonts.plusJakartaSans(
                    color: Colors.white, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    ).then((_) => setState(() => _sosPressed = false));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      body: CustomScrollView(
        slivers: [
          _buildHeader(),
          SliverToBoxAdapter(child: _buildSOSButton()),
          SliverToBoxAdapter(child: _buildMapSection()),
          SliverToBoxAdapter(child: _buildHotlines()),
          SliverToBoxAdapter(child: _buildSafetyTips()),
          const SliverToBoxAdapter(child: SizedBox(height: 32)),
        ],
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
        decoration: BoxDecoration(
          color: AppTheme.surface,
          boxShadow: [
            BoxShadow(
              color: AppTheme.primary.withValues(alpha: 0.06),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('An Toan & Khan Cap',
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 22, fontWeight: FontWeight.w800,
                          color: AppTheme.onSurface)),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Container(
                        width: 8, height: 8,
                        decoration: const BoxDecoration(
                          color: Color(0xFF22C55E), shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text('Dang theo doi vi tri cua ban',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 12, color: AppTheme.onSurfaceVariant)),
                    ],
                  ),
                ],
              ),
            ),
            GestureDetector(
              onTap: _shareLocation,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.share_location_rounded,
                        size: 16, color: AppTheme.primary),
                    const SizedBox(width: 5),
                    Text('Chia se vi tri',
                        style: GoogleFonts.plusJakartaSans(
                            fontSize: 12, fontWeight: FontWeight.w600,
                            color: AppTheme.primary)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── SOS BUTTON ──────────────────────────────────────────
  Widget _buildSOSButton() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
      child: Column(
        children: [
          // Pulsing SOS button
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, child) {
              final pulse = _pulseCtrl.value;
              return Stack(
                alignment: Alignment.center,
                children: [
                  // Outer pulse ring
                  Container(
                    width: 140 + pulse * 30,
                    height: 140 + pulse * 30,
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.08 - pulse * 0.07),
                      shape: BoxShape.circle,
                    ),
                  ),
                  // Middle ring
                  Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                  ),
                  // SOS button
                  GestureDetector(
                    onTap: _onSOSPressed,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 100),
                      width: 96,
                      height: 96,
                      decoration: BoxDecoration(
                        gradient: RadialGradient(
                          colors: _sosPressed
                              ? [Colors.red.shade900, Colors.red.shade700]
                              : [Colors.red.shade600, Colors.red.shade800],
                        ),
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: Colors.red.withValues(alpha: 0.5),
                            blurRadius: 20,
                            spreadRadius: 2,
                            offset: const Offset(0, 6),
                          ),
                        ],
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.sos_rounded,
                              color: Colors.white, size: 32),
                          Text('SOS',
                              style: GoogleFonts.plusJakartaSans(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w900,
                                  fontSize: 14,
                                  letterSpacing: 2)),
                        ],
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 12),
          Text('Nhan SOS de goi cap cuu ngay lap tuc',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 13, color: AppTheme.onSurfaceVariant)),
          const SizedBox(height: 4),
          Text('He thong se chia se vi tri den lien lac khan cap',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 11, color: AppTheme.outlineVariant)),
        ],
      ),
    );
  }

  // ── MAP ─────────────────────────────────────────────────
  Widget _buildMapSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Vi tri hien tai',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 16, fontWeight: FontWeight.w700,
                  color: AppTheme.onSurface)),
          const SizedBox(height: 10),
          Container(
            height: 200,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: FlutterMap(
                options: const MapOptions(
                  initialCenter: _defaultPos,
                  initialZoom: 13,
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'com.wanderai.app',
                  ),
                  MarkerLayer(
                    markers: [
                      Marker(
                        point: _defaultPos,
                        width: 50,
                        height: 50,
                        child: Container(
                          decoration: BoxDecoration(
                            color: Colors.red,
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 3),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.red.withValues(alpha: 0.4),
                                blurRadius: 10,
                              ),
                            ],
                          ),
                          child: const Icon(Icons.person_pin_rounded,
                              color: Colors.white, size: 22),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Icon(Icons.location_on_rounded,
                  size: 14, color: AppTheme.primary),
              const SizedBox(width: 4),
              Text('Ha Noi, Viet Nam • Cap nhat: Vua xong',
                  style: GoogleFonts.plusJakartaSans(
                      fontSize: 12, color: AppTheme.onSurfaceVariant)),
            ],
          ),
        ],
      ),
    );
  }

  // ── HOTLINES ────────────────────────────────────────────
  Widget _buildHotlines() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('So Khan Cap',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 16, fontWeight: FontWeight.w700,
                  color: AppTheme.onSurface)),
          const SizedBox(height: 12),
          GridView.count(
            crossAxisCount: 2,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 2.6,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            children: _hotlines.map((h) {
              final color = h['color'] as Color;
              return GestureDetector(
                onTap: () => _callNumber(h['number'] as String),
                child: Container(
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: color.withValues(alpha: 0.2)),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Row(
                    children: [
                      Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(h['icon'] as IconData, color: color, size: 18),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(h['name'] as String,
                                style: GoogleFonts.plusJakartaSans(
                                    fontSize: 10, fontWeight: FontWeight.w700,
                                    color: AppTheme.onSurface),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis),
                            Text(h['number'] as String,
                                style: GoogleFonts.plusJakartaSans(
                                    fontSize: 13, fontWeight: FontWeight.w800,
                                    color: color)),
                          ],
                        ),
                      ),
                      Icon(Icons.call_rounded, color: color, size: 16),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  // ── SAFETY TIPS ─────────────────────────────────────────
  Widget _buildSafetyTips() {
    final icons = {
      'shield': Icons.verified_user_rounded,
      'pin':    Icons.location_on_rounded,
      'bag':    Icons.medical_services_rounded,
      'phone':  Icons.download_for_offline_rounded,
    };
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Meo An Toan Khi Du Lich',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 16, fontWeight: FontWeight.w700,
                  color: AppTheme.onSurface)),
          const SizedBox(height: 12),
          ..._safetyTips.map((t) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(icons[t['icon']] ?? Icons.info_outline,
                          size: 18, color: AppTheme.primary),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(t['tip'] ?? '',
                          style: GoogleFonts.plusJakartaSans(
                              fontSize: 13, color: AppTheme.onSurface,
                              height: 1.4)),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }
}
