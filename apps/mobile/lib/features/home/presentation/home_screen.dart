import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('WanderAI'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          SearchBar(
            leading: const Icon(Icons.search),
            hintText: 'Search destinations...',
            onTap: () {},
          ),
          const SizedBox(height: 24),
          Text('Categories', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildCategory(Icons.beach_access, 'Beach'),
              _buildCategory(Icons.landscape, 'Mountain'),
              _buildCategory(Icons.location_city, 'City'),
              _buildCategory(Icons.museum, 'Culture'),
              _buildCategory(Icons.restaurant, 'Food'),
            ],
          ),
          const SizedBox(height: 24),
          Text('Trending Destinations', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: 3,
            itemBuilder: (context, index) {
              return Card(
                margin: const EdgeInsets.only(bottom: 16),
                child: ListTile(
                  leading: Container(
                    width: 60,
                    color: Colors.grey[300],
                    child: const Icon(Icons.image),
                  ),
                  title: Text('Destination \${index + 1}'),
                  subtitle: const Text('A beautiful place to visit.'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                ),
              );
            },
          )
        ],
      ),
    );
  }

  Widget _buildCategory(IconData icon, String label) {
    return Column(
      children: [
        CircleAvatar(
          radius: 24,
          child: Icon(icon),
        ),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}
