import 'dart:async';
import 'package:flutter/material.dart';

/// Search bar overlay on the map.
///
/// An optional external [controller] lets the owner clear the visible text
/// (e.g. when a destination chip is tapped). When none is given the bar owns
/// a private controller, exactly as before.
class MapSearchBar extends StatefulWidget {
  final ValueChanged<String> onSearch;
  final VoidCallback onClear;
  final TextEditingController? controller;

  const MapSearchBar({
    super.key,
    required this.onSearch,
    required this.onClear,
    this.controller,
  });

  @override
  State<MapSearchBar> createState() => _MapSearchBarState();
}

class _MapSearchBarState extends State<MapSearchBar> {
  late final TextEditingController _controller =
      widget.controller ?? TextEditingController();
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onControllerChanged);
  }

  void _onControllerChanged() {
    // Keeps the clear (x) button in sync, also for external clears.
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.removeListener(_onControllerChanged);
    if (widget.controller == null) _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 500), () {
      // The text may have been cleared externally while the debounce ran.
      if (_controller.text.trim() != value.trim()) return;
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
                    _debounce?.cancel();
                    _controller.clear();
                    widget.onClear();
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
