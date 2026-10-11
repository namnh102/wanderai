import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/features/ai_chat/data/chat_models.dart';
import 'package:wanderai_mobile/features/ai_chat/data/chat_repository.dart';
import 'package:wanderai_mobile/features/ai_chat/presentation/ai_chat_screen.dart';
import 'package:wanderai_mobile/features/ai_chat/providers/chat_provider.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';

/// Fake repository for predictable, isolated AI chat testing without network calls.
class FakeChatRepository extends ChatRepository {
  bool shouldFail = false;
  int failStatusCode = 503;
  int delayMs = 0;
  final List<ChatRequest> sentRequests = [];
  String nextReply = 'Xin chao, minh la Wandy!';

  FakeChatRepository() : super(Dio());

  @override
  Future<ChatResponse> sendMessage(ChatRequest request) async {
    sentRequests.add(request);
    if (delayMs > 0) {
      await Future.delayed(Duration(milliseconds: delayMs));
    }
    if (shouldFail) {
      throw DioException(
        requestOptions: RequestOptions(path: '/ai/chat'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/ai/chat'),
          statusCode: failStatusCode,
          data: {'message': 'AI Service error'},
        ),
      );
    }
    return ChatResponse(
      reply: nextReply,
      sessionId: request.sessionId ?? 'session_123',
    );
  }
}

class FakeAuthRepository extends AuthRepository {
  bool loggedOut = false;
  FakeAuthRepository() : super(Dio());

  @override
  Future<void> logout() async {
    loggedOut = true;
  }

  @override
  Future<bool> restoreSession() async => true;
}

