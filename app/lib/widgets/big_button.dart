import 'package:flutter/material.dart';

/// Boton circular grande del panel (Arrancar/Abortar/Finalizado, §10).
class BigActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final bool busy;
  final VoidCallback? onPressed;

  const BigActionButton({
    super.key,
    required this.label,
    required this.icon,
    required this.color,
    required this.onPressed,
    this.busy = false,
  });

  @override
  Widget build(BuildContext context) {
    const double size = 168;
    final enabled = onPressed != null && !busy;
    return Semantics(
      button: true,
      label: label,
      child: Material(
        color: enabled ? color : color.withOpacity(0.45),
        shape: const CircleBorder(),
        elevation: enabled ? 6 : 0,
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: enabled ? onPressed : null,
          child: SizedBox(
            width: size,
            height: size,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (busy)
                  const SizedBox(
                    width: 40,
                    height: 40,
                    child: CircularProgressIndicator(
                        strokeWidth: 3, color: Colors.white),
                  )
                else
                  Icon(icon, size: 56, color: Colors.white),
                const SizedBox(height: 8),
                Text(
                  label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
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
