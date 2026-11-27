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

class WandyPlanningContext {
  final String rawPrompt;
  final int? partySize;
  final String? partyDescription;
  final String? timeWindowStart;
  final String? timeWindowEnd;
  final int? totalBudget;
  final List<String> interests;

  const WandyPlanningContext({
    required this.rawPrompt,
    this.partySize,
    this.partyDescription,
    this.timeWindowStart,
    this.timeWindowEnd,
    this.totalBudget,
    this.interests = const [],
  });

  factory WandyPlanningContext.fromJson(
    Map<String, dynamic> json, {
    String fallbackPrompt = '',
  }) {
    final rawInterests = json['interests'] as List<dynamic>? ?? const [];
    return WandyPlanningContext(
      rawPrompt: (json['raw_prompt'] as String?)?.trim().isNotEmpty == true
          ? (json['raw_prompt'] as String).trim()
          : fallbackPrompt,
      partySize: (json['party_size'] as num?)?.toInt() ??
          (json['partySize'] as num?)?.toInt(),
      partyDescription: (json['party_description'] as String?) ??
          (json['partyDescription'] as String?),
      timeWindowStart: (json['time_window_start'] as String?) ??
          (json['timeWindowStart'] as String?),
      timeWindowEnd: (json['time_window_end'] as String?) ??
          (json['timeWindowEnd'] as String?),
      totalBudget: (json['total_budget'] as num?)?.toInt() ??
          (json['totalBudget'] as num?)?.toInt(),
      interests: rawInterests.map((e) => e.toString()).toList(),
    );
  }

