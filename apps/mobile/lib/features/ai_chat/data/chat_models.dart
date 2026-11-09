/// Strongly typed AI Chat models matching NestJS and FastAPI contracts.

enum MessageRole { user, assistant }

/// Tri-state RAG grounding status from FastAPI `/chat`.
enum RetrievalStatus {
  ok,
  empty,
  error;

  static RetrievalStatus fromJsonValue(String? raw) {
    switch (raw?.trim().toLowerCase()) {
      case 'empty':
        return RetrievalStatus.empty;
      case 'error':
        return RetrievalStatus.error;
      case 'ok':
      default:
        return RetrievalStatus.ok;
    }
  }
}

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isError;
  final List<String> sources;
  final RetrievalStatus retrievalStatus;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isError = false,
    this.sources = const [],
    this.retrievalStatus = RetrievalStatus.ok,
  });

  bool get isUser => role == MessageRole.user;
  bool get isAssistant => role == MessageRole.assistant;

  ChatMessage copyWith({
    String? id,
    MessageRole? role,
    String? content,
    DateTime? timestamp,
    bool? isError,
    List<String>? sources,
    RetrievalStatus? retrievalStatus,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isError: isError ?? this.isError,
      sources: sources ?? this.sources,
      retrievalStatus: retrievalStatus ?? this.retrievalStatus,
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
  final List<String> sources;
  final RetrievalStatus retrievalStatus;

  const ChatResponse({
    required this.reply,
    required this.sessionId,
    this.toolsUsed = const [],
    this.sources = const [],
    this.retrievalStatus = RetrievalStatus.ok,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    final toolsList = json['tools_used'] as List<dynamic>? ?? [];
    final sourcesList = json['sources'] as List<dynamic>? ?? [];
    final status = RetrievalStatus.fromJsonValue(
      json['retrieval_status'] as String?,
    );
    final parsedSources = status == RetrievalStatus.ok
        ? sourcesList.map((e) => e.toString()).toList()
        : const <String>[];

    return ChatResponse(
      reply: json['reply'] as String? ?? '',
      sessionId: json['session_id'] as String? ?? '',
      toolsUsed: toolsList.map((e) => e.toString()).toList(),
      sources: parsedSources,
      retrievalStatus: status,
    );
  }
}
