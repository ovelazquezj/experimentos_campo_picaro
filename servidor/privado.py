"""
privado.py — IDs reales del despliegue, fuera del repositorio.

perfil.py y desplegar_decoder.py necesitan el DevEUI del device, los IDs de los
device profiles de ChirpStack y la ruta del fichero con el token de la API. No
se publican: se leen de `ids_privados.json` (en .gitignore), junto a este
fichero. La plantilla versionada es `ids_privados.example.json`:

    cp ids_privados.example.json ids_privados.json
    # y pon los valores reales (consola de ChirpStack)
"""
import json
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent
PRIVADO = AQUI / "ids_privados.json"


def cargar():
    if not PRIVADO.exists():
        raise SystemExit("[x] Falta servidor/ids_privados.json: copia "
                         "ids_privados.example.json y rellenalo con los IDs reales")
    datos = json.loads(PRIVADO.read_text(encoding="utf-8"))
    datos["token_file"] = pathlib.Path(datos["token_file"]).expanduser()
    return datos
