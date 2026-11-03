#!/usr/bin/env python3
"""
pinger.py — Lanza los downlinks de medida de latencia desde el SERVIDOR.

*** OBSOLETO (2026-08-29, D-61) — NO USAR ***
---------------------------------------------
Este script era un proceso nohup suelto y NO envio un solo ping en toda la
campana de agosto-2026: downlinks_enviados.csv quedo como el placeholder del
19/07 y en los _dl.csv de la microSD no hay ningun ping con cadencia de 60 s.
Un proceso aparte, sin supervision ni relacion con la sesion de captura, falla
en silencio y nadie lo nota hasta el analisis.

Su funcion vive ahora en el MICROSERVICIO (microservicio/picaro_campo/
sessions.py): mientras una sesion captura, un ciclo asyncio ligado a ella
encola un ping fPort 98 cada PING_INTERVAL_S (60 s por defecto) por el mismo
camino que el /ping manual, comparte la secuencia con el, persiste cada envio
en la SQLite (tabla downlinks) y lo exporta como <run_label>_dl.csv junto al
CSV de la sesion. El ciclo muere con la sesion. Ver D-61 en BITACORA.md y la
enmienda §15 de docs/CONTRATO-CAMPO.md.

Se conserva solo como referencia historica del formato y del diagnostico.

POR QUE EN EL SERVIDOR Y NO EN CAMPO
------------------------------------
En el cerro no hay cobertura de datos, asi que el equipo no puede enviar
downlinks desde alli. Si los pings los lanzara una persona con portatil, el
escenario 3 se quedaria sin medida de latencia, que es una de las tres
hipotesis del experimento.

Este script corre en el servidor en la nube (que si tiene conectividad),
detecta solo cuando hay una corrida en marcha y envia los pings sin que nadie
tenga que hacer nada en campo.

COMO DETECTA LA CORRIDA
-----------------------
Se suscribe a los uplinks del device y lee el fPort, que identifica la corrida
(11..16 = escenario x clase). No hace falta decirle nada: en cuanto empiezan a
llegar uplinks con un fPort conocido, empieza a pinguear con ese run_id. Si
dejan de llegar durante SILENCIO_S, da la corrida por terminada y para.

SALIDA
------
CSV en downlinks_enviados.csv:   run_id,seq,utc_enviado,fport_uplink
La sonda registra por su lado en la microSD:  run_id,seq,utc_recibido
El cruce de ambos por (run_id, seq) da la latencia. El numero de secuencia
viaja como unico byte del payload del ping, asi que no hace falta nada mas
para emparejarlos.

USO (en el servidor)
--------------------
    pip install paho-mqtt
    python3 pinger.py --intervalo 60
    # y para dejarlo corriendo durante toda la campana:
    nohup python3 pinger.py > pinger.log 2>&1 &
"""
import argparse
import base64
import csv
import json
import os
import ssl
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# --- Configuracion del despliegue -------------------------------------------
HOST = "mqtt.pi-caro.org"
PORT = 8883
USER = "picaro"
# APP_ID y DEV_EUI reales por entorno (no se publican); por defecto, ejemplos.
APP_ID = os.environ.get("APP_ID", "<APP_ID>")
# El device del ejercicio 09, reutilizado (D-16 / R-04). NO hay un segundo
# dispositivo: aqui figuraba "...0002", copiado de un credentials.json que se
# quedo congelado en el diseño original. Con ese valor el pinger se suscribia al
# topic de un device inexistente, no detectaba ninguna corrida y no enviaba un
# solo ping — sin dar error, solo silencio. Habria dejado H4 sin datos.
DEV_EUI = os.environ.get("DEV_EUI", "0011223344550001")
FPORT_PING = 98

# fPort -> identificador de corrida. Debe coincidir con escenarios.h.
CORRIDAS = {
    11: "URBANO-A",  12: "URBANO-C",
    13: "TERRAZA-A", 14: "TERRAZA-C",
    15: "CERRO16-A", 16: "CERRO16-C",
}


