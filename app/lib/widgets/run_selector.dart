import 'package:flutter/material.dart';

import '../runs.dart';
import '../theme.dart';

/// Selector de las corridas (§10). Una fila por escenario, en el orden del
/// menu de la sonda. No se supone que cada escenario tenga A y C: VUELO solo
/// tiene Clase A y ocupa su fila entera (antes era una rejilla fija de 2×3).
class RunSelector extends StatelessWidget {
  final String scenario;
  final String cls;
  final bool enabled;
  final void Function(String scenario, String cls) onSelect;

  /// Sonda conectada (D-65): las corridas que no admite salen deshabilitadas.
  final String sonda;

  const RunSelector({
    super.key,
    required this.scenario,
    required this.cls,
    required this.enabled,
    required this.onSelect,
    this.sonda = kSondaTbeam,
  });

  @override
  Widget build(BuildContext context) {
    final filas = <Widget>[];
    for (final esc in escenariosEnOrden) {
      final corridas = kRuns.where((r) => r.scenario == esc).toList();
      if (filas.isNotEmpty) filas.add(const SizedBox(height: 8));
      filas.add(SizedBox(
        height: 62,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < corridas.length; i++) ...[
              if (i > 0) const SizedBox(width: 8),
              Expanded(
                child: _RunChip(
                  run: corridas[i],
                  selected: corridas[i].scenario == scenario &&
                      corridas[i].cls == cls,
                  enabled: enabled && corridaAdmitida(corridas[i], sonda),
                  onTap: () => onSelect(corridas[i].scenario, corridas[i].cls),
                ),
              ),
            ],
          ],
        ),
      ));
    }
    return Column(mainAxisSize: MainAxisSize.min, children: filas);
  }
}

class _RunChip extends StatelessWidget {
  final RunDef run;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  const _RunChip({
    required this.run,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final border = selected ? AppColors.gold : const Color(0x33FFFFFF);
    final bg = selected ? AppColors.gold.withOpacity(0.12) : AppColors.night1;
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: enabled ? onTap : null,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: border, width: selected ? 2 : 1),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  run.label,
                  style: TextStyle(
                    color: selected ? AppColors.gold : AppColors.text,
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
                Text(
                  run.subtitle,
                  style: const TextStyle(
                      color: AppColors.textDim, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
