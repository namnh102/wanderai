import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:wanderai_mobile/features/ai_chat/data/chat_models.dart';
import 'package:wanderai_mobile/features/ai_chat/data/chat_repository.dart';
import 'package:wanderai_mobile/features/ai_chat/presentation/ai_chat_screen.dart';
import 'package:wanderai_mobile/features/ai_chat/providers/chat_provider.dart';

class FakeChatRepositoryWithSources extends ChatRepository {
  List<String> nextSources = [];
  String nextReply = 'Hà Nội có nhiều di tích văn hóa nổi tiếng.';
  RetrievalStatus nextRetrievalStatus = RetrievalStatus.ok;

  FakeChatRepositoryWithSources() : super(Dio());

  @override
  Future<ChatResponse> sendMessage(ChatRequest request) async {
    return ChatResponse(
      reply: nextReply,
      sessionId: request.sessionId ?? 'session_sources_123',
      sources: nextSources,
      retrievalStatus: nextRetrievalStatus,
    );
  }
}

void main() {
  group('ChatResponse & ChatMessage Models - Sources & RetrievalStatus contract', () {
    test('1. ChatResponse.fromJson parses sources correctly when retrieval_status is ok', () {
      final json = {
        'reply': 'Bảo tàng Lịch sử Quốc gia nằm ở Hà Nội.',
        'session_id': 's_100',
        'tools_used': ['search_places'],
        'retrieval_status': 'ok',
        'sources': [
          'https://www.openstreetmap.org/way/37933256',
          'https://en.wikivoyage.org/wiki/Hanoi',
        ],
      };

      final response = ChatResponse.fromJson(json);
      expect(response.reply, 'Bảo tàng Lịch sử Quốc gia nằm ở Hà Nội.');
      expect(response.sessionId, 's_100');
      expect(response.toolsUsed, ['search_places']);
      expect(response.retrievalStatus, RetrievalStatus.ok);
      expect(response.sources.length, 2);
      expect(response.sources[0], 'https://www.openstreetmap.org/way/37933256');
      expect(response.sources[1], 'https://en.wikivoyage.org/wiki/Hanoi');
    });

    test('2. ChatResponse.fromJson suppresses sources when retrieval_status is empty or error', () {
      final jsonEmpty = {
        'reply': 'Xin chào!',
        'session_id': 's_101',
        'retrieval_status': 'empty',
        'sources': ['https://www.openstreetmap.org/node/should_be_suppressed'],
      };

      final responseEmpty = ChatResponse.fromJson(jsonEmpty);
      expect(responseEmpty.retrievalStatus, RetrievalStatus.empty);
      expect(responseEmpty.sources, isEmpty);

      final jsonError = {
        'reply': 'Fallback',
        'session_id': 's_102',
        'retrieval_status': 'error',
        'sources': ['https://www.openstreetmap.org/node/should_be_suppressed'],
      };

      final responseError = ChatResponse.fromJson(jsonError);
      expect(responseError.retrievalStatus, RetrievalStatus.error);
      expect(responseError.sources, isEmpty);
    });

    test('3. ChatResponse.fromJson handles missing or null sources (backward compatibility)', () {
      final jsonWithoutSources = {
        'reply': 'Tin nhắn cũ không có sources',
        'session_id': 's_legacy',
      };
      final response1 = ChatResponse.fromJson(jsonWithoutSources);
      expect(response1.sources, isEmpty);
      expect(response1.retrievalStatus, RetrievalStatus.ok);

      final jsonWithNullSources = {
        'reply': 'Tin nhắn với sources null',
        'session_id': 's_null',
        'sources': null,
      };
      final response2 = ChatResponse.fromJson(jsonWithNullSources);
      expect(response2.sources, isEmpty);
    });

    test('4. ChatMessage default and copyWith preserves sources and retrievalStatus', () {
      final msg = ChatMessage(
        id: 'msg_1',
        role: MessageRole.assistant,
        content: 'Nội dung',
        timestamp: DateTime(2026, 10, 4),
      );
      expect(msg.sources, isEmpty);
      expect(msg.retrievalStatus, RetrievalStatus.ok);

      final msgWithSources = msg.copyWith(
        sources: ['https://www.openstreetmap.org/node/12345'],
        retrievalStatus: RetrievalStatus.empty,
      );
      expect(msgWithSources.sources, ['https://www.openstreetmap.org/node/12345']);
      expect(msgWithSources.retrievalStatus, RetrievalStatus.empty);

      final copiedAgain = msgWithSources.copyWith(content: 'Nội dung mới');
      expect(copiedAgain.sources, ['https://www.openstreetmap.org/node/12345']);
      expect(copiedAgain.retrievalStatus, RetrievalStatus.empty);
    });
  });

  group('AiChatScreen Widget Tests - Sources UI Rendering', () {
    testWidgets('5. Assistant message with sources renders source section and chips', (tester) async {
      final fakeRepo = FakeChatRepositoryWithSources()
        ..nextReply = 'Bảo tàng Hồ Chí Minh mở cửa từ thứ Ba đến Chủ Nhật.'
        ..nextRetrievalStatus = RetrievalStatus.ok
        ..nextSources = [
          'https://www.openstreetmap.org/way/37933256',
          'https://en.wikivoyage.org/wiki/Hanoi',
        ];

      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pumpAndSettle();

      // Send a message to trigger assistant response with sources
      await container.read(chatProvider.notifier).sendMessage('Giờ mở cửa Bảo tàng Hồ Chí Minh?');
      await tester.pumpAndSettle();

      // Verify the reply content
      expect(find.text('Bảo tàng Hồ Chí Minh mở cửa từ thứ Ba đến Chủ Nhật.'), findsOneWidget);

      // Verify the sources section header
      expect(find.text('Nguồn tham khảo:'), findsOneWidget);

      // Verify source chips labels formatted safely
      expect(find.textContaining('OpenStreetMap'), findsOneWidget);
      expect(find.textContaining('Wikivoyage'), findsOneWidget);

      // Verify tooltip with full URL exists
      expect(find.byType(Tooltip), findsWidgets);
    });

    testWidgets('6. Assistant message with empty retrievalStatus renders ungrounded notice and no source chips', (tester) async {
      final fakeRepo = FakeChatRepositoryWithSources()
        ..nextReply = 'Xin chào, mình có thể giúp gì cho bạn?'
        ..nextRetrievalStatus = RetrievalStatus.empty
        ..nextSources = ['https://www.openstreetmap.org/node/999'];

      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pumpAndSettle();

      await container.read(chatProvider.notifier).sendMessage('Xin chào');
      await tester.pumpAndSettle();

      // Assistant message is rendered
      expect(find.text('Xin chào, mình có thể giúp gì cho bạn?'), findsOneWidget);

      // Source section MUST NOT be rendered even if sources list was non-empty
      expect(find.text('Nguồn tham khảo:'), findsNothing);
      expect(find.textContaining('OpenStreetMap'), findsNothing);
      // Ungrounded notice is rendered
      expect(find.textContaining('Chưa có nguồn đối chiếu trực tiếp'), findsOneWidget);
    });

    testWidgets('7. Handles very long URL without overflow', (tester) async {
      const veryLongUrl = 'https://www.openstreetmap.org/node/9999999999999999999999999999999999999999999999999999999999999999999999999999999999';
      final fakeRepo = FakeChatRepositoryWithSources()
        ..nextReply = 'Thông tin có URL rất dài.'
        ..nextSources = [veryLongUrl];

      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pumpAndSettle();

      await container.read(chatProvider.notifier).sendMessage('Kiểm tra long URL');
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Nguồn tham khảo:'), findsOneWidget);
    });

    testWidgets('8. Source chip is tappable without crash', (tester) async {
      final fakeRepo = FakeChatRepositoryWithSources()
        ..nextReply = 'Thông tin có nguồn có thể bấm.'
        ..nextSources = ['https://www.openstreetmap.org/way/12345'];

      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: AiChatScreen()),
        ),
      );
      await tester.pumpAndSettle();

      await container.read(chatProvider.notifier).sendMessage('Kiểm tra tap');
      await tester.pumpAndSettle();

      final chipFinder = find.textContaining('OpenStreetMap');
      expect(chipFinder, findsOneWidget);

      // Tap chip
      await tester.tap(chipFinder);
      await tester.pump();

      // No crash
      expect(tester.takeException(), isNull);
    });
  });
}
