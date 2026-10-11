import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../data/trip_models.dart';
import '../providers/trip_provider.dart';

class TripFormScreen extends ConsumerStatefulWidget {
  final TripModel? existingTrip;

  const TripFormScreen({super.key, this.existingTrip});

  @override
  ConsumerState<TripFormScreen> createState() => _TripFormScreenState();
}

class _TripFormScreenState extends ConsumerState<TripFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _budgetController;

  DateTime? _startDate;
  DateTime? _endDate;
  String _currency = 'VND';
  String? _travelStyle;
  final Set<String> _selectedInterests = {};
  bool _submitting = false;

  static const _availableStyles = ['BACKPACKER', 'BUDGET', 'COMFORT', 'LUXURY'];
  static const _availableInterests = [
    'nature',
    'mountain',
    'beach',
    'culture',
    'food',
    'adventure',
  ];

  @override
  void initState() {
    super.initState();
    final trip = widget.existingTrip;
    _titleController = TextEditingController(text: trip?.title ?? '');
    _descriptionController = TextEditingController(text: trip?.description ?? '');
    _budgetController = TextEditingController(
      text: trip?.totalBudget != null ? trip!.totalBudget.toString() : '',
    );
    _startDate = trip?.startDate;
    _endDate = trip?.endDate;
    _currency = trip?.currency ?? 'VND';
    _travelStyle = trip?.travelStyle;
    if (trip?.interests != null) {
      _selectedInterests.addAll(trip!.interests);
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    _budgetController.dispose();
    super.dispose();
  }

  Future<void> _pickStartDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate ?? now,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 5),
    );
    if (picked != null) {
      setState(() {
        _startDate = picked;
        // If end date is before new start date, push end date
        if (_endDate != null && _endDate!.isBefore(_startDate!)) {
          _endDate = _startDate;
        }
      });
    }
  }

  Future<void> _pickEndDate() async {
    final base = _startDate ?? DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate ?? base,
      firstDate: base,
      lastDate: DateTime(base.year + 5),
    );
    if (picked != null) {
      setState(() => _endDate = picked);
    }
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;

    if (_startDate != null && _endDate != null && _endDate!.isBefore(_startDate!)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Ngay ket thuc phai sau ngay bat dau')),
      );
      return;
    }

    setState(() => _submitting = true);

    final budgetInt = int.tryParse(_budgetController.text.trim());

    if (widget.existingTrip == null) {
      // Create mode
      final req = CreateTripRequest(
        title: _titleController.text.trim(),
        description: _descriptionController.text.trim(),
        startDate: _startDate?.toIso8601String().split('T').first,
        endDate: _endDate?.toIso8601String().split('T').first,
        totalBudget: budgetInt,
        currency: _currency,
        travelStyle: _travelStyle,
        interests: _selectedInterests.toList(),
      );

      final created =
          await ref.read(tripListProvider.notifier).createTrip(req);
      if (mounted) {
        setState(() => _submitting = false);
        if (created != null) {
          context.pop();
        } else {
          final err = ref.read(tripListProvider).errorMessage ?? 'Loi tao chuyen di';
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
        }
      }
    } else {
      // Edit mode
      final req = UpdateTripRequest(
        title: _titleController.text.trim(),
        description: _descriptionController.text.trim(),
        startDate: _startDate?.toIso8601String().split('T').first,
        endDate: _endDate?.toIso8601String().split('T').first,
        totalBudget: budgetInt,
        currency: _currency,
        travelStyle: _travelStyle,
        interests: _selectedInterests.toList(),
      );

      final success = await ref
          .read(tripDetailProvider.notifier)
          .updateTrip(widget.existingTrip!.id, req);

      if (mounted) {
        setState(() => _submitting = false);
        if (success) {
          // Also refresh list
          ref.read(tripListProvider.notifier).loadTrips();
          context.pop();
        } else {
          final err = ref.read(tripDetailProvider).errorMessage ?? 'Loi cap nhat';
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.existingTrip != null;
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(isEdit ? 'Chinh sua chuyen di' : 'Tao chuyen di moi'),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
              // Title
              TextFormField(
                controller: _titleController,
                decoration: const InputDecoration(
                  labelText: 'Ten chuyen di *',
                  hintText: 'VD: Ha Giang mua hoa tam giac mach',
                  prefixIcon: Icon(Icons.title),
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Vui long nhap ten chuyen di' : null,
              ),
              const SizedBox(height: 16),

              // Date pickers row
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _pickStartDate,
                      icon: const Icon(Icons.calendar_today, size: 16),
                      label: Text(
                        _startDate == null
                            ? 'Ngay bat dau'
                            : '${_startDate!.day}/${_startDate!.month}/${_startDate!.year}',
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _pickEndDate,
                      icon: const Icon(Icons.event, size: 16),
                      label: Text(
                        _endDate == null
                            ? 'Ngay ket thuc'
                            : '${_endDate!.day}/${_endDate!.month}/${_endDate!.year}',
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Budget & Currency
              Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: TextFormField(
                      controller: _budgetController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Ngan sach uoc tinh',
                        hintText: '5000000',
                        prefixIcon: Icon(Icons.payments_outlined),
                      ),
                      validator: (v) {
                        if (v == null || v.isEmpty) return null;
                        final n = int.tryParse(v);
                        if (n == null || n < 0) return 'Ngan sach khong hop le';
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: DropdownButtonFormField<String>(
                      initialValue: _currency,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Tien te',
                        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'VND', child: Text('VND')),
                        DropdownMenuItem(value: 'USD', child: Text('USD')),
                      ],
                      onChanged: (v) {
                        if (v != null) setState(() => _currency = v);
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Travel Style
              Text(
                'Phong cach du lich',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: cs.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: _availableStyles.map((style) {
                  final isSelected = _travelStyle == style;
                  return ChoiceChip(
                    label: Text(style),
                    selected: isSelected,
                    onSelected: (selected) {
                      setState(() {
                        _travelStyle = selected ? style : null;
                      });
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),

              // Interests
              Text(
                'So thich / Hoat dong',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: cs.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: _availableInterests.map((interest) {
                  final isSelected = _selectedInterests.contains(interest);
                  return FilterChip(
                    label: Text(interest),
                    selected: isSelected,
                    onSelected: (selected) {
                      setState(() {
                        if (selected) {
                          _selectedInterests.add(interest);
                        } else {
                          _selectedInterests.remove(interest);
                        }
                      });
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 20),

              // Description
              TextFormField(
                controller: _descriptionController,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Mo ta / Ghi chu',
                  hintText: 'Ke hoach chi tiet hoac luu y...',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 28),

              // Submit Button
              ElevatedButton(
                onPressed: _submitting ? null : _handleSubmit,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size.fromHeight(50),
                ),
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Text(
                        isEdit ? 'Luu thay doi' : 'Tao chuyen di',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
}
