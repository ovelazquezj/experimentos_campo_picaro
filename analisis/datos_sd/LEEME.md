# datos_sd/ — CSV crudos de la microSD (lado ENVIADO)

Aquí van los `<run_id>.csv` que escribe el firmware en la microSD, tal cual, sin
renombrar. Ej.: `20260719-URBANO-A.csv`.

Es el **denominador del PDR**: lo que la sonda intentó enviar. `cruzar.py` los lee
de aquí por defecto (`--sd ./datos_sd`).

## Datos crudos: no se publican

Los archivos de esta carpeta (CSV de la microSD, con la posición GPS de cada envío) **no se versionan** (están en `.gitignore`,
sección «Datos crudos privados»): contienen trazas GPS en torno al laboratorio,
EUIs reales y metadatos del servidor de red que no se pueden anonimizar sin
destruirlos. Se conservan solo en local.

El **dataset público**, anonimizado, está en `reporte/datos/` (ver su
`DICCIONARIO.md`). Este `LEEME.md` sí se versiona, para que la carpeta exista
en el repositorio y se sepa qué va aquí.
