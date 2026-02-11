"""
API interna para el backend principal.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
import logging

from app.services.pseudonymization import pseudonymize_text, depseudonymize_text

logger = logging.getLogger(__name__)

router = APIRouter()


class PseudonymizeRequest(BaseModel):
    """Request para pseudonimizar texto."""
    text: str
    session_id: str


class PseudonymizeResponse(BaseModel):
    """Response de pseudonimización."""
    pseudonymized_text: str
    session_id: str
    mapping: Dict[str, str]
    pseudonyms_count: int


class DepseudonymizeRequest(BaseModel):
    """Request para des-pseudonimizar."""
    text: str
    session_id: str


class DepseudonymizeResponse(BaseModel):
    """Response de des-pseudonimización."""
    original_text: str


@router.post("/pseudonymize", response_model=PseudonymizeResponse)
async def pseudonymize(request: PseudonymizeRequest):
    """
    Pseudonimiza un texto reemplazando datos personales con pseudónimos.
    """
    try:
        result = await pseudonymize_text(request.text, request.session_id)
        return result
    except Exception as e:
        logger.error(f"Error pseudonimizando: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/depseudonymize", response_model=DepseudonymizeResponse)
async def depseudonymize(request: DepseudonymizeRequest):
    """
    Revierte la pseudonimización recuperando datos originales.
    """
    try:
        result = await depseudonymize_text(request.text, request.session_id)
        return result
    except Exception as e:
        logger.error(f"Error des-pseudonimizando: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Elimina todos los datos de una sesión.
    """
    try:
        from app.redis_client import delete_pattern
        delete_pattern(f"{session_id}:*")
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        logger.error(f"Error eliminando sesión: {e}")
        raise HTTPException(status_code=500, detail=str(e))
