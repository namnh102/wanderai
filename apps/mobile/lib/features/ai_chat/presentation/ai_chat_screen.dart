import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/chat_provider.dart';
import 'widgets/chat_bubble.dart';
import 'widgets/typing_indicator.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final _ctrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  void _send() {
    ref.read(chatProvider.notifier).sendMessage(_ctrl.text);
    _ctrl.clear();
    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent, duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatProvider);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Wandy 🤖'),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: () => ref.read(chatProvider.notifier).clearChat())
        ],
      ),
      body: Column(
        children: [
          if (state.messages.isEmpty)
            Expanded(
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text('Xin chào! Mình là Wandy...'),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      children: ['🏖 Gợi ý biển', '⛰ Gợi ý núi', '🍜 Ẩm thực', '💰 Budget']
                          .map((e) => ActionChip(label: Text(e), onPressed: () {
                                _ctrl.text = e;
                                _send();
                              }))
                          .toList(),
                    )
                  ],
                ),
              ),
            )
          else
            Expanded(
              child: ListView.builder(
                controller: _scrollCtrl,
                itemCount: state.messages.length + (state.isLoading ? 1 : 0),
                itemBuilder: (ctx, i) {
                  if (i == state.messages.length) return const TypingIndicator();
                  return ChatBubble(message: state.messages[i]);
                },
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _ctrl,
                    decoration: InputDecoration(
                      hintText: 'Nhắn với Wandy...',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                    ),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                IconButton(icon: const Icon(Icons.send, color: Colors.teal), onPressed: _send),
              ],
            ),
          )
        ],
      ),
    );
  }
}