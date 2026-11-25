const int kMaxPersonalSafetyContacts = 3;

enum MetadataEvidenceState {
  verified,
  unknown;

  static MetadataEvidenceState fromString(String? value) {
    if (value?.toUpperCase() == 'VERIFIED') {
      return MetadataEvidenceState.verified;
    }
    return MetadataEvidenceState.unknown;
  }
}

enum ChargeStatus {
  verifiedFree,
  verifiedCharged,
  unknown;

  static ChargeStatus fromString(String? value) {
    switch (value?.toUpperCase()) {
      case 'VERIFIED_FREE':
        return ChargeStatus.verifiedFree;
      case 'VERIFIED_CHARGED':
        return ChargeStatus.verifiedCharged;
      default:
        return ChargeStatus.unknown;
    }
  }
}

enum EmergencyCategory {
  emergencyNational,
  protectionSocial,
  touristSupport;

  static EmergencyCategory fromString(String? value) {
    switch (value) {
      case 'emergency_national':
        return EmergencyCategory.emergencyNational;
      case 'protection_social':
        return EmergencyCategory.protectionSocial;
      case 'tourist_support':
      default:
        return EmergencyCategory.touristSupport;
    }
  }

  String get apiValue {
    switch (this) {
      case EmergencyCategory.emergencyNational:
        return 'emergency_national';
      case EmergencyCategory.protectionSocial:
        return 'protection_social';
      case EmergencyCategory.touristSupport:
        return 'tourist_support';
    }
  }
}

enum SafetyNetworkSendStatus {
  sandboxSimulated,
  sentOnline,
  notSentOffline,
  localOnly,
  dialerOpened,
  dialerFailed;

  static SafetyNetworkSendStatus fromString(String? value) {
    return SafetyNetworkSendStatus.values.firstWhere(
      (e) => e.name == value,
      orElse: () => SafetyNetworkSendStatus.localOnly,
    );
  }
}

class EmergencyDirectoryEntry {
  final String id;
  final String countryCode;
  final String? regionCode;
  final EmergencyCategory category;
  final String displayName;
  final String phoneNumber;
  final String displayNumber;
  final String governingAuthority;
  final String? operatingHours;
  final MetadataEvidenceState hoursStatus;
  final ChargeStatus chargeStatus;
  final String? description;
  final String? coordinationNote;
  final String? physicalAddress;
  final String? secondaryAddress;
  final String? legacyHotline;
  final MetadataEvidenceState legacyStatus;
  final String? secondaryPhone;
  final ChargeStatus secondaryChargeStatus;
  final String? dialNote;
  final String? neutralBadge;
  final String sourceName;
  final String sourceUrl;
  final String verifiedAt;

  const EmergencyDirectoryEntry({
    required this.id,
    required this.countryCode,
    this.regionCode,
    required this.category,
    required this.displayName,
    required this.phoneNumber,
    required this.displayNumber,
    required this.governingAuthority,
    this.operatingHours,
    required this.hoursStatus,
    required this.chargeStatus,
    this.description,
    this.coordinationNote,
    this.physicalAddress,
    this.secondaryAddress,
    this.legacyHotline,
    this.legacyStatus = MetadataEvidenceState.unknown,
    this.secondaryPhone,
    this.secondaryChargeStatus = ChargeStatus.unknown,
    this.dialNote,
    this.neutralBadge,
    required this.sourceName,
    required this.sourceUrl,
    required this.verifiedAt,
  });

  bool get isVerified24x7 =>
      hoursStatus == MetadataEvidenceState.verified &&
      (operatingHours?.trim().isNotEmpty ?? false);

  bool get isVerifiedFree => chargeStatus == ChargeStatus.verifiedFree;

  bool get hasUnknownMetadata =>
      hoursStatus == MetadataEvidenceState.unknown ||
      chargeStatus == ChargeStatus.unknown;

