"""
Cliente HTTP para comunicarse con el servicio de pseudonimización
Versión 4.1 - CORREGIDO: Soporte para session_id en pseudonymize_text()
"""
import httpx
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PseudonymClient:
    """Cliente para el servicio de pseudonimización"""

    def __init__(self):
        self.base_url = os.getenv("PSEUDONYM_SERVICE_URL", "http://pseudonym-api:8001")
        self.session_id: Optional[str] = None

    async def pseudonymize_text(
            self,
            text: str,
            session_id: Optional[str] = None  # ⬅️ AGREGADO: Parámetro opcional
    ) -> Dict:
        """
        Pseudonimizar texto.

        Args:
            text: Texto a pseudonimizar
            session_id: Session ID opcional para reusar una sesión existente
                       (por ejemplo, de validación previa)

        Returns:
            dict: {
                "pseudonymized_text": str,
                "session_id": str,
                "pseudonyms_count": int,
                "mapping": dict,
                "stats": dict
            }
        """
        try:
            # ✅ NUEVO: Usar session_id proporcionado o generar uno nuevo
            if session_id:
                # Reusar session_id existente (de validación previa)
                current_session_id = session_id
                logger.info(f"♻️  Reusando session_id existente: {current_session_id}")
            elif self.session_id:
                # Reusar session_id de instancia
                current_session_id = self.session_id
                logger.info(f"♻️  Reusando session_id de instancia: {current_session_id}")
            else:
                # Generar nuevo session_id
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = uuid.uuid4().hex[:8]
                current_session_id = f"session_{timestamp}_{unique_id}"
                logger.info(f"🆔 Generado nuevo session_id: {current_session_id}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/internal/pseudonymize",
                    json={
                        "text": text,
                        "session_id": current_session_id  # ⬅️ MODIFICADO: usar current_session_id
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                # Guardar session_id para reusar
                self.session_id = data["session_id"]

                logger.info(f"✅ Texto pseudonimizado: {data['pseudonyms_count']} pseudónimos")
                return data

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP al pseudonimizar: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Error en servicio de pseudonimización: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión al pseudonimizar: {e}")
            raise Exception(f"No se pudo conectar con servicio de pseudonimización: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error al pseudonimizar: {e}")
            raise

    async def depseudonymize_data(self, data: Dict, session_id: Optional[str] = None) -> Dict:
        # Usar session_id proporcionado, o caer en self.session_id como fallback
        effective_session_id = session_id or self.session_id
        """
        Des-pseudonimizar datos.

        Args:
            data: Datos con pseudónimos

        Returns:
            dict: Datos con valores reales
        """
        if not effective_session_id:
            logger.warning("⚠️ No hay session_id, retornando datos sin cambios")
            return data

        try:
            import json
            data_json_str = json.dumps(data, ensure_ascii=False, default=str)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/internal/depseudonymize",
                    json={
                        "text": data_json_str,
                        "session_id": effective_session_id  # ← usa el efectivo
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()

                # Parsear string de vuelta a dict
                original_text = result["original_text"]
                original_data = json.loads(original_text)

                logger.info(f"✅ Datos des-pseudonimizados correctamente")
                return original_data

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP al des-pseudonimizar: {e.response.status_code}")
            raise Exception(f"Error en des-pseudonimización: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión al des-pseudonimizar: {e}")
            raise Exception(f"No se pudo conectar con servicio de pseudonimización: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error al des-pseudonimizar: {e}")
            raise


# Instancia global
pseudonym_client = PseudonymClient()
