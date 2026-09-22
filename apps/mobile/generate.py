import os

files = {
    'lib/core/constants/app_constants.dart': '''
class AppConstants {
  static const String apiBaseUrl = 'http://10.0.2.2:3000'; // Android emulator
  static const String aiBaseUrl = 'http://10.0.2.2:8000';
  static const String appName = 'WanderAI';
  static const int pageSize = 20;
}
''',
    
    'lib/core/network/api_endpoints.dart': '''
class ApiEndpoints {
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String refresh = '/auth/refresh';
  static const String destinations = '/destinations';
  static const String aiChat = '/ai/chat';
}
''',

    'lib/core/network/api_client.dart': '''
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/app_constants.dart';

class ApiClient {
  late final Dio dio;

  ApiClient() {
    dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.apiBaseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
      ),
    );

    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final prefs = await SharedPreferences.getInstance();
        final token = prefs.getString('access_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (DioException e, handler) async {
        if (e.response?.statusCode == 401) {
          // TODO: Implement refresh token logic and logout if fail
        }
        return handler.next(e);
      },
    ));
  }
}

final apiClient = ApiClient().dio;
''',

    'lib/features/auth/data/auth_repository.dart': '''
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';

class AuthRepository {
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await apiClient.post(ApiEndpoints.login, data: {
      'email': email,
      'password': password,
    });
    return response.data;
  }

  Future<void> register(String name, String email, String password) async {
    await apiClient.post(ApiEndpoints.register, data: {
      'name': name,
      'email': email,
      'password': password,
    });
  }

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', accessToken);
    await prefs.setString('refresh_token', refreshToken);
  }

  Future<void> deleteTokens() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
  }
}
''',

    'lib/features/auth/providers/auth_provider.dart': '''
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../data/auth_repository.dart';

enum AuthStateStatus { initial, loading, authenticated, unauthenticated, error }

class AuthState {
  final AuthStateStatus status;
  final String? errorMessage;
  final Map<String, dynamic>? user;

  AuthState({required this.status, this.errorMessage, this.user});

  factory AuthState.initial() => AuthState(status: AuthStateStatus.initial);
  factory AuthState.loading() => AuthState(status: AuthStateStatus.loading);
  factory AuthState.authenticated(Map<String, dynamic> user) => AuthState(status: AuthStateStatus.authenticated, user: user);
  factory AuthState.unauthenticated() => AuthState(status: AuthStateStatus.unauthenticated);
  factory AuthState.error(String message) => AuthState(status: AuthStateStatus.error, errorMessage: message);
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;

  AuthNotifier(this._repo) : super(AuthState.initial()) {
    checkAuth();
  }

  Future<void> checkAuth() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token != null) {
      state = AuthState.authenticated({'id': '1', 'name': 'User'}); // Mock user
    } else {
      state = AuthState.unauthenticated();
    }
  }

  Future<void> login(String email, String password) async {
    try {
      state = AuthState.loading();
      final data = await _repo.login(email, password);
      await _repo.saveTokens(data['access_token'], data['refresh_token']);
      state = AuthState.authenticated({'email': email});
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> register(String name, String email, String password) async {
    try {
      state = AuthState.loading();
      await _repo.register(name, email, password);
      state = AuthState.unauthenticated(); // Require login after
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> logout() async {
    await _repo.deleteTokens();
    state = AuthState.unauthenticated();
  }
}

final authRepositoryProvider = Provider((ref) => AuthRepository());
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.read(authRepositoryProvider));
});
''',

    'lib/features/auth/presentation/login_screen.dart': '''
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _obscure = true;

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    ref.listen(authProvider, (previous, next) {
      if (next.status == AuthStateStatus.error) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(next.errorMessage ?? 'Lỗi')));
      } else if (next.status == AuthStateStatus.authenticated) {
        context.go('/');
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('WanderAI', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.teal)),
              const SizedBox(height: 32),
              TextField(
                controller: _emailCtrl,
                decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passCtrl,
                decoration: InputDecoration(
                  labelText: 'Mật khẩu',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                ),
                obscureText: _obscure,
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: Colors.teal),
                  onPressed: authState.status == AuthStateStatus.loading
                      ? null
                      : () => ref.read(authProvider.notifier).login(_emailCtrl.text, _passCtrl.text),
                  child: authState.status == AuthStateStatus.loading 
                      ? const CircularProgressIndicator(color: Colors.white) 
                      : const Text('Đăng nhập'),
                ),
              ),
              TextButton(
                onPressed: () => context.push('/register'),
                child: const Text('Chưa có tài khoản? Đăng ký'),
              )
            ],
          ),
        ),
      ),
    );
  }
}
''',

    'lib/features/auth/presentation/register_screen.dart': '''
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    ref.listen(authProvider, (previous, next) {
      if (next.status == AuthStateStatus.error) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(next.errorMessage ?? 'Lỗi')));
      } else if (next.status == AuthStateStatus.unauthenticated && previous?.status == AuthStateStatus.loading) {
        // Success
        ref.read(authProvider.notifier).login(_emailCtrl.text, _passCtrl.text);
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Đăng ký')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: 'Họ tên', border: OutlineInputBorder())),
            const SizedBox(height: 16),
            TextField(controller: _emailCtrl, decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder())),
            const SizedBox(height: 16),
            TextField(controller: _passCtrl, decoration: const InputDecoration(labelText: 'Mật khẩu', border: OutlineInputBorder()), obscureText: true),
            const SizedBox(height: 16),
            TextField(controller: _confirmCtrl, decoration: const InputDecoration(labelText: 'Xác nhận mật khẩu', border: OutlineInputBorder()), obscureText: true),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(backgroundColor: Colors.teal),
                onPressed: authState.status == AuthStateStatus.loading
                    ? null
                    : () {
                        if (_passCtrl.text == _confirmCtrl.text) {
                          ref.read(authProvider.notifier).register(_nameCtrl.text, _emailCtrl.text, _passCtrl.text);
                        }
                      },
                child: authState.status == AuthStateStatus.loading 
                    ? const CircularProgressIndicator(color: Colors.white) 
                    : const Text('Đăng ký'),
              ),
            ),
            TextButton(
              onPressed: () => context.pop(),
              child: const Text('Đã có tài khoản? Đăng nhập'),
            )
          ],
        ),
      ),
    );
  }
}
''',

    'lib/features/home/data/destination_model.dart': '''
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
''',

    'lib/features/home/data/destination_repository.dart': '''
import 'package:dio/dio.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import 'destination_model.dart';

class DestinationRepository {
  Future<List<Destination>> getDestinations({int page = 1, int limit = 20, String? search, String? region}) async {
    try {
      final query = {'page': page, 'limit': limit};
      if (search != null) query['search'] = search;
      if (region != null && region != 'Tất cả') query['region'] = region;
      
      final res = await apiClient.get(ApiEndpoints.destinations, queryParameters: query);
      return (res.data['items'] as List).map((e) => Destination.fromJson(e)).toList();
    } catch (e) {
      return []; // fallback
    }
  }

  Future<List<Destination>> getPopular() async {
    try {
      final res = await apiClient.get(ApiEndpoints.destinations, queryParameters: {'isPopular': true});
      return (res.data['items'] as List).map((e) => Destination.fromJson(e)).toList();
    } catch (e) {
      return [];
    }
  }
}
''',

    'lib/features/home/providers/destination_provider.dart': '''
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/destination_repository.dart';
import '../data/destination_model.dart';

final destinationRepositoryProvider = Provider((ref) => DestinationRepository());

final popularDestinationsProvider = FutureProvider<List<Destination>>((ref) {
  return ref.read(destinationRepositoryProvider).getPopular();
});

final searchProvider = StateProvider<String>((ref) => '');
final regionFilterProvider = StateProvider<String?>((ref) => 'Tất cả');

final filteredDestinationsProvider = FutureProvider<List<Destination>>((ref) {
  final search = ref.watch(searchProvider);
  final region = ref.watch(regionFilterProvider);
  return ref.read(destinationRepositoryProvider).getDestinations(
    search: search.isNotEmpty ? search : null,
    region: region,
  );
});
''',

    'lib/features/home/presentation/widgets/category_chip.dart': '''
import 'package:flutter/material.dart';

class CategoryChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onSelected;

  const CategoryChip({
    super.key,
    required this.label,
    required this.isSelected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8.0),
      child: FilterChip(
        label: Text(label, style: TextStyle(color: isSelected ? Colors.white : Colors.black)),
        selected: isSelected,
        onSelected: (_) => onSelected(),
        selectedColor: Colors.teal,
        checkmarkColor: Colors.white,
      ),
    );
  }
}
''',

    'lib/features/home/presentation/widgets/destination_card.dart': '''
import 'package:flutter/material.dart';
import '../../data/destination_model.dart';

class DestinationCard extends StatelessWidget {
  final Destination destination;

  const DestinationCard({super.key, required this.destination});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => print('Tapped \${destination.name}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Container(
                color: Colors.teal.shade200, // Placeholder
                width: double.infinity,
                child: destination.isPopular ? const Align(
                  alignment: Alignment.topRight,
                  child: Padding(
                    padding: EdgeInsets.all(8.0),
                    child: Icon(Icons.star, color: Colors.amber),
                  ),
                ) : null,
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(destination.name, style: const TextStyle(fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
                  Text(destination.province, style: Theme.of(context).textTheme.bodySmall),
                  Row(
                    children: [
                      const Icon(Icons.star, size: 14, color: Colors.amber),
                      Text(destination.rating.toString(), style: const TextStyle(fontSize: 12)),
                    ],
                  )
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
''',

    'lib/features/home/presentation/home_screen.dart': '''
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/destination_provider.dart';
import 'widgets/category_chip.dart';
import 'widgets/destination_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final popularAsync = ref.watch(popularDestinationsProvider);
    final filteredAsync = ref.watch(filteredDestinationsProvider);
    final selectedRegion = ref.watch(regionFilterProvider);
    
    final categories = ['Tất cả', 'Biển', 'Núi', 'Thành phố', 'Văn hóa', 'Ẩm thực'];

    return Scaffold(
      appBar: AppBar(
        title: const Text('WanderAI', style: TextStyle(color: Colors.teal, fontWeight: FontWeight.bold)),
        actions: const [
          Padding(padding: EdgeInsets.all(8.0), child: CircleAvatar(child: Icon(Icons.person))),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.refresh(popularDestinationsProvider);
          ref.refresh(filteredDestinationsProvider);
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              decoration: InputDecoration(
                hintText: 'Tìm kiếm điểm đến...',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(30)),
                contentPadding: const EdgeInsets.symmetric(horizontal: 20),
              ),
              onChanged: (val) => ref.read(searchProvider.notifier).state = val,
            ),
            const SizedBox(height: 16),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: categories.map((cat) => CategoryChip(
                  label: cat,
                  isSelected: selectedRegion == cat,
                  onSelected: () => ref.read(regionFilterProvider.notifier).state = cat,
                )).toList(),
              ),
            ),
            const SizedBox(height: 24),
            const Text('Điểm đến nổi bật', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            SizedBox(
              height: 180,
              child: popularAsync.when(
                data: (items) => ListView.builder(
                  scrollDirection: Axis.horizontal,
                  itemCount: items.length,
                  itemBuilder: (ctx, i) => SizedBox(width: 140, child: DestinationCard(destination: items[i])),
                ),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, s) => const Text('Lỗi tải dữ liệu'),
              ),
            ),
            const SizedBox(height: 24),
            const Text('Khám phá', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            filteredAsync.when(
              data: (items) => items.isEmpty ? const Center(child: Text('Không tìm thấy kết quả')) : GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  childAspectRatio: 0.8,
                  crossAxisSpacing: 10,
                  mainAxisSpacing: 10,
                ),
                itemCount: items.length,
                itemBuilder: (ctx, i) => DestinationCard(destination: items[i]),
              ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, s) => const Text('Lỗi tải dữ liệu'),
            ),
          ],
        ),
      ),
    );
  }
}
''',

    'lib/features/ai_chat/data/chat_model.dart': '''
class ChatMessage {
  final String id;
  final String content;
  final bool isUser;
  final DateTime timestamp;

  ChatMessage({required this.id, required this.content, required this.isUser, required this.timestamp});
}

class ChatResponse {
  final String reply;
  final String sessionId;

  ChatResponse({required this.reply, required this.sessionId});

  factory ChatResponse.fromJson(Map<String, dynamic> json) => ChatResponse(
    reply: json['reply'] ?? '',
    sessionId: json['sessionId'] ?? '',
  );
}
''',

    'lib/features/ai_chat/data/chat_repository.dart': '''
import 'package:dio/dio.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/constants/app_constants.dart';
import 'chat_model.dart';

class ChatRepository {
  Future<ChatResponse> sendMessage(String message, String? sessionId) async {
    try {
      final dio = Dio(BaseOptions(baseUrl: AppConstants.aiBaseUrl)); // specific URL
      final res = await dio.post(ApiEndpoints.aiChat, data: {
        'message': message,
        if (sessionId != null) 'sessionId': sessionId,
      });
      return ChatResponse.fromJson(res.data);
    } catch (e) {
      return ChatResponse(reply: 'Xin lỗi, Wandy đang gặp sự cố. Vui lòng thử lại sau.', sessionId: sessionId ?? 'new');
    }
  }
}
''',

    'lib/features/ai_chat/providers/chat_provider.dart': '''
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/chat_repository.dart';
import '../data/chat_model.dart';

class ChatState {
  final List<ChatMessage> messages;
  final bool isLoading;
  final String? sessionId;

  ChatState({this.messages = const [], this.isLoading = false, this.sessionId});

  ChatState copyWith({List<ChatMessage>? messages, bool? isLoading, String? sessionId}) {
    return ChatState(
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      sessionId: sessionId ?? this.sessionId,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ChatRepository _repo;

  ChatNotifier(this._repo) : super(ChatState());

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    
    final userMsg = ChatMessage(id: DateTime.now().toString(), content: text, isUser: true, timestamp: DateTime.now());
    state = state.copyWith(messages: [...state.messages, userMsg], isLoading: true);

    final response = await _repo.sendMessage(text, state.sessionId);

    final aiMsg = ChatMessage(id: DateTime.now().toString(), content: response.reply, isUser: false, timestamp: DateTime.now());
    state = state.copyWith(messages: [...state.messages, aiMsg], isLoading: false, sessionId: response.sessionId);
  }

  void clearChat() {
    state = ChatState();
  }
}

final chatRepositoryProvider = Provider((ref) => ChatRepository());
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.read(chatRepositoryProvider));
});
''',

    'lib/features/ai_chat/presentation/widgets/chat_bubble.dart': '''
import 'package:flutter/material.dart';
import '../../data/chat_model.dart';

class ChatBubble extends StatelessWidget {
  final ChatMessage message;

  const ChatBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: message.isUser ? Colors.teal : Colors.grey.shade200,
          borderRadius: BorderRadius.circular(16).copyWith(
            bottomRight: message.isUser ? const Radius.circular(0) : const Radius.circular(16),
            bottomLeft: !message.isUser ? const Radius.circular(0) : const Radius.circular(16),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message.content, style: TextStyle(color: message.isUser ? Colors.white : Colors.black87)),
            const SizedBox(height: 4),
            Text(
              '\${message.timestamp.hour}:\${message.timestamp.minute.toString().padLeft(2, '0')}',
              style: TextStyle(fontSize: 10, color: message.isUser ? Colors.white70 : Colors.black54),
            )
          ],
        ),
      ),
    );
  }
}
''',

    'lib/features/ai_chat/presentation/widgets/typing_indicator.dart': '''
import 'package:flutter/material.dart';

class TypingIndicator extends StatelessWidget {
  const TypingIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.all(8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: Colors.grey.shade200, borderRadius: BorderRadius.circular(16)),
        child: const Text('Wandy đang suy nghĩ...', style: TextStyle(color: Colors.black54, fontStyle: FontStyle.italic)),
      ),
    );
  }
}
''',

    'lib/features/ai_chat/presentation/ai_chat_screen.dart': '''
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/chat_provider.dart';
import 'widgets/chat_bubble.dart';
import 'widgets/typing_indicator.dart';

class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key});

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final _ctrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  void _send() {
    ref.read(chatProvider.notifier).sendMessage(_ctrl.text);
    _ctrl.clear();
    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent, duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatProvider);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Wandy 🤖'),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: () => ref.read(chatProvider.notifier).clearChat())
        ],
      ),
      body: Column(
        children: [
          if (state.messages.isEmpty)
            Expanded(
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text('Xin chào! Mình là Wandy...'),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      children: ['🏖 Gợi ý biển', '⛰ Gợi ý núi', '🍜 Ẩm thực', '💰 Budget']
                          .map((e) => ActionChip(label: Text(e), onPressed: () {
                                _ctrl.text = e;
                                _send();
                              }))
                          .toList(),
                    )
                  ],
                ),
              ),
            )
          else
            Expanded(
              child: ListView.builder(
                controller: _scrollCtrl,
                itemCount: state.messages.length + (state.isLoading ? 1 : 0),
                itemBuilder: (ctx, i) {
                  if (i == state.messages.length) return const TypingIndicator();
                  return ChatBubble(message: state.messages[i]);
                },
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _ctrl,
                    decoration: InputDecoration(
                      hintText: 'Nhắn với Wandy...',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                    ),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                IconButton(icon: const Icon(Icons.send, color: Colors.teal), onPressed: _send),
              ],
            ),
          )
        ],
      ),
    );
  }
}
''',

    'lib/core/router/app_router.dart': '''
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/ai_chat/presentation/ai_chat_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    redirect: (context, state) {
      final isAuth = authState.status == AuthStateStatus.authenticated;
      final isLoginRoute = state.matchedLocation == '/login' || state.matchedLocation == '/register';

      if (!isAuth && !isLoginRoute) return '/login';
      if (isAuth && isLoginRoute) return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(path: '/register', builder: (context, state) => const RegisterScreen()),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => Scaffold(
          body: child,
          bottomNavigationBar: BottomNavigationBar(
            currentIndex: _calculateSelectedIndex(state.matchedLocation),
            onTap: (idx) => _onItemTapped(idx, context),
            selectedItemColor: Colors.teal,
            unselectedItemColor: Colors.grey,
            items: const [
              BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
              BottomNavigationBarItem(icon: Icon(Icons.chat), label: 'Wandy'),
              BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Profile'),
            ],
          ),
        ),
        routes: [
          GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
          GoRoute(path: '/chat', builder: (context, state) => const AiChatScreen()),
          GoRoute(path: '/profile', builder: (context, state) => const ProfileScreen()),
        ],
      ),
    ],
  );
});

int _calculateSelectedIndex(String location) {
  if (location.startsWith('/chat')) return 1;
  if (location.startsWith('/profile')) return 2;
  return 0;
}

void _onItemTapped(int index, BuildContext context) {
  switch (index) {
    case 0: context.go('/'); break;
    case 1: context.go('/chat'); break;
    case 2: context.go('/profile'); break;
  }
}
''',

    'lib/features/profile/presentation/profile_screen.dart': '''
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/providers/auth_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user ?? {};

    return Scaffold(
      appBar: AppBar(title: const Text('Hồ sơ')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          CircleAvatar(radius: 40, child: Text(user['name']?.substring(0, 1) ?? 'U', style: const TextStyle(fontSize: 32))),
          const SizedBox(height: 16),
          Text(user['name'] ?? 'User', textAlign: TextAlign.center, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          Text(user['email'] ?? 'user@example.com', textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
          const SizedBox(height: 32),
          ListTile(leading: const Icon(Icons.language), title: const Text('Ngôn ngữ'), onTap: () {}),
          ListTile(leading: const Icon(Icons.notifications), title: const Text('Thông báo'), onTap: () {}),
          ListTile(leading: const Icon(Icons.dark_mode), title: const Text('Chế độ tối'), onTap: () {}),
          ListTile(leading: const Icon(Icons.info), title: const Text('Giới thiệu'), onTap: () {}),
          const SizedBox(height: 32),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => ref.read(authProvider.notifier).logout(),
            child: const Text('Đăng xuất', style: TextStyle(color: Colors.white)),
          )
        ],
      ),
    );
  }
}
'''
}

for path, content in files.items():
    full_path = os.path.join(r'd:\Do_an\wanderai\apps\mobile', path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\\n')
    print(f"Created {path}")

