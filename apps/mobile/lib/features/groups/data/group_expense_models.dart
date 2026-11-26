import 'group_models.dart';

enum ExpenseCategory {
  food('FOOD', 'Ăn uống'),
  transport('TRANSPORT', 'Di chuyển'),
  accommodation('ACCOMMODATION', 'Lưu trú'),
  ticket('TICKET', 'Vé tham quan'),
  shopping('SHOPPING', 'Mua sắm'),
  other('OTHER', 'Khác');

  final String apiValue;
  final String label;

  const ExpenseCategory(this.apiValue, this.label);

  static ExpenseCategory fromApi(String? raw) {
    final norm = raw?.trim().toUpperCase();
    for (final c in ExpenseCategory.values) {
      if (c.apiValue == norm) return c;
    }
    return ExpenseCategory.other;
  }
}

enum SplitType {
  equal('EQUAL', 'Chia đều'),
  custom('CUSTOM', 'Chia tùy chỉnh');

  final String apiValue;
  final String label;

  const SplitType(this.apiValue, this.label);

  static SplitType fromApi(String? raw) {
    return raw?.trim().toUpperCase() == 'CUSTOM'
        ? SplitType.custom
        : SplitType.equal;
  }
}

String formatVnd(int amount) {
  final isNeg = amount < 0;
  final digits = amount.abs().toString();
  final buffer = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) {
      buffer.write('.');
    }
    buffer.write(digits[i]);
  }
  return '${isNeg ? '-' : ''}${buffer.toString()} đ';
}

/// Client-side preview matching backend `computeDeterministicEqualSplits` (`userId.toLowerCase() ASC`).
List<({String userId, int shareAmount})> previewEqualSplits(
  int amount,
  List<String> participantIds,
) {
  final uniqueSorted = participantIds
      .map((id) => id.trim().toLowerCase())
      .where((id) => id.isNotEmpty)
      .toSet()
      .toList()
    ..sort();
  final n = uniqueSorted.length;
  if (n == 0 || amount < n) return const [];
  final base = amount ~/ n;
  final rem = amount % n;
  return [
    for (var i = 0; i < n; i++)
      (userId: uniqueSorted[i], shareAmount: i < rem ? base + 1 : base),
  ];
}

class ExpenseSplitModel {
  final String id;
  final String userId;
  final int shareAmount;
  final GroupMemberUserModel? user;

  const ExpenseSplitModel({
    required this.id,
    required this.userId,
    required this.shareAmount,
    this.user,
  });

  factory ExpenseSplitModel.fromJson(Map<String, dynamic> json) {
    final userMap = json['user'] is Map
        ? Map<String, dynamic>.from(json['user'] as Map)
        : null;
    return ExpenseSplitModel(
      id: (json['id'] as String?) ?? '',
      userId: (json['userId'] as String?) ?? '',
      shareAmount: (json['shareAmount'] as num?)?.toInt() ?? 0,
      user: userMap != null ? GroupMemberUserModel.fromJson(userMap) : null,
    );
  }
}

class ExpenseModel {
  final String id;
  final String groupId;
  final String? tripId;
  final String title;
  final int amount;
  final String currency;
  final ExpenseCategory category;
  final SplitType splitType;
  final DateTime expenseDate;
  final String? notes;
  final String paidByUserId;
  final GroupMemberUserModel? paidBy;
  final String createdByUserId;
  final GroupMemberUserModel? createdBy;
  final DateTime createdAt;
  final bool canDelete;
  final List<ExpenseSplitModel> splits;

  const ExpenseModel({
    required this.id,
    required this.groupId,
    this.tripId,
    required this.title,
    required this.amount,
    this.currency = 'VND',
    required this.category,
    required this.splitType,
    required this.expenseDate,
    this.notes,
    required this.paidByUserId,
    this.paidBy,
    required this.createdByUserId,
    this.createdBy,
    required this.createdAt,
    this.canDelete = false,
    this.splits = const [],
  });