  factory EmergencyDirectoryEntry.fromJson(Map<String, dynamic> json) {
    final phone = (json['phoneNumber'] as String? ?? '').trim();
    final displayNum = (json['displayNumber'] as String?)?.trim();
    return EmergencyDirectoryEntry(
      id: (json['id'] as String? ?? phone).trim(),
      countryCode: (json['countryCode'] as String? ?? 'VN').trim(),
      regionCode: (json['regionCode'] as String?)?.trim(),
      category: EmergencyCategory.fromString(json['category'] as String?),
      displayName: (json['displayName'] as String? ?? '').trim(),
      phoneNumber: phone,
      displayNumber: (displayNum != null && displayNum.isNotEmpty)
          ? displayNum
          : phone,
      governingAuthority:
          (json['governingAuthority'] as String? ?? '').trim(),
      operatingHours: (json['operatingHours'] as String?)?.trim(),
      hoursStatus:
          MetadataEvidenceState.fromString(json['hoursStatus'] as String?),
      chargeStatus: ChargeStatus.fromString(json['chargeStatus'] as String?),
      description: (json['description'] as String?)?.trim(),
      coordinationNote: (json['coordinationNote'] as String?)?.trim(),
      physicalAddress: (json['physicalAddress'] as String?)?.trim(),
      secondaryAddress: (json['secondaryAddress'] as String?)?.trim(),
      legacyHotline: (json['legacyHotline'] as String?)?.trim(),
      legacyStatus:
          MetadataEvidenceState.fromString(json['legacyStatus'] as String?),
      secondaryPhone: (json['secondaryPhone'] as String?)?.trim(),
      secondaryChargeStatus:
          ChargeStatus.fromString(json['secondaryChargeStatus'] as String?),
      dialNote: (json['dialNote'] as String?)?.trim(),
      neutralBadge: (json['neutralBadge'] as String?)?.trim(),
      sourceName: (json['sourceName'] as String? ?? '').trim(),
      sourceUrl: (json['sourceUrl'] as String? ?? '').trim(),
      verifiedAt: (json['verifiedAt'] as String? ?? '').trim(),
    );
  }
}

class EmergencyDirectoryBundle {
  final int schemaVersion;
  final String snapshotDate;
  final String disclaimer;
  final String offlineTelecomNotice;
  final String transitionRoadmapNote;
  final List<EmergencyDirectoryEntry> entries;

  const EmergencyDirectoryBundle({
    required this.schemaVersion,
    required this.snapshotDate,
    required this.disclaimer,
    required this.offlineTelecomNotice,
    required this.transitionRoadmapNote,
    required this.entries,
  });

  static const String defaultDisclaimer =
      'GoMate hỗ trợ bạn truy cập nhanh thông tin an toàn và danh bạ cứu nạn. '
      'GoMate không phải cơ quan điều phối cứu hộ. Trong tình huống khẩn cấp, '
      'vui lòng liên hệ ngay cơ quan chức năng hoặc người hỗ trợ tại địa phương.';

  static const String defaultOfflineTelecomNotice =
      'Cuộc gọi khẩn cấp sử dụng dịch vụ thoại của nhà mạng và không cần kết nối Internet. '
      'Khả năng gọi vẫn phụ thuộc vùng phủ sóng và dịch vụ viễn thông trên thiết bị.';

  factory EmergencyDirectoryBundle.fromJson(Map<String, dynamic> json) {
    final rawEntries = json['entries'];
    final parsedEntries = rawEntries is List
        ? rawEntries
            .whereType<Map>()
            .map(
              (item) => EmergencyDirectoryEntry.fromJson(
                Map<String, dynamic>.from(item),
              ),
            )
            .toList()
        : const <EmergencyDirectoryEntry>[];

    return EmergencyDirectoryBundle(
      schemaVersion: (json['schemaVersion'] as num?)?.toInt() ?? 1,
      snapshotDate:
          (json['snapshotDate'] as String? ?? '2026-10-05').trim(),
      disclaimer:
          (json['disclaimer'] as String?)?.trim().isNotEmpty == true
              ? (json['disclaimer'] as String).trim()
              : defaultDisclaimer,
      offlineTelecomNotice:
          (json['offlineTelecomNotice'] as String?)?.trim().isNotEmpty == true
              ? (json['offlineTelecomNotice'] as String).trim()
              : defaultOfflineTelecomNotice,
      transitionRoadmapNote:
          (json['transitionRoadmapNote'] as String? ?? '').trim(),
      entries: parsedEntries.isEmpty
          ? EmergencyDirectoryBundle.fallback().entries
          : parsedEntries,
    );
  }