  static WandyPlanningContext? extractFromPrompt(
    String rawPrompt, {
    String assistantReply = '',
  }) {
    final trimmed = rawPrompt.trim();
    if (trimmed.isEmpty) return null;
    final lower = trimmed.toLowerCase();
    final planIntent = RegExp(
      r'(lập\s+(?:giúp\s+(?:tôi|mình)\s+)?(?:một\s+)?lịch|lịch\s*trình|lên\s+lịch|kế\s*hoạch|đi\s+.+\s+từ\s+\d{1,2}\s*(?:h|:|giờ))',
      caseSensitive: false,
    );
    final replyHasSchedule = assistantReply.isNotEmpty &&
        RegExp(r'lịch\s*trình', caseSensitive: false)
            .hasMatch(assistantReply) &&
        RegExp(r'\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\b')
            .hasMatch(assistantReply);

    if (!planIntent.hasMatch(lower) && !replyHasSchedule) {
      return null;
    }

    int? partySize;
    String? partyDesc;
    final mNumParty = RegExp(
      r'\b(\d{1,2})\s*(người\s*lớn|người|khách|bạn)\b',
      caseSensitive: false,
    ).firstMatch(lower);
    if (mNumParty != null) {
      partySize = int.tryParse(mNumParty.group(1)!);
      if (partySize != null) {
        partyDesc = '$partySize ${mNumParty.group(2)!.trim()}';
      }
    } else {
      const wordNums = <String, int>{
        'một': 1,
        'hai': 2,
        'ba': 3,
        'bốn': 4,
        'năm': 5,
        'sáu': 6,
        'bảy': 7,
        'tám': 8,
        'chín': 9,
        'mười': 10,
      };
      for (final entry in wordNums.entries) {
        final mWord = RegExp(
          '\\b${entry.key}\\s+(người\\s*lớn|người|khách)\\b',
          caseSensitive: false,
        ).firstMatch(lower);
        if (mWord != null) {
          partySize = entry.value;
          partyDesc = '${entry.value} ${mWord.group(1)!.trim()}';
          break;
        }
      }
    }

    String? timeStart;
    String? timeEnd;
    final mTime = RegExp(
      r'từ\s*(\d{1,2})(?:[:hgiờ\s]*(\d{2}))?\s*(?:h|giờ)?\s*(?:đến|tới|-)\s*(\d{1,2})(?:[:hgiờ\s]*(\d{2}))?\s*(?:h|giờ)?',
      caseSensitive: false,
    ).firstMatch(lower);
    if (mTime != null) {
      final sh = int.tryParse(mTime.group(1)!) ?? -1;
      final sm = int.tryParse(mTime.group(2) ?? '0') ?? 0;
      final eh = int.tryParse(mTime.group(3)!) ?? -1;
      final em = int.tryParse(mTime.group(4) ?? '0') ?? 0;
      if (sh >= 0 && sh <= 23 && eh >= 0 && eh <= 23) {
        timeStart =
            '${sh.toString().padLeft(2, '0')}:${sm.toString().padLeft(2, '0')}';
        timeEnd =
            '${eh.toString().padLeft(2, '0')}:${em.toString().padLeft(2, '0')}';
      }
    }

    int? budget;
    final mTrieu =
        RegExp(r'(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b').firstMatch(lower);
    final mVnd = RegExp(
      r'(\d{1,3}(?:[.,]\d{3})+|\d{5,9})\s*(?:đồng|vnd|vnđ|đ)\b',
    ).firstMatch(lower);
    final mK = RegExp(r'\b(\d{2,5})\s*k\b').firstMatch(lower);
    if (mTrieu != null) {
      final v = double.tryParse(mTrieu.group(1)!.replaceAll(',', '.'));
      if (v != null) budget = (v * 1000000).round();
    } else if (mVnd != null) {
      final digits = mVnd.group(1)!.replaceAll(RegExp(r'[^\d]'), '');
      budget = int.tryParse(digits);
    } else if (mK != null) {
      final k = int.tryParse(mK.group(1)!);
      if (k != null) budget = k * 1000;
    }

    final interests = <String>[];
    const interestKeywords = <String, List<String>>{
      'museum': ['bảo tàng', 'museum'],
      'culture': ['văn hóa', 'lịch sử', 'di tích', 'chùa', 'đền'],
      'beach': ['biển', 'bãi tắm', 'đảo'],
      'food': ['ẩm thực', 'ăn uống', 'quán ăn', 'đặc sản'],
      'nature': ['thiên nhiên', 'núi', 'hang động', 'vịnh'],
      'photography': ['chụp ảnh', 'check-in', 'sống ảo'],
      'shopping': ['chợ', 'mua sắm'],
    };
    for (final entry in interestKeywords.entries) {
      if (entry.value.any(lower.contains)) {
        interests.add(entry.key);
      }
    }

    return WandyPlanningContext(
      rawPrompt: trimmed,
      partySize: partySize,
      partyDescription: partyDesc,
      timeWindowStart: timeStart,
      timeWindowEnd: timeEnd,
      totalBudget: budget,
      interests: interests,
    );
  }
}

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isError;
  /// Candidate source URLs retrieved from the RAG corpus for the query (not claim-level verified answer citations).
  final List<String> sources;
  final RetrievalStatus retrievalStatus;
  final bool canPlanTrip;
  final String? sourceUserPrompt;
  final WandyPlanningContext? planningContext;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isError = false,
    this.sources = const [],
    this.retrievalStatus = RetrievalStatus.ok,
    this.canPlanTrip = false,
    this.sourceUserPrompt,
    this.planningContext,
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
    bool? canPlanTrip,
    String? sourceUserPrompt,
    WandyPlanningContext? planningContext,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isError: isError ?? this.isError,
      sources: sources ?? this.sources,
      retrievalStatus: retrievalStatus ?? this.retrievalStatus,
      canPlanTrip: canPlanTrip ?? this.canPlanTrip,
      sourceUserPrompt: sourceUserPrompt ?? this.sourceUserPrompt,
      planningContext: planningContext ?? this.planningContext,
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
  final bool canPlanTrip;
  final WandyPlanningContext? planningContext;

  const ChatResponse({
    required this.reply,
    required this.sessionId,
    this.toolsUsed = const [],
    this.sources = const [],
    this.retrievalStatus = RetrievalStatus.ok,
    this.canPlanTrip = false,
    this.planningContext,
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
    final rawPlanCtx = json['planning_context'];

    return ChatResponse(
      reply: json['reply'] as String? ?? '',
      sessionId: json['session_id'] as String? ?? '',
      toolsUsed: toolsList.map((e) => e.toString()).toList(),
      sources: parsedSources,
      retrievalStatus: status,
      canPlanTrip: json['can_plan_trip'] as bool? ?? false,
      planningContext: rawPlanCtx is Map<String, dynamic>
          ? WandyPlanningContext.fromJson(rawPlanCtx)
          : null,
    );
  }
}