  factory ExpenseModel.fromJson(Map<String, dynamic> json) {
    final paidByMap = json['paidBy'] is Map
        ? Map<String, dynamic>.from(json['paidBy'] as Map)
        : null;
    final createdByMap = json['createdBy'] is Map
        ? Map<String, dynamic>.from(json['createdBy'] as Map)
        : null;
    final rawSplits = json['splits'];
    final splits = rawSplits is List
        ? rawSplits
            .whereType<Map>()
            .map(
              (e) => ExpenseSplitModel.fromJson(Map<String, dynamic>.from(e)),
            )
            .toList()
        : const <ExpenseSplitModel>[];

    final rawExpenseDate = json['expenseDate'];
    final rawCreatedAt = json['createdAt'];

    return ExpenseModel(
      id: (json['id'] as String?) ?? '',
      groupId: (json['groupId'] as String?) ?? '',
      tripId: json['tripId'] as String?,
      title: (json['title'] as String?) ?? '',
      amount: (json['amount'] as num?)?.toInt() ?? 0,
      currency: (json['currency'] as String?) ?? 'VND',
      category: ExpenseCategory.fromApi(json['category'] as String?),
      splitType: SplitType.fromApi(json['splitType'] as String?),
      expenseDate: rawExpenseDate is String
          ? (DateTime.tryParse(rawExpenseDate) ?? DateTime.now())
          : DateTime.now(),
      notes: json['notes'] as String?,
      paidByUserId: (json['paidByUserId'] as String?) ?? '',
      paidBy:
          paidByMap != null ? GroupMemberUserModel.fromJson(paidByMap) : null,
      createdByUserId: (json['createdByUserId'] as String?) ?? '',
      createdBy: createdByMap != null
          ? GroupMemberUserModel.fromJson(createdByMap)
          : null,
      createdAt: rawCreatedAt is String
          ? (DateTime.tryParse(rawCreatedAt) ?? DateTime.now())
          : DateTime.now(),
      canDelete: json['canDelete'] == true,
      splits: splits,
    );
  }
}

class ExpenseListModel {
  final String groupId;
  final String currency;
  final bool hasSettlements;
  final int totalSpent;
  final int expenseCount;
  final List<ExpenseModel> expenses;

  const ExpenseListModel({
    required this.groupId,
    this.currency = 'VND',
    this.hasSettlements = false,
    this.totalSpent = 0,
    this.expenseCount = 0,
    this.expenses = const [],
  });

  factory ExpenseListModel.fromJson(Map<String, dynamic> json) {
    final rawList = json['expenses'];
    final expenses = rawList is List
        ? rawList
            .whereType<Map>()
            .map((e) => ExpenseModel.fromJson(Map<String, dynamic>.from(e)))
            .toList()
        : const <ExpenseModel>[];

    return ExpenseListModel(
      groupId: (json['groupId'] as String?) ?? '',
      currency: (json['currency'] as String?) ?? 'VND',
      hasSettlements: json['hasSettlements'] == true,
      totalSpent: (json['totalSpent'] as num?)?.toInt() ?? 0,
      expenseCount: (json['expenseCount'] as num?)?.toInt() ?? expenses.length,
      expenses: expenses,
    );
  }
}

class MemberBalanceModel {
  final String userId;
  final GroupMemberUserModel user;
  final bool isActiveMember;
  final int paidAmount;
  final int owedAmount;
  final int outgoingSettlement;
  final int incomingSettlement;
  final int netBalance;

  const MemberBalanceModel({
    required this.userId,
    required this.user,
    this.isActiveMember = true,
    required this.paidAmount,
    required this.owedAmount,
    required this.outgoingSettlement,
    required this.incomingSettlement,
    required this.netBalance,
  });

