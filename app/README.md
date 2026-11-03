# PiCARO — App de campo (Flutter)

App móvil (Android, APK de instalación local) para **operar y monitorizar** la
campaña de pruebas de terreno LoRaWAN. Habla con **dos** interlocutores
independientes:

- el **microservicio de campo** por internet (REST + WebSocket sobre TLS),
  descrito en `docs/CONTRATO-CAMPO.md`;
- la **sonda** por **BLE** (`lib/ble/`), para fijar la corrida y leer su estado.

Desde la **v2**, elegir una corrida y pulsar *Arrancar* hace las dos cosas con una
sola acción: abre la sesión de captura y conmuta el perfil en el servidor, **y**
ordena a la sonda que arranque esa misma corrida. El botón físico de la sonda se
conserva como respaldo completo. Guía de uso: `docs/APP-CAMPO.md`; procedimiento
de campo y emparejamiento: `docs/MANUAL-DE-CAMPO.md`.

## Pantallas

1. **Configuración** — URL base + token (guardados con `shared_preferences`).
   Sin config válida, la app arranca aquí. Reeditable desde el menú ≡ →
   *Configuración*. Botón *Probar* que llama a `GET /health`.
2. **① Panel** — selector de las corridas (6 clásicas + VUELO-A, modo 6); en VUELO, bloque «Vuelo · última lectura»; botón circular grande
   verde *Arrancar* / rojo *Abortar* / azul *Finalizado* según el estado;
   bloque *Sonda (BLE)* con el estado que publica la sonda (el ACK);
   datos tipo OLED (TX n/300, RSSI, SNR, GPS/sats, batería con «--» si es null,
   último downlink); bandas de aviso (desajuste sonda↔sesión, sonda parada con
   sesión abierta, `warning fport_mismatch`, enlace BLE caído); botón de
   *Ping* (`POST /ping`).
   El selector y *Arrancar* están **deshabilitados si la sonda no está lista por
   BLE**; *Abortar* **nunca** lo está (la sesión del servidor tiene que poder
   cerrarse aunque el enlace se caiga).
3. **② Mapa** — `flutter_map` sobre OpenStreetMap (sin API key) con el track de
   la sesión y el marcador del gateway. Conmutador **OSM / Offline**: el modo
   Offline dibuja los puntos y una escala con `CustomPainter` (no depende de la
   red de tiles).
4. **③ Gráficos** — PDR (est.), RSSI/SNR/batería vs tiempo y resumen numérico
   (todo con `CustomPainter`).
5. **④ Sesiones** — `GET /sessions`; detalle por sesión; *Descargar CSV*
   (`GET /sessions/{id}/csv`, guardado con `path_provider` y compartido con
   `share_plus`).
6. **⑤ Dispositivo (BLE)** (menú ≡, y tocando el indicador Bluetooth de la
   AppBar) — escanear filtrando por el UUID del servicio, conectar, ver el
   estado del enlace (conectado / seguro / versión del protocolo / reintentos) y
   el estado de la sonda, y acompañar el emparejamiento. **No hay campo para
   teclear ningún código**: el passkey lo muestra la sonda y se teclea en el
   diálogo del sistema de Android.
7. **⑥ Acerca de** y **⑦ Ayuda** (menú ≡ y botón ?).

En la AppBar hay dos indicadores: el de **Bluetooth** (verde = enlace listo,
ámbar = conectado pero aún no seguro, gris = sin sonda) y el del **WebSocket**.

## Dependencias

| Paquete | Versión | Uso |
|---|---|---|
| `http` | `^1.2.1` | Cliente REST (§6) |
| `web_socket_channel` | `^2.4.5` | WebSocket con token por query param (§7) |
| `shared_preferences` | `^2.2.3` | Persistir URL + token |
| `provider` | `^6.1.2` | Estado (ChangeNotifier), sin dependencias pesadas |
| `flutter_map` | `^6.1.0` | Mapa OSM |
| `latlong2` | `^0.9.1` | Coordenadas para el mapa |
| `path_provider` | `^2.1.3` | Ruta para guardar el CSV |
| `share_plus` | `^7.2.2` | Compartir el CSV |
| `flutter_blue_plus` | `^1.32.12` | Control de la sonda por BLE (`lib/ble/`) |

`flutter_blue_plus` es la **única** dependencia que necesita el cliente BLE: la
seguridad del enlace la da *LE Secure Connections* (emparejamiento del sistema),
así que no hace falta ningún paquete de criptografía ni se guarda ningún secreto
en la app.

