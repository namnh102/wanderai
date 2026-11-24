import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/auth/data/auth_social_port.dart';
import 'package:wanderai_mobile/features/auth/presentation/forgot_password_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/login_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/register_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/reset_password_screen.dart';
import 'package:wanderai_mobile/features/home/presentation/home_screen.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';
import 'package:wanderai_mobile/features/places/providers/place_detail_provider.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';

const _outDirDefine = String.fromEnvironment(
  'SCREENSHOT_OUT_DIR',
  defaultValue: '',
);

String get _effectiveOutDir {
  if (_outDirDefine.isNotEmpty) return _outDirDefine;
  if (Platform.environment['CAPTURE_SCREENSHOTS'] == 'true') {
    return Platform.environment['SCREENSHOT_OUT_DIR'] ?? '';
  }
  return '';
}

const _haLongDestId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';
const _haNoiDestId = '11111111-1111-4111-8111-111111111111';
const _daNangDestId = '22222222-2222-4222-8222-222222222222';
const _clockTowerId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const _clockTowerName = 'Tháp Đồng Hồ';
const _validAccessToken = 'jwt-access-halong';
const _validRefreshToken = 'jwt-refresh-halong';

Future<void> _loadMaterialFonts() async {
  final candidates = [
    Platform.environment['FLUTTER_ROOT'],
    r'D:\flutter',
  ].whereType<String>().where((p) => p.isNotEmpty);

  Directory? fontDir;
  for (final root in candidates) {
    final dir = Directory(
      '$root${Platform.pathSeparator}bin${Platform.pathSeparator}cache'
      '${Platform.pathSeparator}artifacts${Platform.pathSeparator}material_fonts',
    );
    if (dir.existsSync()) {
      fontDir = dir;
      break;
    }
  }
  if (fontDir == null) return;

  for (final family in const ['Roboto', 'Be Vietnam Pro', 'Ahem']) {
    final loader = FontLoader(family);
    for (final name in [
      'roboto-light.ttf',
      'roboto-regular.ttf',
      'roboto-medium.ttf',
      'roboto-bold.ttf',
      'roboto-black.ttf',
    ]) {
      final f = File('${fontDir.path}${Platform.pathSeparator}$name');
      if (f.existsSync()) {
        final bytes = f.readAsBytesSync();
        loader.addFont(Future.value(ByteData.sublistView(bytes)));
      }
    }
    await loader.load();
  }

  final iconsFile = File(
    '${fontDir.path}${Platform.pathSeparator}materialicons-regular.otf',
  );
  if (iconsFile.existsSync()) {
    final icons = FontLoader('MaterialIcons');
    final bytes = iconsFile.readAsBytesSync();
    icons.addFont(Future.value(ByteData.sublistView(bytes)));
    await icons.load();
  }
}

int _crc32(List<int> data) {
  var crc = 0xFFFFFFFF;
  for (final b in data) {
    crc ^= b;
    for (var i = 0; i < 8; i++) {
      crc = (crc & 1) != 0 ? (crc >>> 1) ^ 0xEDB88320 : (crc >>> 1);
    }
  }
  return crc ^ 0xFFFFFFFF;
}

void _writeUint32BE(BytesBuilder out, int value) {
  out.add([
    (value >> 24) & 0xFF,
    (value >> 16) & 0xFF,
    (value >> 8) & 0xFF,
    value & 0xFF,
  ]);
}

void _writeChunk(BytesBuilder out, String type, List<int> data) {
  _writeUint32BE(out, data.length);
  final typeBytes = ascii.encode(type);
  out.add(typeBytes);
  out.add(data);
  _writeUint32BE(out, _crc32([...typeBytes, ...data]));
}

