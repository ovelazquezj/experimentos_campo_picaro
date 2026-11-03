// ============================================================================
//  dispositivo.dart  -  Pantalla de dispositivo (sonda BLE)
// ============================================================================
//  Contrato: equipo/CONTRATO-BLE.md v2, §10.1.
//
//  Escanear, conectar, ver el enlace y acompanar el emparejamiento. NO hay
//  campo para teclear un codigo: con LE Secure Connections el numero de 6
//  digitos se teclea en el dialogo del sistema de Android, y lo muestra la
//  sonda en su OLED. Lo que si hay aqui es la instruccion y el estado del bond.
//
//  Como se abre: `Navigator.push(MaterialPageRoute(builder: (_) =>
//  const DispositivoScreen()))`. Toma el BleClient de `provider`; si no
//  estuviera registrado, se le puede pasar uno por el constructor.
// ============================================================================

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../ble/ble_client.dart';
import '../runs.dart';
import '../theme.dart';

class DispositivoScreen extends StatefulWidget {
  /// Normalmente null: el cliente se toma de `provider`. El parametro existe
  /// para poder abrir la pantalla sin depender del arbol de providers.
  final BleClient? cliente;

  const DispositivoScreen({super.key, this.cliente});

  @override
  State<DispositivoScreen> createState() => _DispositivoScreenState();
}

class _DispositivoScreenState extends State<DispositivoScreen> {
  BleClient get _ble => widget.cliente ?? context.read<BleClient>();

  @override
  void dispose() {
    // §5.4 / §10.8 piden un disconnect() explicito al salir de esta pantalla,
    // porque Android a veces mantiene la conexion GATT y entonces la sonda
    // queda invisible para los demas (solo acepta UN central).
    //
    // Se aplica con un matiz, y es deliberado: si el enlace quedo LISTO no se
    // corta, porque el gate de RF-7 del panel vive precisamente de ese enlace
    // — cortarlo al volver atras dejaria el selector de corrida deshabilitado
    // para siempre. Si el enlace NO llego a estar listo (escaneo a medias,
    // conexion fallida, emparejamiento abandonado) si se suelta la ranura.
    final ble = widget.cliente ?? _leerSinContexto();
    if (ble != null && !ble.listo) {
      ble.desconectar();
    } else {
      ble?.pararEscaneo();
    }
    super.dispose();
  }

  // `context.read` no es seguro en dispose(); se resuelve antes de fallar.
  BleClient? _leerSinContexto() {
    try {
      return Provider.of<BleClient>(context, listen: false);
    } catch (_) {
      return null;
    }
  }

  Future<void> _escanear() async {
    await _ble.escanear();
  }

  Future<void> _conectar(String direccion) async {
    await _ble.conectar(direccion);
  }

  @override
  Widget build(BuildContext context) {
    final ble = widget.cliente ?? context.watch<BleClient>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dispositivo'),
        actions: [
          IconButton(
            tooltip: 'Buscar sonda',
            icon: const Icon(Icons.refresh),
            onPressed: ble.escaneando ? null : _escanear,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _TarjetaEnlace(ble: ble),
          const SizedBox(height: 12),
          if (ble.aviso != null) ...[
            _Aviso(texto: ble.aviso!, fase: ble.fase),
            const SizedBox(height: 12),
          ],
          if (ble.emparejando) ...[
            const _InstruccionEmparejado(),
            const SizedBox(height: 12),
          ],
          _TarjetaSonda(ble: ble),
          const SizedBox(height: 16),
          _Acciones(
            ble: ble,
            onEscanear: _escanear,
          ),
          const SizedBox(height: 16),
          _ListaEncontradas(
            ble: ble,
            onConectar: _conectar,
          ),
          const SizedBox(height: 24),
          const _Ayuda(),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Estado del enlace
// ---------------------------------------------------------------------------

class _TarjetaEnlace extends StatelessWidget {
  final BleClient ble;
  const _TarjetaEnlace({required this.ble});

  @override
  Widget build(BuildContext context) {
    final (texto, color, icono) = _presentar(ble.fase);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icono, color: color),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    texto,
                    style: TextStyle(
                      color: color,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                if (ble.escaneando ||
                    ble.fase == BleFase.conectando ||
                    ble.fase == BleFase.preparando ||
                    ble.fase == BleFase.emparejando)
                  const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            _Fila('Sonda', ble.direccion ?? '—'),
            _Fila('Enlace seguro', ble.seguro ? 'sí (cifrado y autenticado)' : 'no'),
            _Fila(
              'Versión del protocolo',
              ble.ver == null
                  ? '—'
                  : 'v${ble.ver}${ble.ver == bleVerEsperada ? '' : ' (incompatible)'}',
            ),
            if (ble.fase == BleFase.reconectando)
              _Fila('Reintentos', '${ble.intentoReconexion}'),
          ],
        ),
      ),
    );
  }

