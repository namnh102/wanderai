import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/destination_provider.dart';
import 'widgets/category_chip.dart';
import 'widgets/destination_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final popularAsync = ref.watch(popularDestinationsProvider);
    final filteredAsync = ref.watch(filteredDestinationsProvider);
    final selectedRegion = ref.watch(regionFilterProvider);
    
    final categories = ['Tất cả', 'Biển', 'Núi', 'Thành phố', 'Văn hóa', 'Ẩm thực'];

    return Scaffold(
      appBar: AppBar(
        title: const Text('WanderAI', style: TextStyle(color: Colors.teal, fontWeight: FontWeight.bold)),
        actions: const [
          Padding(padding: EdgeInsets.all(8.0), child: CircleAvatar(child: Icon(Icons.person))),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(popularDestinationsProvider);
          ref.invalidate(filteredDestinationsProvider);
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              decoration: InputDecoration(
                hintText: 'Tìm kiếm điểm đến...',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(30)),
                contentPadding: const EdgeInsets.symmetric(horizontal: 20),
              ),
              onChanged: (val) => ref.read(searchProvider.notifier).state = val,
            ),
            const SizedBox(height: 16),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: categories.map((cat) => CategoryChip(
                  label: cat,
                  isSelected: selectedRegion == cat,
                  onSelected: () => ref.read(regionFilterProvider.notifier).state = cat,
                )).toList(),
              ),
            ),
            const SizedBox(height: 24),
            const Text('Điểm đến nổi bật', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            SizedBox(
              height: 180,
              child: popularAsync.when(
                data: (items) => ListView.builder(
                  scrollDirection: Axis.horizontal,
                  itemCount: items.length,
                  itemBuilder: (ctx, i) => SizedBox(width: 140, child: DestinationCard(destination: items[i])),
                ),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, s) => const Text('Lỗi tải dữ liệu'),
              ),
            ),
            const SizedBox(height: 24),
            const Text('Khám phá', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            filteredAsync.when(
              data: (items) => items.isEmpty ? const Center(child: Text('Không tìm thấy kết quả')) : GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  childAspectRatio: 0.8,
                  crossAxisSpacing: 10,
                  mainAxisSpacing: 10,
                ),
                itemCount: items.length,
                itemBuilder: (ctx, i) => DestinationCard(destination: items[i]),
              ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, s) => const Text('Lỗi tải dữ liệu'),
            ),
          ],
        ),
      ),
    );
  }
}