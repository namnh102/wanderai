import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/chat_repository.dart';
import '../data/chat_model.dart';

class ChatState {
  final List<ChatMessage> messages;
  final bool isLoading;
  final String? sessionId;

  ChatState({this.messages = const [], this.isLoading = false, this.sessionId});

  ChatState copyWith({List<ChatMessage>? messages, bool? isLoading, String? sessionId}) {
    return ChatState(
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      sessionId: sessionId ?? this.sessionId,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ChatRepository _repo;

  ChatNotifier(this._repo) : super(ChatState());

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    
    final userMsg = ChatMessage(id: DateTime.now().toString(), content: text, isUser: true, timestamp: DateTime.now());
    state = state.copyWith(messages: [...state.messages, userMsg], isLoading: true);

    final response = await _repo.sendMessage(text, state.sessionId);

    final aiMsg = ChatMessage(id: DateTime.now().toString(), content: response.reply, isUser: false, timestamp: DateTime.now());
    state = state.copyWith(messages: [...state.messages, aiMsg], isLoading: false, sessionId: response.sessionId);
  }

  void clearChat() {
    state = ChatState();
  }
}

final chatRepositoryProvider = Provider((ref) => ChatRepository());
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.read(chatRepositoryProvider));
});