  factory EmergencyDirectoryBundle.fallback() {
    return const EmergencyDirectoryBundle(
      schemaVersion: 1,
      snapshotDate: '2026-10-05',
      disclaimer: defaultDisclaimer,
      offlineTelecomNotice: defaultOfflineTelecomNotice,
      transitionRoadmapNote:
          'Đề án tích hợp các đầu số khẩn cấp đang triển khai theo lộ trình đến 2027–2028; hiện toàn bộ đầu số quốc gia đều hoạt động song song.',
      entries: [
        EmergencyDirectoryEntry(
          id: 'vn-112',
          countryCode: 'VN',
          category: EmergencyCategory.emergencyNational,
          displayName: 'Cứu nạn & tình huống nguy cấp',
          phoneNumber: '112',
          displayNumber: '112',
          governingAuthority: 'Bộ Quốc phòng (chủ trì)',
          operatingHours: '24/7',
          hoursStatus: MetadataEvidenceState.verified,
          chargeStatus: ChargeStatus.verifiedFree,
          description:
              'Tiếp nhận sự cố, thiên tai, thảm họa, tình huống nguy cấp trên phạm vi toàn quốc.',
          coordinationNote:
              'Liên thông với các tổng đài khẩn cấp quốc gia theo quy định hiện hành.',
          sourceName:
              'NĐ 200/2025/NĐ-CP, QĐ 2023/QĐ-TTg, QĐ 2024/QĐ-TTg, TT 22/2014/TT-BTTTT',
          sourceUrl: 'https://bocongan.gov.vn',
          verifiedAt: '2026-10-05',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-113',
          countryCode: 'VN',
          category: EmergencyCategory.emergencyNational,
          displayName: 'Cảnh sát phản ứng nhanh',
          phoneNumber: '113',
          displayNumber: '113',
          governingAuthority: 'Bộ Công an',
          operatingHours: '24/7',
          hoursStatus: MetadataEvidenceState.verified,
          chargeStatus: ChargeStatus.verifiedFree,
          description:
              'Can thiệp an ninh trật tự, tội phạm, trộm cướp, bạo lực, tai nạn giao thông nghiêm trọng.',
          sourceName: 'TT 22/2014/TT-BTTTT · Cổng TTĐT Bộ Công an',
          sourceUrl: 'https://bocongan.gov.vn',
          verifiedAt: '2026-10-05',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-114',
          countryCode: 'VN',
          category: EmergencyCategory.emergencyNational,
          displayName: 'Cứu hộ, Cứu nạn & PCCC',
          phoneNumber: '114',
          displayNumber: '114',
          governingAuthority: 'Cục CS PCCC & CNCH — Bộ Công an',
          operatingHours: '24/7',
          hoursStatus: MetadataEvidenceState.verified,
          chargeStatus: ChargeStatus.verifiedFree,
          description:
              'Hỏa hoạn tại nơi lưu trú, tai nạn mắc kẹt, đuối nước, cứu nạn cứu hộ khẩn cấp.',
          sourceName: 'Luật PCCC, NĐ 136/2020/NĐ-CP, TT 22/2014/TT-BTTTT',
          sourceUrl: 'http://canhsatpccc.gov.vn',
          verifiedAt: '2026-10-05',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-115',
          countryCode: 'VN',
          category: EmergencyCategory.emergencyNational,
          displayName: 'Cấp cứu Y tế',
          phoneNumber: '115',
          displayNumber: '115',
          governingAuthority: 'Bộ Y tế',
          operatingHours: '24/7',
          hoursStatus: MetadataEvidenceState.verified,
          chargeStatus: ChargeStatus.verifiedFree,
          description:
              'Chấn thương nặng, ngộ độc cấp, đột quỵ, sốc nhiệt, tai nạn đe dọa tính mạng.',
          sourceName: 'QĐ 01/2008/QĐ-BYT · Cổng TTĐT Bộ Y tế',
          sourceUrl: 'https://moh.gov.vn',
          verifiedAt: '2026-10-05',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-111',
          countryCode: 'VN',
          category: EmergencyCategory.protectionSocial,
          displayName: 'Tổng đài Quốc gia Bảo vệ Trẻ em',
          phoneNumber: '111',
          displayNumber: '111',
          governingAuthority: 'Cục Bà mẹ và Trẻ em — Bộ Y tế',
          operatingHours: '24/7',
          hoursStatus: MetadataEvidenceState.verified,
          chargeStatus: ChargeStatus.verifiedFree,
          description:
              'Hỗ trợ khẩn cấp bảo vệ trẻ em thất lạc, tai nạn, bạo lực, xâm hại.',
          sourceName: 'Luật Trẻ em 2016, NĐ 56/2017/NĐ-CP',
          sourceUrl: 'https://tongdai111.vn',
          verifiedAt: '2026-10-05',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-dad-8899',
          countryCode: 'VN',
          regionCode: 'DAD',
          category: EmergencyCategory.touristSupport,
          displayName: 'Hỗ trợ Du khách TP. Đà Nẵng',
          phoneNumber: '*8899',
          displayNumber: '*8899',
          governingAuthority:
              'Trung tâm Hỗ trợ Du khách Đà Nẵng — Sở Du lịch TP. Đà Nẵng',
          hoursStatus: MetadataEvidenceState.unknown,
          chargeStatus: ChargeStatus.unknown,
          description:
              'Đầu số ngắn tiếp nhận thông tin hỗ trợ du khách tại TP. Đà Nẵng.',
          physicalAddress: '18 Hùng Vương, phường Hải Châu, Đà Nẵng',
          secondaryAddress: '49 Phan Châu Trinh, phường Hội An, Đà Nẵng',
          legacyHotline: '0236 3550 111',
          legacyStatus: MetadataEvidenceState.unknown,
          neutralBadge: 'Thông tin hỗ trợ du khách',
          sourceName: 'Trung tâm Xúc tiến Du lịch Đà Nẵng (26/09/2026)',
          sourceUrl: 'https://danangfantasticity.com',
          verifiedAt: '2026-09-26',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-han-1800556896',
          countryCode: 'VN',
          regionCode: 'HAN',
          category: EmergencyCategory.touristSupport,
          displayName: 'Hỗ trợ Du khách Thủ đô Hà Nội',
          phoneNumber: '1800556896',
          displayNumber: '1800 556 896',
          governingAuthority:
              'Trung tâm Thông tin & Hỗ trợ Khách Du lịch — Sở Du lịch Hà Nội',
          hoursStatus: MetadataEvidenceState.unknown,
          chargeStatus: ChargeStatus.verifiedFree,
          description:
              'Đường dây hỗ trợ thông tin du khách tại Thủ đô Hà Nội.',
          secondaryPhone: '024 3926 1515',
          secondaryChargeStatus: ChargeStatus.unknown,
          neutralBadge: 'Thông tin hỗ trợ du khách',
          sourceName: 'Sở Du lịch Hà Nội',
          sourceUrl: 'http://sodulich.hanoi.gov.vn',
          verifiedAt: '2026-10-05',
        ),
        EmergencyDirectoryEntry(
          id: 'vn-sgn-1022',
          countryCode: 'VN',
          regionCode: 'SGN',
          category: EmergencyCategory.touristSupport,
          displayName: 'Hỗ trợ Du khách TP. Hồ Chí Minh',
          phoneNumber: '1022',
          displayNumber: '1022',
          governingAuthority: 'Sở Du lịch TP. Hồ Chí Minh',
          hoursStatus: MetadataEvidenceState.unknown,
          chargeStatus: ChargeStatus.unknown,
          description:
              'Tổng đài hỗ trợ thông tin du khách tại TP. Hồ Chí Minh.',
          dialNote: 'Nhánh 8 · Đường dây dự phòng: (+84) 28 3825 8558',
          neutralBadge: 'Thông tin hỗ trợ du khách',
          sourceName: 'Sở Du lịch TP.HCM',
          sourceUrl: 'https://visithcmc.vn',
          verifiedAt: '2026-10-05',
        ),
      ],
    );
  }
}

