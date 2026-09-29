import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

// ── Message model ────────────────────────────────────────────
class ChatMessage {
  final String role; // 'user' | 'ai' | 'loading'
  final String content;
  final List<Map<String, dynamic>> toolCalls; // reasoning chain
  final List<String> toolsUsed;

  const ChatMessage({
    required this.role,
    required this.content,
    this.toolCalls = const [],
    this.toolsUsed = const [],
  });

  ChatMessage copyWith({
    String? content,
    List<Map<String, dynamic>>? toolCalls,
    List<String>? toolsUsed,
  }) =>
      ChatMessage(
        role: role,
        content: content ?? this.content,
        toolCalls: toolCalls ?? this.toolCalls,
        toolsUsed: toolsUsed ?? this.toolsUsed,
      );
}

// ── Chat State ────────────────────────────────────────────────
class ChatState {
  final List<ChatMessage> messages;
  final bool isLoading;
  final String? sessionId;

  const ChatState({
    this.messages = const [],
    this.isLoading = false,
    this.sessionId,
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isLoading,
    String? sessionId,
  }) =>
      ChatState(
        messages: messages ?? this.messages,
        isLoading: isLoading ?? this.isLoading,
        sessionId: sessionId ?? this.sessionId,
      );
}

// ── Provider ──────────────────────────────────────────────────
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>(
  (ref) => ChatNotifier(),
);

class ChatNotifier extends StateNotifier<ChatState> {
  ChatNotifier() : super(const ChatState());

  // Them user message
  void addUserMessage(String text) {
    state = state.copyWith(
      messages: [
        ...state.messages,
        ChatMessage(role: 'user', content: text),
      ],
    );
  }

  // Gui tin nhan + nhan tra loi AI (co tools)
  Future<void> sendMessage(String text) async {
    // Add user msg + loading state
    state = state.copyWith(
      messages: [
        ...state.messages,
        ChatMessage(role: 'user', content: text),
        const ChatMessage(role: 'loading', content: ''),
      ],
      isLoading: true,
    );

    try {
      // Goi FastAPI chat endpoint
      final response = await apiClient.post(
        '/ai/chat',
        data: {
          'message': text,
          'session_id': state.sessionId,
        },
      );

      final data = response.data as Map<String, dynamic>;

      final reply = data['reply'] as String? ??
          data['response'] as String? ??
          'Khong co phan hoi';
      final newSessionId = data['session_id'] as String? ?? state.sessionId;

      // Parse tool calls de hien thi reasoning chain
      final rawToolCalls = data['tool_calls'] as List? ?? [];
      final toolCalls = rawToolCalls
          .map((t) => Map<String, dynamic>.from(t as Map))
          .toList();

      final toolsUsed = (data['tools_used'] as List? ?? [])
          .map((t) => t.toString())
          .toList();

      // Xoa loading message, them AI reply
      final msgs = state.messages.where((m) => m.role != 'loading').toList();
      state = state.copyWith(
        messages: [
          ...msgs,
          ChatMessage(
            role: 'ai',
            content: reply,
            toolCalls: toolCalls,
            toolsUsed: toolsUsed,
          ),
        ],
        isLoading: false,
        sessionId: newSessionId,
      );
    } catch (e) {
      final msgs = state.messages.where((m) => m.role != 'loading').toList();
      state = state.copyWith(
        messages: [
          ...msgs,
          const ChatMessage(
            role: 'ai',
            content: 'Loi ket noi. Vui long thu lai.',
          ),
        ],
        isLoading: false,
      );
    }
  }

  // Tao ke hoach chuyen di (goi /ai/plan)
  Future<Map<String, dynamic>?> sendPlanMessage(String text) async {
    final lower = text.toLowerCase();

    // Parse destination
    String dest = 'Viet Nam';
    final destinations = {
      'ha giang': 'Ha Giang',
      'hoi an': 'Hoi An',
      'da nang': 'Da Nang',
      'da lat': 'Da Lat',
      'nha trang': 'Nha Trang',
      'phu quoc': 'Phu Quoc',
      'sapa': 'Sapa',
      'ha long': 'Ha Long',
      'hue': 'Hue',
      'can tho': 'Can Tho',
    };
    for (final entry in destinations.entries) {
      if (lower.contains(entry.key)) {
        dest = entry.value;
        break;
      }
    }

    // Parse so ngay
    int days = 3;
    final dayMatch = RegExp(r'(\d+)\s*(ngay|day)').firstMatch(lower);
    if (dayMatch != null) days = int.tryParse(dayMatch.group(1) ?? '3') ?? 3;

    // Parse ngan sach
    double budget = 3000000;
    final budgetMatch =
        RegExp(r'(\d+)\s*(trieu|million|tr)').firstMatch(lower);
    if (budgetMatch != null) {
      budget =
          (double.tryParse(budgetMatch.group(1) ?? '3') ?? 3) * 1000000;
    }

    state = state.copyWith(isLoading: true);

    try {
      final response = await apiClient.post('/ai/plan', data: {
        'destination': dest,
        'days': days,
        'budget': budget,
        'travelers': 2,
        'preferences': [],
      });

      state = state.copyWith(isLoading: false);

      if (response.data['success'] == true) {
        final plan = response.data['data'] as Map<String, dynamic>;
        addUserMessage(text);
        state = state.copyWith(
          messages: [
            ...state.messages,
            ChatMessage(
              role: 'ai',
              content:
                  'Da lap xong ke hoach ${days} ngay tai $dest! Xem chi tiet ngay ben duoi.',
            ),
          ],
        );
        return plan;
      }
      return null;
    } catch (_) {
      state = state.copyWith(isLoading: false);
      return null;
    }
  }

  void clearChat() {
    state = const ChatState();
  }
}