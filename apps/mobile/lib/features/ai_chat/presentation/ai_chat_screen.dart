import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
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
              decoration: BoxDecoration(
                color: cs.primary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.auto_awesome, color: cs.primary, size: 20),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Wandy',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                ),
                Text(
                  'AI Travel Copilot',
                  style: TextStyle(
                    fontSize: 11,
                    color: cs.onSurfaceVariant,
                    fontWeight: FontWeight.normal,
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
              tooltip: 'Xoa cuoc tro chuyen',
              onPressed: () {
                ref.read(chatProvider.notifier).clearConversation();
              },
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Message List or Empty State
            Expanded(
              child: chatState.messages.isEmpty
                  ? _buildEmptyState(cs)
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
    );
  }

  Widget _buildEmptyState(ColorScheme cs) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: cs.primary.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.auto_awesome, size: 36, color: cs.primary),
            ),
            const SizedBox(height: 16),
            const Text(
              'Xin chao, minh la Wandy!',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Tro ly AI chuyen ve du lich Viet Nam. Minh co the giup ban tim diem den, du doan thoi tiet, va tinh toan chi phi chuyen di.',
              style: TextStyle(fontSize: 14, color: cs.onSurfaceVariant, height: 1.4),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            const Text(
              'Goi y cau hoi:',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                _buildSuggestionChip('Goi y 3 diem du lich Da Nang'),
                _buildSuggestionChip('Thoi tiet Ha Giang hom nay the nao?'),
                _buildSuggestionChip('Ngan sach du lich Phu Quoc 3 ngay'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionChip(String text) {
    return ActionChip(
      label: Text(text, style: const TextStyle(fontSize: 12)),
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
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
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
            CircleAvatar(
              radius: 16,
              backgroundColor: cs.primary.withValues(alpha: 0.15),
              child: Icon(Icons.auto_awesome, size: 16, color: cs.primary),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isUser ? cs.primary : cs.surfaceContainerLow,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  SelectableText(
                    message.content,
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.4,
                      color: isUser ? cs.onPrimary : cs.onSurface,
                    ),
                  ),
                  if (!isUser && message.sources.isNotEmpty)
                    _buildSourcesSection(message.sources, cs),
                ],
              ),
            ),
          ),
          if (isUser) const SizedBox(width: 8),
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
        const SizedBox(height: 10),
        Divider(
          height: 1,
          thickness: 0.8,
          color: cs.outlineVariant.withValues(alpha: 0.4),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.auto_stories_outlined,
              size: 13,
              color: cs.onSurfaceVariant,
            ),
            const SizedBox(width: 4),
            Text(
              'Nguon tham khao:',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: cs.onSurfaceVariant,
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
        color: cs.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: () => _launchSourceUrl(url),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              border: Border.all(
                color: cs.outlineVariant.withValues(alpha: 0.5),
                width: 0.8,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.open_in_new,
                  size: 11,
                  color: cs.primary,
                ),
                const SizedBox(width: 4),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 220),
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      color: cs.primary,
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
      return 'Nguon tham khao';
    }
  }

  Future<void> _launchSourceUrl(String url) async {
    try {
      final uri = Uri.parse(url);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    } catch (_) {
      // Graceful fallback: do not crash on invalid URL or unsupported environment
    }
  }

  Widget _buildLoadingBubble(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: cs.primary.withValues(alpha: 0.15),
            child: Icon(Icons.auto_awesome, size: 16, color: cs.primary),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: cs.surfaceContainerLow,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
                bottomLeft: Radius.circular(4),
                bottomRight: Radius.circular(16),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: cs.primary,
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  'Wandy dang suy nghi...',
                  style: TextStyle(
                    fontSize: 13,
                    color: cs.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
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
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: cs.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, size: 18, color: cs.onErrorContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              chatState.errorMessage ?? 'Loi khong xac dinh',
              style: TextStyle(fontSize: 12, color: cs.onErrorContainer),
            ),
          ),
          TextButton(
            onPressed: () => ref.read(chatProvider.notifier).retryLastMessage(),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(
              'Thu lai',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: cs.onErrorContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar(ChatState chatState, ColorScheme cs) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: Border(
          top: BorderSide(color: cs.outlineVariant.withValues(alpha: 0.5)),
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
                hintText: 'Hoi Wandy ve du lich Viet Nam...',
                hintStyle: TextStyle(fontSize: 14, color: cs.outline),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 10,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: cs.outlineVariant),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: cs.outlineVariant),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: cs.primary, width: 1.5),
                ),
                filled: true,
                fillColor: cs.surfaceContainerLow,
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            onPressed: chatState.isLoading ? null : _handleSend,
            icon: chatState.isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.send_rounded, size: 20),
          ),
        ],
      ),
    );
  }
}
