"""Catalogo del tenant leido de Postgres con un rol de solo lectura por columnas.

Decide QUE se publica: un dispositivo es publico si tiene el tag `publico=true`,
o si su aplicacion lo tiene y el dispositivo no lo anula con `publico=false`.
"""
import logging
from dataclasses import dataclass, field

import psycopg

log = logging.getLogger("catalogo")


def _si(tags: dict, clave: str):
    v = (tags or {}).get(clave)
    return None if v is None else str(v).strip().lower() in ("true", "si", "sí", "1", "yes")


@dataclass
class Dispositivo:
    eui: str
    nombre: str
    proyecto: str
    perfil: str
    tiene_codec: bool
    tags_perfil: dict


@dataclass
class Gateway:
    eui: str
    nombre: str
    lat: float | None
    lon: float | None


@dataclass
class Catalogo:
    dispositivos: dict = field(default_factory=dict)   # eui -> Dispositivo (solo publicos)
    gateways: dict = field(default_factory=dict)       # eui -> Gateway (todos los del tenant)


def leer(dsn: str, tenant_id: str) -> Catalogo:
    cat = Catalogo()
    with psycopg.connect(dsn, connect_timeout=10) as con, con.cursor() as cur:
        cur.execute(
            """
            select encode(d.dev_eui, 'hex'), d.name, d.tags, a.name, a.tags,
                   p.name, p.tags, p.payload_codec_runtime
              from device d
              join application a on a.id = d.application_id
              join device_profile p on p.id = d.device_profile_id
             where a.tenant_id = %s
            """,
            (tenant_id,),
        )
        for eui, nombre, dtags, app, atags, perfil, ptags, codec in cur.fetchall():
            dev = _si(dtags, "publico")
            if dev is False or not (dev or _si(atags, "publico")):
                continue
            cat.dispositivos[eui] = Dispositivo(
                eui=eui, nombre=nombre, proyecto=app, perfil=perfil,
                tiene_codec=(codec or "NONE") != "NONE", tags_perfil=ptags or {},
            )
        cur.execute(
            "select encode(gateway_id, 'hex'), name, latitude, longitude from gateway where tenant_id = %s",
            (tenant_id,),
        )
        for eui, nombre, lat, lon in cur.fetchall():
            ok = lat is not None and lon is not None and not (lat == 0 and lon == 0)
            cat.gateways[eui] = Gateway(eui, nombre, lat if ok else None, lon if ok else None)
    return cat