class PersonalSafetyContact {
  final String id;
  final String? serverId;
  final String name;
  final String phone;
  final String relation;
  final DateTime createdAt;
  final SafetyNetworkSendStatus sendStatus;
  final String? statusMessage;

  const PersonalSafetyContact({
    required this.id,
    this.serverId,
    required this.name,
    required this.phone,
    required this.relation,
    required this.createdAt,
    this.sendStatus = SafetyNetworkSendStatus.localOnly,
    this.statusMessage,
  });

  PersonalSafetyContact copyWith({
    String? id,
    String? serverId,
    String? name,
    String? phone,
    String? relation,
    DateTime? createdAt,
    SafetyNetworkSendStatus? sendStatus,
    String? statusMessage,
  }) {
    return PersonalSafetyContact(
      id: id ?? this.id,
      serverId: serverId ?? this.serverId,
      name: name ?? this.name,
      phone: phone ?? this.phone,
      relation: relation ?? this.relation,
      createdAt: createdAt ?? this.createdAt,
      sendStatus: sendStatus ?? this.sendStatus,
      statusMessage: statusMessage ?? this.statusMessage,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'serverId': serverId,
        'name': name,
        'phone': phone,
        'relation': relation,
        'createdAt': createdAt.toIso8601String(),
        'sendStatus': sendStatus.name,
        'statusMessage': statusMessage,
      };

  factory PersonalSafetyContact.fromJson(Map<String, dynamic> json) {
    return PersonalSafetyContact(
      id: (json['id'] as String? ?? '').trim(),
      serverId: (json['serverId'] as String?)?.trim(),
      name: (json['name'] as String? ?? '').trim(),
      phone: (json['phone'] as String? ?? '').trim(),
      relation: (json['relation'] as String? ?? 'family').trim(),
      createdAt: DateTime.tryParse(json['createdAt'] as String? ?? '') ??
          DateTime.now(),
      sendStatus:
          SafetyNetworkSendStatus.fromString(json['sendStatus'] as String?),
      statusMessage: (json['statusMessage'] as String?)?.trim(),
    );
  }

  static String relationLabel(String relation) {
    switch (relation) {
      case 'family':
        return 'Gia đình';
      case 'friend':
        return 'Bạn bè';
      case 'colleague':
        return 'Đồng nghiệp';
      case 'embassy':
        return 'Đại sứ quán / Lãnh sự';
      default:
        return 'Khác';
    }
  }
}

class SafetyCheckinNote {
  final String id;
  final String? serverId;
  final String title;
  final String note;
  final double? latitude;
  final double? longitude;
  final String? locationLabel;
  final DateTime createdAt;
  final SafetyNetworkSendStatus sendStatus;
  final String statusMessage;

