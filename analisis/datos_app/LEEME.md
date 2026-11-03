# datos_app/ — CSV descargados desde la app (lado RECIBIDO)

Aquí van los CSV que exporta la app (Sesiones → Descargar CSV): lo que LLEGÓ al
servidor, con RSSI/SNR/gateway. Es la otra mitad del cruce.

## Datos crudos: no se publican

Los archivos de esta carpeta (CSV exportados por la app, incluidos `banco/` y los `_dl.csv`) **no se versionan** (están en `.gitignore`,
sección «Datos crudos privados»): contienen trazas GPS en torno al laboratorio,
EUIs reales y metadatos del servidor de red que no se pueden anonimizar sin
destruirlos. Se conservan solo en local.

El **dataset público**, anonimizado, está en `reporte/datos/` (ver su
`DICCIONARIO.md`). Este `LEEME.md` sí se versiona, para que la carpeta exista
en el repositorio y se sepa qué va aquí.
