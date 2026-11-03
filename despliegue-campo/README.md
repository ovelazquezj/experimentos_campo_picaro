# Despliegue del microservicio de campo (Opción A — subdominio por Caddy)

Entrega para el **coordinador**: ficheros + pasos exactos. El despliegue real lo
hace él por SSH con autorización del usuario. Ver §9 del contrato.

Esta opción **no abre ningún puerto nuevo** en el host ni en el firewall del proveedor
de la nube: el contenedor escucha en un puerto interno `8000` y el Caddy que ya
sirve ChirpStack hace de pasarela HTTPS/WebSocket para `campo.pi-caro.org`.

## Ficheros de esta carpeta

| Fichero | Qué es |
|---|---|
| `docker-compose.campo.yml` | Compose separado; red externa `picaro`, sin `ports:`, volumen SQLite, lee `.env` |
| `Caddyfile.campo.snippet` | Bloque a añadir al Caddyfile de ChirpStack |
| `README.md` | Este documento |

## Requisitos previos

- El stack de ChirpStack ya corriendo (`<infra-privada>/picaro-chirpstack`), con su red
  Docker creada y su Caddy en marcha.
- Un registro **DNS A** `campo.pi-caro.org` apuntando a la IP del servidor (para
  que Caddy pueda emitir el certificado por HTTP-01).
- El código de `../microservicio/` presente en el servidor (para `build`).

## Pasos

### 1. Preparar el `.env`

En esta carpeta (`despliegue-campo/`):

```bash
cp ../microservicio/.env.example .env
# Edita .env y rellena: CAMPO_TOKEN, MQTT_PASSWORD, CHIRPSTACK_TOKEN,
# GW_LAT, GW_LON, APP_ID, DEV_EUI* y PROFILE_ID_* (los de tu ChirpStack;
# el .env.example solo trae valores de ejemplo).
#   CAMPO_TOKEN:    openssl rand -hex 24
#   CHIRPSTACK_TOKEN: el token de la API de ChirpStack (documentacion interna)
```

### 2. Confirmar el nombre real de la red externa

El compose de ChirpStack tiene proyecto `picaro-chirpstack` y red `picaro`, así
que Docker la nombra `picaro-chirpstack_picaro`. Compruébalo:

```bash
docker network ls | grep picaro
```

Si el nombre difiere, añade al `.env` de esta carpeta:

```
PICARO_NETWORK=<el-nombre-que-hayas-visto>
```

### 3. Levantar el contenedor

```bash
docker compose -f docker-compose.campo.yml up -d --build
docker compose -f docker-compose.campo.yml logs -f    # comprobar "MQTT OK ..."
```

El contenedor `picaro-campo` queda en la red `picaro`, sin puerto publicado. Aún
no es accesible desde fuera: falta el paso de Caddy.

### 4. Añadir el bloque de Caddy (en el stack de ChirpStack)

> Estos cambios tocan `<infra-privada>/picaro-chirpstack/`. Se dejan aquí **como
> instrucciones**; este agente no modifica esos ficheros.

1. **Variable de dominio.** En el `.env` del stack de ChirpStack añade:
   ```
   DOMAIN_CAMPO=campo.pi-caro.org
   ```
   y en `<infra-privada>/picaro-chirpstack/docker-compose.yml`, servicio `caddy`, añade la
   variable a `environment:`:
   ```yaml
       environment:
         - DOMAIN_CAMPO=${DOMAIN_CAMPO:?falta DOMAIN_CAMPO en .env}
   ```

2. **Bloque del sitio.** Añade el contenido de `Caddyfile.campo.snippet` al final
   de `<infra-privada>/picaro-chirpstack/caddy/Caddyfile`:
   ```
   {$DOMAIN_CAMPO} {
       reverse_proxy picaro-campo:8000
   }
   ```
   (Si prefieres no tocar el entorno de Caddy, usa el dominio literal
   `campo.pi-caro.org { ... }` como indica el propio snippet.)

3. **Recargar Caddy** (recrea el contenedor para que tome la nueva variable):
   ```bash
   cd <infra-privada>/picaro-chirpstack
   docker compose up -d caddy
   ```
   Caddy pedirá el certificado de `campo.pi-caro.org` automáticamente.

### 5. Comprobar

```bash
curl https://campo.pi-caro.org/health
# → {"status":"ok","mqtt_connected":true,"version":"1.0.0"}
```

Desde la app: configura `https://campo.pi-caro.org` y el `CAMPO_TOKEN`. El
WebSocket usa `wss://campo.pi-caro.org/ws?token=<CAMPO_TOKEN>`.

## Operación

```bash
# Ver estado / logs
docker compose -f docker-compose.campo.yml ps
docker compose -f docker-compose.campo.yml logs -f

# Actualizar tras cambios de código
docker compose -f docker-compose.campo.yml up -d --build

# Parar (los datos persisten en el volumen campo-data)
docker compose -f docker-compose.campo.yml down
```

La SQLite vive en el volumen `campo-data` (`/data/campo.db` dentro del
contenedor) y sobrevive a reinicios y reconstrucciones de la imagen.
