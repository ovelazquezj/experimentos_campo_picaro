"""picaro_campo — Microservicio de campo de PiCARO (FastAPI + MQTT + SQLite).

Ver docs/CONTRATO-CAMPO.md (fuente de verdad). Punto de entrada ASGI:
`picaro_campo.main:app`.
"""
from .config import VERSION

__version__ = VERSION
