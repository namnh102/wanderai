import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/chat_models.dart';
import '../data/chat_repository.dart';
import '../../../core/network/api_client.dart';
import '../../auth/providers/auth_provider.dart';

enum ChatStatus { initial, loading, success, error }

class PendingWandyPlanHandoff {
  final String tripId;
  final String rawPrompt;
  final String initialChatReply;
  final WandyPlanningContext? planningContext;

  const PendingWandyPlanHandoff({
    required this.tripId,
    required this.rawPrompt,
    required this.initialChatReply,
    this.planningContext,
  });
}

class ChatState {
  final List<ChatMessage> messages;
  final ChatStatus status;
  final String? errorMessage;
  final String? sessionId;
  final String? lastFailedMessage;
  final String? selectedTripId;
  final String? selectedTripTitle;

  const ChatState({
    this.messages = const [],
    this.status = ChatStatus.initial,
    this.errorMessage,
    this.sessionId,
    this.lastFailedMessage,
    this.selectedTripId,
    this.selectedTripTitle,
  });

  bool get isLoading => status == ChatStatus.loading;
  bool get hasError => status == ChatStatus.error;

  ChatState copyWith({
    List<ChatMessage>? messages,
    ChatStatus? status,
    String? errorMessage,
    String? sessionId,
    String? lastFailedMessage,
    String? selectedTripId,
    String? selectedTripTitle,
    bool clearError = false,
    bool clearSessionId = false,
    bool clearSelectedTrip = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      status: status ?? this.status,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      sessionId: clearSessionId ? null : (sessionId ?? this.sessionId),
      lastFailedMessage:
          clearError ? null : (lastFailedMessage ?? this.lastFailedMessage),
      selectedTripId:
          clearSelectedTrip ? null : (selectedTripId ?? this.selectedTripId),
      selectedTripTitle: clearSelectedTrip
          ? null
          : (selectedTripTitle ?? this.selectedTripTitle),
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ChatRepository _repository;
  final Ref _ref;
  int _sessionEpoch = 0;

  ChatNotifier(this._repository, this._ref) : super(const ChatState());

  /// Send message to Wandy with immediate UI update, optimistic user bubble,
  /// session tracking, epoch-based stale response protection, and fail-closed error handling.
  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;

    final int requestEpoch = _sessionEpoch;

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

      // Discard late in-flight response if notifier was disposed, session was cleared, or user changed
      if (!mounted || requestEpoch != _sessionEpoch) {
        return;
      }

      final safeSources = response.retrievalStatus == RetrievalStatus.ok
          ? response.sources
          : const <String>[];

      final resolvedPlanCtx = response.planningContext ??
          WandyPlanningContext.extractFromPrompt(
            trimmed,
            assistantReply: response.reply,
          );
      final canPlan = response.canPlanTrip || resolvedPlanCtx != null;

      final assistantMessage = ChatMessage(
        id: 'assistant_${DateTime.now().millisecondsSinceEpoch}',
        role: MessageRole.assistant,
        content: response.reply,
        timestamp: DateTime.now(),
        sources: safeSources,
        retrievalStatus: response.retrievalStatus,
        canPlanTrip: canPlan,
        sourceUserPrompt: trimmed,
        planningContext: resolvedPlanCtx,
      );

      state = state.copyWith(
        messages: [...state.messages, assistantMessage],
        status: ChatStatus.success,
        sessionId: response.sessionId.isNotEmpty
            ? response.sessionId
            : state.sessionId,
        clearError: true,
      );
    } on DioException catch (e) {
      if (!mounted || requestEpoch != _sessionEpoch) {
        return;
      }

      final status = e.response?.statusCode;
      final errorMsg = _mapError(e);

      // Handle 401 Unauthorized -> log out, clear sessionId, and surface auth expiry
      if (status == 401) {
        _sessionEpoch++;
        await _ref.read(authProvider.notifier).logout();
        if (!mounted) {
          return;
        }
        state = state.copyWith(
          status: ChatStatus.error,
          errorMessage: 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.',
          lastFailedMessage: trimmed,
          clearSessionId: true,
        );
        return;
      }

      // Handle 403 Forbidden (session ownership mismatch) -> clear sessionId so retry starts fresh
      if (status == 403) {
        state = state.copyWith(
          status: ChatStatus.error,
          errorMessage: errorMsg,
          lastFailedMessage: trimmed,
          clearSessionId: true,
        );
        return;
      }

      state = state.copyWith(
        status: ChatStatus.error,
        errorMessage: errorMsg,
        lastFailedMessage: trimmed,
      );
    } catch (_) {
      if (!mounted || requestEpoch != _sessionEpoch) {
        return;
      }

      state = state.copyWith(
        status: ChatStatus.error,
        errorMessage:
            'Có lỗi xảy ra khi trò chuyện với Wandy. Vui lòng thử lại.',
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

  void selectTripForChat(String? tripId, {String? tripTitle}) {
    if (tripId == null || tripId.trim().isEmpty) {
      state = state.copyWith(clearSelectedTrip: true);
      return;
    }
    state = state.copyWith(
      selectedTripId: tripId.trim(),
      selectedTripTitle: tripTitle?.trim(),
    );
  }

  /// Clear in-memory conversation and best-effort clear server session.
  void clearConversation({bool syncRemote = true}) {
    final previousSessionId = state.sessionId;
    _sessionEpoch++;
    state = const ChatState();
    if (syncRemote &&
        previousSessionId != null &&
        previousSessionId.isNotEmpty) {
      _repository.clearSession(previousSessionId).catchError((_) {});
    }
  }

  /// Immediately invalidate any in-flight responses and wipe chat state on logout/user switch.
  void resetForAuthTransition() {
    _sessionEpoch++;
    if (mounted) {
      state = const ChatState();
    }
  }

  @override
  void dispose() {
    _sessionEpoch++;
    super.dispose();
  }

  /// Map API errors to user-friendly messages without exposing system internals.
  String _mapError(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return 'AI phản hồi quá lâu. Vui lòng thử lại.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Không thể kết nối máy chủ. Vui lòng kiểm tra mạng.';
    }
    final status = e.response?.statusCode;
    if (status == 401) {
      return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.';
    }
    if (status == 403) {
      return 'Phiên trò chuyện không hợp lệ hoặc đã hết quyền truy cập. Vui lòng thử lại.';
    }
    if (status == 400) {
      return 'Tin nhắn không hợp lệ.';
    }
    if (status == 429) {
      return 'Hệ thống AI đang quá tải yêu cầu (429). Vui lòng đợi một lát rồi thử lại.';
    }
    if (status == 504) {
      return 'AI phản hồi quá lâu. Vui lòng thử lại.';
    }
    if (status == 503 || status == 502) {
      return 'Dịch vụ AI đang bận hoặc quá tải. Vui lòng thử lại sau.';
    }
    return 'Có lỗi xảy ra khi trò chuyện với Wandy. Vui lòng thử lại.';
  }
}

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return ChatRepository(dio);
});

final pendingChatPromptProvider = StateProvider<String?>((ref) => null);

final pendingWandyPlanHandoffProvider =
    StateProvider<PendingWandyPlanHandoff?>((ref) => null);

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final repo = ref.read(chatRepositoryProvider);
  return ChatNotifier(repo, ref);
});
