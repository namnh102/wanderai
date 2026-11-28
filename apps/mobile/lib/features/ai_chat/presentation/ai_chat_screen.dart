import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../places/data/navigation_service.dart';
import '../../trips/data/trip_models.dart';
import '../../trips/providers/trip_provider.dart';
import '../data/chat_models.dart';
import '../providers/chat_provider.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _applyPendingPrompt();
    });
  }

  void _applyPendingPrompt() {
    if (!mounted) return;
    final pending = ref.read(pendingChatPromptProvider);
    if (pending != null && pending.trim().isNotEmpty) {
      _textController.text = pending;
      _textController.selection = TextSelection.fromPosition(
        TextPosition(offset: _textController.text.length),
      );
      ref.read(pendingChatPromptProvider.notifier).state = null;
      _focusNode.requestFocus();
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSend() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _textController.clear();
    _scrollToBottom();
    await ref.read(chatProvider.notifier).sendMessage(text);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final cs = Theme.of(context).colorScheme;

    // Listen to changes to scroll down when messages arrive
    ref.listen<ChatState>(chatProvider, (prev, next) {
      if (prev?.messages.length != next.messages.length) {
        _scrollToBottom();
      }
    });

    // Consume quick-action prompt handoff from Home / Discover when /ai is already mounted in ShellRoute
    ref.listen<String?>(pendingChatPromptProvider, (prev, next) {
      if (next != null && next.trim().isNotEmpty) {
        _applyPendingPrompt();
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: const BoxDecoration(
                color: AppColors.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.auto_awesome, color: AppColors.primary, size: 20),
            ),
            const SizedBox(width: AppSpacing.sm),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Wandy',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                ),
                Text(
                  'AI Travel Copilot',
                  style: AppTypography.bodyS.copyWith(
                    fontSize: 11,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          if (chatState.messages.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Xóa cuộc trò chuyện',
              color: AppColors.textSecondary,
              onPressed: () {
                ref.read(chatProvider.notifier).clearConversation();
              },
            ),
        ],
      ),
      body: SafeArea(
        child: ResponsiveWrapper(
          maxWidth: 720.0,
          child: Column(
            children: [
              // Message List or Empty State
              Expanded(
                child: chatState.messages.isEmpty
                    ? _buildEmptyState()
                    : _buildMessageList(chatState, cs),
              ),

              // Error & Retry Banner
              if (chatState.hasError && chatState.errorMessage != null)
                _buildErrorBanner(chatState, cs),

              // Input Bar
              _buildInputBar(chatState, cs),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 68,
              height: 68,
              decoration: const BoxDecoration(
                color: AppColors.primaryContainer,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.auto_awesome, size: 34, color: AppColors.primary),
            ),
            const SizedBox(height: AppSpacing.md),
            const Text(
              'Xin chào, mình là Wandy!',
              style: AppTypography.h2,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Trợ lý AI chuyên về du lịch Việt Nam. Mình có thể gợi ý điểm đến, lập lịch trình, và giải đáp thông tin được xác thực.',
              style: AppTypography.bodyM.copyWith(height: 1.45),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            const Text(
              'Gợi ý câu hỏi:',
              style: AppTypography.label,
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              alignment: WrapAlignment.center,
              children: [
                _buildSuggestionChip('Gợi ý 3 điểm du lịch Đà Nẵng'),
                _buildSuggestionChip('Thời tiết Hà Giang hôm nay thế nào?'),
                _buildSuggestionChip('Ngân sách du lịch Phú Quốc 3 ngày'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionChip(String text) {
    return ActionChip(
      label: Text(text, style: AppTypography.bodyS.copyWith(color: AppColors.primary)),
      backgroundColor: AppColors.primaryContainer.withValues(alpha: 0.5),
      side: BorderSide(color: AppColors.primary.withValues(alpha: 0.3)),
      shape: const RoundedRectangleBorder(borderRadius: AppRadius.pillRadius),
      onPressed: () {
        _textController.text = text;
        _handleSend();
      },
    );
  }

  Widget _buildMessageList(ChatState chatState, ColorScheme cs) {
    final itemCount = chatState.messages.length + (chatState.isLoading ? 1 : 0);

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.mdSmall,
      ),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        if (index == chatState.messages.length && chatState.isLoading) {
          return _buildLoadingBubble(cs);
        }

        final message = chatState.messages[index];
        return _buildMessageBubble(message, chatState, cs);
      },
    );
  }

  Widget _buildMessageBubble(
    ChatMessage message,
    ChatState chatState,
    ColorScheme cs,
  ) {
    final isUser = message.isUser;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            const CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.primaryContainer,
              child: Icon(Icons.auto_awesome, size: 16, color: AppColors.primary),
            ),
            const SizedBox(width: AppSpacing.sm),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.mdSmall,
              ),
              decoration: BoxDecoration(
                color: isUser ? AppColors.primary : AppColors.surface,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(AppRadius.card),
                  topRight: const Radius.circular(AppRadius.card),
                  bottomLeft: Radius.circular(isUser ? AppRadius.card : 4),
                  bottomRight: Radius.circular(isUser ? 4 : AppRadius.card),
                ),
                border: isUser
                    ? null
                    : Border.all(color: AppColors.border, width: 1),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 4,
                    offset: const Offset(0, 1),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  SelectableText(
                    message.content,
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.45,
                      color: isUser ? AppColors.onPrimary : AppColors.textPrimary,
                    ),
                  ),
                  if (!isUser &&
                      !message.isError &&
                      message.retrievalStatus == RetrievalStatus.ok &&
                      message.sources.isNotEmpty)
                    _buildSourcesSection(message.sources, cs),
                  if (!isUser &&
                      !message.isError &&
                      message.retrievalStatus == RetrievalStatus.empty)
                    _buildUngroundedNotice(),
                  if (!isUser && !message.isError && message.canPlanTrip)
                    _buildPlanForTripAction(message, chatState, cs),
                ],
              ),
            ),
          ),
          if (isUser) const SizedBox(width: AppSpacing.sm),
        ],
      ),
    );
  }

  Widget _buildPlanForTripAction(
    ChatMessage message,
    ChatState chatState,
    ColorScheme cs,
  ) {
    final boundTripId = chatState.selectedTripId;
    final boundTripTitle = chatState.selectedTripTitle;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          const Divider(height: 12, thickness: 0.8, color: AppColors.border),
          if (boundTripId != null && boundTripTitle != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.luggage_outlined,
                    size: 13,
                    color: AppColors.textSecondary,
                  ),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      'Chuyến đang gắn: $boundTripTitle',
                      style: AppTypography.bodyS.copyWith(
                        fontSize: 11,
                        color: AppColors.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 6),
                  InkWell(
                    key: Key('wandy_change_trip_${message.id}'),
                    onTap: () => _openTripPickerAndTransfer(message),
                    child: const Text(
                      'Đổi chuyến',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          SizedBox(
            width: double.infinity,
            child: FilledButton.tonalIcon(
              key: Key('wandy_plan_for_trip_button_${message.id}'),
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.primaryContainer.withValues(alpha: 0.75),
                foregroundColor: AppColors.primary,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                  side: BorderSide(color: AppColors.primary.withValues(alpha: 0.35)),
                ),
              ),
              onPressed: () => _handlePlanForTripTap(message, chatState),
              icon: const Icon(Icons.event_available_rounded, size: 17),
              label: const Text(
                'Lập lịch cho chuyến đi',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _handlePlanForTripTap(
    ChatMessage message,
    ChatState chatState,
  ) async {
    final existingTripId = chatState.selectedTripId;
    if (existingTripId != null && existingTripId.isNotEmpty) {
      _dispatchWandyPlanHandoff(existingTripId, message);
      return;
    }
    await _openTripPickerAndTransfer(message);
  }

  Future<void> _openTripPickerAndTransfer(ChatMessage message) async {
    await ref.read(tripListProvider.notifier).loadTrips();
    if (!mounted) return;

    final chosenTrip = await showModalBottomSheet<TripModel>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetCtx) {
        return Consumer(
          builder: (ctx, sheetRef, _) {
            final tripState = sheetRef.watch(tripListProvider);
            return ConstrainedBox(
              key: const Key('wandy_trip_picker_sheet'),
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(ctx).size.height * 0.65,
              ),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Expanded(
                          child: Text(
                            'Chọn chuyến đi để lập lịch',
                            style: TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close),
                          onPressed: () => Navigator.pop(sheetCtx),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Yêu cầu từ khung chat (số người, thời gian, ngân sách, sở thích) sẽ được chuyển nguyên sang bản xem trước lịch trình.',
                      style: AppTypography.bodyS.copyWith(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    const Divider(height: 20),
                    if (tripState.isLoading)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 28),
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (tripState.trips.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 20),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Text(
                              'Bạn chưa có chuyến đi nào. Hãy tạo chuyến đi mới để lập lịch trình.',
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 12),
                            FilledButton.icon(
                              onPressed: () {
                                Navigator.pop(sheetCtx);
                                context.push('/trips/create');
                              },
                              icon: const Icon(Icons.add),
                              label: const Text('Tạo chuyến đi mới'),
                            ),
                          ],
                        ),
                      )
                    else
                      Flexible(
                        child: ListView.separated(
                          shrinkWrap: true,
                          itemCount: tripState.trips.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (_, idx) {
                            final t = tripState.trips[idx];
                            final destLabel = t.destinationName ?? '';
                            final budgetLabel = t.totalBudget != null
                                ? '${t.totalBudget} ${t.currency}'
                                : 'Chưa đặt ngân sách';
                            return ListTile(
                              key: Key('wandy_trip_option_${t.id}'),
                              contentPadding: const EdgeInsets.symmetric(
                                horizontal: 4,
                                vertical: 2,
                              ),
                              leading: const CircleAvatar(
                                backgroundColor: AppColors.primaryContainer,
                                child: Icon(
                                  Icons.luggage_outlined,
                                  color: AppColors.primary,
                                  size: 18,
                                ),
                              ),
                              title: Text(
                                t.title,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 14,
                                ),
                              ),
                              subtitle: Text(
                                destLabel.isNotEmpty
                                    ? '$destLabel • $budgetLabel'
                                    : budgetLabel,
                                style: const TextStyle(fontSize: 12),
                              ),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () => Navigator.pop(sheetCtx, t),
                            );
                          },
                        ),
                      ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );

    if (chosenTrip == null || !mounted) return;
    ref
        .read(chatProvider.notifier)
        .selectTripForChat(chosenTrip.id, tripTitle: chosenTrip.title);
    _dispatchWandyPlanHandoff(chosenTrip.id, message);
  }

  void _dispatchWandyPlanHandoff(String tripId, ChatMessage message) {
    final promptText = (message.sourceUserPrompt ?? '').trim().isNotEmpty
        ? message.sourceUserPrompt!.trim()
        : message.content.trim();
    final ctx = message.planningContext ??
        WandyPlanningContext.extractFromPrompt(
          promptText,
          assistantReply: message.content,
        );
    ref.read(pendingWandyPlanHandoffProvider.notifier).state =
        PendingWandyPlanHandoff(
      tripId: tripId,
      rawPrompt: promptText,
      initialChatReply: message.content,
      planningContext: ctx,
    );
    context.push('/trips/$tripId');
  }

  Widget _buildUngroundedNotice() {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.info_outline,
            size: 12,
            color: AppColors.textSecondary,
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              'Chưa có nguồn đối chiếu trực tiếp trong kho dữ liệu.',
              style: AppTypography.bodyS.copyWith(
                fontSize: 11,
                fontStyle: FontStyle.italic,
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSourcesSection(List<String> sources, ColorScheme cs) {
    if (sources.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: AppSpacing.sm),
        const Divider(
          height: 1,
          thickness: 0.8,
          color: AppColors.border,
        ),
        const SizedBox(height: AppSpacing.sm),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.auto_stories_outlined,
              size: 13,
              color: AppColors.textSecondary,
            ),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                'Nguồn dữ liệu truy xuất (chưa đối chiếu từng chi tiết trả lời):',
                style: AppTypography.label.copyWith(
                  fontSize: 11,
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: sources.map((url) => _buildSourceChip(url, cs)).toList(),
        ),
      ],
    );
  }

  Widget _buildSourceChip(String url, ColorScheme cs) {
    final label = _formatSourceLabel(url);

    return Tooltip(
      message: url,
      child: Material(
        color: AppColors.primaryContainer.withValues(alpha: 0.4),
        borderRadius: AppRadius.smRadius,
        child: InkWell(
          borderRadius: AppRadius.smRadius,
          onTap: () => _launchSourceUrl(url),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              border: Border.all(
                color: AppColors.primary.withValues(alpha: 0.3),
                width: 0.8,
              ),
              borderRadius: AppRadius.smRadius,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.open_in_new,
                  size: 11,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 4),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 220),
                  child: Text(
                    label,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.primary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _formatSourceLabel(String url) {
    try {
      final uri = Uri.parse(url);
      if (uri.host.contains('openstreetmap.org')) {
        final segments = uri.pathSegments;
        if (segments.length >= 2) {
          return 'OpenStreetMap (${segments[0]}/${segments[1]})';
        }
        return 'OpenStreetMap';
      }
      if (uri.host.contains('wikivoyage.org')) {
        final segments = uri.pathSegments;
        if (segments.isNotEmpty) {
          final title = Uri.decodeComponent(segments.last).replaceAll('_', ' ');
          return 'Wikivoyage: $title';
        }
        return 'Wikivoyage';
      }
      return uri.host.isNotEmpty ? uri.host : url;
    } catch (_) {
      return 'Nguồn dữ liệu truy xuất';
    }
  }

  Future<void> _launchSourceUrl(String url) async {
    final opened = await openExternalUrlString(
      url,
      opener: ref.read(externalUriOpenerProvider),
    );
    if (!opened && mounted) {
      ScaffoldMessenger.of(context)
        ..removeCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(
            content: Text(citationLinkOpenFailedText),
            behavior: SnackBarBehavior.floating,
            margin: EdgeInsets.fromLTRB(16, 0, 16, 80),
          ),
        );
    }
  }

  Widget _buildLoadingBubble(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primaryContainer,
            child: Icon(Icons.auto_awesome, size: 16, color: AppColors.primary),
          ),
          const SizedBox(width: AppSpacing.sm),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.mdSmall,
            ),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(AppRadius.card),
                topRight: Radius.circular(AppRadius.card),
                bottomLeft: Radius.circular(4),
                bottomRight: Radius.circular(AppRadius.card),
              ),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  'Wandy đang suy nghĩ...',
                  style: AppTypography.bodyS.copyWith(
                    fontStyle: FontStyle.italic,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorBanner(ChatState chatState, ColorScheme cs) {
    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: 4,
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.mdSmall,
        vertical: AppSpacing.sm,
      ),
      decoration: const BoxDecoration(
        color: AppColors.errorContainer,
        borderRadius: AppRadius.smRadius,
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, size: 18, color: AppColors.error),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              chatState.errorMessage ?? 'Lỗi không xác định',
              style: AppTypography.bodyS.copyWith(color: AppColors.error),
            ),
          ),
          TextButton(
            onPressed: () => ref.read(chatProvider.notifier).retryLastMessage(),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text(
              'Thử lại',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: AppColors.error,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar(ChatState chatState, ColorScheme cs) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.mdSmall,
        vertical: AppSpacing.sm,
      ),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(color: AppColors.border),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _textController,
              focusNode: _focusNode,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _handleSend(),
              decoration: InputDecoration(
                hintText: 'Hỏi Wandy về du lịch Việt Nam...',
                hintStyle: AppTypography.bodyM.copyWith(color: AppColors.textTertiary),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: 10,
                ),
                border: const OutlineInputBorder(
                  borderRadius: AppRadius.pillRadius,
                  borderSide: BorderSide(color: AppColors.border),
                ),
                enabledBorder: const OutlineInputBorder(
                  borderRadius: AppRadius.pillRadius,
                  borderSide: BorderSide(color: AppColors.border),
                ),
                focusedBorder: const OutlineInputBorder(
                  borderRadius: AppRadius.pillRadius,
                  borderSide: BorderSide(color: AppColors.primary, width: 1.5),
                ),
                filled: true,
                fillColor: AppColors.background,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          IconButton.filled(
            style: IconButton.styleFrom(backgroundColor: AppColors.primary),
            onPressed: chatState.isLoading ? null : _handleSend,
            icon: chatState.isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  )
                : const Icon(Icons.send_rounded, size: 20, color: Colors.white),
          ),
        ],
      ),
    );
  }
}
