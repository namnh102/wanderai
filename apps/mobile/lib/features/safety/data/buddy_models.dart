class BuddyPeerModel {
  final String id;
  final String displayName;
  final String? avatar;
  final String? bio;
  final String? nationality;
  final List<String> languages;
  final String? travelStyle;
  final List<String> interests;

  const BuddyPeerModel({
    required this.id,
    required this.displayName,
    this.avatar,
    this.bio,
    this.nationality,
    this.languages = const [],
    this.travelStyle,
    this.interests = const [],
  });

  factory BuddyPeerModel.fromJson(Map<String, dynamic> json) {
    return BuddyPeerModel(
      id: json['id'] as String? ?? '',
      displayName: (json['displayName'] as String?)?.trim().isNotEmpty == true
          ? (json['displayName'] as String).trim()
          : 'Du khách GoMate',
      avatar: json['avatar'] as String?,
      bio: json['bio'] as String?,
      nationality: json['nationality'] as String?,
      languages: List<String>.from((json['languages'] as List? ?? const []).map((e) => e.toString())),
      travelStyle: json['travelStyle'] as String?,
      interests: List<String>.from((json['interests'] as List? ?? const []).map((e) => e.toString())),
    );
  }
}

class BuddyCandidateModel {
  final BuddyPeerModel peer;
  final int compatibilityScore;
  final String compatibilityBand;
  final List<String> sharedInterests;
  final List<String> sharedDestinationNames;
  final String explanation;
  final String? matchId;
  final String? matchStatus;
  final String? matchDirection;

  const BuddyCandidateModel({
    required this.peer,
    required this.compatibilityScore,
    required this.compatibilityBand,
    this.sharedInterests = const [],
    this.sharedDestinationNames = const [],
    required this.explanation,
    this.matchId,
    this.matchStatus,
    this.matchDirection,
  });

  factory BuddyCandidateModel.fromJson(Map<String, dynamic> json) {
    return BuddyCandidateModel(
      peer: BuddyPeerModel.fromJson(
        Map<String, dynamic>.from((json['peer'] as Map?) ?? const {}),
      ),
      compatibilityScore: (json['compatibilityScore'] as num?)?.toInt() ?? 0,
      compatibilityBand: json['compatibilityBand'] as String? ?? 'LOW',
      sharedInterests: List<String>.from(
        (json['sharedInterests'] as List? ?? const []).map((e) => e.toString()),
      ),
      sharedDestinationNames: List<String>.from(
        (json['sharedDestinationNames'] as List? ?? const []).map((e) => e.toString()),
      ),
      explanation: json['explanation'] as String? ?? '',
      matchId: json['matchId'] as String?,
      matchStatus: json['matchStatus'] as String?,
      matchDirection: json['matchDirection'] as String?,
    );
  }
}

class BuddyMatchRecord {
  final String id;
  final String status;
  final String direction;
  final double? score;
  final String? explanation;
  final BuddyPeerModel peer;

  const BuddyMatchRecord({
    required this.id,
    required this.status,
    required this.direction,
    this.score,
    this.explanation,
    required this.peer,
  });

  factory BuddyMatchRecord.fromJson(Map<String, dynamic> json) {
    return BuddyMatchRecord(
      id: json['id'] as String? ?? '',
      status: json['status'] as String? ?? 'PENDING',
      direction: json['direction'] as String? ?? 'SENT',
      score: (json['score'] as num?)?.toDouble(),
      explanation: json['explanation'] as String?,
      peer: BuddyPeerModel.fromJson(
        Map<String, dynamic>.from((json['peer'] as Map?) ?? const {}),
      ),
    );
  }
}
