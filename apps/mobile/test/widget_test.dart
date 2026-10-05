import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/app/app.dart';

void main() {
  testWidgets('App starts without crashing', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: WanderApp()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