  static (String, Color, IconData) _presentar(BleFase f) {
    switch (f) {
      case BleFase.inactivo:
        return ('Sin conectar', AppColors.textDim, Icons.bluetooth_disabled);
      case BleFase.escaneando:
        return ('Buscando la sonda…', AppColors.cyan, Icons.bluetooth_searching);
      case BleFase.conectando:
        return ('Conectando…', AppColors.cyan, Icons.bluetooth_connected);
      case BleFase.emparejando:
        return ('Emparejando…', AppColors.gold, Icons.vpn_key);
      case BleFase.preparando:
        return ('Preparando el enlace…', AppColors.cyan, Icons.settings_ethernet);
      case BleFase.listo:
        return ('Enlace listo', AppColors.green, Icons.bluetooth_connected);
      case BleFase.reconectando:
        return ('Reconectando…', AppColors.gold, Icons.sync_problem);
      case BleFase.incompatible:
        return ('Firmware incompatible', AppColors.red, Icons.report);
      case BleFase.apartada:
        return ('Apartada: sonda emparejando', AppColors.gold, Icons.pause_circle);
      case BleFase.error:
        return ('Sin enlace', AppColors.red, Icons.error_outline);
    }
  }
}

// ---------------------------------------------------------------------------
// Estado de la sonda (bytes 1, 2 y 4 de la caracteristica Estado)
// ---------------------------------------------------------------------------

class _TarjetaSonda extends StatelessWidget {
  final BleClient ble;
  const _TarjetaSonda({required this.ble});

  @override
  Widget build(BuildContext context) {
    final modo = ble.modo;
    final corrida = (modo != null && modo >= 0 && modo < kRuns.length)
        ? '${kRuns[modo].label} · ${kRuns[modo].subtitle}'
        : '—';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Estado de la sonda',
                style: TextStyle(color: AppColors.gold, fontSize: 12)),
            const SizedBox(height: 10),
            _Fila('Situación', BleEstadoSonda.etiqueta(ble.estadoSonda)),
            _Fila(
              ble.estadoSonda == BleEstadoSonda.corriendo
                  ? 'Corrida en marcha'
                  : 'Cursor / última corrida',
              corrida,
            ),
            _Fila('Último comando', BleUltCmd.etiqueta(ble.ultCmd)),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Acciones
// ---------------------------------------------------------------------------

class _Acciones extends StatelessWidget {
  final BleClient ble;
  final Future<void> Function() onEscanear;

  const _Acciones({required this.ble, required this.onEscanear});

