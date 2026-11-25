enum GroupRole {
  admin('admin', 'Trưởng nhóm (admin)'),
  member('member', 'Thành viên (member)');

  final String apiValue;
  final String label;

  const GroupRole(this.apiValue, this.label);

  static GroupRole fromApi(String? raw) {
    final normalized = raw?.trim().toLowerCase();
    if (normalized == 'admin' ||
        normalized == 'owner' ||
        normalized == 'leader') {
      return GroupRole.admin;
    }
    return GroupRole.member;
  }
}

/// PII-safe member user model matching backend `SAFE_BUDDY_USER_SELECT` +
/// `toSafeBuddyPeerView`. Strictly excludes `email`, `phone`, `dateOfBirth`,
/// `passwordHash`, `safetyContacts`, and `safetyCheckins`.
class GroupMemberUserModel {
  final String id;
  final String displayName;
  final String? avatar;
  final String? bio;
  final String? nationality;
  final List<String> languages;
  final String? travelStyle;
  final List<String> interests;

  const GroupMemberUserModel({
    required this.id,
    required this.displayName,
    this.avatar,
    this.bio,
    this.nationality,
    this.languages = const [],
    this.travelStyle,
    this.interests = const [],
  });

  factory GroupMemberUserModel.fromJson(Map<String, dynamic> json) {
    final profile = json['profile'] is Map
        ? Map<String, dynamic>.from(json['profile'] as Map)
        : null;
    final prefs = json['preferences'] is Map
        ? Map<String, dynamic>.from(json['preferences'] as Map)
        : null;

    final rawDisplay =
        (json['displayName'] as String?) ?? (profile?['displayName'] as String?);
    final trimmedDisplay = rawDisplay?.trim();

    final rawLanguages =
        (json['languages'] as List?) ?? (profile?['languages'] as List?);
    final rawInterests =
        (json['interests'] as List?) ?? (prefs?['interests'] as List?);

    return GroupMemberUserModel(
      id: (json['id'] as String?) ?? '',
      displayName: (trimmedDisplay != null && trimmedDisplay.isNotEmpty)
          ? trimmedDisplay
          : 'Du khách GoMate',
      avatar: (json['avatar'] as String?) ?? (profile?['avatar'] as String?),
      bio: (json['bio'] as String?) ?? (profile?['bio'] as String?),
      nationality: (json['nationality'] as String?) ??
          (profile?['nationality'] as String?),
      languages: rawLanguages
              ?.whereType<String>()
              .map((e) => e.trim())
              .where((e) => e.isNotEmpty)
              .toList() ??
          const [],
      travelStyle: (json['travelStyle'] as String?) ??
          (prefs?['travelStyle'] as String?),
      interests: rawInterests
              ?.whereType<String>()
              .map((e) => e.trim())
              .where((e) => e.isNotEmpty)
              .toList() ??
          const [],
    );
  }
}

class GroupMemberModel {
  final String id;
  final String groupId;
  final String userId;
  final GroupRole role;
  final String rawRole;
  final bool isTripOwner;
  final GroupMemberUserModel user;

  const GroupMemberModel({
    required this.id,
    required this.groupId,
    required this.userId,
    required this.role,
    required this.rawRole,
    this.isTripOwner = false,
    required this.user,
  });

  bool get isAdmin => role == GroupRole.admin;

  factory GroupMemberModel.fromJson(Map<String, dynamic> json) {
    final userJson = json['user'] is Map
        ? Map<String, dynamic>.from(json['user'] as Map)
        : <String, dynamic>{};
    final user = GroupMemberUserModel.fromJson(userJson);
    final rawRole = (json['role'] as String?) ?? 'member';
    final parsedUserId = (json['userId'] as String?)?.trim();

    return GroupMemberModel(
      id: (json['id'] as String?) ?? '',
      groupId: (json['groupId'] as String?) ?? '',
      userId: (parsedUserId != null && parsedUserId.isNotEmpty)
          ? parsedUserId
          : user.id,
      role: GroupRole.fromApi(rawRole),
      rawRole: rawRole,
      isTripOwner: json['isTripOwner'] == true,
      user: user,
    );
  }
}

class GroupModel {
  final String id;
  final String name;
  final String? description;
  final String? tripId;
  final String? tripTitle;
  final String? tripOwnerId;
  final DateTime? createdAt;
  final GroupRole? myRole;
  final int memberCount;
  final List<GroupMemberModel> members;

  const GroupModel({
    required this.id,
    required this.name,
    this.description,
    this.tripId,
    this.tripTitle,
    this.tripOwnerId,
    this.createdAt,
    this.myRole,
    required this.memberCount,
    this.members = const [],
  });

  factory GroupModel.fromJson(Map<String, dynamic> json) {
    final rawMembers = json['members'];
    final members = rawMembers is List
        ? rawMembers
            .whereType<Map>()
            .map((e) => GroupMemberModel.fromJson(Map<String, dynamic>.from(e)))
            .toList()
        : const <GroupMemberModel>[];

    final rawCount = (json['memberCount'] as num?)?.toInt() ??
        (json['_count'] is Map
            ? ((json['_count'] as Map)['members'] as num?)?.toInt()
            : null) ??
        members.length;

    final rawCreatedAt = json['createdAt'];
    DateTime? parsedCreatedAt;
    if (rawCreatedAt is String) {
      parsedCreatedAt = DateTime.tryParse(rawCreatedAt);
    }

    final rawMyRole = json['myRole'] as String?;

    return GroupModel(
      id: (json['id'] as String?) ?? '',
      name: (json['name'] as String?) ?? '',
      description: json['description'] as String?,
      tripId: json['tripId'] as String?,
      tripTitle: json['tripTitle'] as String?,
      tripOwnerId: json['tripOwnerId'] as String?,
      createdAt: parsedCreatedAt,
      myRole: rawMyRole != null ? GroupRole.fromApi(rawMyRole) : null,
      memberCount: rawCount,
      members: members,
    );
  }

  GroupRole? resolveMyRole(String? currentUserId) {
    if (myRole != null) return myRole;
    if (currentUserId == null || currentUserId.isEmpty) return null;
    if (tripOwnerId != null && tripOwnerId == currentUserId) {
      return GroupRole.admin;
    }
    for (final m in members) {
      if (m.userId == currentUserId) return m.role;
    }
    return null;
  }

  bool canManage(String? currentUserId) {
    return resolveMyRole(currentUserId) == GroupRole.admin;
  }

  int get adminCount => members.where((m) => m.isAdmin || m.isTripOwner).length;
}

class CreateGroupRequest {
  final String name;
  final String? description;
  final String? tripId;

  const CreateGroupRequest({
    required this.name,
    this.description,
    this.tripId,
  });

  Map<String, dynamic> toJson() {
    final desc = description?.trim();
    final tid = tripId?.trim();
    return {
      'name': name.trim(),
      if (desc != null && desc.isNotEmpty) 'description': desc,
      if (tid != null && tid.isNotEmpty) 'tripId': tid,
    };
  }
}

class UpdateGroupRequest {
  final String? name;
  final String? description;

  const UpdateGroupRequest({
    this.name,
    this.description,
  });

  Map<String, dynamic> toJson() {
    return {
      if (name != null) 'name': name!.trim(),
      if (description != null) 'description': description!.trim(),
    };
  }
}

class AddGroupMemberRequest {
  final String userId;

  const AddGroupMemberRequest({required this.userId});

  Map<String, dynamic> toJson() => {
        'userId': userId.trim(),
      };
}