Dev: `flutter_lints ^3.0.1`, `flutter_launcher_icons ^0.13.1`,
`flutter_native_splash ^2.4.0`.

Los gráficos usan `CustomPainter` (no `fl_chart`) para no arrastrar una
dependencia extra ni depender de su API entre versiones.

## Requisitos

- **Flutter ≥ 3.16** (canal stable), Dart ≥ 3.2.
- Para compilar APK: Android SDK (lo instala Android Studio o el
  `flutter doctor`).

## Puesta en marcha

Este repositorio versiona **solo** el código Dart, `pubspec.yaml` y los assets
de marca. Las carpetas de plataforma (`android/`, `ios/`, …) **no** se versionan
(ver `.gitignore`): se generan localmente una vez.

```bash
cd app

# 1) Generar el andamiaje de plataforma (crea android/, ios/, …).
#    Respeta el pubspec.yaml y el lib/ existentes.
flutter create --org org.pi_caro --project-name picaro_campo .

# 2) Descargar dependencias.
flutter pub get

# 3) Generar icono adaptativo y splash a partir de los PNG de assets/.
dart run flutter_launcher_icons
dart run flutter_native_splash:create

# 4) Compilar el APK de release.
flutter build apk --release
# -> build/app/outputs/flutter-apk/app-release.apk
```

> Si prefieres no fijar `--org`, ejecuta `flutter create .` a secas; en ese caso
> ajusta `userAgentPackageName`/applicationId a tu gusto (no es funcionalmente
> necesario).

## Solución de problemas (build de Android)

El andamiaje que genera `flutter create` puede venir con versiones de Gradle/AGP
antiguas que **no compilan con Java 21** (el JDK que trae Android Studio
reciente). El síntoma es un fallo en `JdkImageTransform` /
`compileDebugJavaWithJavac` al hacer `flutter build apk`. Verificado en este
entorno (Flutter 3.27.1, Android SDK 35, JDK 21). Se arregla subiendo dos
versiones dentro de `android/` (carpeta generada, no versionada):

- `android/settings.gradle`: `com.android.application` a **8.3.0**
  (cualquier AGP ≥ 8.2.1 sirve).
- `android/gradle/wrapper/gradle-wrapper.properties`: `distributionUrl` a
  **gradle-8.7-all.zip**.

Tras esos dos cambios, `flutter build apk` produjo el APK sin más incidencias.

### Permiso de INTERNET en release (¡imprescindible!)

