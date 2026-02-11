"""
Cliente HTTP para comunicarse con el servicio de pseudonimización
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

    async def pseudonymize_text(self, text: str) -> Dict:
        """
        Pseudonimizar texto.

        Args:
            text: Texto a pseudonimizar

        Returns:
            dict: {
                "pseudonymized_text": str,
                "session_id": str,
                "pseudonyms_count": int
            }
        """
        try:
            # ✅ FIX: Generar session_id único si no existe
            if not self.session_id:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = uuid.uuid4().hex[:8]
                self.session_id = f"session_{timestamp}_{unique_id}"
                logger.info(f"🆔 Generado nuevo session_id: {self.session_id}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/internal/pseudonymize",
                    json={
                        "text": text,
                        "session_id": self.session_id  # ✅ Ahora nunca es None
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                # Guardar session_id para reusar
                self.session_id = data["session_id"]

                logger.info(f"✅ Texto pseudonimizado: {data['pseudonyms_count']} pseudónimos")
                return data
        except Exception as e:
            logger.error(f"❌ Error al pseudonimizar: {e}")
            raise

    async def depseudonymize_data(self, data: Dict) -> Dict:
        """
        Des-pseudonimizar datos.

        Args:
            data: Datos con pseudónimos

        Returns:
            dict: Datos con valores reales
        """
        if not self.session_id:
            logger.warning("⚠️ No hay session_id, retornando datos sin cambios")
            return data

        try:
            import json  # ✅ Agregar import

            # ✅ Convertir dict a JSON string
            data_json_str = json.dumps(data, ensure_ascii=False, default=str)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/internal/depseudonymize",
                    json={
                        "text": data_json_str,  # ✅ Enviar como string
                        "session_id": self.session_id
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()

                # ✅ Parsear string de vuelta a dict
                original_text = result["original_text"]
                original_data = json.loads(original_text)

                logger.info(f"✅ Datos des-pseudonimizados correctamente")
                return original_data  # ✅ Retornar dict
        except Exception as e:
            logger.error(f"❌ Error al des-pseudonimizar: {e}")
            raise


# Instancia global
pseudonym_client = PseudonymClient()
