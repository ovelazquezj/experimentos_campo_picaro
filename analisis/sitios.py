"""
sitios.py  -  Posicion del laboratorio y EUIs reales, fuera del repositorio.

La posicion exacta del gateway del laboratorio y los EUIs de las placas no se
publican. Los scripts de este directorio los leen de `sitios_privados.json`
(en .gitignore). La plantilla versionada es `sitios_privados.example.json`:

    cp sitios_privados.example.json sitios_privados.json
    # y pon la posicion y los EUIs reales

Si falta el fichero privado se usa la plantilla (con un aviso): los scripts
corren, pero las distancias al gateway salen con la posicion redondeada y los
filtros por EUI no encuentran nada en los datos crudos.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PRIVADO = os.path.join(AQUI, "sitios_privados.json")
EJEMPLO = os.path.join(AQUI, "sitios_privados.example.json")


def _cargar():
    if os.path.exists(PRIVADO):
        ruta = PRIVADO
    else:
        ruta = EJEMPLO
        print("[!] Falta analisis/sitios_privados.json: uso la plantilla "
              "(posicion redondeada y EUIs de ejemplo)", file=sys.stderr)
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


_S = _cargar()

# (lat, lon) del gateway del laboratorio
GATEWAY = (float(_S["gateway_laboratorio"]["lat"]), float(_S["gateway_laboratorio"]["lon"]))

# EUIs (16 hex, minusculas)
EUI = {k: v.lower() for k, v in _S["eui"].items()}
