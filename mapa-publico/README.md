# mapa-publico — mapa en vivo de la red PiCARO (https://pi-caro.org)

Mapa público con los dispositivos del tenant **Proyecto PiCARO** en ChirpStack:
qué datos reportan (el `object` de su codec, tal cual) y con qué calidad los
recibe cada gateway (RSSI, SNR y margen sobre el mínimo del SF).

```
Mosquitto (1883 interno, usuario de solo lectura, event/up)
   └─> picaro-mapa: filtro por tenant + tag publico ─> SQLite (7 días) ─> SSE al navegador
Postgres de ChirpStack (rol de solo lectura por columnas) ─> catálogo cada 60 s
Caddy: pi-caro.org ─> picaro-mapa:8000   ·   www ─> 301 a la raíz
```

Mismo patrón que `microservicio/` + `despliegue-campo/`: compose propio, unido a
la red del stack, sin puertos publicados; Caddy le pone HTTPS delante.

## Publicar un dispositivo

En la consola de ChirpStack (tenant Proyecto PiCARO) añade un tag al dispositivo
o a su aplicación:

| Dónde | Tag | Efecto |
|---|---|---|
| Dispositivo | `publico = true` | Se publica |
| Aplicación | `publico = true` | Se publican todos sus dispositivos |
| Dispositivo | `publico = false` | No se publica aunque su app tenga `publico = true` |

Aparece en el mapa en menos de 60 s, sin reiniciar nada. Quitar el tag lo retira.

## Qué se muestra de cada nodo

- **Proyecto** (nombre de la app) y **nodo** (nombre del dispositivo).
- **Datos**: el `object` decodificado, sin renombrar ni traducir. **Los codecs no
  se tocan**: cada uno es de un equipo distinto. Si el perfil no tiene codec, solo
  se muestran proyecto, nodo y señal.
- **Señal** por gateway del último uplink, SF/BW, frecuencia, fCnt, y en el
  historial de 7 días: RSSI/SNR, campos numéricos, paquetes perdidos (huecos de
  fCnt) y los últimos 30 mensajes.

## Estado de cada nodo

Se calcula en el navegador con el tiempo desde su último uplink (en LoRaWAN no hay
"desconexión": solo dejan de llegar uplinks).

| Estado | Condición | En el mapa | En la lista |
|---|---|---|---|
| Activo | último uplink hace < 5 min | color según el margen | margen en dB |
| Activo (atenuado) | entre 5 min y 1 h | color del último margen, semitransparente | margen en dB, punto atenuado |
| Inactivo | entre 1 h y 24 h | gris | gris, "inactivo" |
| Fuera del mapa | más de 24 h | no aparece | sección "Inactivos más de 24 h" |
| Sin datos | publicado pero sin uplinks todavía | en el ITPA, borde discontinuo | "sin datos" |

El último uplink de cada nodo se conserva aunque supere los 7 días del historial,
para que un nodo apagado no vuelva a contarse como "sin datos".

## Geolocalización

Para cada uplink, en este orden:

1. **Declarada en el device profile** con tags `geo_lat`, `geo_lon` (y opcional
   `geo_alt`) cuyo valor es la ruta del campo dentro del `object`, con puntos si
   va anidado (p. ej. `geo_lat = gps.y`). Si están declarados, no se adivina nada.
2. **Detectada** por nombre: el primer par `lat | latitude | latitud` con
   `lon | lng | long | longitude | longitud` (sin distinguir mayúsculas, hasta
   3 niveles). Se descartan `null` y `0,0`.
3. **ITPA** (`ITPA_LAT`, `ITPA_LON`) si el nodo nunca ha reportado posición; se
   dibuja con borde discontinuo.

La última posición válida se conserva aunque los siguientes uplinks no la traigan
(en VUELO solo el paquete P1 lleva posición).

Los gateways se dibujan si tienen ubicación en ChirpStack o la reportan en
`rxInfo` (GPS propio). Con `0,0` no salen como marcador, aunque sí en la tabla de
señal de cada nodo.

## Identidad visual

Título del sitio: **SatLink 2026 · Red PiCARO**.

| Uso | Color |
|---|---|
| Cabecera, acento (selección, gráficas, enlaces) | Azul TecNM `#1B396A` |
| Franja bajo la cabecera | ITPA: amarillo `#F7A90F`, rojo `#E52D30`, índigo `#393685` |
| Modo oscuro (fondos y paneles) | Azul noche de SatLink `#021132` y derivados |
| Calidad de señal (marcadores, márgenes) | Semáforo verde / ámbar / rojo, **independiente** de los colores institucionales |

Los colores institucionales solo se usan en la interfaz: en el mapa, el color de un
marcador significa calidad de señal.

Logos en `picaro_mapa/static/marca/`, derivados de los originales (fuera del repo,
en `C:\dev\PiCARO\Logos`) solo con cambio de tamaño:

