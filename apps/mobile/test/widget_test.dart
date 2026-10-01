import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/app/app.dart';

void main() {
  testWidgets('App starts without crashing', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: WanderApp()));
    await tester.pumpAndSettle();
    // App should render without exceptions
    expect(find.byType(MaterialApp), findsOneWidget);
  });

  testWidgets('Navigation bar has 5 tabs', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: WanderApp()));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Khám phá'), findsOneWidget);
    expect(find.text('Đồng hành'), findsOneWidget);
    expect(find.text('AI Agent'), findsOneWidget);
    expect(find.text('An toàn'), findsOneWidget);
    expect(find.text('Chuyến đi'), findsOneWidget);
  });
}
