# capturas_lns/ — capturas MQTT en campo

`captura_lns.sh` escribe aquí un `eventos_<fecha>.jsonl` por día (una línea JSON
por evento MQTT). Necesita `PICARO_SSH_KEY` y, opcionalmente, `DEV_TTGO` y
`DEV_TBEAM` en el entorno.

## Datos crudos: no se publican

Los archivos de esta carpeta (los `eventos_*.jsonl`) **no se versionan** (están en `.gitignore`,
sección «Datos crudos privados»): contienen trazas GPS en torno al laboratorio,
EUIs reales y metadatos del servidor de red que no se pueden anonimizar sin
destruirlos. Se conservan solo en local.

El **dataset público**, anonimizado, está en `reporte/datos/` (ver su
`DICCIONARIO.md`). Este `LEEME.md` sí se versiona, para que la carpeta exista
en el repositorio y se sepa qué va aquí.
