import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/app_text_field.dart';
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
  String? _formError;

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
    _descriptionController =
        TextEditingController(text: trip?.description ?? '');
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

    if (_startDate != null &&
        _endDate != null &&
        _endDate!.isBefore(_startDate!)) {
      setState(() {
        _formError = 'Ngày kết thúc phải sau ngày bắt đầu';
      });
      return;
    }

    setState(() {
      _submitting = true;
      _formError = null;
    });

    final budgetInt = int.tryParse(_budgetController.text.trim());

    if (widget.existingTrip == null) {
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

      final created = await ref.read(tripListProvider.notifier).createTrip(req);
      if (mounted) {
        setState(() => _submitting = false);
        if (created != null) {
          context.pop();
        } else {
          setState(() {
            _formError =
                ref.read(tripListProvider).errorMessage ?? 'Lỗi tạo chuyến đi';
          });
        }
      }
    } else {
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
          ref.read(tripListProvider.notifier).loadTrips();
          context.pop();
        } else {
          setState(() {
            _formError =
                ref.read(tripDetailProvider).errorMessage ?? 'Lỗi cập nhật';
          });
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
        title: Text(isEdit ? 'Chỉnh sửa chuyến đi' : 'Tạo chuyến đi mới'),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_formError != null) ...[
                  AppStateBanner(
                    message: _formError!,
                    tone: AppStateBannerTone.error,
                  ),
                  const SizedBox(height: AppSpacing.md),
                ],
                // Title
                AppTextField(
                  controller: _titleController,
                  enabled: !_submitting,
                  labelText: 'Tên chuyến đi *',
                  hintText: 'VD: Hà Giang mùa hoa tam giác mạch',
                  prefixIcon: const Icon(Icons.title),
                  validator: (v) => (v == null || v.trim().isEmpty)
                      ? 'Vui lòng nhập tên chuyến đi'
                      : null,
                ),
                const SizedBox(height: 16),

                // Date pickers row
                Row(
                  children: [
                    Expanded(
                      child: AppButton(
                        variant: AppButtonVariant.secondary,
                        icon: Icons.calendar_today,
                        text: _startDate == null
                            ? 'Ngày bắt đầu'
                            : '${_startDate!.day}/${_startDate!.month}/${_startDate!.year}',
                        onPressed: _submitting ? null : _pickStartDate,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: AppButton(
                        variant: AppButtonVariant.secondary,
                        icon: Icons.event,
                        text: _endDate == null
                            ? 'Ngày kết thúc'
                            : '${_endDate!.day}/${_endDate!.month}/${_endDate!.year}',
                        onPressed: _submitting ? null : _pickEndDate,
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
                      child: AppTextField(
                        controller: _budgetController,
                        enabled: !_submitting,
                        keyboardType: TextInputType.number,
                        labelText: 'Ngân sách ước tính',
                        hintText: '5000000',
                        prefixIcon: const Icon(Icons.payments_outlined),
                        validator: (v) {
                          if (v == null || v.isEmpty) return null;
                          final n = int.tryParse(v);
                          if (n == null || n < 0) return 'Ngân sách không hợp lệ';
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
                          labelText: 'Tiền tệ',
                          contentPadding: EdgeInsets.symmetric(
                              horizontal: 10, vertical: 12),
                        ),
                        items: const [
                          DropdownMenuItem(value: 'VND', child: Text('VND')),
                          DropdownMenuItem(value: 'USD', child: Text('USD')),
                        ],
                        onChanged: _submitting
                            ? null
                            : (v) {
                                if (v != null) setState(() => _currency = v);
                              },
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // Travel Style
                Text(
                  'Phong cách du lịch',
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
                  'Sở thích / Hoạt động',
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
                AppTextField(
                  controller: _descriptionController,
                  enabled: !_submitting,
                  maxLines: 3,
                  labelText: 'Mô tả / Ghi chú',
                  hintText: 'Kế hoạch chi tiết hoặc lưu ý...',
                ),
                const SizedBox(height: 28),

                // Submit Button
                AppButton(
                  text: isEdit ? 'Lưu thay đổi' : 'Tạo chuyến đi',
                  isLoading: _submitting,
                  onPressed: _submitting ? null : _handleSubmit,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
