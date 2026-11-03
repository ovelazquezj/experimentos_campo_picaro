import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:picaro_campo/runs.dart';
import 'package:picaro_campo/widgets/run_selector.dart';

/// Dos sondas, un microservicio (D-65): la T-Beam corre todas las corridas y
/// la T3 (PICARO-LORA32) solo VUELO-A.
void main() {
  group('corridas admitidas por sonda', () {
    test('la T-Beam admite las 7', () {
      expect(kRuns.where((r) => corridaAdmitida(r, kSondaTbeam)).length, 7);
    });

    test('la T3 solo admite VUELO A', () {
      final admitidas =
          kRuns.where((r) => corridaAdmitida(r, kSondaLora32)).toList();
      expect(admitidas.length, 1);
      expect(admitidas.single.scenario, kEscenarioVuelo);
      expect(admitidas.single.cls, 'A');
    });
  });

  testWidgets('con la T3, el selector solo deja tocar VUELO A', (tester) async {
    final tocadas = <String>[];
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RunSelector(
          scenario: kEscenarioVuelo,
          cls: 'A',
          enabled: true,
          sonda: kSondaLora32,
          onSelect: (s, c) => tocadas.add('$s $c'),
        ),
      ),
    ));
    await tester.tap(find.text('URBANO A'));
    await tester.tap(find.text('CERRO16 C'));
    await tester.tap(find.text('VUELO A'));
    expect(tocadas, ['VUELO A']);
  });
}
