class Destination {
  final String id;
  final String name;
  final String nameEn;
  final String description;
  final String province;
  final String region;
  final double rating;
  final bool isPopular;
  final String coverImage;

  Destination({
    required this.id, required this.name, required this.nameEn,
    required this.description, required this.province, required this.region,
    required this.rating, required this.isPopular, required this.coverImage
  });

  factory Destination.fromJson(Map<String, dynamic> json) => Destination(
    id: json['id'] ?? '',
    name: json['name'] ?? '',
    nameEn: json['nameEn'] ?? '',
    description: json['description'] ?? '',
    province: json['province'] ?? '',
    region: json['region'] ?? '',
    rating: (json['rating'] ?? 0).toDouble(),
    isPopular: json['isPopular'] ?? false,
    coverImage: json['coverImage'] ?? '',
  );
}