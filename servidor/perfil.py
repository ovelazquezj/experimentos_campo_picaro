#!/usr/bin/env python3
"""
perfil.py — Cambia el device profile de la radiosonda entre el del ejercicio 09
y los de las pruebas de terreno (Clase A / Clase C).

POR QUE HACE FALTA
------------------
El device es el mismo (`0011223344550001`), pero lo que se ejecuta encima no:

  · ejercicio 09  -> payload de 19 bytes big-endian, Clase A
  · terreno A / C -> payload de 11/14 bytes little-endian, Clase A o C

El codec vive en el device profile, asi que si el perfil no coincide con el
firmware flasheado, el campo `object` sale mal y es facil no darse cuenta hasta
el analisis. Este script hace el cambio en un comando y verifica el resultado.

QUE NO HACE
-----------
No toca la configuracion del servidor. Cambiar el perfil de un device es una
operacion sobre un objeto propio del proyecto; modificar `region_*.toml` o
`chirpstack.toml` NO se hace nunca desde aqui.

USO
---
    python perfil.py               # dice cual esta activo
    python perfil.py ej09          # vuelve al del ejercicio 09
    python perfil.py terreno-a     # pruebas de terreno, Clase A
    python perfil.py terreno-c     # pruebas de terreno, Clase C

Necesita servidor/ids_privados.json (DevEUI, IDs de los perfiles y ruta del
fichero con el token de la API); ver privado.py.
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

import privado

API     = "https://api.pi-caro.org"
# IDs reales fuera del repo: servidor/ids_privados.json (ver privado.py)
_IDS    = privado.cargar()
DEV_EUI = _IDS["dev_eui"]
TOKEN_F = _IDS["token_file"]

PERFILES = {
    "ej09":      (_IDS["perfiles"]["ej09"], "Radiosonda-PICARO-Full-US915",
                  "ejercicio 09 — payload 19 B big-endian, Clase A"),
    "terreno-a": (_IDS["perfiles"]["terreno-a"], "Radiosonda-Terreno-ClaseA",
                  "pruebas de terreno — payload 11/14 B little-endian, Clase A"),
    "terreno-c": (_IDS["perfiles"]["terreno-c"], "Radiosonda-Terreno-ClaseC",
                  "pruebas de terreno — payload 11/14 B little-endian, Clase C"),
}


def api(method, path, body=None):
    tok = TOKEN_F.read_text().strip()
    req = urllib.request.Request(
        API + path, method=method,
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[x] {method} {path} -> {e.code}: {e.read().decode()[:200]}")


def activo():
    dev = api("GET", f"/api/devices/{DEV_EUI}")["device"]
    pid = dev["deviceProfileId"]
    for clave, (i, nombre, desc) in PERFILES.items():
        if i == pid:
            return clave, nombre, desc
    return None, pid, "(perfil no reconocido)"


def main():
    if len(sys.argv) < 2:
        clave, nombre, desc = activo()
        print(f"\n  Device  : {DEV_EUI}")
        print(f"  Perfil  : {nombre}")
        print(f"  Es decir: {desc}\n")
        print("  Para cambiarlo:  python perfil.py [ej09|terreno-a|terreno-c]\n")
        return

    destino = sys.argv[1].lower()
    if destino not in PERFILES:
        raise SystemExit(f"[x] Perfil desconocido: {destino}. Usa: {', '.join(PERFILES)}")

    pid, nombre, desc = PERFILES[destino]
    dev = api("GET", f"/api/devices/{DEV_EUI}")["device"]
    if dev["deviceProfileId"] == pid:
        print(f"  Ya estaba en {nombre}. Nada que hacer.")
        return

    anterior = activo()[1]
    dev["deviceProfileId"] = pid
    api("PUT", f"/api/devices/{DEV_EUI}", {"device": dev})

    _, ahora, desc_ahora = activo()
    if ahora != nombre:
        raise SystemExit(f"[x] El cambio no surtio efecto: sigue en {ahora}")

    print(f"\n  {anterior}")
    print(f"    -> {nombre}")
    print(f"       {desc_ahora}\n")
    print("  Recuerda: el firmware flasheado debe corresponder con este perfil,")
    print("  o el payload se decodificara mal sin dar error visible.\n")


if __name__ == "__main__":
    main()
