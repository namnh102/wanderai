import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_badge.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../places/data/navigation_service.dart';
import '../data/buddy_models.dart';
import '../providers/buddy_provider.dart';

/// Wave C / W08 Preparation Tab (`/safety`):
/// Combines emergency safety guidance & Vietnam hotlines with opt-in W08 Buddy Matching.
class SafetyAndBuddiesScreen extends ConsumerStatefulWidget {
  const SafetyAndBuddiesScreen({super.key});

  @override
  ConsumerState<SafetyAndBuddiesScreen> createState() =>
      _SafetyAndBuddiesScreenState();
}

class _SafetyAndBuddiesScreenState
    extends ConsumerState<SafetyAndBuddiesScreen> {
  int _selectedSection = 0; // 0 = Bạn đồng hành (W08), 1 = An toàn & SOS

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) {
        ref.read(buddyProvider.notifier).load();
      }
    });
  }

  Future<void> _dialEmergency(String number) async {
    final opened = await openExternalUrlString(
      'tel:$number',
      opener: ref.read(externalUriOpenerProvider),
    );
    if (!opened && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Không thể mở trình gọi điện tới số $number.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(buddyProvider);

    return Scaffold(
      backgroundColor: AppColors.warmBackground,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        title: const Text('An toàn & Bạn đồng hành', style: AppTypography.h3),
      ),
      body: ResponsiveWrapper(
        maxWidth: 760,
        child: Column(
          children: [
            Container(
              color: AppColors.surface,
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                AppSpacing.xs,
                AppSpacing.md,
                AppSpacing.mdSmall,
              ),
              child: SegmentedButton<int>(
                segments: const [
                  ButtonSegment(
                    value: 0,
                    icon: Icon(Icons.group_outlined, size: 18),
                    label: Text('Bạn đồng hành (W08)'),
                  ),
                  ButtonSegment(
                    value: 1,
                    icon: Icon(Icons.shield_outlined, size: 18),
                    label: Text('An toàn & SOS'),
                  ),
                ],
                selected: {_selectedSection},
                onSelectionChanged: (s) =>
                    setState(() => _selectedSection = s.first),
              ),
            ),
            Expanded(
              child: _selectedSection == 0
                  ? _BuddiesTab(state: state)
                  : _SafetyTab(onDial: _dialEmergency),
            ),
          ],
        ),
      ),
    );
  }
}

class _BuddiesTab extends ConsumerWidget {
  final BuddyState state;
  const _BuddiesTab({required this.state});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (state.isLoading && state.candidates.isEmpty && state.matches.isEmpty) {
      return const AppLoading(message: 'Đang tìm bạn đồng hành phù hợp...');
    }

    if (state.errorMessage != null &&
        state.candidates.isEmpty &&
        state.matches.isEmpty) {
      return AppErrorState(
        message: state.errorMessage!,
        onRetry: () => ref.read(buddyProvider.notifier).load(),
      );
    }

    final incoming = state.matches
        .where((m) => m.direction == 'RECEIVED' && m.status == 'PENDING')
        .toList();

    return RefreshIndicator(
      onRefresh: () => ref.read(buddyProvider.notifier).load(),
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          const AppStateBanner(
            message:
                'Chế độ kết nối bảo mật: email, số điện thoại và vị trí chính xác luôn được ẩn khi ghép đôi.',
            tone: AppStateBannerTone.info,
          ),
          const SizedBox(height: AppSpacing.md),
          if (incoming.isNotEmpty) ...[
            const Text('Lời mời đang chờ phản hồi', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.sm),
            for (final m in incoming)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AppCard(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          CircleAvatar(
                            backgroundColor: AppColors.primaryContainer,
                            child: Text(m.peer.displayName.characters.first),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(m.peer.displayName,
                                    style: AppTypography.h3),
                                if (m.score != null)
                                  Text(
                                    'Độ tương thích ${m.score!.round()}%',
                                    style: AppTypography.bodyS
                                        .copyWith(color: AppColors.primary),
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      if (m.explanation != null) ...[
                        const SizedBox(height: AppSpacing.xs),
                        Text(m.explanation!, style: AppTypography.bodyS),
                      ],
                      const SizedBox(height: AppSpacing.sm),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              key: Key('match_reject_${m.id}'),
                              onPressed: () => ref
                                  .read(buddyProvider.notifier)
                                  .respond(m.id, 'REJECTED'),
                              child: const Text('Từ chối'),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: ElevatedButton(
                              key: Key('match_accept_${m.id}'),
                              onPressed: () => ref
                                  .read(buddyProvider.notifier)
                                  .respond(m.id, 'ACCEPTED'),
                              child: const Text('Chấp nhận'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.md),
          ],
          const Text('Gợi ý bạn đồng hành phù hợp', style: AppTypography.h3),
          const SizedBox(height: AppSpacing.sm),
          if (state.candidates.isEmpty)
            const AppEmptyState(
              icon: Icons.people_outline,
              title: 'Chưa có bạn đồng hành phù hợp',
              description:
                  'Hãy cập nhật sở thích du lịch hoặc tạo chuyến đi để tìm người cùng hành trình.',
            )
          else
            for (final c in state.candidates)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: _CandidateCard(candidate: c),
              ),
        ],
      ),
    );
  }
}

