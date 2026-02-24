"""
Schemas Pydantic para Petición Razonada.

Versión 2.0: Actualizado para aceptar formatos reales de ARCOTEL

IMPORTANTE: ARCOTEL usa DOS formatos para peticiones razonadas:
- Formato 1: CCDS-PR-2023-0008 (con -PR-)
- Formato 2: CTDG-2025-GE-0335 (formato de informe técnico, sin -PR-)

Este schema valida AMBOS formatos.
"""
from pydantic import BaseModel, validator
from datetime import date
from typing import Optional, List


class InformeBaseSchema(BaseModel):
    """Datos del informe técnico base referenciado."""
    numero: str
    fecha: Optional[date] = None

    @validator('numero')
    def validar_numero_informe(cls, v):
        if not v:
            raise ValueError('numero de informe no puede estar vacío')
        # Formato típico: CTDG-GE-2022-0487
        if len(v) < 10:
            raise ValueError(f'numero de informe parece incompleto: {v}')
        return v


class DocumentosAnexosSchema(BaseModel):
    """Documentos adjuntos a la petición."""
    memorandos: List[str] = []
    oficios: List[str] = []

    class Config:
        extra = 'allow'


class FirmanteSchema(BaseModel):
    """Datos del firmante de la petición."""
    nombre: str
    cargo: str
    unidad: Optional[str] = None

    @validator('nombre')
    def validar_nombre(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('nombre del firmante no puede estar vacío')
        return v.strip()


class PeticionRazonadaSchema(BaseModel):
    """
    Schema completo de Petición Razonada.

    Valida estructura y tipos de datos extraídos.
    NO valida consistencia de contenido.
    """
    numero: str
    fecha: date
    unidad_emisora: Optional[str] = None  # CCDS, CCDE, CTDG, etc.

    # Prestador (puede ser empresa o persona natural)
    prestador_nombre: str
    prestador_ruc: Optional[str] = None  # Opcional: puede no estar en petición

    # Informe base
    informe_base: InformeBaseSchema

    # Tipo de infracción
    tipo_infraccion: str
    descripcion_hecho: str

    # Documentos anexos
    documentos_anexos: Optional[DocumentosAnexosSchema] = None

    # Firmante
    firmante: FirmanteSchema

    # Metadata
    articulo_coa_invocado: Optional[str] = "Art 186"  # Siempre Art 186 COA
    solicitud: str = "inicio_procedimiento_sancionador"

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }

    @validator('numero')
    def validar_numero(cls, v):
        """
        Validar número de petición razonada.

        ACTUALIZADO v2.0: Acepta AMBOS formatos usados por ARCOTEL:
        - Formato 1 (con -PR-): CCDS-PR-2023-0008, CCDE-PR-2022-269
        - Formato 2 (sin -PR-): CTDG-2025-GE-0335, CTDG-GE-2022-0487

        El Formato 2 se usa cuando la petición se numera igual que el informe técnico.
        """
        if not v:
            raise ValueError('numero no puede estar vacío')

        # Validación básica: longitud mínima
        if len(v) < 10:
            raise ValueError(f'numero parece incompleto (muy corto): {v}')

        # Validación de estructura básica: debe tener guiones
        if '-' not in v:
            raise ValueError(f'numero debe contener guiones: {v}')

        # LOG: Mostrar qué formato se detectó (útil para debugging)
        if '-PR-' in v:
            print(f"   ✓ Formato detectado: Petición con -PR- ({v})")
        else:
            print(f"   ✓ Formato detectado: Petición estilo informe técnico ({v})")

        return v

    @validator('unidad_emisora')
    def validar_unidad(cls, v):
        """Validar que sea una unidad conocida de ARCOTEL."""
        if v is None:
            return v  # ✅ permitir None
        unidades_validas = ['CCDS', 'CCDE', 'CTDG', 'CTHB', 'CCON']
        if v.upper() not in unidades_validas:
            print(f"⚠️ Advertencia: Unidad '{v}' no está en lista conocida: {unidades_validas}")
        return v.upper()

    @validator('prestador_ruc')
    def validar_ruc(cls, v):
        """
        RUC puede ser 10 dígitos (natural) o 13 dígitos (empresa).
        También puede ser None si no está en el documento.
        """
        if v is None:
            return v  # Permitir None

        # Limpiar espacios
        ruc_limpio = v.strip().replace(' ', '').replace('-', '')

        if not ruc_limpio.isdigit():
            raise ValueError(f'RUC debe contener solo dígitos: {v}')

        if len(ruc_limpio) not in [10, 13]:
            raise ValueError(f'RUC debe tener 10 o 13 dígitos, tiene {len(ruc_limpio)}: {v}')

        return ruc_limpio

    @validator('tipo_infraccion')
    def validar_tipo_infraccion(cls, v):
        """Validar que tipo_infraccion no esté vacío."""
        if not v or len(v.strip()) < 3:
            raise ValueError('tipo_infraccion no puede estar vacío')
        return v.strip().lower().replace(' ', '_')
