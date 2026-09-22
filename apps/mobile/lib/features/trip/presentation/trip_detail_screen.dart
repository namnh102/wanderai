import 'package:flutter/material.dart';

class TripDetailScreen extends StatelessWidget {
  final String id;
  const TripDetailScreen({super.key, required this.id});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Trip \$id'),
      ),
      body: Center(
        child: Text(
          'Details for trip ID: \$id',
          style: const TextStyle(fontSize: 18),
        ),
      ),
    );
  }
}
