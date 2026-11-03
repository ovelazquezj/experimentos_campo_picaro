#!/usr/bin/env python3
"""
desplegar_decoder.py — Sube firmware/decoder.js a los device profiles de terreno.

POR QUE EXISTE
--------------
El codec (decoder.js) vive en el device profile de ChirpStack, no en el device.
Si el firmware cambia el formato del payload, el codec del servidor tiene que
cambiar con el o el campo `object` sale mal sin dar error. Este script mantiene
ambos device profiles del experimento (Clase A y Clase C) con el MISMO codec, en
un comando, en vez de copiar y pegar en la consola web dos veces.

QUE TOCA Y QUE NO
-----------------
Solo escribe en los device profiles `terreno-a` y `terreno-c`, que son objetos
PROPIOS de este proyecto. Hace un round-trip (GET, cambia unicamente
payloadCodecRuntime/payloadCodecScript, PUT) para no alterar ningun otro campo.
NO toca la configuracion global del servidor (region_*.toml, chirpstack.toml),
ni el perfil del ejercicio 09, ni ningun otro proyecto.

USO
---
    python desplegar_decoder.py            # muestra que cambiaria, sin escribir
    python desplegar_decoder.py --aplicar  # lo aplica y verifica

Necesita servidor/ids_privados.json, igual que perfil.py (ver privado.py).
"""
import difflib
import json
import pathlib
import sys
import urllib.error
import urllib.request

import privado

API        = "https://api.pi-caro.org"
_IDS       = privado.cargar()          # IDs reales: servidor/ids_privados.json
TOKEN_F    = _IDS["token_file"]
DECODER_F  = pathlib.Path(__file__).resolve().parents[1] / "firmware" / "decoder.js"

# Solo los perfiles del experimento de terreno. El de ej09 NO se toca.
PERFILES = {
    "terreno-a": _IDS["perfiles"]["terreno-a"],
    "terreno-c": _IDS["perfiles"]["terreno-c"],
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
        raise SystemExit(f"[x] {method} {path} -> {e.code}: {e.read().decode()[:300]}")


def diff(viejo, nuevo, nombre):
    a = (viejo or "").splitlines()
    b = (nuevo or "").splitlines()
    lineas = list(difflib.unified_diff(a, b, fromfile=f"{nombre} (servidor)",
                                       tofile=f"{nombre} (decoder.js)", lineterm=""))
    return lineas


def main():
    aplicar = "--aplicar" in sys.argv
    nuevo = DECODER_F.read_text(encoding="utf-8")
    print(f"decoder.js: {DECODER_F}  ({len(nuevo)} bytes)\n")

    algun_cambio = False
    for clave, pid in PERFILES.items():
        dp = api("GET", f"/api/device-profiles/{pid}")["deviceProfile"]
        actual = dp.get("payloadCodecScript", "")
        runtime = dp.get("payloadCodecRuntime", "NONE")

        if actual == nuevo and runtime == "JS":
            print(f"  {clave:10} ({dp['name']}): ya esta al dia. Nada que hacer.")
            continue

        algun_cambio = True
        d = diff(actual, nuevo, "decoder.js")
        print(f"  {clave:10} ({dp['name']}): runtime={runtime} -> JS, "
              f"{'sin codec previo' if not actual else f'{len(d)} lineas de diff'}")
        if d and len(d) <= 40:
            for l in d:
                print("      " + l)

        if aplicar:
            dp["payloadCodecRuntime"] = "JS"
            dp["payloadCodecScript"]  = nuevo
            api("PUT", f"/api/device-profiles/{pid}", {"deviceProfile": dp})
            verif = api("GET", f"/api/device-profiles/{pid}")["deviceProfile"]
            ok = (verif.get("payloadCodecScript") == nuevo
                  and verif.get("payloadCodecRuntime") == "JS")
            print(f"      -> {'APLICADO y verificado' if ok else 'ERROR: no coincide tras PUT'}")
            if not ok:
                raise SystemExit(1)

    print()
    if not algun_cambio:
        print("Todo al dia.")
    elif aplicar:
        print("Hecho. Los dos perfiles de terreno llevan el mismo decoder.js.")
    else:
        print("Esto es una PREVISUALIZACION. Nada se ha escrito.")
        print("Para aplicarlo:  python desplegar_decoder.py --aplicar")


if __name__ == "__main__":
    main()
