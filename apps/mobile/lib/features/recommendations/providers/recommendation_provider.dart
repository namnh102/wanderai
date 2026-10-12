import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/recommendation_models.dart';
import '../data/recommendation_repository.dart';

enum RecommendationStatus { initial, loading, success, empty, error }

class RecommendationState {
  final RecommendationStatus status;
  final RecommendationDestination destination;

  /// Result for [destination] only. Cleared whenever the destination changes so a
  /// previous destination's items can never be shown under another one.
  final RecommendationResult? result;
  final String? errorMessage;

  const RecommendationState({
    this.status = RecommendationStatus.initial,
    this.destination = RecommendationDestination.daNang,
    this.result,
    this.errorMessage,
  });

  bool get isLoading => status == RecommendationStatus.loading;
}

/// Holds UI state only. Ranking is performed by REC-A behind the NestJS endpoint.
class RecommendationNotifier extends StateNotifier<RecommendationState> {
  final RecommendationRepository _repo;
  int _requestSeq = 0;

  RecommendationNotifier(this._repo) : super(const RecommendationState());

  /// Load recommendations for the currently selected destination.
  Future<void> load() => _fetch(state.destination);

  /// Switch destination: drops the old result immediately and refetches.
  Future<void> selectDestination(RecommendationDestination destination) {
    if (destination == state.destination && state.status != RecommendationStatus.initial) {
      return Future.value();
    }
    return _fetch(destination);
  }

  Future<void> retry() => _fetch(state.destination);

  Future<void> _fetch(RecommendationDestination destination) async {
    final seq = ++_requestSeq;
    state = RecommendationState(
      status: RecommendationStatus.loading,
      destination: destination,
    );
    try {
      final result = await _repo.fetch(destination: destination.slug);
      // Ignore a response that is no longer the latest request (stale destination).
      if (!mounted || seq != _requestSeq) return;
      state = RecommendationState(
        status: result.isEmpty ? RecommendationStatus.empty : RecommendationStatus.success,
        destination: destination,
        result: result,
      );
    } on RecommendationException catch (e) {
      if (!mounted || seq != _requestSeq) return;
      state = RecommendationState(
        status: RecommendationStatus.error,
        destination: destination,
        errorMessage: e.message,
      );
    } catch (_) {
      if (!mounted || seq != _requestSeq) return;
      state = RecommendationState(
        status: RecommendationStatus.error,
        destination: destination,
        errorMessage: 'Không thể tải gợi ý. Vui lòng thử lại.',
      );
    }
  }
}

final recommendationProvider =
    StateNotifierProvider<RecommendationNotifier, RecommendationState>((ref) {
  return RecommendationNotifier(ref.read(recommendationRepositoryProvider));
});
