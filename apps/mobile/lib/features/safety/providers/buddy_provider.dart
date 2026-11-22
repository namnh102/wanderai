import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/buddy_models.dart';
import '../data/buddy_repository.dart';

class BuddyState {
  final bool isLoading;
  final List<BuddyCandidateModel> candidates;
  final List<BuddyMatchRecord> matches;
  final String? errorMessage;

  const BuddyState({
    this.isLoading = false,
    this.candidates = const [],
    this.matches = const [],
    this.errorMessage,
  });

  BuddyState copyWith({
    bool? isLoading,
    List<BuddyCandidateModel>? candidates,
    List<BuddyMatchRecord>? matches,
    String? errorMessage,
    bool clearError = false,
  }) {
    return BuddyState(
      isLoading: isLoading ?? this.isLoading,
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
    state = const BuddyState();
  }

  Future<void> load() async {
    final seq = ++_loadSeq;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final results = await Future.wait([
        _repo.getCandidates(),
        _repo.getMyMatches(),
      ]);
      if (!mounted || seq != _loadSeq) return;
      state = BuddyState(
        isLoading: false,
        candidates: results[0] as List<BuddyCandidateModel>,
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

  Future<bool> sendRequest(String receiverId) async {
    try {
      await _repo.sendRequest(receiverId);
      await load();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> respond(String matchId, String action) async {
    try {
      await _repo.respond(matchId, action);
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
