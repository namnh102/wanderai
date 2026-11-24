import 'dart:convert';
import 'dart:io';

import 'package:flutter_driver/flutter_driver.dart' as driver;
import 'package:integration_test/integration_test_driver.dart';

Future<void> main() async {
  await integrationDriver(
    responseDataCallback: (Map<String, dynamic>? data) async {
      if (data == null) return;

      final summaryReport = <String, dynamic>{
        'capturedAt': DateTime.now().toUtc().toIso8601String(),
        'custom_metrics': data['custom_metrics'] ?? const <String, dynamic>{},
        'scroll_timelines': <String, dynamic>{},
      };

      for (final key in const [
        'dest_sheet_scroll',
        'trip_list_scroll',
        'trip_detail_scroll',
      ]) {
        final rawTimeline = data[key];
        if (rawTimeline is Map<String, dynamic>) {
          final timeline = driver.Timeline.fromJson(rawTimeline);
          final summary = driver.TimelineSummary.summarize(timeline);
          (summaryReport['scroll_timelines'] as Map<String, dynamic>)[key] =
              summary.summaryJson;
        }
      }

      final outPath = Platform.environment['PERF_OUT_FILE'] ??
          '../../docs/beta/mobile/benchmarks/after_perf.json';
      final outFile = File(outPath);
      if (!outFile.parent.existsSync()) {
        outFile.parent.createSync(recursive: true);
      }
      outFile.writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(summaryReport),
      );
    },
  );
}