Flutter añade el permiso `android.permission.INTERNET` **solo** en los builds
*debug*/*profile*. En el APK de **release** hay que declararlo a mano en el
manifiesto principal, o la app falla al conectar con
`ClientException: SocketException: Failed host lookup` (el navegador del móvil sí
resuelve, pero la app no tiene permiso de red). En
`android/app/src/main/AndroidManifest.xml`, dentro de `<manifest>` y antes de
`<application>`:

```xml
<uses-permission android:name="android.permission.INTERNET"/>
```

Como `android/` no se versiona, **hay que reañadirlo cada vez** que se regenere
con `flutter create .`.

### Permisos de Bluetooth (¡imprescindible!)

Mismo problema que INTERNET, y con la misma trampa: `android/` **se regenera** y
estos permisos se pierden. Además, `flutter_blue_plus` **no declara ninguno a
propósito** (su `AndroidManifest.xml` va vacío y así lo dice en un comentario),
de modo que si no están en el manifiesto de la app **no los pone nadie**. Sin
ellos el escaneo devuelve una lista vacía para siempre, sin ningún error: la
sonda simplemente «no aparece».

En `android/app/src/main/AndroidManifest.xml`, dentro de `<manifest>` y antes de
`<application>`, junto al de INTERNET:

```xml
<!-- Android 12+ (API 31+) -->
<uses-permission android:name="android.permission.BLUETOOTH_SCAN"
    android:usesPermissionFlags="neverForLocation"
    tools:targetApi="s"/>
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>

<!-- Android 11 y anteriores (API ≤ 30) -->
<uses-permission android:name="android.permission.BLUETOOTH"
    android:maxSdkVersion="30"/>
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN"
    android:maxSdkVersion="30"/>

<!-- GPS del telefono (D-65, app >= 2.3): distancia de la sonda T3 -->
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
```

Y en la etiqueta `<manifest>` hay que tener el namespace `tools`, que
`flutter create` **no** pone:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
          xmlns:tools="http://schemas.android.com/tools">
```

Detalles que no son opcionales:

- **`neverForLocation` en `BLUETOOTH_SCAN`**: declara que no se usa el
  Bluetooth para deducir la ubicación. Con él, Android 12+ **no** pide el
  permiso de ubicación al escanear (el cliente llama a `startScan` con
  `androidUsesFineLocation: false`, coherente con esta declaración).
- **`maxSdkVersion="30"` en los dos de Bluetooth clásico**: los limita a
  Android 11 y anteriores.
- **Ubicación sin tope de versión (desde la 2.3).** La app usa el GPS del
  teléfono para medir la distancia de la sonda T3, que no tiene GPS
  (`lib/gps/gps_telefono.dart`, paquete `geolocator`). El permiso se pide al
  arrancar la primera sesión de la T3, no al escanear. El escaneo BLE sigue sin
  pedirlo gracias a `neverForLocation`.
- **`BLUETOOTH_CONNECT` (12+) y `BLUETOOTH_ADMIN` (anteriores) ya cubren el
  emparejamiento** (`createBond()`). El emparejamiento **no** necesita ningún
  permiso adicional: lo gestiona el sistema.
- `minSdkVersion` debe ser **≥ 21** (el que pone `flutter create` por defecto).

Los permisos en tiempo de ejecución los pide el propio `flutter_blue_plus` al
escanear y al conectar; no hace falta `permission_handler`.

### El BLE no se puede probar en un emulador

El emulador de Android **no tiene radio Bluetooth**: el escaneo devuelve siempre
una lista vacía y el emparejamiento no existe. Toda la mitad BLE se verifica en
un **teléfono real y con la sonda encendida delante**. `flutter analyze` y
`flutter build apk` sí valen para lo de siempre, pero no dicen nada del enlace.

Para depurar sin la app —o para validar el firmware antes de que la app
exista— sirve cualquier escáner GATT con soporte de emparejamiento (nRF Connect):
la sonda anuncia el servicio `PICARO-CAMPO` y hace *Passkey Entry* igual con él.

### Firma de release (para publicar el APK)

El APK que se distribuye va firmado con una **clave de release propia**, no con la
de debug, para que las **actualizaciones se instalen encima** sin conflicto de firma.

- El **keystore** vive en `<infra-privada>/picaro-campo-release.jks` (fuera del repo) y su
  contraseña en `<infra-privada>/.campo-keystore`. **No se regeneran nunca**: perder esa clave
  significa no poder actualizar la app instalada (habría que desinstalar y reinstalar).
- `android/key.properties` (gitignorado) apunta al keystore:
  ```
  storePassword=…
  keyPassword=…
  keyAlias=picaro-campo
  storeFile=<ruta-a-tu-keystore>/picaro-campo-release.jks
  ```
- En `android/app/build.gradle` se carga ese fichero y se firma el `release` con él
  (bloque `signingConfigs.release` + `buildTypes.release.signingConfig`).

Como `android/` se regenera, **tras un `flutter create .` hay que volver a crear
`key.properties` y el `signingConfigs` del `build.gradle`**. Si faltan, el build cae
a la firma de debug (y una app así no puede actualizar a la firmada, ni al revés).

Para regenerar la clave desde cero (solo si se perdió el keystore):
```bash
keytool -genkeypair -v -keystore <infra-privada>/picaro-campo-release.jks -storetype PKCS12 \
  -keyalg RSA -keysize 2048 -validity 10000 -alias picaro-campo
```

## Primera ejecución (introducir URL + token)

Al abrir la app por primera vez aparece la pantalla de **Configuración**:

1. **URL base**: `https://campo.pi-caro.org` (o la que corresponda).
2. **Token**: el token Bearer que exige la API (`CAMPO_TOKEN` del microservicio).
3. (Opcional) **GW lat / GW lon**: posición del gateway para dibujar su marcador
   en el mapa. El contrato no expone estas coordenadas por la API, así que se
   introducen aquí; si se dejan vacías, simplemente no se dibuja el marcador.
4. Pulsa **Probar** para verificar `GET /health` y luego **Guardar**.

Se puede volver a esta pantalla en cualquier momento desde el menú ≡ →
*Configuración*.

## Estructura

```
lib/
  main.dart              arranque + enrutado (config vs home)
  config.dart            AppConfig (URL, token, gw) + persistencia
  app_state.dart         ChangeNotifier: REST + WS + sesión/métricas en vivo
  theme.dart             paleta §11, modo oscuro
  runs.dart              las 6 corridas (§5)
  api/campo_api.dart     cliente REST (§6)
  api/campo_ws.dart      WebSocket con reconexión + backoff (§7)
  ble/ble_client.dart    cliente BLE: escaneo por UUID, bond explícito,
                         Comando/Estado, reconexión con backoff (1→15 s)
  models/                Session, Metrics, Uplink, Summary, responses…
  screens/               config, home, panel, mapa, graficos, sesiones,
                         dispositivo (BLE), acerca, ayuda
  widgets/               big_button, run_selector, oled_panel, warning_banner,
                         line_chart, points_map (mapa offline)
  utils/geo.dart         haversine (escala del mapa offline)
assets/
  icon/ (icon, foreground, background)   branding/ (splash)
```

## Notas de coherencia con el contrato

- La clave del campo de clase en el JSON es literalmente `class` (valores
  `"A"`/`"C"`); en Dart el campo se llama `sessionClass` pero (de)serializa con
  `json['class']` / `'class': ...`.
- `battery_pct` puede llegar **null** y se muestra como «--» (no como 0).
- `pdr_est` se etiqueta siempre como **est.**
- WebSocket: `wss://host/ws?token=<token>`, con reconexión exponencial
  (1→30 s) y keepalive `{"type":"pong"}`.

## Notas de la mitad BLE

- **La app no guarda ningún secreto de BLE.** Las llaves del emparejamiento las
  custodia Android por un lado y la sonda por el otro. Consecuencia práctica:
  **desinstalar y reinstalar la app no obliga a emparejar de nuevo**, y no hay
  ninguna clave que limpiar ni migrar.
- **Emparejamiento explícito.** El cliente pide `createBond()` en cuanto conecta,
  en vez de dejar que lo dispare el primer acceso a una característica protegida.
  Los dos caminos funcionan contra el mismo firmware; el explícito evita un baile
  de «falla, espera, reintenta» con un fallo esperado en medio.
- **Filtro por UUID de servicio, nunca por nombre.** El nombre viaja en el *scan
  response* (no cabe en el advertising junto a un UUID de 128 bits), así que
  filtrar por nombre da resultados inconsistentes entre fabricantes.
- **Errores ATT propios de la aplicación:** llegan como enteros crudos **130**
  (longitud), **131** (parámetro) y **132** (la sonda no admite ese comando en su
  estado actual). No existen constantes con nombre en `BluetoothGatt` para ese
  rango; se mapean por número. El **132** es el único que verá el usuario y por
  eso su mensaje se redacta con cuidado.
- **Una conexión a la vez.** Mientras un móvil tiene la sonda, ésta deja de
  anunciarse. Por eso el cliente hace `disconnect()` explícito al salir de la
  pantalla de dispositivo: Android a veces mantiene la conexión GATT tras cerrar
  la app y la sonda quedaría invisible para los demás.
- **Al reconectar no se reenvía ningún comando pendiente.** Nunca. Se re-lee el
  estado y se muestra lo que la sonda diga: mientras el enlace estaba caído, la
  corrida siguió.

## Publicar una versión

`pubspec.yaml` lleva la versión de la app (`version: 2.0.0+2` para la v2). Para
publicar: subir `versionName`/`versionCode` ahí, `flutter build apk --release`
(firma sola con el keystore) y `gh release create vX.Y.Z <apk>`. El repo es
privado, así que la descarga queda limitada a colaboradores.

## Estado de verificación

El código se verificó con el SDK disponible (Flutter 3.27.1 / Dart 3.6.0):

- `flutter pub get` — resuelve todas las dependencias con las versiones fijadas.
- `flutter analyze` — **0 errores, 0 warnings**; solo 3 avisos informativos de
  `withOpacity` (deprecado en Flutter ≥ 3.27). Se mantiene `withOpacity` a
  propósito porque `withValues` no existe en versiones anteriores a 3.27 y el
  `pubspec` admite Flutter ≥ 3.16.
- `dart run flutter_launcher_icons` y `flutter_native_splash:create` — generan
  icono adaptativo y splash de Android a partir de los PNG de `assets/`.
- `flutter build apk` — produce el APK (tras el ajuste de Gradle/AGP descrito en
  «Solución de problemas»).

Las carpetas de plataforma y de build no se versionan (se regeneran con
`flutter create .`); por eso el árbol entregado contiene solo el código fuente,
`pubspec.yaml`, los assets y este README.
