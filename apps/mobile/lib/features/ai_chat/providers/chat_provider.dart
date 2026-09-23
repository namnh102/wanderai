import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/chat_repository.dart';

class ChatMessage {
  final String id;
  final String text;
  final bool isUser;
  final DateTime timestamp;

  ChatMessage({
    required this.id,
    required this.text,
    required this.isUser,
    required this.timestamp,
  });
}

class ChatState {
  final List<ChatMessage> messages;
  final bool isLoading;
  final String? sessionId;
  final String? error;

  ChatState({
    this.messages = const [],
    this.isLoading = false,
    this.sessionId,
    this.error,
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isLoading,
    String? sessionId,
    String? error,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      sessionId: sessionId ?? this.sessionId,
      error: error,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ChatRepository _repo;

  ChatNotifier(this._repo) : super(ChatState());

  // Gá»­i tin nháº¯n
  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    
    final userMsg = ChatMessage(
      id: DateTime.now().toString(),
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    );
    
    state = state.copyWith(
      messages: [...state.messages, userMsg],
      isLoading: true,
    );

    final result = await _repo.sendMessage(text, state.sessionId);

    final aiMsg = ChatMessage(
      id: DateTime.now().toString(),
      text: result['reply'] as String? ?? 'Không có phản hồi',
      isUser: false,
      timestamp: DateTime.now(),
    );

    state = state.copyWith(
      messages: [...state.messages, aiMsg],
      isLoading: false,
      sessionId: result['session_id'] as String? ?? state.sessionId,
    );
  }

  // XÃ³a chat
  void clearChat() {
    state = ChatState();
  }
}

final chatRepositoryProvider = Provider((ref) => ChatRepository());
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.read(chatRepositoryProvider));
});