  const SafetyCheckinNote({
    required this.id,
    this.serverId,
    required this.title,
    required this.note,
    this.latitude,
    this.longitude,
    this.locationLabel,
    required this.createdAt,
    required this.sendStatus,
    required this.statusMessage,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'serverId': serverId,
        'title': title,
        'note': note,
        'latitude': latitude,
        'longitude': longitude,
        'locationLabel': locationLabel,
        'createdAt': createdAt.toIso8601String(),
        'sendStatus': sendStatus.name,
        'statusMessage': statusMessage,
      };

  factory SafetyCheckinNote.fromJson(Map<String, dynamic> json) {
    return SafetyCheckinNote(
      id: (json['id'] as String? ?? '').trim(),
      serverId: (json['serverId'] as String?)?.trim(),
      title: (json['title'] as String? ?? '').trim(),
      note: (json['note'] as String? ?? '').trim(),
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      locationLabel: (json['locationLabel'] as String?)?.trim(),
      createdAt: DateTime.tryParse(json['createdAt'] as String? ?? '') ??
          DateTime.now(),
      sendStatus:
          SafetyNetworkSendStatus.fromString(json['sendStatus'] as String?),
      statusMessage: (json['statusMessage'] as String? ?? '').trim(),
    );
  }
}

class SafetyEventLogEntry {
  final String id;
  final String? serverId;
  final String actionType;
  final String targetNumber;
  final String targetLabel;
  final bool isSandbox;
  final double? latitude;
  final double? longitude;
  final SafetyNetworkSendStatus sendStatus;
  final String statusMessage;
  final DateTime createdAt;