Uint8List _encodeRgbaPng({
  required int width,
  required int height,
  required int r,
  required int g,
  required int b,
  bool grid = false,
}) {
  final raw = BytesBuilder(copy: false);
  for (var y = 0; y < height; y++) {
    raw.addByte(0);
    for (var x = 0; x < width; x++) {
      final isLine = grid && (x % 16 == 0 || y % 16 == 0);
      raw.addByte(isLine ? (r - 20).clamp(0, 255) : r);
      raw.addByte(isLine ? (g - 15).clamp(0, 255) : g);
      raw.addByte(isLine ? (b - 15).clamp(0, 255) : b);
      raw.addByte(255);
    }
  }
  final compressed = zlib.encode(raw.toBytes());

  final png = BytesBuilder(copy: false);
  png.add(const [137, 80, 78, 71, 13, 10, 26, 10]);
  final ihdr = BytesBuilder(copy: false);
  _writeUint32BE(ihdr, width);
  _writeUint32BE(ihdr, height);
  ihdr.add(const [8, 6, 0, 0, 0]);
  _writeChunk(png, 'IHDR', ihdr.toBytes());
  _writeChunk(png, 'IDAT', compressed);
  _writeChunk(png, 'IEND', const []);
  return png.toBytes();
}

class _StubHttpClient implements HttpClient {
  final Uint8List tilePng;
  final Uint8List photoPng;

  _StubHttpClient({required this.tilePng, required this.photoPng});

  @override
  bool autoUncompress = true;
  @override
  Duration? connectionTimeout;
  @override
  Duration idleTimeout = const Duration(seconds: 15);
  @override
  int? maxConnectionsPerHost;
  @override
  String? userAgent;

