"""
auth.py — Autenticacion por token compartido.

Toda la API (salvo /health) exige `Authorization: Bearer <CAMPO_TOKEN>` (§6). El
WebSocket lo recibe por query param `?token=...` porque muchos clientes WS de
navegador no permiten fijar cabeceras (§7).

No es OAuth ni JWT a proposito: es un unico token compartido entre la app y el
servicio, suficiente para una herramienta interna de campo detras de HTTPS. La
comparacion se hace con hmac.compare_digest para no filtrar informacion por el
tiempo de comparacion.
"""
import hmac

from fastapi import Header, HTTPException, Request


def _token_ok(candidate: str, expected: str) -> bool:
    if not expected or not candidate:
        return False
    return hmac.compare_digest(candidate, expected)


def require_token(request: Request, authorization: str = Header(default=None)):
    """Dependencia FastAPI: valida el Bearer o corta con 401."""
    expected = request.app.state.config.campo_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="falta el token Bearer")
    token = authorization[len("Bearer "):].strip()
    if not _token_ok(token, expected):
        raise HTTPException(status_code=401, detail="token invalido")
    return True


def ws_token_ok(token: str, expected: str) -> bool:
    """Valida el token del WebSocket (query param)."""
    return _token_ok(token or "", expected)