| Fichero | Origen | Notas |
|---|---|---|
| `tecnm.png` | `tecnmblanco.png` | Versión blanca: solo sobre el azul TecNM. Enlaza a https://www.tecnm.mx/ |
| `tecnm-engrane.png` | `tecnmblanco.png` | Solo el engrane, para la cabecera en móvil (recorte autorizado) |
| `itpa.png` | `itpa.png` | Siempre sobre un recuadro blanco (texto oscuro). Enlaza a https://pabellon.tecnm.mx/ |
| `satlink.png`, `satlink-64.png` | `satlink-2026.png` | Recorte circular con transparencia; el de 64 px es el favicon. Sin enlace |
| `ieee.png` | `ieee_blue.jpg` | Recortado el margen blanco. Enlaza a https://www.ieee.org/ |
| `iea.png` | `escudo-iea.png` | Instituto de Educación de Aguascalientes. Enlaza a https://www.iea.gob.mx/ |

El logo del ITPA no se recorta. Cabecera: TecNM, título, ITPA y SatLink (en móvil,
solo el engrane, el título y SatLink). Al pie de la lista, en todas las pantallas, el
bloque **Organizan**: TecNM, ITPA, IEEE e IEA, cada uno en su recuadro.

Los logos se exportan al doble o triple de su tamaño en pantalla para que se vean
nítidos en pantallas de alta densidad.

**Caché:** `index.html` carga `app.css`, `app.js` y `marca/*` con `?v=<versión>`, y
Caddy manda `Cache-Control: no-cache`. **Al cambiar CSS, JS o logos, sube el valor de
`v`** en `index.html`; si no, un navegador puede mezclar ficheros nuevos y viejos.

## Qué no se publica nunca

DevEUI, DevAddr, EUIs de gateway ni IPs. Nodos y gateways se identifican con un
HMAC de 12 caracteres (`ID_SECRET`); la SQLite tampoco guarda EUIs. Los eventos de
otros tenants se descartan en memoria. Los valores de los codecs se insertan en la
página como texto, nunca como HTML.

## Despliegue

Requisitos en el servidor del LNS (una sola vez):

1. **Usuario MQTT de solo lectura** `picaro-mapa`. Contraseña con
   `mosquitto_passwd` y, en el `acl`, **por encima** del bloque generado de los
   equipos:

   ```
   user picaro-mapa
   topic read application/+/device/+/event/up
   ```

   Recargar sin cortar a nadie: `docker compose kill -s HUP mosquitto`.

2. **Rol de Postgres de solo lectura**, solo con las columnas que usa el servicio:

   ```sql
   create role picaro_mapa login password '<contraseña>' connection limit 3;
   grant connect on database chirpstack to picaro_mapa;
   grant usage on schema public to picaro_mapa;
   grant select (id, tenant_id, name, tags) on application to picaro_mapa;
   grant select (dev_eui, application_id, device_profile_id, name, tags) on device to picaro_mapa;
   grant select (id, tenant_id, name, tags, payload_codec_runtime) on device_profile to picaro_mapa;
   grant select (gateway_id, tenant_id, name, latitude, longitude) on gateway to picaro_mapa;
   ```

3. **`.env`**: copia `.env.example`, rellénalo (`ID_SECRET` con `openssl rand -hex 32`)
   y déjalo con permisos 600. Si `ID_SECRET` cambia, cambian los IDs públicos y el
   historial guardado queda huérfano.

4. **Arranque**: copia esta carpeta al servidor y

   ```bash
   docker compose up -d --build
   ```

5. **Dominio**: registro `A @` del dominio hacia la IP del servidor, y los bloques
   de `Caddyfile.snippet` al final del Caddyfile del stack. Validar y recargar:

   ```bash
   docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
   docker compose exec caddy caddy reload   --config /etc/caddy/Caddyfile --adapter caddyfile
   ```

   Caddy pide el certificado solo. Añade los bloques **después** de que el DNS
   resuelva a la IP del servidor, o la validación de Let's Encrypt fallará.

   > El Caddyfile se monta como fichero: edítalo en sitio (`cat >>`, editor), no
   > con `sed -i`, que cambia el inodo y el contenedor seguiría viendo el viejo.

## Operación

```bash
docker compose up -d --build                   # tras cambiar el código
docker logs --tail 50 picaro-mapa
docker exec picaro-mapa python -c "import urllib.request as u;print(u.urlopen('http://localhost:8000/salud').read())"
```

`/salud` devuelve 404 desde Internet (lo bloquea Caddy): úsalo desde el contenedor.

Pruebas: `pip install -r requirements.txt pytest` y `python -m pytest -q tests`.

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| El nodo no aparece | Falta el tag `publico=true`, o aún no pasan 60 s |
| Aparece en el ITPA teniendo GPS | Sin fix (lat/lon nulos o 0,0), o su codec usa otros nombres: declara `geo_lat/geo_lon` en el perfil |
| "Reconectando…" fijo | El contenedor está caído o Caddy no tiene `flush_interval -1` |
| Un gateway no sale en el mapa | Tiene ubicación `0,0` en ChirpStack |
