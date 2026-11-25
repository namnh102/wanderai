import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/buddy_models.dart';
import '../data/buddy_repository.dart';

class BuddyState {
  final bool isLoading;
  final bool isTogglingDiscovery;
  final bool isDiscoverable;
  final List<BuddyCandidateModel> candidates;
  final List<BuddyMatchRecord> matches;
  final String? errorMessage;

  const BuddyState({
    this.isLoading = false,
    this.isTogglingDiscovery = false,
    this.isDiscoverable = false,
    this.candidates = const [],
    this.matches = const [],
    this.errorMessage,
  });

  BuddyState copyWith({
    bool? isLoading,
    bool? isTogglingDiscovery,
    bool? isDiscoverable,
    List<BuddyCandidateModel>? candidates,
    List<BuddyMatchRecord>? matches,
    String? errorMessage,
    bool clearError = false,
  }) {
    return BuddyState(
      isLoading: isLoading ?? this.isLoading,
      isTogglingDiscovery: isTogglingDiscovery ?? this.isTogglingDiscovery,
      isDiscoverable: isDiscoverable ?? this.isDiscoverable,
      candidates: candidates ?? this.candidates,
      matches: matches ?? this.matches,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class BuddyNotifier extends StateNotifier<BuddyState> {
  final BuddyRepository _repo;
  int _loadSeq = 0;

  BuddyNotifier(this._repo) : super(const BuddyState());

  void resetForLogout() {
    _loadSeq++;
    if (!mounted) return;
    state = const BuddyState();
  }

  Future<void> load({String? destinationId}) async {
    if (!mounted) return;
    final seq = ++_loadSeq;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final results = await Future.wait([
        _repo.getCandidatesWithConsent(destinationId: destinationId),
        _repo.getMyMatches(),
      ]);
      if (!mounted || seq != _loadSeq) return;
      final candRes = results[0] as BuddyCandidatesResponse;
      state = BuddyState(
        isLoading: false,
        isDiscoverable: candRes.isDiscoverable,
        candidates: candRes.items,
        matches: results[1] as List<BuddyMatchRecord>,
      );
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.response?.statusCode == 401
            ? 'Vui lòng đăng nhập lại để xem gợi ý bạn đồng hành.'
            : 'Không thể tải danh sách bạn đồng hành.',
      );
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Không thể tải danh sách bạn đồng hành.',
      );
    }
  }

  Future<bool> toggleDiscovery(bool nextValue) async {
    state = state.copyWith(isTogglingDiscovery: true, clearError: true);
    try {
      final updated = await _repo.updateDiscoveryConsent(nextValue);
      if (!mounted) return false;
      state = state.copyWith(
        isTogglingDiscovery: false,
        isDiscoverable: updated,
      );
      await load();
      return true;
    } catch (_) {
      if (!mounted) return false;
      state = state.copyWith(
        isTogglingDiscovery: false,
        errorMessage: 'Không thể cập nhật trạng thái tìm bạn đồng hành.',
      );
      return false;
    }
  }

  Future<bool> sendRequest(String receiverId) async {
    try {
      await _repo.sendRequest(receiverId);
      if (!mounted) return true;
      await load();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> withdrawRequest(String matchId) async {
    try {
      await _repo.withdrawRequest(matchId);
      if (!mounted) return true;
      await load();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> respond(String matchId, String action) async {
    try {
      await _repo.respond(matchId, action);
      if (!mounted) return true;
      await load();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> blockPeer(String peerId) async {
    try {
      await _repo.blockUser(peerId);
      if (!mounted) return true;
      await load();
      return true;
    } catch (_) {
      return false;
    }
  }
}

final buddyProvider = StateNotifierProvider<BuddyNotifier, BuddyState>((ref) {
  return BuddyNotifier(ref.read(buddyRepositoryProvider));
});
