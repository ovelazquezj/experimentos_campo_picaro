"""
models.py — Modelos Pydantic de request (y helpers de respuesta).

Las RESPUESTAS del contrato (session, metrics, summary) son dicts planos que se
arman en sessions.py; no las modelamos con Pydantic para no duplicar el esquema
del contrato en dos sitios (la fuente de verdad es §4/§6). Aqui solo validamos
lo que ENTRA, que es donde interesa rechazar pronto con un 400 claro.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StartRequest(BaseModel):
    """Cuerpo de POST /session/start: {scenario, class, sonda?}.

    `class` es palabra reservada en Python, asi que el campo interno se llama
    `class_` y se expone con alias "class" (lo que manda la app). Se permite
    poblar por nombre o por alias (populate_by_name) para que los tests puedan
    construirlo comodo."""
    model_config = ConfigDict(populate_by_name=True)

    scenario: str
    class_: str = Field(alias="class")
    # Sonda de la sesion (D-65). Opcional: la app <= 2.1.0 no lo manda y sus
    # sesiones son de la T-Beam, como siempre.
    sonda: str = "tbeam"


class PosicionRequest(BaseModel):
    """Cuerpo de POST /session/{id}/posicion: un fix del GPS del telefono
    (D-65). `ts` es el instante del fix (epoch UTC); sin el, el de llegada."""
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: Optional[float] = None
    precision_m: Optional[float] = Field(default=None, ge=0)
    ts: Optional[float] = None


class ProfileRequest(BaseModel):
    """Cuerpo de POST /profile: {profile}. El valor se valida contra los perfiles
    conocidos en el endpoint (para devolver 400, no 422)."""
    profile: str
    sonda: str = "tbeam"
