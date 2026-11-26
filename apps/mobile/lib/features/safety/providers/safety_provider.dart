import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/providers/auth_provider.dart';
import '../../places/data/navigation_service.dart';
import '../../profile/providers/profile_provider.dart';
import '../data/safety_models.dart';
import '../data/safety_repository.dart';

/// Optional explicit scope override for isolated unit/widget testing.
final safetyScopeOverrideProvider = Provider<String?>((ref) => null);

/// Initial sandbox mode setting when no persisted user preference exists yet.
final safetyInitialSandboxModeProvider = Provider<bool>((ref) => true);

class SafetyState {
  final bool isLoading;
  final bool hasLoaded;
  final bool isOffline;
  final bool isSandboxMode;
  final bool isTriggerInFlight;
  final bool isSavingData;
  final String scopeKey;
  final EmergencyDirectoryBundle directoryBundle;
  final List<PersonalSafetyContact> contacts;
  final List<SafetyCheckinNote> notes;
  final List<SafetyEventLogEntry> events;
  final SafetyNetworkSendStatus? lastActionStatus;
  final String? lastActionBannerMessage;
  final String? errorMessage;

  const SafetyState({
    required this.isLoading,
    required this.hasLoaded,
    required this.isOffline,
    required this.isSandboxMode,
    required this.isTriggerInFlight,
    required this.isSavingData,
    required this.scopeKey,
    required this.directoryBundle,
    required this.contacts,
    required this.notes,
    required this.events,
    this.lastActionStatus,
    this.lastActionBannerMessage,
    this.errorMessage,
  });

  factory SafetyState.initial({
    EmergencyDirectoryBundle? directoryBundle,
    bool isSandboxMode = true,
  }) {
    return SafetyState(
      isLoading: false,
      hasLoaded: false,
      isOffline: false,
      isSandboxMode: isSandboxMode,
      isTriggerInFlight: false,
      isSavingData: false,
      scopeKey: 'guest',
      directoryBundle: directoryBundle ?? EmergencyDirectoryBundle.fallback(),
      contacts: const [],
      notes: const [],
      events: const [],
    );
  }

  bool get hasPersonalData =>
      contacts.isNotEmpty || notes.isNotEmpty || events.isNotEmpty;

  List<EmergencyDirectoryEntry> get directory => directoryBundle.entries;

  List<EmergencyDirectoryEntry> get nationalEntries => directory
      .where((e) => e.category == EmergencyCategory.emergencyNational)
      .toList();

  List<EmergencyDirectoryEntry> get protectionEntries => directory
      .where((e) => e.category == EmergencyCategory.protectionSocial)
      .toList();

  List<EmergencyDirectoryEntry> get touristSupportEntries => directory
      .where((e) => e.category == EmergencyCategory.touristSupport)
      .toList();