  factory MemberBalanceModel.fromJson(Map<String, dynamic> json) {
    final userMap = json['user'] is Map
        ? Map<String, dynamic>.from(json['user'] as Map)
        : <String, dynamic>{};
    return MemberBalanceModel(
      userId: (json['userId'] as String?) ?? '',
      user: GroupMemberUserModel.fromJson(userMap),
      isActiveMember: json['isActiveMember'] != false,
      paidAmount: (json['paidAmount'] as num?)?.toInt() ?? 0,
      owedAmount: (json['owedAmount'] as num?)?.toInt() ?? 0,
      outgoingSettlement: (json['outgoingSettlement'] as num?)?.toInt() ?? 0,
      incomingSettlement: (json['incomingSettlement'] as num?)?.toInt() ?? 0,
      netBalance: (json['netBalance'] as num?)?.toInt() ?? 0,
    );
  }
}

class SuggestedSettlementModel {
  final String fromUserId;
  final GroupMemberUserModel fromUser;
  final String toUserId;
  final GroupMemberUserModel toUser;
  final int amount;

  const SuggestedSettlementModel({
    required this.fromUserId,
    required this.fromUser,
    required this.toUserId,
    required this.toUser,
    required this.amount,
  });

  factory SuggestedSettlementModel.fromJson(Map<String, dynamic> json) {
    final fromMap = json['fromUser'] is Map
        ? Map<String, dynamic>.from(json['fromUser'] as Map)
        : <String, dynamic>{};
    final toMap = json['toUser'] is Map
        ? Map<String, dynamic>.from(json['toUser'] as Map)
        : <String, dynamic>{};
    return SuggestedSettlementModel(
      fromUserId: (json['fromUserId'] as String?) ?? '',
      fromUser: GroupMemberUserModel.fromJson(fromMap),
      toUserId: (json['toUserId'] as String?) ?? '',
      toUser: GroupMemberUserModel.fromJson(toMap),
      amount: (json['amount'] as num?)?.toInt() ?? 0,
    );
  }
}

class SettlementModel {
  final String id;
  final String groupId;
  final String debtorId;
  final GroupMemberUserModel debtor;
  final String creditorId;
  final GroupMemberUserModel creditor;
  final String createdByUserId;
  final int amount;
  final String currency;
  final String? notes;
  final DateTime settledAt;

  const SettlementModel({
    required this.id,
    required this.groupId,
    required this.debtorId,
    required this.debtor,
    required this.creditorId,
    required this.creditor,
    required this.createdByUserId,
    required this.amount,
    this.currency = 'VND',
    this.notes,
    required this.settledAt,
  });

  factory SettlementModel.fromJson(Map<String, dynamic> json) {
    final debtorMap = json['debtor'] is Map
        ? Map<String, dynamic>.from(json['debtor'] as Map)
        : <String, dynamic>{};
    final creditorMap = json['creditor'] is Map
        ? Map<String, dynamic>.from(json['creditor'] as Map)
        : <String, dynamic>{};
    final rawSettledAt = json['settledAt'];
    return SettlementModel(
      id: (json['id'] as String?) ?? '',
      groupId: (json['groupId'] as String?) ?? '',
      debtorId: (json['debtorId'] as String?) ?? '',
      debtor: GroupMemberUserModel.fromJson(debtorMap),
      creditorId: (json['creditorId'] as String?) ?? '',
      creditor: GroupMemberUserModel.fromJson(creditorMap),
      createdByUserId: (json['createdByUserId'] as String?) ?? '',
      amount: (json['amount'] as num?)?.toInt() ?? 0,
      currency: (json['currency'] as String?) ?? 'VND',
      notes: json['notes'] as String?,
      settledAt: rawSettledAt is String
          ? (DateTime.tryParse(rawSettledAt) ?? DateTime.now())
          : DateTime.now(),
    );
  }
}

class SettlementPlanModel {
  final String groupId;
  final String currency;
  final int totalSpent;
  final int totalOutstandingDebt;
  final bool zeroSumVerified;
  final List<MemberBalanceModel> balances;
  final List<SuggestedSettlementModel> suggestedTransactions;
  final List<SettlementModel> settlements;

  const SettlementPlanModel({
    required this.groupId,
    this.currency = 'VND',
    this.totalSpent = 0,
    this.totalOutstandingDebt = 0,
    this.zeroSumVerified = true,
    this.balances = const [],
    this.suggestedTransactions = const [],
    this.settlements = const [],
  });

