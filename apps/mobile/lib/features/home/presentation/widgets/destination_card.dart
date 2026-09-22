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
        onTap: () => debugPrint('Tapped ${destination.name}'),
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