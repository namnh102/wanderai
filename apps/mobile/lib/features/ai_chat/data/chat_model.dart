class ChatMessage {
  final String id;
  final String content;
  final bool isUser;
  final DateTime timestamp;

  ChatMessage({required this.id, required this.content, required this.isUser, required this.timestamp});
}

class ChatResponse {
  final String reply;
  final String sessionId;

  ChatResponse({required this.reply, required this.sessionId});

  factory ChatResponse.fromJson(Map<String, dynamic> json) => ChatResponse(
    reply: json['reply'] ?? '',
    sessionId: json['sessionId'] ?? '',
  );
}