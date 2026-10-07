import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_chip.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../data/profile_models.dart';
import '../providers/profile_provider.dart';

class PreferencesScreen extends ConsumerStatefulWidget {
  const PreferencesScreen({super.key});

  @override
  ConsumerState<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends ConsumerState<PreferencesScreen> {
  late TextEditingsControllerWrapper _minController;
  late TextEditingsControllerWrapper _maxController;
  final TextEditingController _customAvoidanceController = TextEditingController();
  final TextEditingController _customDietaryController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _minController = TextEditingsControllerWrapper();
    _maxController = TextEditingsControllerWrapper();
  }

  @override
  void dispose() {
    _minController.dispose();
    _maxController.dispose();
    _customAvoidanceController.dispose();
    _customDietaryController.dispose();
    super.dispose();
  }

  void _syncBudgetControllers(TravelPreferences prefs) {
    if (!_minController.isFocused && _minController.text != prefs.budgetMin.toString()) {
      _minController.text = prefs.budgetMin.toString();
    }
    if (!_maxController.isFocused && _maxController.text != prefs.budgetMax.toString()) {
      _maxController.text = prefs.budgetMax.toString();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(profileProvider);
    final notifier = ref.read(profileProvider.notifier);

    if (state.isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Sở thích du lịch')),
        body: const Center(child: AppLoading(message: 'Đang tải sở thích...')),
      );
    }

    _syncBudgetControllers(state.formPreferences);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sở thích du lịch'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Tải lại',
            onPressed: state.isSaving ? null : () => notifier.loadProfile(),
          ),
        ],
      ),
      body: ResponsiveWrapper(
        maxWidth: 720.0,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header description
              const Text(
                'Tùy chỉnh thông tin du lịch cá nhân',
                style: AppTypography.h2,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'GoMate sẽ gợi ý điểm đến và lộ trình phù hợp nhất dựa trên phong cách và sở thích của bạn.',
                style: AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: AppSpacing.md),

              // Status Banner (Success / Error)
              if (state.errorMessage != null) ...[
                Container(
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: AppColors.error.withValues(alpha: 0.1),
                    borderRadius: AppRadius.smRadius,
                    border: Border.all(color: AppColors.error),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: AppColors.error, size: 20),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(
                        child: Text(
                          state.errorMessage!,
                          style: AppTypography.bodyS.copyWith(color: AppColors.error),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],

              if (state.status == ProfileEditStatus.success && state.successMessage != null) ...[
                Container(
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: AppColors.success.withValues(alpha: 0.1),
                    borderRadius: AppRadius.smRadius,
                    border: Border.all(color: AppColors.success),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.check_circle_outline, color: AppColors.success, size: 20),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(
                        child: Text(
                          state.successMessage!,
                          style: AppTypography.bodyS.copyWith(color: AppColors.success),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],

              // 1. Travel Style
              _buildSectionTitle(context, 'Phong cách du lịch', Icons.explore_outlined),
              const SizedBox(height: AppSpacing.xs),
              _buildTravelStyleSelector(state.formPreferences.travelStyle, notifier),
              const SizedBox(height: AppSpacing.lg),

              // 2. Budget Range
              _buildSectionTitle(context, 'Khoảng ngân sách (VND)', Icons.payments_outlined),
              const SizedBox(height: AppSpacing.xs),
              _buildBudgetInputs(state.formPreferences, notifier),
              const SizedBox(height: AppSpacing.lg),

              // 3. Preferred Group Size
              _buildSectionTitle(context, 'Quy mô nhóm ưu tiên', Icons.groups_outlined),
              const SizedBox(height: AppSpacing.xs),
              _buildGroupSizeSelector(state.formPreferences.preferredGroup, notifier),
              const SizedBox(height: AppSpacing.lg),

              // 4. Canonical Interests
              _buildSectionTitle(context, 'Sở thích du lịch', Icons.favorite_border),
              const SizedBox(height: AppSpacing.xs),
              _buildInterestsSelector(state.formPreferences.interests, notifier),
              const SizedBox(height: AppSpacing.lg),

              // 5. Avoidances
              _buildSectionTitle(context, 'Những điều cần tránh', Icons.block_outlined),
              const SizedBox(height: AppSpacing.xs),
              _buildAvoidancesSelector(state.formPreferences.avoidances, notifier),
              const SizedBox(height: AppSpacing.lg),

              // 6. Dietary Needs
              _buildSectionTitle(context, 'Nhu cầu ăn uống đặc biệt', Icons.restaurant_menu_outlined),
              const SizedBox(height: AppSpacing.xs),
              _buildDietarySelector(state.formPreferences.dietaryNeeds, notifier),
              const SizedBox(height: AppSpacing.xl),

              // Save Button
              AppButton(
                text: 'Lưu sở thích du lịch',
                icon: Icons.save_outlined,
                isLoading: state.isSaving,
                onPressed: state.isSaving ? null : () => notifier.savePreferences(),
              ),
              const SizedBox(height: AppSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(BuildContext context, String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 20, color: AppColors.primary),
        const SizedBox(width: AppSpacing.xs),
        Text(title, style: AppTypography.h3),
      ],
    );
  }

  Widget _buildTravelStyleSelector(TravelStyle currentStyle, ProfileNotifier notifier) {
    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      children: TravelStyle.values.map((style) {
        final isSelected = style == currentStyle;
        return AppChip(
          label: style.label,
          icon: style.icon,
          isSelected: isSelected,
          onTap: () => notifier.setTravelStyle(style),
        );
      }).toList(),
    );
  }

  Widget _buildBudgetInputs(TravelPreferences prefs, ProfileNotifier notifier) {
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.sm),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _minController.controller,
                  focusNode: _minController.focusNode,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Ngân sách tối thiểu (VND)',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  onChanged: (val) {
                    final min = int.tryParse(val) ?? 0;
                    notifier.setBudget(min, prefs.budgetMax);
                  },
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: TextField(
                  controller: _maxController.controller,
                  focusNode: _maxController.focusNode,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Ngân sách tối đa (VND)',
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  onChanged: (val) {
                    final max = int.tryParse(val) ?? 0;
                    notifier.setBudget(prefs.budgetMin, max);
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildGroupSizeSelector(GroupSize currentGroup, ProfileNotifier notifier) {
    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      children: GroupSize.values.map((group) {
        final isSelected = group == currentGroup;
        return AppChip(
          label: group.label,
          icon: group.icon,
          isSelected: isSelected,
          onTap: () => notifier.setPreferredGroup(group),
        );
      }).toList(),
    );
  }

  Widget _buildInterestsSelector(List<String> selectedInterests, ProfileNotifier notifier) {
    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      children: kCanonicalInterests.map((item) {
        final isSelected = selectedInterests.contains(item.key);
        return AppChip(
          label: item.label,
          icon: item.icon,
          isSelected: isSelected,
          onTap: () => notifier.toggleInterest(item.key),
        );
      }).toList(),
    );
  }

  Widget _buildAvoidancesSelector(List<String> selectedAvoidances, ProfileNotifier notifier) {
    final allAvoidances = <String>{...kCommonAvoidances, ...selectedAvoidances}.toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: allAvoidances.map((tag) {
            final isSelected = selectedAvoidances.contains(tag);
            return AppChip(
              label: tag,
              isSelected: isSelected,
              onTap: () => notifier.toggleAvoidance(tag),
            );
          }).toList(),
        ),
        const SizedBox(height: AppSpacing.xs),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _customAvoidanceController,
                decoration: const InputDecoration(
                  hintText: 'Thêm điều cần tránh khác...',
                  border: OutlineInputBorder(),
                  contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.xs),
            IconButton(
              icon: const Icon(Icons.add_circle, color: AppColors.primary),
              onPressed: () {
                final text = _customAvoidanceController.text.trim();
                if (text.isNotEmpty) {
                  notifier.toggleAvoidance(text);
                  _customAvoidanceController.clear();
                }
              },
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDietarySelector(List<String> selectedDietary, ProfileNotifier notifier) {
    final allDietary = <String>{...kCommonDietaryNeeds, ...selectedDietary}.toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: allDietary.map((tag) {
            final isSelected = selectedDietary.contains(tag);
            return AppChip(
              label: tag,
              isSelected: isSelected,
              onTap: () => notifier.toggleDietary(tag),
            );
          }).toList(),
        ),
        const SizedBox(height: AppSpacing.xs),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _customDietaryController,
                decoration: const InputDecoration(
                  hintText: 'Thêm nhu cầu ăn uống khác...',
                  border: OutlineInputBorder(),
                  contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.xs),
            IconButton(
              icon: const Icon(Icons.add_circle, color: AppColors.primary),
              onPressed: () {
                final text = _customDietaryController.text.trim();
                if (text.isNotEmpty) {
                  notifier.toggleDietary(text);
                  _customDietaryController.clear();
                }
              },
            ),
          ],
        ),
      ],
    );
  }
}

class TextEditingsControllerWrapper {
  final TextEditingController controller = TextEditingController();
  final FocusNode focusNode = FocusNode();

  bool get isFocused => focusNode.hasFocus;
  String get text => controller.text;
  set text(String val) => controller.text = val;

  void dispose() {
    controller.dispose();
    focusNode.dispose();
  }
}