  const SafetyEventLogEntry({
    required this.id,
    this.serverId,
    required this.actionType,
    required this.targetNumber,
    required this.targetLabel,
    required this.isSandbox,
    this.latitude,
    this.longitude,
    required this.sendStatus,
    required this.statusMessage,
    required this.createdAt,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'serverId': serverId,
        'actionType': actionType,
        'targetNumber': targetNumber,
        'targetLabel': targetLabel,
        'isSandbox': isSandbox,
        'latitude': latitude,
        'longitude': longitude,
        'sendStatus': sendStatus.name,
        'statusMessage': statusMessage,
        'createdAt': createdAt.toIso8601String(),
      };

  factory SafetyEventLogEntry.fromJson(Map<String, dynamic> json) {
    return SafetyEventLogEntry(
      id: (json['id'] as String? ?? '').trim(),
      serverId: (json['serverId'] as String?)?.trim(),
      actionType: (json['actionType'] as String? ?? 'sos').trim(),
      targetNumber: (json['targetNumber'] as String? ?? '').trim(),
      targetLabel: (json['targetLabel'] as String? ?? '').trim(),
      isSandbox: json['isSandbox'] == true,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      sendStatus:
          SafetyNetworkSendStatus.fromString(json['sendStatus'] as String?),
      statusMessage: (json['statusMessage'] as String? ?? '').trim(),
      createdAt: DateTime.tryParse(json['createdAt'] as String? ?? '') ??
          DateTime.now(),
    );
  }
}

class SafetyUserStoreSnapshot {
  final List<PersonalSafetyContact> contacts;
  final List<SafetyCheckinNote> notes;
  final List<SafetyEventLogEntry> events;
  final bool? isSandboxMode;

  const SafetyUserStoreSnapshot({
    this.contacts = const [],
    this.notes = const [],
    this.events = const [],
    this.isSandboxMode,
  });

  SafetyUserStoreSnapshot copyWith({
    List<PersonalSafetyContact>? contacts,
    List<SafetyCheckinNote>? notes,
    List<SafetyEventLogEntry>? events,
    bool? isSandboxMode,
  }) {
    return SafetyUserStoreSnapshot(
      contacts: contacts ?? this.contacts,
      notes: notes ?? this.notes,
      events: events ?? this.events,
      isSandboxMode: isSandboxMode ?? this.isSandboxMode,
    );
  }

  Map<String, dynamic> toJson() => {
        'contacts': contacts.map((c) => c.toJson()).toList(),
        'notes': notes.map((n) => n.toJson()).toList(),
        'events': events.map((e) => e.toJson()).toList(),
        if (isSandboxMode != null) 'isSandboxMode': isSandboxMode,
      };

  factory SafetyUserStoreSnapshot.fromJson(Map<String, dynamic> json) {
    final rawContacts = json['contacts'];
    final rawNotes = json['notes'];
    final rawEvents = json['events'];

    return SafetyUserStoreSnapshot(
      contacts: rawContacts is List
          ? rawContacts
              .whereType<Map>()
              .map(
                (item) => PersonalSafetyContact.fromJson(
                  Map<String, dynamic>.from(item),
                ),
              )
              .toList()
          : const [],
      notes: rawNotes is List
          ? rawNotes
              .whereType<Map>()
              .map(
                (item) => SafetyCheckinNote.fromJson(
                  Map<String, dynamic>.from(item),
                ),
              )
              .toList()
          : const [],
      events: rawEvents is List
          ? rawEvents
              .whereType<Map>()
              .map(
                (item) => SafetyEventLogEntry.fromJson(
                  Map<String, dynamic>.from(item),
                ),
              )
              .toList()
          : const [],
      isSandboxMode:
          json['isSandboxMode'] is bool ? json['isSandboxMode'] as bool : null,
    );
  }
}
