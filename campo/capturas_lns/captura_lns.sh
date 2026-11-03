#!/bin/bash
# Captura continua de eventos MQTT (up/join/ack/txack/status) del TTGO y la T-Beam.
# Reconecta sola si se cae el SSH. Una linea JSON por evento, con el topic delante.
#
# La clave SSH y los DevEUI reales NO estan en el repo: van por entorno.
#   PICARO_SSH_KEY=<ruta-a-tu-clave-ssh> DEV_TTGO=... DEV_TBEAM=... ./captura_lns.sh
SSH_KEY="${PICARO_SSH_KEY:?Falta PICARO_SSH_KEY (ruta a tu clave SSH del servidor)}"
DEV_TTGO="${DEV_TTGO:-0011223344550003}"
DEV_TBEAM="${DEV_TBEAM:-0011223344550001}"
OUT="$(dirname "$0")/eventos_$(date -u +%Y-%m-%d).jsonl"
while true; do
  /c/Windows/System32/OpenSSH/ssh.exe -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    -i "$SSH_KEY" root@lns.pi-caro.org \
    'cd /opt/picaro-chirpstack && set -a && . ./.env && docker compose exec -T mosquitto sh -c "mosquitto_sub -h localhost -p 1883 -u $MQTT_CHIRPSTACK_USER -P $MQTT_CHIRPSTACK_PASSWORD -v -t application/+/device/'"$DEV_TTGO"'/event/+ -t application/+/device/'"$DEV_TBEAM"'/event/+"' \
    >> "$OUT"
  echo "$(date -u +%FT%TZ) reconectando" >&2
  sleep 5
done
