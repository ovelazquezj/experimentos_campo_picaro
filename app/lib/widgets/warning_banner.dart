import 'package:flutter/material.dart';

import '../theme.dart';

/// Banda roja de aviso (desajuste de fPort, §10). Descartable.
class WarningBanner extends StatelessWidget {
  final String message;
  final VoidCallback onDismiss;
  const WarningBanner({super.key, required this.message, required this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.red,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.w600),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.close, color: Colors.white),
              onPressed: onDismiss,
              tooltip: 'Descartar',
            ),
          ],
        ),
      ),
    );
  }
}
