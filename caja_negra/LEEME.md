# caja_negra/ — copias íntegras de la microSD

Copia tal cual de la microSD de la sonda (`Serie 1/` y `banco pruebas/`), con
los `<run_id>.csv` y los `_dl.csv` de downlinks.

## Datos crudos: no se publican

Los archivos de esta carpeta (registros completos de la microSD) **no se versionan** (están en `.gitignore`,
sección «Datos crudos privados»): contienen trazas GPS en torno al laboratorio,
EUIs reales y metadatos del servidor de red que no se pueden anonimizar sin
destruirlos. Se conservan solo en local.

El **dataset público**, anonimizado, está en `reporte/datos/` (ver su
`DICCIONARIO.md`). Este `LEEME.md` sí se versiona, para que la carpeta exista
en el repositorio y se sepa qué va aquí.
