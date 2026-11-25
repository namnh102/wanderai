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
      languages: List<String>.from(
        (json['languages'] as List? ?? const []).map((e) => e.toString()),
      ),
      travelStyle: json['travelStyle'] as String?,
      interests: List<String>.from(
        (json['interests'] as List? ?? const []).map((e) => e.toString()),
      ),
    );
  }
}

class BuddyPlannedDestinationSummary {
  final String destinationId;
  final String destinationName;
  final bool hasOverlappingWindow;

  const BuddyPlannedDestinationSummary({
    required this.destinationId,
    required this.destinationName,
    this.hasOverlappingWindow = false,
  });

  factory BuddyPlannedDestinationSummary.fromJson(Map<String, dynamic> json) {
    return BuddyPlannedDestinationSummary(
      destinationId: json['destinationId'] as String? ?? '',
      destinationName: json['destinationName'] as String? ?? '',
      hasOverlappingWindow: json['hasOverlappingWindow'] as bool? ?? false,
    );
  }
}

class BuddyCandidateModel {
  final BuddyPeerModel peer;
  final int compatibilityScore;
  final String compatibilityBand;
  final List<String> sharedInterests;
  final List<String> sharedDestinationNames;
  final bool hasOverlappingTripWindow;
  final String explanation;
  final String? matchId;
  final String? matchStatus;
  final String? handshakeState;
  final bool isMatched;
  final String? matchDirection;

  const BuddyCandidateModel({
    required this.peer,
    required this.compatibilityScore,
    required this.compatibilityBand,
    this.sharedInterests = const [],
    this.sharedDestinationNames = const [],
    this.hasOverlappingTripWindow = false,
    required this.explanation,
    this.matchId,
    this.matchStatus,
    this.handshakeState,
    this.isMatched = false,
    this.matchDirection,
  });

  factory BuddyCandidateModel.fromJson(Map<String, dynamic> json) {
    final status = json['matchStatus'] as String?;
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
        (json['sharedDestinationNames'] as List? ?? const [])
            .map((e) => e.toString()),
      ),
      hasOverlappingTripWindow:
          json['hasOverlappingTripWindow'] as bool? ?? false,
      explanation: json['explanation'] as String? ?? '',
      matchId: json['matchId'] as String?,
      matchStatus: status,
      handshakeState: json['handshakeState'] as String? ??
          (status == 'ACCEPTED' ? 'MATCHED' : status),
      isMatched: json['isMatched'] as bool? ?? (status == 'ACCEPTED'),
      matchDirection: json['matchDirection'] as String?,
    );
  }
}

class BuddyMaskedProfileModel {
  final BuddyPeerModel peer;
  final int compatibilityScore;
  final String compatibilityBand;
  final List<String> sharedInterests;
  final List<String> sharedDestinationNames;
  final bool hasOverlappingTripWindow;
  final String explanation;
  final List<BuddyPlannedDestinationSummary> plannedDestinations;
  final String? matchId;
  final String? matchStatus;
  final String? handshakeState;
  final bool isMatched;
  final String? matchDirection;
  final String privacyNotice;

  const BuddyMaskedProfileModel({
    required this.peer,
    required this.compatibilityScore,
    required this.compatibilityBand,
    this.sharedInterests = const [],
    this.sharedDestinationNames = const [],
    this.hasOverlappingTripWindow = false,
    required this.explanation,
    this.plannedDestinations = const [],
    this.matchId,
    this.matchStatus,
    this.handshakeState,
    this.isMatched = false,
    this.matchDirection,
    this.privacyNotice =
        'Thông tin liên hệ cá nhân (email, số điện thoại, tọa độ) luôn được ẩn bảo mật.',
  });

  factory BuddyMaskedProfileModel.fromJson(Map<String, dynamic> json) {
    final status = json['matchStatus'] as String?;
    return BuddyMaskedProfileModel(
      peer: BuddyPeerModel.fromJson(
        Map<String, dynamic>.from((json['peer'] as Map?) ?? const {}),
      ),
      compatibilityScore: (json['compatibilityScore'] as num?)?.toInt() ?? 0,
      compatibilityBand: json['compatibilityBand'] as String? ?? 'LOW',
      sharedInterests: List<String>.from(
        (json['sharedInterests'] as List? ?? const []).map((e) => e.toString()),
      ),
      sharedDestinationNames: List<String>.from(
        (json['sharedDestinationNames'] as List? ?? const [])
            .map((e) => e.toString()),
      ),
      hasOverlappingTripWindow:
          json['hasOverlappingTripWindow'] as bool? ?? false,
      explanation: json['explanation'] as String? ?? '',
      plannedDestinations: (json['plannedDestinations'] as List? ?? const [])
          .whereType<Map>()
          .map(
            (m) => BuddyPlannedDestinationSummary.fromJson(
              Map<String, dynamic>.from(m),
            ),
          )
          .toList(),
      matchId: json['matchId'] as String?,
      matchStatus: status,
      handshakeState: json['handshakeState'] as String? ??
          (status == 'ACCEPTED' ? 'MATCHED' : status),
      isMatched: json['isMatched'] as bool? ?? (status == 'ACCEPTED'),
      matchDirection: json['matchDirection'] as String?,
      privacyNotice: json['privacyNotice'] as String? ??
          'Thông tin liên hệ cá nhân (email, số điện thoại, tọa độ) luôn được ẩn bảo mật.',
    );
  }
}

class BuddyCandidatesResponse {
  final bool isDiscoverable;
  final List<BuddyCandidateModel> items;

  const BuddyCandidatesResponse({
    required this.isDiscoverable,
    required this.items,
  });
}

class BuddyMatchRecord {
  final String id;
  final String status;
  final String handshakeState;
  final bool isMatched;
  final String direction;
  final double? score;
  final String? explanation;
  final BuddyPeerModel peer;

  const BuddyMatchRecord({
    required this.id,
    required this.status,
    String? handshakeState,
    bool? isMatched,
    required this.direction,
    this.score,
    this.explanation,
    required this.peer,
  })  : handshakeState =
            handshakeState ?? (status == 'ACCEPTED' ? 'MATCHED' : status),
        isMatched = isMatched ?? (status == 'ACCEPTED');

  factory BuddyMatchRecord.fromJson(Map<String, dynamic> json) {
    final status = json['status'] as String? ?? 'PENDING';
    return BuddyMatchRecord(
      id: json['id'] as String? ?? '',
      status: status,
      handshakeState: json['handshakeState'] as String?,
      isMatched: json['isMatched'] as bool?,
      direction: json['direction'] as String? ?? 'SENT',
      score: (json['score'] as num?)?.toDouble(),
      explanation: json['explanation'] as String?,
      peer: BuddyPeerModel.fromJson(
        Map<String, dynamic>.from((json['peer'] as Map?) ?? const {}),
      ),
    );
  }
}