void main() {
  group('ChatNotifier & ChatRepository Unit Tests', () {
    test('1. Empty message is rejected and not sent', () async {
      final fakeRepo = FakeChatRepository();
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('');
      await notifier.sendMessage('   ');

      expect(container.read(chatProvider).messages, isEmpty);
      expect(fakeRepo.sentRequests, isEmpty);
    });

    test('2 & 3. User message and AI response appear in conversation', () async {
      final fakeRepo = FakeChatRepository();
      fakeRepo.nextReply = 'Da Nang co cau Rong rat dep!';
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('Goi y Da Nang');

      final state = container.read(chatProvider);
      expect(state.messages.length, 2);
      expect(state.messages[0].isUser, true);
      expect(state.messages[0].content, 'Goi y Da Nang');
      expect(state.messages[1].isAssistant, true);
      expect(state.messages[1].content, 'Da Nang co cau Rong rat dep!');
      expect(state.status, ChatStatus.success);
      expect(state.sessionId, 'session_123');
    });

    test('4. Loading state appears while waiting for AI', () async {
      final fakeRepo = FakeChatRepository()..delayMs = 100;
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      final future = notifier.sendMessage('Dang hoi...');

      // State immediately transitions to loading with user message present
      final loadingState = container.read(chatProvider);
      expect(loadingState.isLoading, true);
      expect(loadingState.messages.length, 1);
      expect(loadingState.messages.first.content, 'Dang hoi...');

      await future;

      // After completion, loading is false
      final doneState = container.read(chatProvider);
      expect(doneState.isLoading, false);
      expect(doneState.messages.length, 2);
    });

    test('5. API error produces error state and preserves user message', () async {
      final fakeRepo = FakeChatRepository()..shouldFail = true;
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('Cau hoi bi loi');

      final state = container.read(chatProvider);
      expect(state.hasError, true);
      expect(state.errorMessage, isNotNull);
      expect(state.lastFailedMessage, 'Cau hoi bi loi');
      expect(state.messages.length, 1); // User message still visible
    });

    test('6. Retry works for the failed message', () async {
      final fakeRepo = FakeChatRepository()..shouldFail = true;
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('Cau hoi can thu lai');
      expect(container.read(chatProvider).hasError, true);

      // Now service recovers
      fakeRepo.shouldFail = false;
      fakeRepo.nextReply = 'Tra loi thanh cong sau khi thu lai!';
      await notifier.retryLastMessage();

      final state = container.read(chatProvider);
      expect(state.hasError, false);
      expect(state.status, ChatStatus.success);
      expect(state.messages.any((m) => m.content == 'Tra loi thanh cong sau khi thu lai!'), true);
    });

    test('7. Conversation preserves session ID and message history order', () async {
      final fakeRepo = FakeChatRepository();
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('Cau 1');
      await notifier.sendMessage('Cau 2');

      final state = container.read(chatProvider);
      expect(state.messages.length, 4);
      expect(state.messages[0].content, 'Cau 1');
      expect(state.messages[1].isAssistant, true);
      expect(state.messages[2].content, 'Cau 2');
      expect(state.messages[3].isAssistant, true);

      // Verify second request sent the session ID
      expect(fakeRepo.sentRequests[1].sessionId, 'session_123');
    });

    test('Clear conversation resets messages and state', () async {
      final fakeRepo = FakeChatRepository();
      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('Tin nhan sap bi xoa');
      expect(container.read(chatProvider).messages.isNotEmpty, true);

      notifier.clearConversation();
      expect(container.read(chatProvider).messages, isEmpty);
      expect(container.read(chatProvider).sessionId, isNull);
    });

    test('401 unauthorized error triggers logout on AuthNotifier', () async {
      final fakeChatRepo = FakeChatRepository();
      // Configure 401 error
      fakeChatRepo.shouldFail = true;
      fakeChatRepo.failStatusCode = 401;
      final fakeAuthRepo = FakeAuthRepository();

      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeChatRepo),
          authRepositoryProvider.overrideWithValue(fakeAuthRepo),
        ],
      );

      // Verify initial auth state is initialized
      container.read(authProvider.notifier);

      // Force fakeChatRepo to throw 401
      final notifier = container.read(chatProvider.notifier);
      await notifier.sendMessage('Thử gọi khi token hết hạn');

      expect(container.read(chatProvider).hasError, true);
      expect(container.read(chatProvider).errorMessage, contains('het han'));
      expect(fakeAuthRepo.loggedOut, true);
      expect(container.read(authProvider).status, AuthStatus.unauthenticated);
    });
  });

  group('AiChatScreen Widget Tests', () {
    testWidgets('Renders empty state with suggestions when no messages', (tester) async {
      final fakeRepo = FakeChatRepository();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            chatRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pump();

      expect(find.text('Wandy'), findsOneWidget);
      expect(find.text('Xin chào, mình là Wandy!'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
      expect(find.byType(ActionChip), findsWidgets);
    });

    testWidgets('8. Send button sends message and displays bubbles', (tester) async {
      final fakeRepo = FakeChatRepository();
      fakeRepo.nextReply = 'Wandy xin chao ban!';

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            chatRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pump();

      // Enter text and tap send
      await tester.enterText(find.byType(TextField), 'Xin chao Wandy');
      await tester.tap(find.byType(IconButton).last); // Send icon
      await tester.pump(); // Start send

      // User bubble should be visible immediately
      expect(find.text('Xin chao Wandy'), findsOneWidget);

      await tester.pump(); // Finish future
      await tester.pumpAndSettle();

      // Assistant response should now be visible
      expect(find.text('Wandy xin chao ban!'), findsOneWidget);
      // Input text field should be cleared
      expect(find.text('Xin chao Wandy'), findsOneWidget); // In message bubble only
    });

    testWidgets('Error banner with retry button appears on failure', (tester) async {
      final fakeRepo = FakeChatRepository()..shouldFail = true;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            chatRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pump();

      await tester.enterText(find.byType(TextField), 'Tin gay loi');
      await tester.tap(find.byType(IconButton).last);
      await tester.pump();
      await tester.pumpAndSettle();

      // Error banner and retry button should be visible
      expect(find.text('Thử lại'), findsOneWidget);
    });
  });
}
