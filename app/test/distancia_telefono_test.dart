import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:picaro_campo/gps/gps_telefono.dart';
import 'package:picaro_campo/models/models.dart';
import 'package:picaro_campo/widgets/distancia_telefono.dart';

/// Distancia de la T3 medida con el GPS del telefono (D-65).
void main() {
  test('la sesion de la T3 mide con el GPS del telefono; la de la T-Beam no', () {
    final t3 = Session.fromJson({'id': 1, 'state': 'capturing', 'sonda': 'lora32'});
    final tb = Session.fromJson({'id': 2, 'state': 'capturing'});
    expect(t3.gpsDelTelefono, isTrue);
    expect(tb.sonda, 'tbeam');
    expect(tb.gpsDelTelefono, isFalse);
  });

  test('metricas: distancia ultima, posicion del telefono y gateway', () {
    final m = Metrics.fromJson({
      'received': 3,
      'dist_gw_km_max': 3.6,
      'dist_gw_km_ultima': 3.412,
      'posicion_telefono': {'lat': 22.19, 'lon': -102.28, 'precision_m': 4.0},
      'gateway_ultimo': {'id': '00800000a0000003', 'lat': 22.16, 'lon': -102.27},
    });
    expect(m.distGwKmUltima, 3.412);
    expect(m.posicionTelefono!.precisionM, 4.0);
    expect(m.gatewayUltimo, '00800000a0000003');
    // Un servidor < 1.4.0 no manda nada de esto: queda null sin fallar.
    final viejo = Metrics.fromJson({'received': 1});
    expect(viejo.distGwKmUltima, isNull);
    expect(viejo.posicionTelefono, isNull);
  });

  test('el fix se envia con ts en segundos epoch', () {
    final f = FixTelefono(
        lat: 22.19, lon: -102.28, precisionM: 5,
        ts: DateTime.fromMillisecondsSinceEpoch(1500, isUtc: true));
    expect(f.toJson(), {'lat': 22.19, 'lon': -102.28, 'precision_m': 5.0, 'ts': 1.5});
  });

  testWidgets('el panel pinta distancia, gateway, telefono y aviso', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: DistanciaTelefono(
          metrics: Metrics.fromJson({
            'dist_gw_km_max': 3.6,
            'dist_gw_km_ultima': 3.412,
            'gateway_ultimo': {'id': '00800000a0000003'},
          }),
          fixLocal: FixTelefono(
              lat: 22.19, lon: -102.28, precisionM: 4, ts: DateTime.now()),
          aviso: 'Sin permiso de ubicación',
        ),
      ),
    ));
    expect(find.text('3.41 km al gateway'), findsOneWidget);
    expect(find.text('3.6 km'), findsOneWidget);
    expect(find.text('00800000a0000003'), findsOneWidget);
    expect(find.text('22.19000, -102.28000'), findsOneWidget);
    expect(find.text('±4 m'), findsOneWidget);
    expect(find.text('Sin permiso de ubicación'), findsOneWidget);
  });
}
