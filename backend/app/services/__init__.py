"""
Módulo de servicios para gestión de casos PAS.
"""

from .caso_service import (
    guardar_informe_tecnico,
    guardar_peticion_razonada,
    guardar_validacion,
    obtener_caso_por_numero,
    contar_casos
)

__all__ = [
    'guardar_informe_tecnico',
    'guardar_peticion_razonada',
    'guardar_validacion',
    'obtener_caso_por_numero',
    'contar_casos'
]
