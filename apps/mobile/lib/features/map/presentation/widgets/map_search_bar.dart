import 'dart:async';
import 'package:flutter/material.dart';

/// Search bar overlay on the map.
class MapSearchBar extends StatefulWidget {
  final ValueChanged<String> onSearch;
  final VoidCallback onClear;

  const MapSearchBar({
    super.key,
    required this.onSearch,
    required this.onClear,
  });

  @override
  State<MapSearchBar> createState() => _MapSearchBarState();
}

class _MapSearchBarState extends State<MapSearchBar> {
  final _controller = TextEditingController();
  Timer? _debounce;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 500), () {
      if (value.trim().isEmpty) {
        widget.onClear();
      } else {
        widget.onSearch(value.trim());
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Material(
      elevation: 4,
      borderRadius: BorderRadius.circular(28),
      color: theme.colorScheme.surface,
      child: TextField(
        controller: _controller,
        onChanged: _onChanged,
        onSubmitted: (v) {
          _debounce?.cancel();
          if (v.trim().isNotEmpty) widget.onSearch(v.trim());
        },
        decoration: InputDecoration(
          hintText: 'Tìm địa điểm...',
          prefixIcon: Icon(Icons.search, color: theme.colorScheme.primary),
          suffixIcon: _controller.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, size: 20),
                  onPressed: () {
                    _controller.clear();
                    widget.onClear();
                    setState(() {});
                  },
                )
              : null,
          border: InputBorder.none,
          filled: false,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        style: theme.textTheme.bodyMedium,
      ),
    );
  }
}
