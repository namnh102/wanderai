import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/destination_provider.dart';
import 'widgets/destination_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final destinationsAsync = ref.watch(destinationsProvider);
    final filteredDestinations = ref.watch(filteredDestinationsProvider);
    final selectedRegion = ref.watch(selectedRegionProvider);

    final regions = ['Táº¥t cáº£', 'Miá» n Báº¯c', 'Miá» n Trung', 'Miá» n Nam'];

    return Scaffold(
      appBar: AppBar(
        title: const Text('WanderAI âœˆï¸ ', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.teal)),
        actions: [
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16.0),
            child: CircleAvatar(
              backgroundColor: Colors.teal,
              child: Icon(Icons.person, color: Colors.white),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(destinationsProvider);
        },
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Colors.teal, Color(0xFF004D40)],
                        ),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('KhÃ¡m phÃ¡', style: TextStyle(color: Colors.white70, fontSize: 16)),
                          Text('Viá»‡t Nam', style: TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),
                    TextField(
                      decoration: InputDecoration(
                        hintText: 'TÃ¬m kiáº¿m Ä‘á»‹a Ä‘iá»ƒm...',
                        prefixIcon: const Icon(Icons.search),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                      ),
                      onChanged: (value) => ref.read(searchQueryProvider.notifier).state = value,
                    ),
                    const SizedBox(height: 24),
                    SizedBox(
                      height: 40,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        itemCount: regions.length,
                        itemBuilder: (context, index) {
                          final region = regions[index];
                          final isSelected = (region == 'Táº¥t cáº£' && selectedRegion == null) || region == selectedRegion;
                          return Padding(
                            padding: const EdgeInsets.only(right: 8.0),
                            child: FilterChip(
                              label: Text(region),
                              selected: isSelected,
                              onSelected: (selected) {
                                ref.read(selectedRegionProvider.notifier).state = region == 'Táº¥t cáº£' ? null : region;
                              },
                              selectedColor: Colors.teal.withOpacity(0.2),
                              checkmarkColor: Colors.teal,
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),
            destinationsAsync.when(
              loading: () => const SliverFillRemaining(
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (err, stack) => SliverFillRemaining(
                child: Center(child: Text('Ä Ã£ xáº£y ra lá»—i')),
              ),
              data: (_) {
                if (filteredDestinations.isEmpty) {
                  return const SliverFillRemaining(
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('ðŸ žï¸ ', style: TextStyle(fontSize: 48)),
                          SizedBox(height: 16),
                          Text('KhÃ´ng tÃ¬m tháº¥y Ä‘á»‹a Ä‘iá»ƒm nÃ o'),
                        ],
                      ),
                    ),
                  );
                }

                final popular = filteredDestinations.where((d) => d['isPopular'] == true).toList();
                
                return SliverList(
                  delegate: SliverChildListDelegate([
                    if (popular.isNotEmpty) ...[
                      const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 16.0),
                        child: Text('Ná»•i báº­t', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(height: 16),
                      SizedBox(
                        height: 200,
                        child: ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          scrollDirection: Axis.horizontal,
                          itemCount: popular.length,
                          itemBuilder: (context, index) {
                            return Padding(
                              padding: const EdgeInsets.only(right: 16.0),
                              child: SizedBox(
                                width: 160,
                                child: DestinationCard(destination: popular[index]),
                              ),
                            );
                          },
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 16.0),
                      child: Text('KhÃ¡m phÃ¡', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                    ),
                    const SizedBox(height: 16),
                    GridView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        childAspectRatio: 0.8,
                        crossAxisSpacing: 16,
                        mainAxisSpacing: 16,
                      ),
                      itemCount: filteredDestinations.length,
                      itemBuilder: (context, index) {
                        return DestinationCard(destination: filteredDestinations[index]);
                      },
                    ),
                    const SizedBox(height: 24),
                  ]),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}