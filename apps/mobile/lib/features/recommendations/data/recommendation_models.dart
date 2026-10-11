/// Typed models for the NestJS `GET /places/recommendations` response.
///
/// The REC-A response is consumed as-is; no scoring or ranking logic lives here.
/// The backend envelope is `{success, data: {...}, timestamp}` and `data` holds
/// `recommendations`, `metadata` and `unsupported_user_features` (snake_case).
library;

/// MVP destinations selectable in the recommendation UI.
/// `slug` is what is sent to the backend (`destination` query parameter).
enum RecommendationDestination {
  haNoi('ha-noi', 'Hà Nội'),
  daNang('da-nang', 'Đà Nẵng'),
  haLong('ha-long', 'Hạ Long');

  final String slug;
  final String label;
  const RecommendationDestination(this.slug, this.label);
}

class RecommendationExplanation {
  final String reasonCode;
  final List<String> matchedInterests;
  final List<String> matchedTaxonomy;
  final String text;

  const RecommendationExplanation({
    required this.reasonCode,
    required this.matchedInterests,
    required this.matchedTaxonomy,
    required this.text,
  });

  factory RecommendationExplanation.fromJson(Map<String, dynamic> json) {
    return RecommendationExplanation(
      reasonCode: json['reason_code'] as String? ?? '',
      matchedInterests: _stringList(json['matched_interests']),
      matchedTaxonomy: _stringList(json['matched_taxonomy']),
      text: json['text'] as String? ?? '',
    );
  }
}

class RecommendedPlace {
  final String placeId;
  final String name;
  final String destination;
  final String destinationSlug;
  final String category;
  final double score;
  final int rank;
  final List<String> matchedInterests;
  final RecommendationExplanation explanation;
  final String strategy;

  const RecommendedPlace({
    required this.placeId,
    required this.name,
    required this.destination,
    required this.destinationSlug,
    required this.category,
    required this.score,
    required this.rank,
    required this.matchedInterests,
    required this.explanation,
    required this.strategy,
  });

  factory RecommendedPlace.fromJson(Map<String, dynamic> json) {
    return RecommendedPlace(
      placeId: json['place_id'] as String,
      name: json['name'] as String? ?? '',
      destination: json['destination'] as String? ?? '',
      destinationSlug: json['destination_slug'] as String? ?? '',
      category: json['category'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      rank: (json['rank'] as num?)?.toInt() ?? 0,
      matchedInterests: _stringList(json['matched_interests']),
      explanation: RecommendationExplanation.fromJson(
        (json['explanation'] as Map<String, dynamic>?) ?? const {},
      ),
      strategy: json['strategy'] as String? ?? '',
    );
  }
}

class RecommendationMetadata {
  final String algorithm;
  final String model;
  final String? destinationFilter;
  final int totalCandidates;
  final int returnedCount;
  final bool coldStart;

  const RecommendationMetadata({
    required this.algorithm,
    required this.model,
    required this.destinationFilter,
    required this.totalCandidates,
    required this.returnedCount,
    required this.coldStart,
  });

  factory RecommendationMetadata.fromJson(Map<String, dynamic> json) {
    return RecommendationMetadata(
      algorithm: json['algorithm'] as String? ?? '',
      model: json['model'] as String? ?? '',
      destinationFilter: json['destination_filter'] as String?,
      totalCandidates: (json['total_candidates'] as num?)?.toInt() ?? 0,
      returnedCount: (json['returned_count'] as num?)?.toInt() ?? 0,
      coldStart: json['cold_start'] as bool? ?? false,
    );
  }
}

class UnsupportedUserFeature {
  final String feature;
  final String status;
  final String reason;

  const UnsupportedUserFeature({
    required this.feature,
    required this.status,
    required this.reason,
  });

  factory UnsupportedUserFeature.fromJson(Map<String, dynamic> json) {
    return UnsupportedUserFeature(
      feature: json['feature'] as String? ?? '',
      status: json['status'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
    );
  }
}

class RecommendationResult {
  final List<RecommendedPlace> recommendations;
  final RecommendationMetadata metadata;
  final List<UnsupportedUserFeature> unsupportedUserFeatures;

  const RecommendationResult({
    required this.recommendations,
    required this.metadata,
    required this.unsupportedUserFeatures,
  });

  bool get isEmpty => recommendations.isEmpty;

  /// Parse the `data` object of the NestJS envelope.
  factory RecommendationResult.fromJson(Map<String, dynamic> json) {
    return RecommendationResult(
      recommendations: ((json['recommendations'] as List<dynamic>?) ?? const [])
          .map((e) => RecommendedPlace.fromJson(e as Map<String, dynamic>))
          .toList(),
      metadata: RecommendationMetadata.fromJson(
        (json['metadata'] as Map<String, dynamic>?) ?? const {},
      ),
      unsupportedUserFeatures:
          ((json['unsupported_user_features'] as List<dynamic>?) ?? const [])
              .map((e) => UnsupportedUserFeature.fromJson(e as Map<String, dynamic>))
              .toList(),
    );
  }
}

List<String> _stringList(dynamic v) =>
    (v as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [];
