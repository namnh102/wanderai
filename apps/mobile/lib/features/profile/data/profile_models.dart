import 'package:flutter/material.dart';

enum TravelStyle {
  backpacker('BACKPACKER', 'Phượt', Icons.backpack_outlined),
  budget('BUDGET', 'Tiết kiệm', Icons.savings_outlined),
  comfort('COMFORT', 'Thoải mái', Icons.hotel_outlined),
  luxury('LUXURY', 'Sang trọng', Icons.diamond_outlined);

  final String apiValue;
  final String label;
  final IconData icon;

  const TravelStyle(this.apiValue, this.label, this.icon);

  static TravelStyle fromApi(String? val) {
    if (val == null) return TravelStyle.comfort;
    final upper = val.toUpperCase();
    return TravelStyle.values.firstWhere(
      (e) => e.apiValue == upper,
      orElse: () => TravelStyle.comfort,
    );
  }
}

enum GroupSize {
  solo('SOLO', 'Đi một mình', Icons.person_outline),
  couple('COUPLE', 'Cặp đôi', Icons.favorite_border),
  smallGroup('SMALL_GROUP', 'Nhóm nhỏ (3-5)', Icons.group_outlined),
  largeGroup('LARGE_GROUP', 'Nhóm lớn (6+)', Icons.groups_outlined),
  family('FAMILY', 'Gia đình', Icons.family_restroom_outlined);

  final String apiValue;
  final String label;
  final IconData icon;

  const GroupSize(this.apiValue, this.label, this.icon);

  static GroupSize fromApi(String? val) {
    if (val == null) return GroupSize.solo;
    final upper = val.toUpperCase();
    return GroupSize.values.firstWhere(
      (e) => e.apiValue == upper,
      orElse: () => GroupSize.solo,
    );
  }
}

class CanonicalInterestItem {
  final String key;
  final String label;
  final IconData icon;

  const CanonicalInterestItem({
    required this.key,
    required this.label,
    required this.icon,
  });
}

const List<CanonicalInterestItem> kCanonicalInterests = [
  CanonicalInterestItem(
    key: 'food_cuisine',
    label: 'Ẩm thực & Đặc sản',
    icon: Icons.restaurant_outlined,
  ),
  CanonicalInterestItem(
    key: 'culture_history',
    label: 'Văn hóa & Lịch sử',
    icon: Icons.account_balance_outlined,
  ),
  CanonicalInterestItem(
    key: 'nature_outdoor',
    label: 'Thiên nhiên & Dã ngoại',
    icon: Icons.terrain_outlined,
  ),
  CanonicalInterestItem(
    key: 'coffee_culture',
    label: 'Cà phê & Trà quán',
    icon: Icons.local_cafe_outlined,
  ),
  CanonicalInterestItem(
    key: 'beach_island',
    label: 'Biển đảo & Nghỉ dưỡng',
    icon: Icons.beach_access_outlined,
  ),
  CanonicalInterestItem(
    key: 'shopping_local',
    label: 'Mua sắm & Chợ địa phương',
    icon: Icons.shopping_bag_outlined,
  ),
  CanonicalInterestItem(
    key: 'nightlife_entertainment',
    label: 'Giải trí về đêm',
    icon: Icons.nightlife_outlined,
  ),
];

const List<String> kCommonAvoidances = [
  'Đông đúc',
  'Độ cao',
  'Âm thanh lớn',
  'Leo cầu thang dốc',
  'Say xe/tàu',
];

const List<String> kCommonDietaryNeeds = [
  'Ăn chay',
  'Thuần chay',
  'Halal',
  'Không hải sản',
  'Không cay',
];

class TravelPreferences {
  final String? id;
  final String? userId;
  final TravelStyle travelStyle;
  final int budgetMin;
  final int budgetMax;
  final GroupSize preferredGroup;
  final List<String> interests;
  final List<String> avoidances;
  final List<String> dietaryNeeds;

  const TravelPreferences({
    this.id,
    this.userId,
    this.travelStyle = TravelStyle.comfort,
    this.budgetMin = 0,
    this.budgetMax = 10000000,
    this.preferredGroup = GroupSize.solo,
    this.interests = const [],
    this.avoidances = const [],
    this.dietaryNeeds = const [],
  });

  factory TravelPreferences.fromJson(Map<String, dynamic> json) {
    return TravelPreferences(
      id: json['id'] as String?,
      userId: json['userId'] as String?,
      travelStyle: TravelStyle.fromApi(json['travelStyle'] as String?),
      budgetMin: (json['budgetMin'] as num?)?.toInt() ?? 0,
      budgetMax: (json['budgetMax'] as num?)?.toInt() ?? 10000000,
      preferredGroup: GroupSize.fromApi(json['preferredGroup'] as String?),
      interests: (json['interests'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      avoidances: (json['avoidances'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      dietaryNeeds: (json['dietaryNeeds'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'travelStyle': travelStyle.apiValue,
        'budgetMin': budgetMin,
        'budgetMax': budgetMax,
        'preferredGroup': preferredGroup.apiValue,
        'interests': interests,
        'avoidances': avoidances,
        'dietaryNeeds': dietaryNeeds,
      };

  TravelPreferences copyWith({
    String? id,
    String? userId,
    TravelStyle? travelStyle,
    int? budgetMin,
    int? budgetMax,
    GroupSize? preferredGroup,
    List<String>? interests,
    List<String>? avoidances,
    List<String>? dietaryNeeds,
  }) {
    return TravelPreferences(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      travelStyle: travelStyle ?? this.travelStyle,
      budgetMin: budgetMin ?? this.budgetMin,
      budgetMax: budgetMax ?? this.budgetMax,
      preferredGroup: preferredGroup ?? this.preferredGroup,
      interests: interests ?? this.interests,
      avoidances: avoidances ?? this.avoidances,
      dietaryNeeds: dietaryNeeds ?? this.dietaryNeeds,
    );
  }
}

class UserProfile {
  final String id;
  final String email;
  final String? role;
  final String? displayName;
  final String? avatar;
  final String? bio;
  final String? phone;
  final TravelPreferences? preferences;

  const UserProfile({
    required this.id,
    required this.email,
    this.role,
    this.displayName,
    this.avatar,
    this.bio,
    this.phone,
    this.preferences,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    final profileData = json['profile'] as Map<String, dynamic>?;
    final prefData = json['preferences'] as Map<String, dynamic>?;

    return UserProfile(
      id: json['id'] as String,
      email: json['email'] as String,
      role: json['role'] as String?,
      displayName: profileData?['displayName'] as String?,
      avatar: profileData?['avatar'] as String?,
      bio: profileData?['bio'] as String?,
      phone: profileData?['phone'] as String?,
      preferences: prefData != null ? TravelPreferences.fromJson(prefData) : null,
    );
  }
}
