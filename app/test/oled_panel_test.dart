import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:picaro_campo/models/metrics.dart';
import 'package:picaro_campo/widgets/oled_panel.dart';

/// Regresion del bug de campo (ago-2026): el «TX n/300» del panel se pintaba
/// con el fCnt LoRaWAN absoluto (`last_fcnt`), que NO se reinicia entre
/// corridas si la sonda no vuelve a hacer join. Tras una corrida de 300, la
/// siguiente mostraba 301/300, 302/300, … en vez de partir de 0. El contador
/// correcto es el de la sesion: `received + gaps` (§12.3 del contrato).
void main() {
  /// Texto plano de todos los RichText del arbol (las celdas del OledPanel).
  Iterable<String> textosDe(WidgetTester tester) => tester
      .widgetList<RichText>(find.byType(RichText))
      .map((w) => w.text.toPlainText());

  Future<void> bombear(WidgetTester tester, Metrics? m) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: OledPanel(session: null, metrics: m, lastDownlink: null),
      ),
    ));
  }

  test('Metrics.sentEst es received + gaps, no el fCnt absoluto', () {
    const m = Metrics(received: 2, gaps: 0, lastFcnt: 301);
    expect(m.sentEst, 2);
  });

  testWidgets('TX parte de 0 aunque el fCnt venga alto de la corrida anterior',
      (tester) async {
    // Segunda corrida sin reiniciar la sonda: primer uplink con fCnt 300.
    const m = Metrics(received: 1, gaps: 0, lastFcnt: 300);
    await bombear(tester, m);

    final textos = textosDe(tester).toList();
    expect(textos, contains('TX 1/300'));
    expect(textos, isNot(contains('TX 300/300')));
    expect(textos, contains('RX 1'));
  });

  testWidgets('TX cuenta enviados de la sesion (recibidos + huecos)',
      (tester) async {
    // 250 recibidos con 10 perdidos: la sonda ha enviado 260 desde el inicio.
    const m = Metrics(received: 250, gaps: 10, lastFcnt: 559);
    await bombear(tester, m);

    expect(textosDe(tester), contains('TX 260/300'));
  });

  testWidgets('sin metricas, TX 0/300', (tester) async {
    await bombear(tester, null);
    expect(textosDe(tester), contains('TX 0/300'));
  });
}