class _CandidateCard extends ConsumerWidget {
  final BuddyCandidateModel candidate;
  const _CandidateCard({required this.candidate});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final peer = candidate.peer;
    final hasMatch = candidate.matchStatus != null;

    return AppCard(
      key: Key('buddy_candidate_${peer.id}'),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundColor: AppColors.primaryContainer,
                child: Text(peer.displayName.characters.first),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(peer.displayName, style: AppTypography.h3),
                    Text(
                      peer.travelStyle != null
                          ? 'Phong cách: ${peer.travelStyle}'
                          : 'Thành viên GoMate',
                      style: AppTypography.bodyS,
                    ),
                  ],
                ),
              ),
              AppBadge(
                label: '${candidate.compatibilityScore}% hợp nhau',
                icon: Icons.favorite_border,
                color: candidate.compatibilityBand == 'HIGH'
                    ? AppColors.primary
                    : AppColors.warning,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(candidate.explanation, style: AppTypography.bodyS),
          if (peer.bio != null && peer.bio!.trim().isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              peer.bio!,
              style: AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          Align(
            alignment: Alignment.centerRight,
            child: hasMatch
                ? AppBadge(
                    label: candidate.matchStatus == 'ACCEPTED'
                        ? 'Đã kết nối'
                        : 'Đã gửi lời mời',
                    icon: Icons.check_circle_outline,
                    color: AppColors.primary,
                  )
                : AppButton(
                    key: Key('buddy_request_${peer.id}'),
                    text: 'Mời đồng hành',
                    icon: Icons.person_add_alt_1_outlined,
                    onPressed: () async {
                      final ok = await ref
                          .read(buddyProvider.notifier)
                          .sendRequest(peer.id);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              ok
                                  ? 'Đã gửi lời mời kết nối tới ${peer.displayName}'
                                  : 'Không thể gửi lời mời lúc này.',
                            ),
                          ),
                        );
                      }
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _SafetyTab extends StatelessWidget {
  final Future<void> Function(String number) onDial;
  const _SafetyTab({required this.onDial});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        const AppStateBanner(
          message:
              'Số khẩn cấp Việt Nam hoạt động 24/7. Nhấn để mở trình gọi điện mặc định.',
          tone: AppStateBannerTone.warning,
        ),
        const SizedBox(height: AppSpacing.md),
        _EmergencyTile(
          number: '113',
          title: 'Công an / An ninh khẩn cấp',
          subtitle: 'Báo cáo sự cố an ninh, mất trộm, đe dọa an toàn.',
          icon: Icons.local_police_outlined,
          onTap: () => onDial('113'),
        ),
        const SizedBox(height: AppSpacing.sm),
        _EmergencyTile(
          number: '114',
          title: 'Cứu hỏa & Cứu hộ',
          subtitle: 'Hỗ trợ hỏa hoạn, tai nạn mắc kẹt, cứu nạn khẩn cấp.',
          icon: Icons.local_fire_department_outlined,
          onTap: () => onDial('114'),
        ),
        const SizedBox(height: AppSpacing.sm),
        _EmergencyTile(
          number: '115',
          title: 'Cấp cứu y tế',
          subtitle: 'Điều phối xe cứu thương và hỗ trợ y tế khẩn cấp.',
          icon: Icons.medical_services_outlined,
          onTap: () => onDial('115'),
        ),
        const SizedBox(height: AppSpacing.lg),
        const AppCard(
          padding: EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Lộ trình an toàn W08 (Wave C)', style: AppTypography.h3),
              SizedBox(height: AppSpacing.xs),
              Text(
                '• Danh bạ khẩn cấp cá nhân & Check-in tọa độ chuyến đi đã có bảng schema (safety_contacts, safety_checkins).\n'
                '• Tuyệt đối không chia sẻ email, SĐT hoặc lịch trình chi tiết với người lạ trước khi đồng ý kết nối 2 chiều.',
                style: AppTypography.bodyS,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _EmergencyTile extends StatelessWidget {
  final String number;
  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  const _EmergencyTile({
    required this.number,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppColors.error.withValues(alpha: 0.12),
              borderRadius: AppRadius.mdRadius,
            ),
            child: Icon(icon, color: AppColors.error),
          ),
          const SizedBox(width: AppSpacing.mdSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$number — $title', style: AppTypography.h3),
                const SizedBox(height: 2),
                Text(subtitle, style: AppTypography.bodyS),
              ],
            ),
          ),
          const Icon(Icons.phone_forwarded_outlined, color: AppColors.error),
        ],
      ),
    );
  }
}