  factory SettlementPlanModel.fromJson(Map<String, dynamic> json) {
    final rawBal = json['balances'];
    final rawSug = json['suggestedTransactions'];
    final rawSet = json['settlements'];

    return SettlementPlanModel(
      groupId: (json['groupId'] as String?) ?? '',
      currency: (json['currency'] as String?) ?? 'VND',
      totalSpent: (json['totalSpent'] as num?)?.toInt() ?? 0,
      totalOutstandingDebt:
          (json['totalOutstandingDebt'] as num?)?.toInt() ?? 0,
      zeroSumVerified: json['zeroSumVerified'] != false,
      balances: rawBal is List
          ? rawBal
              .whereType<Map>()
              .map(
                (e) =>
                    MemberBalanceModel.fromJson(Map<String, dynamic>.from(e)),
              )
              .toList()
          : const [],
      suggestedTransactions: rawSug is List
          ? rawSug
              .whereType<Map>()
              .map(
                (e) => SuggestedSettlementModel.fromJson(
                  Map<String, dynamic>.from(e),
                ),
              )
              .toList()
          : const [],
      settlements: rawSet is List
          ? rawSet
              .whereType<Map>()
              .map(
                (e) => SettlementModel.fromJson(Map<String, dynamic>.from(e)),
              )
              .toList()
          : const [],
    );
  }
}

class CustomSplitRequestEntry {
  final String userId;
  final int shareAmount;

  const CustomSplitRequestEntry({
    required this.userId,
    required this.shareAmount,
  });

  Map<String, dynamic> toJson() => {
        'userId': userId.trim().toLowerCase(),
        'shareAmount': shareAmount,
      };
}

class CreateExpenseRequest {
  final String title;
  final int amount;
  final String? paidByUserId;
  final ExpenseCategory category;
  final SplitType splitType;
  final String? notes;
  final List<String>? participantIds;
  final List<CustomSplitRequestEntry>? customSplits;
  final String? clientRequestId;

  const CreateExpenseRequest({
    required this.title,
    required this.amount,
    this.paidByUserId,
    this.category = ExpenseCategory.other,
    this.splitType = SplitType.equal,
    this.notes,
    this.participantIds,
    this.customSplits,
    this.clientRequestId,
  });

  Map<String, dynamic> toJson() {
    return {
      'title': title.trim(),
      'amount': amount,
      if (paidByUserId != null && paidByUserId!.trim().isNotEmpty)
        'paidByUserId': paidByUserId!.trim().toLowerCase(),
      'category': category.apiValue,
      'splitType': splitType.apiValue,
      if (notes != null && notes!.trim().isNotEmpty) 'notes': notes!.trim(),
      if (splitType == SplitType.equal && participantIds != null)
        'participantIds': participantIds!
            .map((e) => e.trim().toLowerCase())
            .toList(),
      if (splitType == SplitType.custom && customSplits != null)
        'customSplits': customSplits!.map((e) => e.toJson()).toList(),
      if (clientRequestId != null && clientRequestId!.trim().isNotEmpty)
        'clientRequestId': clientRequestId!.trim(),
    };
  }
}

class CreateSettlementRequest {
  final String debtorId;
  final String creditorId;
  final int amount;
  final String? notes;
  final String? clientRequestId;

  const CreateSettlementRequest({
    required this.debtorId,
    required this.creditorId,
    required this.amount,
    this.notes,
    this.clientRequestId,
  });

  Map<String, dynamic> toJson() {
    return {
      'debtorId': debtorId.trim().toLowerCase(),
      'creditorId': creditorId.trim().toLowerCase(),
      'amount': amount,
      if (notes != null && notes!.trim().isNotEmpty) 'notes': notes!.trim(),
      if (clientRequestId != null && clientRequestId!.trim().isNotEmpty)
        'clientRequestId': clientRequestId!.trim(),
    };
  }
}