class Pinger:
    def __init__(self, password, intervalo, silencio, salida, max_pings):
        self.intervalo = intervalo
        self.silencio = silencio
        self.salida = salida
        self.max_pings = max_pings

        self.lock = threading.Lock()
        self.corrida = None          # run_id activo, None si no hay corrida
        self.fport = None
        self.ultimo_uplink = 0.0
        self.seq = 0                 # numero de secuencia, 1..255 ciclico
        self.enviados = 0

        self.cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.cli.username_pw_set(USER, password)
        self.cli.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.cli.on_connect = self._on_connect
        self.cli.on_message = self._on_message

        nuevo = not os.path.exists(salida)
        self.fh = open(salida, "a", newline="", encoding="utf-8")
        self.csv = csv.writer(self.fh)
        if nuevo:
            self.csv.writerow(["run_id", "seq", "utc_enviado", "fport_uplink"])
            self.fh.flush()

    # --- MQTT ---------------------------------------------------------------
    def _on_connect(self, cli, userdata, flags, rc, props=None):
        if rc.is_failure if hasattr(rc, "is_failure") else rc != 0:
            print(f"[!] No pude conectar al broker: {rc}", flush=True)
            return
        topic = f"application/{APP_ID}/device/{DEV_EUI}/event/up"
        cli.subscribe(topic)
        print(f"[ok] Conectado. Escuchando {topic}", flush=True)

    def _on_message(self, cli, userdata, msg):
        try:
            ev = json.loads(msg.payload.decode())
        except Exception:
            return
        fport = ev.get("fPort")
        run = CORRIDAS.get(fport)
        if run is None:
            return   # uplink de otra cosa: no es una corrida del experimento

        with self.lock:
            self.ultimo_uplink = time.time()
            if run != self.corrida:
                # Cambio de corrida: se reinicia la secuencia para que el
                # cruce por (run_id, seq) no sea ambiguo entre corridas.
                print(f"\n[>>] Corrida detectada: {run} (fPort {fport})", flush=True)
                self.corrida = run
                self.fport = fport
                self.seq = 0
                self.enviados = 0

    # --- Envio --------------------------------------------------------------
    def _enviar_ping(self, run, seq):
        # El unico byte del payload es el numero de secuencia: es lo que
        # permite emparejar este envio con lo que registre la sonda.
        payload = base64.b64encode(bytes([seq])).decode()
        topic = f"application/{APP_ID}/device/{DEV_EUI}/command/down"
        cuerpo = json.dumps({
            "devEui": DEV_EUI, "confirmed": False,
            "fPort": FPORT_PING, "data": payload,
        })
        utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self.cli.publish(topic, cuerpo, qos=0)
        self.csv.writerow([run, seq, utc, self.fport])
        self.fh.flush()   # sin buffer: si el proceso muere no se pierde nada
        print(f"[ping] {run} seq={seq:3d} {utc}", flush=True)

    def bucle(self):
        self.cli.connect(HOST, PORT, keepalive=30)
        self.cli.loop_start()
        try:
            while True:
                time.sleep(1)
                with self.lock:
                    if self.corrida is None:
                        continue
                    # Silencio prolongado -> la corrida termino.
                    if time.time() - self.ultimo_uplink > self.silencio:
                        print(f"[--] {self.corrida} terminada "
                              f"({self.enviados} pings)\n", flush=True)
                        self.corrida = None
                        continue
                    if self.max_pings and self.enviados >= self.max_pings:
                        continue
                    if self.enviados and (time.time() - self._ultimo_ping) < self.intervalo:
                        continue
                    self.seq = (self.seq % 255) + 1
                    self.enviados += 1
                    self._ultimo_ping = time.time()
                    run, seq = self.corrida, self.seq
                self._enviar_ping(run, seq)
        except KeyboardInterrupt:
            print("\n[--] Detenido a mano", flush=True)
        finally:
            self.cli.loop_stop()
            self.fh.close()

    _ultimo_ping = 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--password", default=os.environ.get("MQTT_PASSWORD"),
                    help="contrasena MQTT (o variable de entorno MQTT_PASSWORD)")
    ap.add_argument("--intervalo", type=int, default=60,
                    help="segundos entre pings (por defecto 60)")
    ap.add_argument("--silencio", type=int, default=120,
                    help="segundos sin uplinks para dar la corrida por terminada")
    ap.add_argument("--max-pings", type=int, default=40,
                    help="pings maximos por corrida (0 = sin limite). El "
                         "protocolo pide >=30")
    ap.add_argument("--salida", default="downlinks_enviados.csv")
    args = ap.parse_args()

    if not args.password:
        print("[x] Falta la contrasena MQTT: usa --password o MQTT_PASSWORD",
              file=sys.stderr)
        sys.exit(1)

    print(f"Pinger listo. Intervalo {args.intervalo}s, "
          f"maximo {args.max_pings or 'sin limite'} pings por corrida.")
    print("Esperando a que empiece una corrida...\n")
    Pinger(args.password, args.intervalo, args.silencio,
           args.salida, args.max_pings).bucle()


if __name__ == "__main__":
    main()