  SafetyState copyWith({
    bool? isLoading,
    bool? hasLoaded,
    bool? isOffline,
    bool? isSandboxMode,
    bool? isTriggerInFlight,
    bool? isSavingData,
    String? scopeKey,
    EmergencyDirectoryBundle? directoryBundle,
    List<PersonalSafetyContact>? contacts,
    List<SafetyCheckinNote>? notes,
    List<SafetyEventLogEntry>? events,
    SafetyNetworkSendStatus? lastActionStatus,
    String? lastActionBannerMessage,
    String? errorMessage,
    bool clearError = false,
    bool clearLastAction = false,
  }) {
    return SafetyState(
      isLoading: isLoading ?? this.isLoading,
      hasLoaded: hasLoaded ?? this.hasLoaded,
      isOffline: isOffline ?? this.isOffline,
      isSandboxMode: isSandboxMode ?? this.isSandboxMode,
      isTriggerInFlight: isTriggerInFlight ?? this.isTriggerInFlight,
      isSavingData: isSavingData ?? this.isSavingData,
      scopeKey: scopeKey ?? this.scopeKey,
      directoryBundle: directoryBundle ?? this.directoryBundle,
      contacts: contacts ?? this.contacts,
      notes: notes ?? this.notes,
      events: events ?? this.events,
      lastActionStatus: clearLastAction
          ? null
          : (lastActionStatus ?? this.lastActionStatus),
      lastActionBannerMessage: clearLastAction
          ? null
          : (lastActionBannerMessage ?? this.lastActionBannerMessage),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class SafetyNotifier extends StateNotifier<SafetyState> {
  final Ref _ref;
  final SafetyRepository _repo;
  final SafetyNetworkClient _networkClient;
  final bool _defaultSandboxMode;
  final String? _scopeOverride;

  bool _inFlightLock = false;
  bool _isMutationInFlight = false;
  int _sessionEpoch = 0;
  int _loadSeq = 0;
  int _idCounter = 0;

  SafetyNotifier(
    this._ref,
    this._repo,
    this._networkClient, {
    bool defaultSandboxMode = true,
    String? scopeOverride,
  })  : _defaultSandboxMode = defaultSandboxMode,
        _scopeOverride = scopeOverride,
        super(SafetyState.initial(isSandboxMode: defaultSandboxMode));

  bool get _isAuthenticated =>
      _ref.read(authProvider).status == AuthStatus.authenticated;

  String? get _loadedProfileUserId {
    if (!_ref.exists(profileProvider)) return null;
    return _ref.read(profileProvider).user?.id;
  }

  String _nextId(String prefix) {
    _idCounter++;
    return '${prefix}_${DateTime.now().microsecondsSinceEpoch}_$_idCounter';
  }

  SafetyUserStoreSnapshot _currentSnapshot() {
    return SafetyUserStoreSnapshot(
      contacts: state.contacts,
      notes: state.notes,
      events: state.events,
      isSandboxMode: state.isSandboxMode,
    );
  }

  Future<void> load({bool checkConnectivity = true}) async {
    final epoch = _sessionEpoch;
    final seq = ++_loadSeq;
    state = state.copyWith(isLoading: true, clearError: true);

    final scopeKey = await _repo.resolveScope(
      isAuthenticated: _isAuthenticated,
      loadedProfileUserId: _loadedProfileUserId,
      overrideScope: _scopeOverride,
    );
    if (!mounted || seq != _loadSeq || epoch != _sessionEpoch) return;

    final bundle = await _repo.loadEmergencyDirectory();
    if (!mounted || seq != _loadSeq || epoch != _sessionEpoch) return;

    final snapshot = await _repo.loadUserStore(scopeKey);
    if (!mounted || seq != _loadSeq || epoch != _sessionEpoch) return;

    final isOnline =
        checkConnectivity ? await _networkClient.checkReachability() : !state.isOffline;

    if (!mounted || seq != _loadSeq || epoch != _sessionEpoch) return;

    state = state.copyWith(
      isLoading: false,
      hasLoaded: true,
      isOffline: !isOnline,
      scopeKey: scopeKey,
      directoryBundle: bundle,
      contacts: snapshot.contacts,
      notes: snapshot.notes,
      events: snapshot.events,
      isSandboxMode: snapshot.isSandboxMode ?? _defaultSandboxMode,
    );
  }

  Future<void> refreshConnectivity() async {
    final epoch = _sessionEpoch;
    final seq = _loadSeq;
    final online = await _networkClient.checkReachability();
    if (!mounted || seq != _loadSeq || epoch != _sessionEpoch) return;
    state = state.copyWith(isOffline: !online);
  }

  Future<void> setSandboxMode(bool enabled) async {
    final epoch = _sessionEpoch;
    final scopeKey = state.scopeKey;
    state = state.copyWith(
      isSandboxMode: enabled,
      clearError: true,
    );
    final snapshot = _currentSnapshot();
    if (!mounted || epoch != _sessionEpoch) return;
    await _repo.saveUserStore(scopeKey, snapshot);
  }

  Future<bool> addContact({
    required String name,
    required String phone,
    required String relation,
  }) async {
    final epoch = _sessionEpoch;
    if (_isMutationInFlight || state.isSavingData) {
      return false;
    }

    final cleanName = name.trim();
    final cleanPhone = phone.trim();
    final cleanRelation = relation.trim().isEmpty ? 'family' : relation.trim();

    if (cleanName.isEmpty || cleanPhone.isEmpty) {
      state = state.copyWith(
        errorMessage: 'Vui lòng nhập đầy đủ tên và số điện thoại liên hệ.',
      );
      return false;
    }

    if (state.contacts.length >= kMaxPersonalSafetyContacts) {
      state = state.copyWith(
        errorMessage:
            'Chỉ lưu tối đa $kMaxPersonalSafetyContacts người liên hệ tin cậy.',
      );
      return false;
    }

    _isMutationInFlight = true;
    state = state.copyWith(isSavingData: true, clearError: true);
    try {
      final scopeKey = await _ensureActiveScope();
      if (!mounted || epoch != _sessionEpoch) return false;

      final networkResult = await _networkClient.createContact(
        name: cleanName,
        phone: cleanPhone,
        relation: cleanRelation,
        isAuthenticated: _isAuthenticated,
      );
      if (!mounted || epoch != _sessionEpoch) return false;

      if (state.contacts.length >= kMaxPersonalSafetyContacts) {
        state = state.copyWith(
          errorMessage:
              'Chỉ lưu tối đa $kMaxPersonalSafetyContacts người liên hệ tin cậy.',
        );
        return false;
      }

      final contact = PersonalSafetyContact(
        id: _nextId('contact'),
        serverId: networkResult.serverId,
        name: cleanName,
        phone: cleanPhone,
        relation: cleanRelation,
        createdAt: DateTime.now(),
        sendStatus: networkResult.status,
        statusMessage: networkResult.message,
      );

      final updatedContacts = [...state.contacts, contact];
      final updatedSnapshot =
          _currentSnapshot().copyWith(contacts: updatedContacts);
      await _repo.saveUserStore(scopeKey, updatedSnapshot);

      if (!mounted || epoch != _sessionEpoch) return false;
      state = state.copyWith(
        isSavingData: false,
        scopeKey: scopeKey,
        contacts: updatedContacts,
        isOffline: networkResult.isOfflineError ? true : state.isOffline,
        lastActionStatus: networkResult.status,
        lastActionBannerMessage:
            'Đã lưu người liên hệ "$cleanName": ${networkResult.message}',
      );
      return true;
    } finally {
      if (epoch == _sessionEpoch) {
        _isMutationInFlight = false;
        if (mounted) {
          state = state.copyWith(isSavingData: false);
        }
      }
    }
  }

  Future<bool> removeContact(String contactId) async {
    final epoch = _sessionEpoch;
    if (_isMutationInFlight || state.isSavingData) {
      return false;
    }

    final idx = state.contacts.indexWhere((c) => c.id == contactId);
    if (idx < 0) return false;
    final target = state.contacts[idx];

    _isMutationInFlight = true;
    state = state.copyWith(isSavingData: true, clearError: true);
    try {
      final scopeKey = await _ensureActiveScope();
      if (!mounted || epoch != _sessionEpoch) return false;

      SafetyNetworkResult? networkResult;
      if (target.serverId != null && _isAuthenticated) {
        networkResult = await _networkClient.deleteContact(
          serverId: target.serverId!,
          isAuthenticated: _isAuthenticated,
        );
        if (!mounted || epoch != _sessionEpoch) return false;
      }

      final updatedContacts =
          state.contacts.where((c) => c.id != contactId).toList();
      final updatedSnapshot =
          _currentSnapshot().copyWith(contacts: updatedContacts);
      await _repo.saveUserStore(scopeKey, updatedSnapshot);

      if (!mounted || epoch != _sessionEpoch) return false;
      final effectiveStatus =
          networkResult?.status ?? SafetyNetworkSendStatus.localOnly;
      final bannerMessage = networkResult != null
          ? 'Đã xóa người liên hệ "${target.name}": ${networkResult.message}'
          : 'Đã xóa người liên hệ "${target.name}" khỏi danh sách an toàn.';
      state = state.copyWith(
        isSavingData: false,
        scopeKey: scopeKey,
        contacts: updatedContacts,
        isOffline: (networkResult?.isOfflineError ?? false)
            ? true
            : state.isOffline,
        lastActionStatus: effectiveStatus,
        lastActionBannerMessage: bannerMessage,
      );
      return true;
    } finally {
      if (epoch == _sessionEpoch) {
        _isMutationInFlight = false;
        if (mounted) {
          state = state.copyWith(isSavingData: false);
        }
      }
    }
  }

  Future<SafetyCheckinNote?> addCheckinNote({
    required String title,
    required String note,
    double? latitude,
    double? longitude,
    String? locationLabel,
    bool syncOnline = true,
  }) async {
    final epoch = _sessionEpoch;
    if (_isMutationInFlight || state.isSavingData) {
      return null;
    }

    final cleanTitle =
        title.trim().isEmpty ? 'Ghi chú check-in an toàn' : title.trim();
    final cleanNote = note.trim();
    if (cleanNote.isEmpty) {
      state = state.copyWith(
        errorMessage: 'Vui lòng nhập nội dung ghi chú an toàn.',
      );
      return null;
    }

    _isMutationInFlight = true;
    state = state.copyWith(isSavingData: true, clearError: true);
    try {
      final scopeKey = await _ensureActiveScope();
      if (!mounted || epoch != _sessionEpoch) return null;

      final SafetyNetworkResult networkResult;
      if (syncOnline) {
        networkResult = await _networkClient.createCheckin(
          latitude: latitude ?? 0.0,
          longitude: longitude ?? 0.0,
          note: '$cleanTitle: $cleanNote',
          isAuthenticated: _isAuthenticated,
        );
        if (!mounted || epoch != _sessionEpoch) return null;
      } else {
        networkResult = const SafetyNetworkResult(
          status: SafetyNetworkSendStatus.localOnly,
          message: 'Đã lưu cục bộ trên thiết bị',
        );
      }

      final item = SafetyCheckinNote(
        id: _nextId('note'),
        serverId: networkResult.serverId,
        title: cleanTitle,
        note: cleanNote,
        latitude: latitude,
        longitude: longitude,
        locationLabel: locationLabel?.trim().isNotEmpty == true
            ? locationLabel!.trim()
            : null,
        createdAt: DateTime.now(),
        sendStatus: networkResult.status,
        statusMessage: networkResult.message,
      );

      final updatedNotes = [item, ...state.notes];
      final updatedSnapshot = _currentSnapshot().copyWith(notes: updatedNotes);
      await _repo.saveUserStore(scopeKey, updatedSnapshot);

      if (!mounted || epoch != _sessionEpoch) return null;
      state = state.copyWith(
        isSavingData: false,
        scopeKey: scopeKey,
        notes: updatedNotes,
        isOffline: networkResult.isOfflineError ? true : state.isOffline,
        lastActionStatus: networkResult.status,
        lastActionBannerMessage:
            'Đã lưu "$cleanTitle": ${networkResult.message}',
      );
      return item;
    } finally {
      if (epoch == _sessionEpoch) {
        _isMutationInFlight = false;
        if (mounted) {
          state = state.copyWith(isSavingData: false);
        }
      }
    }
  }

  Future<void> removeNote(String noteId) async {
    final epoch = _sessionEpoch;
    if (_isMutationInFlight || state.isSavingData) {
      return;
    }

    _isMutationInFlight = true;
    state = state.copyWith(isSavingData: true, clearError: true);
    try {
      final scopeKey = await _ensureActiveScope();
      if (!mounted || epoch != _sessionEpoch) return;

      final updatedNotes = state.notes.where((n) => n.id != noteId).toList();
      final updatedSnapshot = _currentSnapshot().copyWith(notes: updatedNotes);
      await _repo.saveUserStore(scopeKey, updatedSnapshot);

      if (!mounted || epoch != _sessionEpoch) return;
      state = state.copyWith(
        isSavingData: false,
        scopeKey: scopeKey,
        notes: updatedNotes,
      );
    } finally {
      if (epoch == _sessionEpoch) {
        _isMutationInFlight = false;
        if (mounted) {
          state = state.copyWith(isSavingData: false);
        }
      }
    }
  }

  /// Executes an emergency or dialer action under a synchronous single-trigger
  /// lock so double-taps can never trigger more than one execution.
  Future<SafetyEventLogEntry?> triggerEmergencyAction({
    required String actionType,
    required String targetNumber,
    required String targetLabel,
    double? latitude,
    double? longitude,
    bool syncToServer = true,
  }) async {
    final epoch = _sessionEpoch;
    if (_inFlightLock) {
      return null;
    }
    _inFlightLock = true;
    state = state.copyWith(isTriggerInFlight: true, clearError: true);

    try {
      final scopeKey = await _ensureActiveScope();
      if (!mounted || epoch != _sessionEpoch) return null;

      final isSandbox = state.isSandboxMode;

      late final SafetyNetworkSendStatus sendStatus;
      late final String statusMessage;
      String? serverId;
      bool offlineObserved = false;

      if (isSandbox) {
        if (actionType == 'sos' && syncToServer) {
          final networkResult = await _networkClient.createEmergencyEvent(
            latitude: latitude ?? 0.0,
            longitude: longitude ?? 0.0,
            message: 'Sandbox SOS: $targetLabel',
            isSandbox: true,
            isAuthenticated: _isAuthenticated,
          );
          if (!mounted || epoch != _sessionEpoch) return null;

          serverId = networkResult.serverId;
          offlineObserved = networkResult.isOfflineError;

          if (networkResult.status == SafetyNetworkSendStatus.sentOnline) {
            sendStatus = SafetyNetworkSendStatus.sandboxSimulated;
            statusMessage =
                'Chế độ kiểm thử (Sandbox): Đã mô phỏng $targetLabel và ghi nhận kiểm thử lên máy chủ — không gọi số thật.';
          } else if (networkResult.status ==
              SafetyNetworkSendStatus.notSentOffline) {
            sendStatus = SafetyNetworkSendStatus.notSentOffline;
            statusMessage =
                'Chế độ kiểm thử (Sandbox): Chưa gửi được lên máy chủ do mất mạng — đã lưu mô phỏng cục bộ (không gọi số thật).';
          } else {
            sendStatus = SafetyNetworkSendStatus.sandboxSimulated;
            statusMessage =
                'Chế độ kiểm thử (Sandbox): Đã mô phỏng $targetLabel và lưu cục bộ — không gọi số thật.';
          }
        } else {
          sendStatus = SafetyNetworkSendStatus.sandboxSimulated;
          statusMessage =
              'Chế độ kiểm thử (Sandbox): Đã mô phỏng gọi $targetLabel ($targetNumber) — không mở trình gọi điện thật.';
        }
      } else if (actionType == 'dial') {
        final opener = _ref.read(externalUriOpenerProvider);
        final dialNumber = targetNumber.replaceAll(RegExp(r'\s+'), '');
        final opened = dialNumber.isEmpty
            ? false
            : await openExternalUrlString(
                'tel:$dialNumber',
                opener: opener,
              );
        if (!mounted || epoch != _sessionEpoch) return null;

        if (opened) {
          sendStatus = SafetyNetworkSendStatus.dialerOpened;
          statusMessage =
              'Đã mở trình quay số tới $targetLabel ($targetNumber).';
        } else {
          sendStatus = SafetyNetworkSendStatus.dialerFailed;
          statusMessage =
              'Không thể mở trình gọi điện tới số $targetNumber.';
        }
      } else {
        final networkResult = await _networkClient.createEmergencyEvent(
          latitude: latitude ?? 0.0,
          longitude: longitude ?? 0.0,
          message: 'SOS: $targetLabel',
          isSandbox: false,
          isAuthenticated: _isAuthenticated,
        );
        if (!mounted || epoch != _sessionEpoch) return null;

        sendStatus = networkResult.status;
        statusMessage = networkResult.message;
        serverId = networkResult.serverId;
        offlineObserved = networkResult.isOfflineError;
      }

      final entry = SafetyEventLogEntry(
        id: _nextId('event'),
        serverId: serverId,
        actionType: actionType,
        targetNumber: targetNumber,
        targetLabel: targetLabel,
        isSandbox: isSandbox,
        latitude: latitude,
        longitude: longitude,
        sendStatus: sendStatus,
        statusMessage: statusMessage,
        createdAt: DateTime.now(),
      );

      final updatedEvents = [entry, ...state.events];
      final updatedSnapshot =
          _currentSnapshot().copyWith(events: updatedEvents);
      await _repo.saveUserStore(scopeKey, updatedSnapshot);

      if (!mounted || epoch != _sessionEpoch) return null;
      state = state.copyWith(
        scopeKey: scopeKey,
        events: updatedEvents,
        isOffline: offlineObserved ? true : state.isOffline,
        lastActionStatus: sendStatus,
        lastActionBannerMessage: statusMessage,
      );
      return entry;
    } finally {
      if (epoch == _sessionEpoch) {
        _inFlightLock = false;
        if (mounted) {
          state = state.copyWith(isTriggerInFlight: false);
        }
      }
    }
  }

  /// Clears in-memory safety state immediately on auth transitions without
  /// deleting the previous user's persisted `SharedPreferences` bucket so
  /// offline restart (Case 3) works while User A <-> User B stay isolated.
  Future<void> resetForAuthTransition() async {
    _sessionEpoch++;
    _loadSeq++;
    _inFlightLock = false;
    _isMutationInFlight = false;
    state = SafetyState.initial(
      directoryBundle: state.directoryBundle,
      isSandboxMode: _defaultSandboxMode,
    );
    await _repo.clearLastUserId();
  }

  @override
  void dispose() {
    _sessionEpoch++;
    super.dispose();
  }

  Future<String> _ensureActiveScope() async {
    final resolved = await _repo.resolveScope(
      isAuthenticated: _isAuthenticated,
      loadedProfileUserId: _loadedProfileUserId,
      overrideScope: _scopeOverride,
    );
    return resolved;
  }
}

final safetyProvider =
    StateNotifierProvider<SafetyNotifier, SafetyState>((ref) {
  final repo = ref.watch(safetyRepositoryProvider);
  final networkClient = ref.watch(safetyNetworkClientProvider);
  final defaultSandbox = ref.watch(safetyInitialSandboxModeProvider);
  final scopeOverride = ref.watch(safetyScopeOverrideProvider);
  return SafetyNotifier(
    ref,
    repo,
    networkClient,
    defaultSandboxMode: defaultSandbox,
    scopeOverride: scopeOverride,
  );
});
