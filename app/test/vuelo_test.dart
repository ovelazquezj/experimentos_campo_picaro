import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:picaro_campo/ble/ble_client.dart';
import 'package:picaro_campo/models/models.dart';
import 'package:picaro_campo/runs.dart';
import 'package:picaro_campo/utils/geo.dart';
import 'package:picaro_campo/widgets/oled_panel.dart';
import 'package:picaro_campo/widgets/vuelo_panel.dart';

/// Corrida VUELO (docs/VUELO-ESPEC.md): modo BLE 6, solo Clase A, fPort 17,
/// rafagas de 3 paquetes que traen cada uno un trozo de la lectura.
void main() {
  group('tabla de corridas y modos BLE', () {
    test('las 6 corridas antiguas no cambian (modo, fPort, perfil, radio)', () {
      const esperadas = [
        ['URBANO', 'A', 11, 'terreno-a', 'DR1/SF9', 14],
        ['URBANO', 'C', 12, 'terreno-c', 'DR1/SF9', 14],
        ['TERRAZA', 'A', 13, 'terreno-a', 'DR3/SF7', 14],
        ['TERRAZA', 'C', 14, 'terreno-c', 'DR3/SF7', 14],
        ['CERRO16', 'A', 15, 'terreno-a', 'DR0/SF10', 11],
        ['CERRO16', 'C', 16, 'terreno-c', 'DR0/SF10', 11],
      ];
      for (var modo = 0; modo < esperadas.length; modo++) {
        final e = esperadas[modo];
        final r = kRuns[modo];
        expect([r.scenario, r.cls, r.fPort, r.profile, r.radio, r.payloadBytes],
            e,
            reason: 'modo $modo');
        expect(r.targetUplinks, 300);
        expect(r.esRafagas, isFalse);
        expect(r.subtitle, 'fP${r.fPort} · ${r.radio}');
        expect(modoDeCorrida(r.scenario, r.cls), modo);
        // El nombre BLE sigue siendo el de la formula antigua para 0..5.
        const esc = ['URBANO', 'TERRAZA', 'CERRO16'];
        expect(bleNombreModo(modo),
            '${esc[modo ~/ 2]}-${modo % 2 == 0 ? 'A' : 'C'}');
      }
    });

    test('modo 6 <-> VUELO-A', () {
      expect(kRuns.length, 7);
      final v = kRuns[6];
      expect(v.scenario, 'VUELO');
      expect(v.cls, 'A');
      expect(v.fPort, 17);
      expect(v.profile, 'terreno-a');
      expect(v.radio, 'DR0/SF10');
      expect(v.payloadBytes, 11);
      expect(v.targetUplinks, 165);
      expect(v.paquetesPorRafaga, 3);
      expect(v.rafagasObjetivo, 55);
      expect(v.esRafagas, isTrue);

      expect(modoDeCorrida('VUELO', 'A'), 6);
      expect(corridaDeModo(6), same(v));
      expect(bleNombreModo(6), 'VUELO-A');
      expect(bleModoMax, 6);
    });

    test('VUELO no tiene Clase C y los modos fuera de tabla dan null', () {
      expect(findRun('VUELO', 'C'), isNull);
      expect(modoDeCorrida('VUELO', 'C'), isNull);
      expect(corridaDeModo(7), isNull);
      expect(corridaDeModo(-1), isNull);
      expect(corridaDeModo(null), isNull);
      expect(bleNombreModo(7), 'modo 7');
    });

    test('la tabla de nombres BLE coincide con kRuns', () {
      expect(bleNombresModo.length, kRuns.length);
      for (var i = 0; i < kRuns.length; i++) {
        expect(bleNombresModo[i], '${kRuns[i].scenario}-${kRuns[i].cls}');
      }
    });

    test('escenarios en orden del menu, sin suponer pares A/C', () {
      expect(escenariosEnOrden, ['URBANO', 'TERRAZA', 'CERRO16', 'VUELO']);
    });

    test('Session sin target_uplinks toma el de la corrida', () {
      final s = Session.fromJson({
        'id': 1,
        'scenario': 'VUELO',
        'class': 'A',
        'expected_fport': 17,
        'state': 'capturing',
      });
      expect(s.targetUplinks, 165);
      expect(s.esVuelo, isTrue);
      final c = Session.fromJson({
        'id': 2,
        'scenario': 'CERRO16',
        'class': 'C',
        'expected_fport': 16,
        'state': 'capturing',
      });
      expect(c.targetUplinks, 300);
      expect(c.esVuelo, isFalse);
    });
  });

  // ---------------------------------------------------------------------------
  // Uplinks de una rafaga tal como los manda el microservicio: columnas planas
  // (null si el paquete no las trae) y el resto en la clave `vuelo`.
  // ---------------------------------------------------------------------------
  Map<String, dynamic> p1(int fcnt, int rafaga,
          {double? lat, double? lon, double? alt, bool fix = true}) =>
      {
        'f_cnt': fcnt,
        'f_port': 17,
        'rssi': -110,
        'snr': -5.0,
        'gps_fix': fix,
        'latitude': lat,
        'longitude': lon,
        'altitude_m': alt,
        'battery_v': null,
        'temperature_c': null,
        'vuelo': {'tipo_paquete': 'posicion', 'rafaga': rafaga},
      };

  Map<String, dynamic> p2(int fcnt, int rafaga,
          {double? temp, double? pres, int? hum, double? bat}) =>
      {
        'f_cnt': fcnt,
        'f_port': 17,
        'gps_fix': true,
        'satellites': 9,
        'latitude': null,
        'longitude': null,
        'battery_v': bat,
        'battery_pct': 80,
        'temperature_c': temp,
        'pressure_hpa': pres,
        'vuelo': {
          'tipo_paquete': 'ambiente',
          'rafaga': rafaga,
          'humidity_pct': hum,
        },
      };

  Map<String, dynamic> p3(int fcnt, int rafaga,
          {double? vs, double? rumbo, double? vel}) =>
      {
        'f_cnt': fcnt,
        'f_port': 17,
        'latitude': null,
        'longitude': null,
        'vuelo': {
          'tipo_paquete': 'navegacion',
          'rafaga': rafaga,
          'vspeed_ms': vs,
          'heading_deg': rumbo,
          'speed_kmh': vel,
          'hdop': 1.2,
          'uptime_s': 600,
        },
      };

  group('Uplink de VUELO', () {
    test('lee los campos de la clave `vuelo`', () {
      final u = Uplink.fromJson(p3(10, 3, vs: 4.5, rumbo: 270.5, vel: 12.3));
      expect(u.esVuelo, isTrue);
      expect(u.tipoPaquete, TipoPaquete.navegacion);
      expect(u.rafaga, 3);
      expect(u.vspeedMs, 4.5);
      expect(u.headingDeg, 270.5);
      expect(u.speedKmh, 12.3);
      expect(u.uptimeS, 600);
    });

    test('tolera `vuelo` null, ausente o `raw_json` en texto', () {
      final a = Uplink.fromJson({'f_port': 11, 'vuelo': null});
      expect(a.tipoPaquete, isNull);
      expect(a.rafaga, isNull);
      final b = Uplink.fromJson({
        'f_port': 17,
        'raw_json': '{"object":{"tipo_paquete":"ambiente","rafaga":7,'
            '"humidity_pct":40}}',
      });
      expect(b.tipoPaquete, TipoPaquete.ambiente);
      expect(b.rafaga, 7);
      expect(b.humidityPct, 40);
      final c = Uplink.fromJson({'f_port': 17, 'raw_json': '{no es json'});
      expect(c.rafaga, isNull);
    });

    test('sin tipo_paquete se deduce P2 de las columnas', () {
      final u = Uplink.fromJson({'f_port': 17, 'battery_v': 4.1});
      expect(u.tipoEfectivo, TipoPaquete.ambiente);
    });

    test('P2/P3 y P1 sin fix no aportan punto al mapa', () {
      final ups = [
        Uplink.fromJson(p1(1, 0, lat: 19.5, lon: -99.1, alt: 2300)),
        Uplink.fromJson(p2(2, 0, temp: 20)),
        Uplink.fromJson(p3(3, 0)),
        Uplink.fromJson(p1(4, 1, fix: false)), // sin fix: null
        Uplink.fromJson({
          'f_port': 17,
          'gps_fix': true,
          'latitude': 0.0,
          'longitude': 0.0,
        }),
      ];
      final pts = puntosConFix(ups);
      expect(pts.length, 1);
      expect(pts.single.latitude, 19.5);
    });
  });

  group('último valor conocido', () {
    test('secuencia P1/P2/P3: cada magnitud del ultimo paquete que la trajo',
        () {
      final ups = [
        // rafaga 0 completa
        p1(1, 0, lat: 19.40, lon: -99.10, alt: 2300),
        p2(2, 0, temp: 21.5, pres: 780.2, hum: 40, bat: 4.10),
        p3(3, 0, rumbo: 90), // primera rafaga: vspeed null
        // rafaga 1: P1 sin fix y P2 perdido
        p1(4, 1, fix: false),
        p3(6, 1, vs: 2.5, rumbo: 95, vel: 10),
        // rafaga 2: solo el P2, con la temperatura en sentinela (null)
        p2(8, 2, temp: null, pres: 779.0, hum: 42, bat: 4.05),
      ].map(Uplink.fromJson).toList();

      final l = LecturaVuelo.desde(ups);

      // Posicion: la del ultimo P1 CON fix (rafaga 0), no el null del P1 de
      // la rafaga 1 ni un 0,0.
      expect(l.latitude!.valor, 19.40);
      expect(l.longitude!.valor, -99.10);
      expect(l.latitude!.rafaga, 0);
      expect(l.altitudeM!.valor, 2300);

      // gps_fix: el P2 de la rafaga 2 dice true (despues del P1 sin fix).
      expect(l.gpsFix!.valor, isTrue);
      expect(l.gpsFix!.rafaga, 2);

      // Temperatura: la rafaga 2 no la trae (null), se conserva 21.5 de la 0.
      expect(l.temperatureC!.valor, 21.5);
      expect(l.temperatureC!.rafaga, 0);
      expect(l.temperatureC!.tipo, TipoPaquete.ambiente);
      // Presion, humedad y bateria si llegaron en la rafaga 2.
      expect(l.pressureHpa!.valor, 779.0);
      expect(l.humidityPct!.valor, 42);
      expect(l.batteryV!.valor, 4.05);
      expect(l.pressureHpa!.rafaga, 2);

      // Navegacion: del P3 de la rafaga 1.
      expect(l.vspeedMs!.valor, 2.5);
      expect(l.headingDeg!.valor, 95);
      expect(l.speedKmh!.valor, 10);
      expect(l.headingDeg!.rafaga, 1);

      // Lo que se esta oyendo ahora.
      expect(l.rafagaActual, 2);
      expect(l.tipoActual, TipoPaquete.ambiente);

      // Rafagas vistas: 0 completa; 1 y 2 parciales.
      expect(l.rafagasCompletasLocal, 1);
      expect(l.rafagasParcialesLocal, 2);
    });

    test('lo que nunca llego queda null (no 0)', () {
      final l = LecturaVuelo.desde([Uplink.fromJson(p3(1, 0))]);
      expect(l.temperatureC, isNull);
      expect(l.latitude, isNull);
      expect(l.batteryV, isNull);
      expect(l.vspeedMs, isNull);
      expect(l.hdop!.valor, 1.2);
    });
  });

  group('métricas vuelo', () {
    test('parsea el bloque `vuelo` del microservicio', () {
      final m = Metrics.fromJson({
        'received': 30,
        'vuelo': {
          'por_tipo': {'posicion': 10, 'ambiente': 11, 'navegacion': 9},
          'rafagas_completas': 8,
          'rafagas_parciales': 3,
          'rafagas_perdidas': 1,
          'rafaga_max': 11,
          'rafagas_objetivo': 55,
        },
      });
      final v = m.vuelo!;
      expect(v.completas, 8);
      expect(v.parciales, 3);
      expect(v.perdidas, 1);
      expect(v.rafagaUltima, 11);
      expect(v.rafagasObjetivo, 55);
      expect([v.p1, v.p2, v.p3], [10, 11, 9]);
    });

    test('sin la clave (o null) no falla', () {
      expect(Metrics.fromJson({'received': 3}).vuelo, isNull);
      expect(Metrics.fromJson({'received': 3, 'vuelo': null}).vuelo, isNull);
      expect(SessionSummary.fromJson({'received': 3}).vuelo, isNull);
    });
  });

  group('widgets', () {
    Iterable<String> textos(WidgetTester t) => [
          ...t
              .widgetList<RichText>(find.byType(RichText))
              .map((w) => w.text.toPlainText()),
        ];

    testWidgets('OLED en VUELO: bateria del ultimo P2 aunque el ultimo '
        'uplink sea un P3', (tester) async {
      final ups = [
        p2(1, 0, temp: 20, bat: 4.10),
        p3(2, 0),
      ].map(Uplink.fromJson).toList();
      // Las metricas copian el ultimo uplink (un P3): sin bateria.
      const m = Metrics(received: 2);
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: OledPanel(
            session: Session.fromJson(const {
              'id': 1,
              'scenario': 'VUELO',
              'class': 'A',
              'expected_fport': 17,
              'state': 'capturing',
              'target_uplinks': 165,
            }),
            metrics: m,
            lastDownlink: null,
            lectura: LecturaVuelo.desde(ups),
          ),
        ),
      ));
      final t = textos(tester).toList();
      expect(t, contains('TX 2/165'));
      expect(t, contains('Bat 80% 4100 mV'));
    });

    testWidgets('panel VUELO: ráfaga n/55 · Pn y «--» para lo no recibido',
        (tester) async {
      final ups = [
        p1(1, 11, lat: 19.4, lon: -99.1, alt: 2300),
        p2(2, 11, temp: null, pres: 780.0, hum: 40, bat: 4.1),
      ].map(Uplink.fromJson).toList();
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: VueloPanel(
              lectura: LecturaVuelo.desde(ups),
              metrics: null,
              rafagasObjetivo: 55,
            ),
          ),
        ),
      ));
      expect(find.text('ráfaga 12/55 · P2'), findsOneWidget);
      expect(find.text('780.0 hPa'), findsOneWidget);
      expect(find.text('40 %'), findsOneWidget);
      // Temperatura en sentinela y P3 sin recibir: «--», nunca 0.
      expect(find.text('0.0 °C'), findsNothing);
      expect(find.text('--'), findsWidgets);
    });
  });
}
