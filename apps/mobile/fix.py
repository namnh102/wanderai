import os

path_repo = 'lib/features/home/data/destination_repository.dart'
with open(path_repo, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("final query = {'page': page, 'limit': limit};", "final query = <String, dynamic>{'page': page, 'limit': limit};").replace("import 'package:dio/dio.dart';", "")
with open(path_repo, 'w', encoding='utf-8') as f:
    f.write(content)

path_home = 'lib/features/home/presentation/home_screen.dart'
with open(path_home, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("ref.refresh(popularDestinationsProvider);", "ref.invalidate(popularDestinationsProvider);").replace("ref.refresh(filteredDestinationsProvider);", "ref.invalidate(filteredDestinationsProvider);")
with open(path_home, 'w', encoding='utf-8') as f:
    f.write(content)
