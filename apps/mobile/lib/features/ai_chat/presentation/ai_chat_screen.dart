import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/responsive_wrapper.dart';
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
        return _buildMessageBubble(message, cs);
      },
    );
  }

  Widget _buildMessageBubble(ChatMessage message, ColorScheme cs) {
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
                  if (!isUser && message.sources.isNotEmpty)
                    _buildSourcesSection(message.sources, cs),
                ],
              ),
            ),
          ),
          if (isUser) const SizedBox(width: AppSpacing.sm),
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
            Text(
              'Nguồn tham khảo:',
              style: AppTypography.label.copyWith(
                fontSize: 11,
                color: AppColors.textSecondary,
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
      return 'Nguồn tham khảo';
    }
  }

  Future<void> _launchSourceUrl(String url) async {
    try {
      final uri = Uri.parse(url);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    } catch (_) {
      // Graceful fallback
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
