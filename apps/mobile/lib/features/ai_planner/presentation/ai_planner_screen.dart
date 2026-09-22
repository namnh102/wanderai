import 'package:flutter/material.dart';

class AiPlannerScreen extends StatelessWidget {
  const AiPlannerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Planner'),
      ),
      body: const Center(
        child: Text(
          'AI Planner',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}
