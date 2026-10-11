import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/chat_models.dart';
import '../data/chat_repository.dart';
import '../../../core/network/api_client.dart';
import '../../auth/providers/auth_provider.dart';

enum ChatStatus { initial, loading, success, error }

class ChatState {
  final List<ChatMessage> messages;
  final ChatStatus status;
  final String? errorMessage;
  final String? sessionId;
  final String? lastFailedMessage;

  const ChatState({
    this.messages = const [],
    this.status = ChatStatus.initial,
    this.errorMessage,
    this.sessionId,
    this.lastFailedMessage,
  });

  bool get isLoading => status == ChatStatus.loading;
  bool get hasError => status == ChatStatus.error;

  ChatState copyWith({
    List<ChatMessage>? messages,
    ChatStatus? status,
    String? errorMessage,
    String? sessionId,
    String? lastFailedMessage,
    bool clearError = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      status: status ?? this.status,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      sessionId: sessionId ?? this.sessionId,
      lastFailedMessage: clearError ? null : (lastFailedMessage ?? this.lastFailedMessage),
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ChatRepository _repository;
  final Ref _ref;

  ChatNotifier(this._repository, this._ref) : super(const ChatState());

  /// Send message to Wandy with immediate UI update, optimistic user bubble,
  /// session tracking, and graceful error handling.
  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;

    final userMessage = ChatMessage(
      id: 'user_${DateTime.now().millisecondsSinceEpoch}',
      role: MessageRole.user,
      content: trimmed,
      timestamp: DateTime.now(),
    );

    // Optimistically show user message, switch to loading
    state = state.copyWith(
      messages: [...state.messages, userMessage],
      status: ChatStatus.loading,
      clearError: true,
    );

    try {
      final request = ChatRequest(
        message: trimmed,
        sessionId: state.sessionId,
      );

      final response = await _repository.sendMessage(request);

      final assistantMessage = ChatMessage(
        id: 'assistant_${DateTime.now().millisecondsSinceEpoch}',
        role: MessageRole.assistant,
        content: response.reply,
        timestamp: DateTime.now(),
        sources: response.sources,
      );

      state = state.copyWith(
        messages: [...state.messages, assistantMessage],
        status: ChatStatus.success,
        sessionId: response.sessionId.isNotEmpty ? response.sessionId : state.sessionId,
        clearError: true,
      );
    } on DioException catch (e) {
      final errorMsg = _mapError(e);

      // Handle 401 Unauthorized -> log out and redirect to login
      if (e.response?.statusCode == 401) {
        await _ref.read(authProvider.notifier).logout();
        state = state.copyWith(
          status: ChatStatus.error,
          errorMessage: 'Phien dang nhap het han. Vui long dang nhap lai.',
          lastFailedMessage: trimmed,
        );
        return;
      }

      state = state.copyWith(
        status: ChatStatus.error,
        errorMessage: errorMsg,
        lastFailedMessage: trimmed,
      );
    } catch (_) {
      state = state.copyWith(
        status: ChatStatus.error,
        errorMessage: 'Co loi xay ra khi tro chuyen voi Wandy. Vui long thu lai.',
        lastFailedMessage: trimmed,
      );
    }
  }

  /// Retry the last failed message.
  Future<void> retryLastMessage() async {
    final failedMsg = state.lastFailedMessage;
    if (failedMsg != null && failedMsg.isNotEmpty) {
      await sendMessage(failedMsg);
    }
  }

  /// Clear in-memory conversation for current session.
  void clearConversation() {
    state = const ChatState();
  }

  /// Map API errors to user-friendly messages without exposing system internals.
  String _mapError(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return 'AI phan hoi qua lau. Vui long thu lai.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Khong the ket noi may chu. Vui long kiem tra mang.';
    }
    final status = e.response?.statusCode;
    if (status == 401) {
      return 'Phien dang nhap het han. Vui long dang nhap lai.';
    }
    if (status == 400) {
      return 'Tin nhan khong hop le.';
    }
    if (status == 503 || status == 502) {
      return 'Dich vu AI dang ban hoac qua tai. Vui long thu lai sau.';
    }
    return 'Co loi xay ra khi tro chuyen voi Wandy. Vui long thu lai.';
  }
}

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return ChatRepository(dio);
});

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final repo = ref.read(chatRepositoryProvider);
  return ChatNotifier(repo, ref);
});
