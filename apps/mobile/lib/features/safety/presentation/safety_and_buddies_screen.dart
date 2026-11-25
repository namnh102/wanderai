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
import '../data/buddy_repository.dart';
import '../providers/buddy_provider.dart';

/// W08 Buddy Matching & Safety Tab (`/safety`):
/// Calls real NestJS `/matches/*` endpoints via [BuddyRepository]:
/// - Opt-in discovery toggle (`PATCH /matches/discovery`)
/// - Filtered candidate list (`GET /matches/candidates`)
/// - Masked profile bottom sheet (`GET /matches/peers/:peerId`)
/// - Double opt-in handshake (`POST /matches/request`, `PATCH /matches/:id/withdraw`,
///   `PATCH /matches/:id/respond`, `POST /matches/blocks`)
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

Future<void> showBuddyMaskedProfileSheet(
  BuildContext context, {
  required String peerId,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _BuddyMaskedProfileSheet(peerId: peerId),
  );
}

class _BuddyMaskedProfileSheet extends ConsumerStatefulWidget {
  final String peerId;
  const _BuddyMaskedProfileSheet({required this.peerId});

  @override
  ConsumerState<_BuddyMaskedProfileSheet> createState() =>
      _BuddyMaskedProfileSheetState();
}

class _BuddyMaskedProfileSheetState
    extends ConsumerState<_BuddyMaskedProfileSheet> {
  bool _loading = true;
  String? _error;
  BuddyMaskedProfileModel? _profile;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final p = await ref
          .read(buddyRepositoryProvider)
          .getMaskedProfile(widget.peerId);
      if (!mounted) return;
      setState(() {
        _profile = p;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Không thể mở hồ sơ rút gọn của thành viên này.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final maxHeight = MediaQuery.of(context).size.height * 0.82;
    return ResponsiveWrapper(
      maxWidth: 640,
      fillHeight: false,
      child: Container(
        key: const Key('buddy_masked_profile_sheet'),
        constraints: BoxConstraints(maxHeight: maxHeight),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadius.sheetRadius,
        ),
        padding: const EdgeInsets.all(AppSpacing.md),
        child: _loading
            ? const Padding(
                padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
                child: AppLoading(
                  isCompact: true,
                  message: 'Đang tải hồ sơ rút gọn...',
                ),
              )
            : _error != null
                ? AppErrorState(message: _error!, onRetry: _loadProfile)
                : _buildContent(context, _profile!),
      ),
    );
  }

  Widget _buildContent(BuildContext context, BuddyMaskedProfileModel profile) {
    final peer = profile.peer;
    return SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: AppColors.primaryContainer,
                child: Text(peer.displayName.characters.first),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(peer.displayName, style: AppTypography.h2),
                    Text(
                      peer.travelStyle != null
                          ? 'Phong cách: ${peer.travelStyle}'
                          : 'Du khách GoMate',
                      style: AppTypography.bodyS,
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Đóng',
                icon: const Icon(Icons.close_rounded),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            children: [
              AppBadge(
                label: '${profile.compatibilityScore}% hợp nhau',
                icon: Icons.favorite_border,
                color: profile.compatibilityBand == 'HIGH'
                    ? AppColors.primary
                    : AppColors.warning,
              ),
              if (profile.hasOverlappingTripWindow)
                const AppBadge(
                  label: 'Trùng khung lịch đi',
                  icon: Icons.event_available_outlined,
                  color: AppColors.primary,
                ),
              if (profile.isMatched)
                const AppBadge(
                  label: 'Đã kết nối (MATCHED)',
                  icon: Icons.verified_user_outlined,
                  color: AppColors.primary,
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(profile.explanation, style: AppTypography.bodyM),
          if (peer.bio != null && peer.bio!.trim().isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              peer.bio!,
              style:
                  AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
            ),
          ],
          if (profile.plannedDestinations.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.mdSmall),
            const Text('Điểm đến dự kiến', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final d in profile.plannedDestinations)
                  Chip(
                    label: Text(
                      d.hasOverlappingWindow
                          ? '${d.destinationName} (Trùng lịch)'
                          : d.destinationName,
                    ),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
          ],
          const SizedBox(height: AppSpacing.mdSmall),
          AppStateBanner(
            message: profile.privacyNotice,
            tone: AppStateBannerTone.info,
          ),
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            alignment: WrapAlignment.spaceBetween,
            children: [
              TextButton.icon(
                key: Key('buddy_block_${peer.id}'),
                onPressed: () async {
                  final ok =
                      await ref.read(buddyProvider.notifier).blockPeer(peer.id);
                  if (context.mounted) {
                    Navigator.of(context).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          ok
                              ? 'Đã chặn hai chiều ${peer.displayName}.'
                              : 'Không thể chặn người dùng lúc này.',
                        ),
                      ),
                    );
                  }
                },
                icon: const Icon(Icons.block, size: 18, color: AppColors.error),
                label: const Text(
                  'Chặn người dùng',
                  style: TextStyle(color: AppColors.error),
                ),
              ),
              if (profile.matchStatus == null)
                AppButton(
                  key: Key('buddy_sheet_invite_${peer.id}'),
                  text: 'Mời đồng hành',
                  icon: Icons.person_add_alt_1_outlined,
                  isFullWidth: false,
                  onPressed: () async {
                    final ok = await ref
                        .read(buddyProvider.notifier)
                        .sendRequest(peer.id);
                    if (context.mounted) {
                      Navigator.of(context).pop();
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
                )
              else if (profile.matchStatus == 'PENDING' &&
                  profile.matchDirection == 'SENT' &&
                  profile.matchId != null)
                OutlinedButton.icon(
                  key: Key('buddy_sheet_withdraw_${profile.matchId}'),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(120, 44),
                  ),
                  onPressed: () async {
                    final ok = await ref
                        .read(buddyProvider.notifier)
                        .withdrawRequest(profile.matchId!);
                    if (context.mounted) {
                      Navigator.of(context).pop();
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            ok
                                ? 'Đã rút lại lời mời kết nối.'
                                : 'Không thể rút lời mời lúc này.',
                          ),
                        ),
                      );
                    }
                  },
                  icon: const Icon(Icons.undo_rounded, size: 18),
                  label: const Text('Rút lời mời'),
                ),
            ],
          ),
        ],
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
    final outgoingPending = state.matches
        .where((m) => m.direction == 'SENT' && m.status == 'PENDING')
        .toList();
    final connected = state.matches.where((m) => m.isMatched).toList();

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
          const SizedBox(height: AppSpacing.sm),
          AppCard(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.xs,
            ),
            child: SwitchListTile(
              key: const Key('buddy_discovery_switch'),
              contentPadding: EdgeInsets.zero,
              title: const Text(
                'Bật tìm bạn đồng hành',
                style: AppTypography.h3,
              ),
              subtitle: Text(
                state.isDiscoverable
                    ? 'Đang bật hiển thị hồ sơ rút gọn với du khách phù hợp.'
                    : 'Đang tắt. Bật đồng thuận để xem và nhận gợi ý bạn đồng hành.',
                style: AppTypography.bodyS,
              ),
              value: state.isDiscoverable,
              onChanged: state.isTogglingDiscovery
                  ? null
                  : (v) => ref.read(buddyProvider.notifier).toggleDiscovery(v),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          if (connected.isNotEmpty) ...[
            const Text('Đã kết nối đồng thuận (MATCHED)',
                style: AppTypography.h3),
            const SizedBox(height: AppSpacing.sm),
            for (final m in connected)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AppCard(
                  key: Key('match_connected_${m.id}'),
                  onTap: () => showBuddyMaskedProfileSheet(
                    context,
                    peerId: m.peer.id,
                  ),
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Row(
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
                            Text(m.peer.displayName, style: AppTypography.h3),
                            if (m.explanation != null)
                              Text(m.explanation!, style: AppTypography.bodyS),
                          ],
                        ),
                      ),
                      const AppBadge(
                        label: 'Đã kết nối',
                        icon: Icons.verified_user_outlined,
                        color: AppColors.primary,
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.md),
          ],
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
                                Text(
                                  m.peer.displayName,
                                  style: AppTypography.h3,
                                ),
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
          if (outgoingPending.isNotEmpty) ...[
            const Text('Lời mời đã gửi', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.sm),
            for (final m in outgoingPending)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AppCard(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.peer.displayName, style: AppTypography.h3),
                            const Text(
                              'Đang chờ đối phương đồng thuận',
                              style: AppTypography.bodyS,
                            ),
                          ],
                        ),
                      ),
                      OutlinedButton(
                        key: Key('match_withdraw_${m.id}'),
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size(116, 40),
                        ),
                        onPressed: () => ref
                            .read(buddyProvider.notifier)
                            .withdrawRequest(m.id),
                        child: const Text('Rút lời mời'),
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.md),
          ],
          const Text('Gợi ý bạn đồng hành phù hợp', style: AppTypography.h3),
          const SizedBox(height: AppSpacing.sm),
          if (!state.isDiscoverable)
            AppEmptyState(
              key: const Key('buddy_opt_in_off_state'),
              icon: Icons.visibility_off_outlined,
              title: 'Chưa bật tìm bạn đồng hành',
              description:
                  'Bật công tắc đồng thuận phía trên để khám phá du khách có cùng hành trình và sở thích.',
              actionLabel: 'Bật tìm bạn ngay',
              onAction: () =>
                  ref.read(buddyProvider.notifier).toggleDiscovery(true),
            )
          else if (state.candidates.isEmpty)
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
      onTap: () => showBuddyMaskedProfileSheet(context, peerId: peer.id),
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
              style:
                  AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              TextButton.icon(
                key: Key('buddy_open_profile_${peer.id}'),
                onPressed: () =>
                    showBuddyMaskedProfileSheet(context, peerId: peer.id),
                icon: const Icon(Icons.assignment_ind_outlined, size: 16),
                label: const Text('Hồ sơ rút gọn'),
              ),
              hasMatch
                  ? AppBadge(
                      label:
                          candidate.isMatched ? 'Đã kết nối' : 'Đã gửi lời mời',
                      icon: Icons.check_circle_outline,
                      color: AppColors.primary,
                    )
                  : AppButton(
                      key: Key('buddy_request_${peer.id}'),
                      text: 'Mời đồng hành',
                      icon: Icons.person_add_alt_1_outlined,
                      isFullWidth: false,
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
            ],
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