  @override
  Widget build(BuildContext context) {
    final ocupado = ble.escaneando ||
        ble.fase == BleFase.conectando ||
        ble.fase == BleFase.preparando ||
        ble.fase == BleFase.emparejando;

    // Tras apartarse por EMPAREJADO (§10.7) la app NO vuelve sola: hace falta
    // este boton explicito.
    final puedeReconectar =
        ble.direccion != null && ble.reconexionPausada && !ble.conectado;

    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            icon: const Icon(Icons.bluetooth_searching),
            label: const Text('Buscar sonda'),
            onPressed: ocupado ? null : () => onEscanear(),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: puedeReconectar
              ? FilledButton.icon(
                  icon: const Icon(Icons.link),
                  label: const Text('Reconectar'),
                  onPressed: ocupado ? null : () => ble.reconectar(),
                )
              : FilledButton.icon(
                  icon: const Icon(Icons.link_off),
                  label: const Text('Desconectar'),
                  onPressed:
                      (ocupado || !ble.conectado) ? null : () => ble.desconectar(),
                ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Resultados del escaneo
// ---------------------------------------------------------------------------

class _ListaEncontradas extends StatelessWidget {
  final BleClient ble;
  final Future<void> Function(String direccion) onConectar;

  const _ListaEncontradas({required this.ble, required this.onConectar});

  @override
  Widget build(BuildContext context) {
    if (ble.encontradas.isEmpty) {
      return Text(
        ble.escaneando
            ? 'Escaneando 10 s…'
            : 'Pulsa «Buscar sonda» para escanear. Solo aparecen los equipos '
                'que anuncian el servicio PICARO-CAMPO.',
        style: const TextStyle(color: AppColors.textDim),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Sondas encontradas',
            style: TextStyle(color: AppColors.gold, fontSize: 12)),
        const SizedBox(height: 8),
        ...ble.encontradas.map(
          (s) => Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: const Icon(Icons.sensors, color: AppColors.cyan),
              title: Text(s.etiqueta),
              subtitle: Text('${s.rssi} dBm · ${s.direccion}',
                  style: const TextStyle(color: AppColors.textDim)),
              trailing: s.direccion == ble.direccion && ble.conectado
                  ? const Icon(Icons.check_circle, color: AppColors.green)
                  : const Icon(Icons.chevron_right),
              onTap: () => onConectar(s.direccion),
            ),
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Avisos y ayuda
// ---------------------------------------------------------------------------

class _Aviso extends StatelessWidget {
  final String texto;
  final BleFase fase;
  const _Aviso({required this.texto, required this.fase});

  @override
  Widget build(BuildContext context) {
    final grave = fase == BleFase.error || fase == BleFase.incompatible;
    final color = grave ? AppColors.red : AppColors.gold;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        border: Border.all(color: color),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(grave ? Icons.error_outline : Icons.info_outline,
              color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(texto, style: TextStyle(color: color))),
        ],
      ),
    );
  }
}

/// Lo unico que la app tiene que decir durante el emparejamiento: el numero no
/// se escribe aqui, se escribe en el dialogo del sistema.
class _InstruccionEmparejado extends StatelessWidget {
  const _InstruccionEmparejado();

  @override
  Widget build(BuildContext context) {
    return const Card(
      color: AppColors.night1,
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.pin, color: AppColors.gold),
                SizedBox(width: 10),
                Text('Emparejamiento en curso',
                    style: TextStyle(
                        color: AppColors.gold, fontWeight: FontWeight.w600)),
              ],
            ),
            SizedBox(height: 10),
            Text(
              'Mira la pantalla de la sonda: muestra un código de 6 dígitos. '
              'Tecléalo en el diálogo que abre Android encima de esta app.',
              style: TextStyle(color: AppColors.text),
            ),
            SizedBox(height: 8),
            Text(
              'El código cambia en cada emparejamiento y no se guarda en '
              'ningún sitio. Si la sonda no muestra ningún número, ponla en '
              'modo emparejar: pulsación larga desde el menú.',
              style: TextStyle(color: AppColors.textDim, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class _Ayuda extends StatelessWidget {
  const _Ayuda();

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Cómo se empareja', style: TextStyle(color: AppColors.gold, fontSize: 12)),
        SizedBox(height: 8),
        Text(
          '1. La sonda debe estar en modo emparejar: al arrancar sin ningún '
          'móvil emparejado entra sola, y desde el menú se entra con una '
          'pulsación larga.\n'
          '2. Pulsa «Buscar sonda» y toca PICARO-CAMPO en la lista.\n'
          '3. Teclea en el móvil el código de 6 dígitos que ves en la sonda.\n'
          '4. A partir de ahí las reconexiones son automáticas y sin código: '
          'las llaves las guarda Android, no la app. Reinstalar la app o '
          'reiniciar la sonda no obliga a emparejar de nuevo.',
          style: TextStyle(color: AppColors.textDim, fontSize: 12),
        ),
        SizedBox(height: 12),
        Text(
          'Si otro móvil está conectado a la sonda, ésta deja de anunciarse y '
          'no aparecerá en el escaneo: solo admite una conexión a la vez.',
          style: TextStyle(color: AppColors.textDim, fontSize: 12),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------

class _Fila extends StatelessWidget {
  final String etiqueta;
  final String valor;
  const _Fila(this.etiqueta, this.valor);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 150,
            child: Text(etiqueta,
                style: const TextStyle(color: AppColors.textDim, fontSize: 13)),
          ),
          Expanded(
            child: Text(valor,
                style: const TextStyle(color: AppColors.text, fontSize: 13)),
          ),
        ],
      ),
    );
  }
}
