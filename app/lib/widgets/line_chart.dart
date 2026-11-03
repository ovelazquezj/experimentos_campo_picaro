import 'package:flutter/material.dart';

import '../theme.dart';

/// Grafico de linea sencillo dibujado con CustomPainter (sin dependencias).
/// El eje X es el orden temporal de los uplinks; el Y, la magnitud.
class SimpleLineChart extends StatelessWidget {
  final String title;
  final List<double> values;
  final Color color;
  final String unit;
  final double height;

  const SimpleLineChart({
    super.key,
    required this.title,
    required this.values,
    required this.color,
    this.unit = '',
    this.height = 150,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: const TextStyle(
                    color: AppColors.text, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            SizedBox(
              height: height,
              width: double.infinity,
              child: values.length < 2
                  ? const Center(
                      child: Text('Sin datos suficientes',
                          style: TextStyle(color: AppColors.textDim)),
                    )
                  : CustomPaint(
                      painter: _LinePainter(values: values, color: color, unit: unit),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LinePainter extends CustomPainter {
  final List<double> values;
  final Color color;
  final String unit;

  _LinePainter({required this.values, required this.color, required this.unit});

  @override
  void paint(Canvas canvas, Size size) {
    double minV = values.first, maxV = values.first;
    for (final v in values) {
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }
    if ((maxV - minV).abs() < 1e-9) {
      minV -= 1;
      maxV += 1;
    }
    // Margen para etiquetas del eje Y.
    const left = 44.0;
    const bottom = 6.0;
    const top = 6.0;
    final plotW = size.width - left - 6;
    final plotH = size.height - top - bottom;

    // Gridlines + etiquetas (3 niveles).
    final gridPaint = Paint()
      ..color = const Color(0x22FFFFFF)
      ..strokeWidth = 1;
    for (var i = 0; i <= 2; i++) {
      final t = i / 2;
      final y = top + plotH * t;
      canvas.drawLine(Offset(left, y), Offset(left + plotW, y), gridPaint);
      final val = maxV - (maxV - minV) * t;
      _label(canvas, Offset(2, y - 6), val.toStringAsFixed(_dec(maxV - minV)));
    }

    // Linea.
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = left + plotW * (i / (values.length - 1));
      final y = top + plotH * (1 - (values[i] - minV) / (maxV - minV));
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke,
    );

    // Ultimo valor destacado.
    final lastX = left + plotW;
    final lastY = top + plotH * (1 - (values.last - minV) / (maxV - minV));
    canvas.drawCircle(Offset(lastX, lastY), 3, Paint()..color = color);
    _label(canvas, Offset(lastX - 40, lastY - 16),
        '${values.last.toStringAsFixed(_dec(maxV - minV))}$unit',
        colorText: color);
  }

  int _dec(double span) => span >= 10 ? 0 : 1;

  void _label(Canvas canvas, Offset at, String text, {Color? colorText}) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(color: colorText ?? AppColors.textDim, fontSize: 10),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, at);
  }

  @override
  bool shouldRepaint(covariant _LinePainter old) =>
      old.values != values || old.color != color;
}
