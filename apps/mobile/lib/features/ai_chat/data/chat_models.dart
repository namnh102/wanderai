/// Strongly typed AI Chat models matching NestJS and FastAPI contracts.

enum MessageRole { user, assistant }

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isError;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isError = false,
  });

  bool get isUser => role == MessageRole.user;
  bool get isAssistant => role == MessageRole.assistant;

  ChatMessage copyWith({
    String? id,
    MessageRole? role,
    String? content,
    DateTime? timestamp,
    bool? isError,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isError: isError ?? this.isError,
    );
  }
}

class ChatRequest {
  final String message;
  final String? sessionId;

  const ChatRequest({
    required this.message,
    this.sessionId,
  });

  Map<String, dynamic> toJson() => {
    'message': message,
    if (sessionId != null) 'session_id': sessionId,
  };
}

class ChatResponse {
  final String reply;
  final String sessionId;
  final List<String> toolsUsed;

  const ChatResponse({
    required this.reply,
    required this.sessionId,
    this.toolsUsed = const [],
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    final toolsList = json['tools_used'] as List<dynamic>? ?? [];
    return ChatResponse(
      reply: json['reply'] as String? ?? '',
      sessionId: json['session_id'] as String? ?? '',
      toolsUsed: toolsList.map((e) => e.toString()).toList(),
    );
  }
}