  @override
  Future<HttpClientRequest> getUrl(Uri url) async =>
      _StubHttpRequest(url, url.host.contains('tile') ? tilePng : photoPng);

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) => getUrl(url);

  @override
  Future<HttpClientRequest> open(
    String method,
    String host,
    int port,
    String path,
  ) =>
      getUrl(Uri(scheme: 'https', host: host, port: port, path: path));

  @override
  void close({bool force = false}) {}

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _StubHttpRequest implements HttpClientRequest {
  @override
  final Uri uri;
  final Uint8List bytes;
  @override
  final HttpHeaders headers = _StubHttpHeaders();
  @override
  bool followRedirects = true;
  @override
  int maxRedirects = 5;
  @override
  bool persistentConnection = true;
  @override
  int contentLength = -1;
  @override
  bool bufferOutput = true;
  @override
  Encoding encoding = utf8;

  _StubHttpRequest(this.uri, this.bytes);

  @override
  void add(List<int> data) {}

  @override
  void addError(Object error, [StackTrace? stackTrace]) {}

  @override
  Future<void> addStream(Stream<List<int>> stream) async {
    await stream.drain<void>();
  }

  @override
  Future<void> flush() async {}

  @override
  void abort([Object? exception, StackTrace? stackTrace]) {}

  @override
  Future<HttpClientResponse> close() async => _StubHttpResponse(bytes);

  @override
  Future<HttpClientResponse> get done => close();

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _StubHttpHeaders implements HttpHeaders {
  @override
  ContentType? contentType;
  @override
  List<String>? operator [](String name) => null;
  @override
  String? value(String name) => null;
  @override
  void add(String name, Object value, {bool preserveHeaderCase = false}) {}
  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {}
  @override
  void removeAll(String name) {}
  @override
  void forEach(void Function(String name, List<String> values) action) {}
  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _StubHttpResponse extends Stream<List<int>> implements HttpClientResponse {
  final Uint8List bytes;
  final _headers = _StubHttpHeaders()..contentType = ContentType('image', 'png');
  _StubHttpResponse(this.bytes);

  @override
  int get statusCode => 200;
  @override
  String get reasonPhrase => 'OK';
  @override
  int get contentLength => bytes.length;
  @override
  HttpHeaders get headers => _headers;
  @override
  bool get isRedirect => false;
  @override
  List<RedirectInfo> get redirects => const [];
  @override
  bool get persistentConnection => false;
  @override
  HttpClientResponseCompressionState get compressionState =>
      HttpClientResponseCompressionState.notCompressed;

  @override
  StreamSubscription<List<int>> listen(
    void Function(List<int> event)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) {
    return Stream<List<int>>.fromIterable([bytes]).listen(
      onData,
      onError: onError,
      onDone: onDone,
      cancelOnError: cancelOnError,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class _PassiveLocationService implements LocationService {
  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.denied;
  @override
  Future<LocationPermissionState> requestPermission() async =>
      LocationPermissionState.denied;
  @override
  Future<bool> isServiceEnabled() async => true;
  @override
  Future<LocationFix> currentFix() async => LocationFix(
        position: const LatLng(20.95161, 107.08520),
        accuracyMeters: 15,
        timestamp: DateTime(2026, 11, 25, 1, 45),
      );
  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95161, 107.08520);
  @override
  Future<bool> openAppSettings() async => true;
  @override
  Future<bool> openLocationSettings() async => true;
}

class _NoopSocialPort implements AuthSocialPort {
  @override
  Future<SocialAuthResult> signInWithFacebook() async =>
      const SocialAuthCancelled();
  @override
  Future<SocialAuthResult> signInWithGoogle() async =>
      const SocialAuthCancelled();
  @override
  Future<void> signOutAll() async {}
}

class _ScreenshotBackendAdapter implements HttpClientAdapter {
  final Map<String, Map<String, dynamic>> _tripsById = {
    'trip-halong-001': {
      'id': 'trip-halong-001',
      'userId': 'user-halong-1',
      'destinationId': _haLongDestId,
      'destination': {
        'id': _haLongDestId,
        'name': 'Hạ Long',
        'slug': 'ha-long',
      },
      'title': 'Hành trình Hạ Long 2N1Đ',
      'description': 'Khám phá Tháp Đồng Hồ và Vịnh Hạ Long',
      'status': 'PLANNED',
      'totalBudget': 3500000,
      'currency': 'VND',
      'travelStyle': 'COMFORT',
      'interests': <String>['culture', 'nature'],
      'itineraries': [
        {
          'id': 'itin-day-1',
          'dayNumber': 1,
          'title': 'Trung tâm Hòn Gai',
          'items': [
            {
              'id': 'itin-item-1',
              'orderIndex': 1,
              'activity': 'Tham quan $_clockTowerName',
              'placeId': _clockTowerId,
              'startTime': '09:00',
              'estimatedCost': 0,
              'notes': 'Ngã 5 Bến Đoan, Phường Bạch Đằng',
              'place': {
                'id': _clockTowerId,
                'name': _clockTowerName,
                'address': 'Ngã 5 Bến Đoan, Phường Bạch Đằng, Hạ Long',
              },
            },
          ],
        },
      ],
    },
  };

  Map<String, dynamic> get _clockTowerJson => {
        'id': _clockTowerId,
        'name': _clockTowerName,
        'nameEn': 'Ha Long Clock Tower',
        'description':
            'Tháp Đồng Hồ tại ngã 5 Bến Đoan là điểm nhận diện trung tâm thành phố Hạ Long, gần bảo tàng và khu vực vịnh.',
        'address': 'Ngã 5 Bến Đoan, Phường Bạch Đằng, Hạ Long, Quảng Ninh',
        'latitude': 20.9516105,
        'longitude': 107.0851999,
        'rating': 4.6,
        'reviewCount': 18,
        'coverImage': 'https://upload.wikimedia.org/wikipedia/commons/thap.jpg',
        'images': ['https://upload.wikimedia.org/wikipedia/commons/thap.jpg'],
        'isVerified': true,
        'provenanceCount': 2,
        'category': {'name': 'attraction'},
        'destination': {
          'id': _haLongDestId,
          'name': 'Hạ Long',
          'slug': 'ha-long',
        },
        'source': {
          'name': 'OpenStreetMap',
          'sourceId': 'way/674228542',
          'canonicalUrl': 'https://www.openstreetmap.org/way/674228542',
          'license': 'ODbL 1.0',
          'attribution': '© OpenStreetMap contributors',
        },
        'enrichmentMeta': {
          'descriptionSourceUrl':
              'https://vi.wikipedia.org/wiki/H%E1%BA%A1_Long_(th%C3%A0nh_ph%E1%BB%91)',
          'descriptionLicense': 'CC BY-SA 4.0',
          'imageAttributions': [
            {'license': 'CC BY-SA 4.0', 'artist': 'Pdhadam'}
          ],
        },
        'reviews': [
          {
            'id': 'rev-1',
            'rating': 5.0,
            'content': 'Điểm hẹn đẹp vào buổi tối ngay trung tâm Hòn Gai.',
            'user': {
              'profile': {'displayName': 'Minh Anh'}
            },
          },
        ],
      };

  List<Map<String, dynamic>> get _places => [
        _clockTowerJson,
        {
          'id': '00000000-0000-4000-8000-000000000002',
          'name': 'Bảo tàng Quảng Ninh',
          'address': 'Trần Quốc Nghiễn, Hạ Long',
          'latitude': 20.9467,
          'longitude': 107.0921,
          'rating': 4.8,
          'reviewCount': 24,
          'coverImage':
              'https://upload.wikimedia.org/wikipedia/commons/baotang.jpg',
          'isVerified': true,
          'category': {'name': 'museum'},
          'destination': {
            'id': _haLongDestId,
            'name': 'Hạ Long',
            'slug': 'ha-long',
          },
        },
        {
          'id': '00000000-0000-4000-8000-000000000003',
          'name': 'Cầu Bãi Cháy',
          'address': 'Quốc lộ 18, Hạ Long',
          'latitude': 20.9619,
          'longitude': 107.0672,
          'rating': 4.5,
          'reviewCount': 12,
          'isVerified': true,
          'category': {'name': 'attraction'},
          'destination': {
            'id': _haLongDestId,
            'name': 'Hạ Long',
            'slug': 'ha-long',
          },
        },
      ];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final method = options.method.toUpperCase();
    final path = options.path;

    if (method == 'GET' && path == '/auth/reset-password/validate') {
      return _json(200, {
        'success': true,
        'data': {
          'valid': true,
          'expiresAt': '2026-11-25T10:00:00.000Z',
        },
      });
    }

    if (method == 'GET' && path == '/destinations') {
      return _json(200, {
        'success': true,
        'data': {
          'items': [
            {
              'id': _haLongDestId,
              'name': 'Hạ Long',
              'slug': 'ha-long',
              'province': 'Quảng Ninh',
              'region': 'north',
              'latitude': 20.9516,
              'longitude': 107.0852,
              'description': 'Kỳ quan thiên nhiên thế giới Vịnh Hạ Long.',
              'rating': 4.8,
              'reviewCount': 42,
              'isPopular': true,
              '_count': {'places': 197},
            },
            {
              'id': _haNoiDestId,
              'name': 'Hà Nội',
              'slug': 'ha-noi',
              'province': 'Hà Nội',
              'region': 'north',
              'latitude': 21.0285,
              'longitude': 105.8542,
              'description': 'Thủ đô ngàn năm văn hiến.',
              'rating': 4.7,
              'reviewCount': 80,
              'isPopular': true,
              '_count': {'places': 240},
            },
            {
              'id': _daNangDestId,
              'name': 'Đà Nẵng',
              'slug': 'da-nang',
              'province': 'Đà Nẵng',
              'region': 'central',
              'latitude': 16.0544,
              'longitude': 108.2022,
              'description': 'Thành phố biển đáng sống.',
              'rating': 4.8,
              'reviewCount': 64,
              'isPopular': true,
              '_count': {'places': 185},
            },
          ],
        },
      });
    }

    if (method == 'GET' && path == '/places/trending') {
      return _json(200, {
        'success': true,
        'data': {'items': _places},
      });
    }

    if (method == 'GET' && path == '/places') {
      final search =
          (options.queryParameters['search']?.toString() ?? '').trim();
      var list = _places;
      if (search.isNotEmpty) {
        list = list
            .where((p) => (p['name'] as String)
                .toLowerCase()
                .contains(search.toLowerCase()))
            .toList();
      }
      return _json(200, {
        'success': true,
        'data': {'items': list, 'total': list.length},
      });
    }

    if (method == 'GET' && path == '/places/$_clockTowerId') {
      return _json(200, {'success': true, 'data': _clockTowerJson});
    }

    if (method == 'GET' && path == '/places/$_clockTowerId/youtube-updates') {
      return _json(200, {
        'success': true,
        'data': {
          'placeId': _clockTowerId,
          'placeName': _clockTowerName,
          'destinationId': _haLongDestId,
          'destinationSlug': 'ha-long',
          'destinationName': 'Hạ Long',
          'governanceRole': 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
          'notPrimaryFactualCorpus': true,
          'serverDeliveredAt': '2026-11-25T01:49:30.000Z',
          'realtimeSlaMaxLatencyMs': 300000,
          'total': 1,
          'items': [
            {
              'id': 'yt-thap-dong-ho-1',
              'placeId': _clockTowerId,
              'destinationId': _haLongDestId,
              'destinationSlug': 'ha-long',
              'scope': 'POI',
              'source': 'youtube',
              'channelId': 'UC_HALONG_TRAVEL',
              'channelTitle': 'Hạ Long Explorer',
              'videoId': 'hlClockTower2026',
              'videoUrl': 'https://www.youtube.com/watch?v=hlClockTower2026',
              'title': 'Toàn cảnh Tháp Đồng Hồ Hạ Long lung linh về đêm',
              'description': 'Cập nhật thực tế tại ngã 5 Bến Đoan, Hạ Long.',
              'tags': ['ha-long', 'thap-dong-ho'],
              'publishedAt': '2026-11-25T01:49:15.000Z',
              'receivedAt': '2026-11-25T01:49:27.000Z',
              'updatedAt': '2026-11-25T01:49:20.000Z',
              'sourceUpdatedAt': '2026-11-25T01:49:20.000Z',
              'lastReceivedAt': '2026-11-25T01:49:27.000Z',
              'ingestLatencyMs': 12000,
              'deliveryLagMs': 12000,
              'groundingBasis': 'EXPLICIT_POI_REF_AND_TEXT_MATCH',
              'groundingEvidence': {'matched': true},
            },
          ],
          'cityFallbackTotal': 0,
          'cityFallbackItems': [],
        },
      });
    }

    if (method == 'GET' && path == '/users/me') {
      return _json(200, {
        'success': true,
        'data': {
          'id': 'user-halong-1',
          'email': 'traveler@gomate.vn',
          'profile': {'displayName': 'Hải Nam'},
          'preferences': {
            'interests': ['culture', 'nature']
          },
        },
      });
    }

    if (method == 'GET' && path == '/trips') {
      return _json(
          200, {'success': true, 'data': _tripsById.values.toList()});
    }

    final tripMatch = RegExp(r'^/trips/([^/]+)$').firstMatch(path);
    if (method == 'GET' && tripMatch != null) {
      final trip = _tripsById[tripMatch.group(1)!];
      if (trip != null) {
        return _json(200, {'success': true, 'data': trip});
      }
    }

    return _json(404, {'message': 'Not found'});
  }

  ResponseBody _json(int code, Map<String, dynamic> payload) {
    return ResponseBody.fromString(
      jsonEncode(payload),
      code,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

ProviderContainer _createContainer(_ScreenshotBackendAdapter backend) {
  return ProviderContainer(
    overrides: [
      authSocialPortProvider.overrideWithValue(_NoopSocialPort()),
      locationServiceProvider.overrideWithValue(_PassiveLocationService()),
      youtubeClockProvider.overrideWithValue(
        () => DateTime.utc(2026, 11, 25, 1, 50, 0),
      ),
      apiClientProvider.overrideWith((ref) {
        final epoch = ref.read(sessionEpochControllerProvider);
        return createApiClient(
          baseUrlOverride: 'http://localhost:3000',
          sessionEpoch: epoch,
        )..httpClientAdapter = backend;
      }),
    ],
  );
}

Future<void> _pump(WidgetTester tester, [int count = 6]) async {
  for (var i = 0; i < count; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

Future<void> _capture(
  WidgetTester tester,
  GlobalKey boundaryKey,
  String outDir,
  String fileName,
) async {
  if (outDir.isEmpty) return;
  await _pump(tester, 4);
  final boundary =
      boundaryKey.currentContext!.findRenderObject()! as RenderRepaintBoundary;
  final pngBytes = await tester.runAsync(() async {
    final image = await boundary.toImage(pixelRatio: 1.0);
    expect(image.width, 390);
    expect(image.height, 844);
    final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    return byteData!.buffer.asUint8List();
  });
  final dir = Directory(outDir);
  if (!dir.existsSync()) dir.createSync(recursive: true);
  final file = File('${dir.path}${Platform.pathSeparator}$fileName');
  file.writeAsBytesSync(pngBytes!);
}

void main() {
  late Uint8List tilePng;
  late Uint8List photoPng;
  late Directory cacheTempDir;

  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    cacheTempDir = Directory('build/test_img_cache');
    if (!cacheTempDir.existsSync()) {
      cacheTempDir.createSync(recursive: true);
    }
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      (MethodCall call) async => cacheTempDir.path,
    );
    await _loadMaterialFonts();
    tilePng = _encodeRgbaPng(
      width: 64,
      height: 64,
      r: 230,
      g: 244,
      b: 241,
      grid: true,
    );
    photoPng = _encodeRgbaPng(
      width: 256,
      height: 172,
      r: 15,
      g: 118,
      b: 110,
    );
  });

  tearDownAll(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      null,
    );
    if (cacheTempDir.existsSync()) {
      try {
        cacheTempDir.deleteSync(recursive: true);
      } catch (_) {}
    }
  });

  testWidgets('Capture After 390x844 Tháp Đồng Hồ & Auth screenshots',
      (tester) async {
    await HttpOverrides.runZoned(() async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final backend = _ScreenshotBackendAdapter();
      final shotKey = GlobalKey();

      // 1. LoginScreen (with redirect notice, OAuth buttons, Forgot Password, Cancel Login)
      SharedPreferences.setMockInitialValues({});
      var container = _createContainer(backend);
      await tester.pumpWidget(
        RepaintBoundary(
          key: shotKey,
          child: UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(
              debugShowCheckedModeBanner: false,
              theme: AppTheme.lightTheme.copyWith(
                textTheme: AppTheme.lightTheme.textTheme.apply(
                  fontFamily: 'Roboto',
                ),
                appBarTheme: AppTheme.lightTheme.appBarTheme.copyWith(
                  titleTextStyle:
                      AppTypography.h3.copyWith(fontFamily: 'Roboto'),
                ),
              ),
              routerConfig: container.read(appRouterProvider),
            ),
          ),
        ),
      );
      await _pump(tester, 6);
      container.read(appRouterProvider).go(
          '/login?redirect=${Uri.encodeComponent('/places/$_clockTowerId')}');
      await _pump(tester, 6);
      expect(find.byType(LoginScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '01_login.png');

      // 2. RegisterScreen
      container.read(appRouterProvider).go(
          '/register?redirect=${Uri.encodeComponent('/places/$_clockTowerId')}');
      await _pump(tester, 6);
      expect(find.byType(RegisterScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '02_register.png');

      // 10. ForgotPasswordScreen
      container.read(appRouterProvider).go('/forgot-password');
      await _pump(tester, 6);
      expect(find.byType(ForgotPasswordScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '10_forgot_password.png');

      // 11. ResetPasswordScreen (validated token)
      container.read(appRouterProvider).go('/reset-password?token=valid-tok');
      await _pump(tester, 6);
      expect(find.byType(ResetPasswordScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '11_reset_password.png');

      await tester.pumpWidget(const SizedBox.shrink());
      container.dispose();

      // 3-9. Authenticated Tháp Đồng Hồ journey
      SharedPreferences.setMockInitialValues({
        'access_token': _validAccessToken,
        'refresh_token': _validRefreshToken,
      });
      container = _createContainer(backend);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        RepaintBoundary(
          key: shotKey,
          child: UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(
              debugShowCheckedModeBanner: false,
              theme: AppTheme.lightTheme.copyWith(
                textTheme: AppTheme.lightTheme.textTheme.apply(
                  fontFamily: 'Roboto',
                ),
                appBarTheme: AppTheme.lightTheme.appBarTheme.copyWith(
                  titleTextStyle:
                      AppTypography.h3.copyWith(fontFamily: 'Roboto'),
                ),
              ),
              routerConfig: container.read(appRouterProvider),
            ),
          ),
        ),
      );
      await _pump(tester, 8);
      expect(find.byType(HomeScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '03_home_halong.png');

      // 4. DestinationPlacesSheet for Hạ Long
      final haLongCard = find.byKey(const Key('home_dest_ha-long'));
      await tester.ensureVisible(haLongCard);
      await _pump(tester, 2);
      await tester.tap(haLongCard);
      await _pump(tester, 8);
      await _capture(
          tester, shotKey, _effectiveOutDir, '04_destination_places_halong.png');

      Navigator.of(tester
              .element(find.byKey(const Key('destination_places_search_bar'))))
          .pop();
      await _pump(tester, 4);

      // 5. MapScreen + PlacePreviewSheet for Tháp Đồng Hồ
      container.read(appRouterProvider).go('/map');
      await _pump(tester, 6);
      unawaited(container.read(mapProvider.notifier).selectDestination('ha-long'));
      await _pump(tester, 10);
      final clockModel = PlaceModel.fromJson(backend._clockTowerJson);
      container.read(mapProvider.notifier).selectPlace(clockModel);
      await _pump(tester, 6);
      await _capture(tester, shotKey, _effectiveOutDir, '05_map_place_preview.png');

      // 6. PlaceDetailScreen for Tháp Đồng Hồ (top view + scrolled YouTube freshness view)
      container.read(appRouterProvider).push('/places/$_clockTowerId');
      await _pump(tester, 8);
      expect(find.byType(PlaceDetailScreen), findsOneWidget);
      await _capture(
          tester, shotKey, _effectiveOutDir, '06_place_detail_thap_dong_ho.png');

      final ytSection = find.byKey(const Key('place_youtube_freshness_section'));
      await tester.ensureVisible(ytSection);
      await _pump(tester, 4);
      expect(find.text('Thời gian thực'), findsOneWidget);
      await _capture(
        tester,
        shotKey,
        _effectiveOutDir,
        '06b_place_detail_youtube_freshness.png',
      );

      // 7. SavePlaceToTripSheet
      await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
      await _pump(tester, 8);
      expect(find.byKey(const Key('save_place_to_trip_sheet')), findsOneWidget);
      await _capture(
          tester, shotKey, _effectiveOutDir, '07_save_place_to_trip.png');

      Navigator.of(
              tester.element(find.byKey(const Key('save_place_to_trip_sheet'))))
          .pop();
      await _pump(tester, 4);

      // 8. TripListScreen
      container.read(appRouterProvider).go('/trips');
      await _pump(tester, 8);
      expect(find.byType(TripListScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '08_trip_list.png');

      // 9. TripDetailScreen
      await tester.tap(find.byKey(const Key('trip_card_trip-halong-001')));
      await _pump(tester, 8);
      expect(find.byType(TripDetailScreen), findsOneWidget);
      await _capture(tester, shotKey, _effectiveOutDir, '09_trip_detail.png');

      // Drain flutter_cache_manager's 10s cleanup timer before test exit.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(seconds: 11));
    },
        createHttpClient: (_) =>
            _StubHttpClient(tilePng: tilePng, photoPng: photoPng));
  });
}
