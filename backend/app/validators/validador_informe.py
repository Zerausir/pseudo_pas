#!/usr/bin/env python3
"""
Validador de Consistencia de Informes Técnicos
Versión 1.0

PROPÓSITO:
- Recibe datos EXTRAÍDOS del documento (pueden tener errores)
- CALCULA lo que debería ser según normativa
- COMPARA extraído vs calculado
- GENERA reporte de inconsistencias

FLUJO:
EXTRACTOR → datos_extraidos → VALIDADOR → reporte_inconsistencias
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class NivelInconsistencia(Enum):
    """Nivel de severidad de la inconsistencia detectada."""
    INFO = "info"  # Información adicional
    WARNING = "warning"  # Advertencia, revisar
    ERROR = "error"  # Error que debe corregirse
    CRITICAL = "critical"  # Error crítico que invalida el documento


@dataclass
class Inconsistencia:
    """Representa una inconsistencia detectada en los datos."""
    campo: str
    nivel: NivelInconsistencia
    valor_extraido: Any
    valor_esperado: Any
    descripcion: str
    articulo_legal: Optional[str] = None


class ValidadorInformeTecnico:
    """
    Validador de consistencia para Informes Técnicos.

    Verifica que los datos extraídos cumplan con:
    1. Normativa legal (Art 204 ROTH: 15 días antes)
    2. Consistencia matemática (cálculo de días)
    3. Coherencia temporal (fechas lógicas)
    """

    def __init__(self):
        self.inconsistencias: List[Inconsistencia] = []

    def validar(self, datos_extraidos: dict) -> Dict[str, Any]:
        """
        Valida consistencia de datos extraídos.

        Args:
            datos_extraidos: Diccionario con datos del extractor

        Returns:
            Dict con:
                - es_valido: bool
                - inconsistencias: List[Inconsistencia]
                - metricas: dict con estadísticas
        """
        self.inconsistencias = []
        infraccion = datos_extraidos.get('infraccion', {})

        # 1. Validar fecha máxima entrega (Art 204 ROTH)
        self._validar_fecha_maxima_entrega(infraccion)

        # 2. Validar cálculo de días de retraso
        self._validar_dias_retraso(infraccion)

        # 3. Validar coherencia temporal
        self._validar_coherencia_fechas(infraccion)

        # 4. Validar tipo de infracción
        self._validar_tipo_infraccion(infraccion)

        # Generar reporte
        return self._generar_reporte()

    def _validar_fecha_maxima_entrega(self, infraccion: dict):
        """
        Valida que fecha_maxima_entrega_gfc = fecha_vencimiento_gfc - 15 días.
        Según Art 204 ROTH.
        """
        fecha_vencimiento = infraccion.get('fecha_vencimiento_gfc')
        fecha_maxima_extraida = infraccion.get('fecha_maxima_entrega_gfc')

        if not fecha_vencimiento:
            self.inconsistencias.append(Inconsistencia(
                campo='fecha_vencimiento_gfc',
                nivel=NivelInconsistencia.CRITICAL,
                valor_extraido=None,
                valor_esperado='<fecha válida>',
                descripcion='Fecha de vencimiento GFC no fue extraída',
                articulo_legal='ROTH Art 204'
            ))
            return

        # Calcular fecha máxima esperada
        if isinstance(fecha_vencimiento, str):
            from datetime import datetime
            fecha_vencimiento = datetime.strptime(fecha_vencimiento, '%Y-%m-%d').date()

        fecha_maxima_esperada = fecha_vencimiento - timedelta(days=15)

        if not fecha_maxima_extraida:
            self.inconsistencias.append(Inconsistencia(
                campo='fecha_maxima_entrega_gfc',
                nivel=NivelInconsistencia.ERROR,
                valor_extraido=None,
                valor_esperado=fecha_maxima_esperada.isoformat(),
                descripcion='Fecha máxima de entrega no aparece en el documento',
                articulo_legal='ROTH Art 204'
            ))
            return

        # Convertir si es string
        if isinstance(fecha_maxima_extraida, str):
            from datetime import datetime
            fecha_maxima_extraida = datetime.strptime(fecha_maxima_extraida, '%Y-%m-%d').date()

        # Comparar
        if fecha_maxima_extraida != fecha_maxima_esperada:
            self.inconsistencias.append(Inconsistencia(
                campo='fecha_maxima_entrega_gfc',
                nivel=NivelInconsistencia.ERROR,
                valor_extraido=fecha_maxima_extraida.isoformat(),
                valor_esperado=fecha_maxima_esperada.isoformat(),
                descripcion=f'Fecha máxima entrega incorrecta. Debería ser 15 días antes del vencimiento.',
                articulo_legal='ROTH Art 204'
            ))

    def _validar_dias_retraso(self, infraccion: dict):
        """
        Valida que dias_retraso_extraido = fecha_real_entrega - fecha_maxima_entrega_gfc.
        """
        fecha_maxima = infraccion.get('fecha_maxima_entrega_gfc')
        fecha_real = infraccion.get('fecha_real_entrega')
        dias_extraidos = infraccion.get('dias_retraso_extraido')

        # Convertir fechas si son strings
        if isinstance(fecha_maxima, str):
            from datetime import datetime
            fecha_maxima = datetime.strptime(fecha_maxima, '%Y-%m-%d').date()

        if isinstance(fecha_real, str):
            from datetime import datetime
            fecha_real = datetime.strptime(fecha_real, '%Y-%m-%d').date()

        if not fecha_maxima or not fecha_real:
            self.inconsistencias.append(Inconsistencia(
                campo='dias_retraso',
                nivel=NivelInconsistencia.WARNING,
                valor_extraido=dias_extraidos,
                valor_esperado=None,
                descripcion='No se pueden calcular días de retraso (faltan fechas)',
                articulo_legal=None
            ))
            return

        # Calcular días de retraso esperados
        dias_calculados = (fecha_real - fecha_maxima).days

        if dias_extraidos is None:
            self.inconsistencias.append(Inconsistencia(
                campo='dias_retraso_extraido',
                nivel=NivelInconsistencia.INFO,
                valor_extraido=None,
                valor_esperado=dias_calculados,
                descripcion=f'Días de retraso no aparecen en documento (calculado: {dias_calculados})',
                articulo_legal=None
            ))
        elif dias_extraidos != dias_calculados:
            self.inconsistencias.append(Inconsistencia(
                campo='dias_retraso_extraido',
                nivel=NivelInconsistencia.ERROR,
                valor_extraido=dias_extraidos,
                valor_esperado=dias_calculados,
                descripcion=f'Días de retraso incorrectos en documento. Cálculo correcto: {dias_calculados}',
                articulo_legal=None
            ))

    def _validar_coherencia_fechas(self, infraccion: dict):
        """
        Valida coherencia temporal: fecha_real debe ser después de fecha_maxima.
        """
        fecha_maxima = infraccion.get('fecha_maxima_entrega_gfc')
        fecha_real = infraccion.get('fecha_real_entrega')

        if not fecha_maxima or not fecha_real:
            return

        # Convertir si son strings
        if isinstance(fecha_maxima, str):
            from datetime import datetime
            fecha_maxima = datetime.strptime(fecha_maxima, '%Y-%m-%d').date()

        if isinstance(fecha_real, str):
            from datetime import datetime
            fecha_real = datetime.strptime(fecha_real, '%Y-%m-%d').date()

        if fecha_real <= fecha_maxima:
            self.inconsistencias.append(Inconsistencia(
                campo='fecha_real_entrega',
                nivel=NivelInconsistencia.WARNING,
                valor_extraido=fecha_real.isoformat(),
                valor_esperado=f'> {fecha_maxima.isoformat()}',
                descripcion='Fecha real de entrega no es posterior a fecha máxima (¿se entregó a tiempo?)',
                articulo_legal=None
            ))

    def _validar_tipo_infraccion(self, infraccion: dict):
        """
        Valida que el tipo de infracción sea consistente con las fechas.
        """
        tipo = infraccion.get('tipo')
        fecha_maxima = infraccion.get('fecha_maxima_entrega_gfc')
        fecha_real = infraccion.get('fecha_real_entrega')

        if tipo == 'garantia_gfc_tardia' and fecha_maxima and fecha_real:
            # Convertir si son strings
            if isinstance(fecha_maxima, str):
                from datetime import datetime
                fecha_maxima = datetime.strptime(fecha_maxima, '%Y-%m-%d').date()

            if isinstance(fecha_real, str):
                from datetime import datetime
                fecha_real = datetime.strptime(fecha_real, '%Y-%m-%d').date()

            if fecha_real <= fecha_maxima:
                self.inconsistencias.append(Inconsistencia(
                    campo='tipo',
                    nivel=NivelInconsistencia.ERROR,
                    valor_extraido=tipo,
                    valor_esperado='garantia_gfc_a_tiempo',
                    descripcion='Tipo "garantia_gfc_tardia" pero se entregó a tiempo',
                    articulo_legal='ROTH Art 204'
                ))

    def _generar_reporte(self) -> Dict[str, Any]:
        """
        Genera reporte de validación.
        """
        # Contar por nivel
        contadores = {
            NivelInconsistencia.INFO: 0,
            NivelInconsistencia.WARNING: 0,
            NivelInconsistencia.ERROR: 0,
            NivelInconsistencia.CRITICAL: 0
        }

        for inc in self.inconsistencias:
            contadores[inc.nivel] += 1

        # Documento es válido si no hay ERROR ni CRITICAL
        es_valido = (contadores[NivelInconsistencia.ERROR] == 0 and
                     contadores[NivelInconsistencia.CRITICAL] == 0)

        return {
            'es_valido': es_valido,
            'total_inconsistencias': len(self.inconsistencias),
            'contadores': {
                'info': contadores[NivelInconsistencia.INFO],
                'warnings': contadores[NivelInconsistencia.WARNING],
                'errors': contadores[NivelInconsistencia.ERROR],
                'critical': contadores[NivelInconsistencia.CRITICAL]
            },
            'inconsistencias': [
                {
                    'campo': inc.campo,
                    'nivel': inc.nivel.value,
                    'valor_extraido': str(inc.valor_extraido),
                    'valor_esperado': str(inc.valor_esperado),
                    'descripcion': inc.descripcion,
                    'articulo_legal': inc.articulo_legal
                }
                for inc in self.inconsistencias
            ]
        }

    def imprimir_reporte(self, reporte: Dict[str, Any]):
        """
        Imprime reporte en consola de forma legible.
        """
        print("\n" + "=" * 80)
        print("REPORTE DE VALIDACIÓN DE CONSISTENCIA")
        print("=" * 80)

        if reporte['es_valido']:
            print("✅ DOCUMENTO VÁLIDO - No se detectaron errores críticos\n")
        else:
            print("❌ DOCUMENTO CON ERRORES - Revisar inconsistencias\n")

        print(f"Total de inconsistencias: {reporte['total_inconsistencias']}")
        print(f"   ℹ️  Info:     {reporte['contadores']['info']}")
        print(f"   ⚠️  Warnings: {reporte['contadores']['warnings']}")
        print(f"   ❌ Errors:   {reporte['contadores']['errors']}")
        print(f"   🚨 Critical: {reporte['contadores']['critical']}")

        if reporte['inconsistencias']:
            print("\n" + "-" * 80)
            print("DETALLES DE INCONSISTENCIAS:")
            print("-" * 80)

            for i, inc in enumerate(reporte['inconsistencias'], 1):
                simbolo = {
                    'info': 'ℹ️',
                    'warning': '⚠️',
                    'error': '❌',
                    'critical': '🚨'
                }[inc['nivel']]

                print(f"\n{i}. {simbolo} [{inc['nivel'].upper()}] {inc['campo']}")
                print(f"   Extraído del documento: {inc['valor_extraido']}")
                print(f"   Valor esperado:         {inc['valor_esperado']}")
                print(f"   Descripción: {inc['descripcion']}")
                if inc['articulo_legal']:
                    print(f"   Base legal: {inc['articulo_legal']}")

        print("\n" + "=" * 80 + "\n")


# ========================================
# FUNCIÓN DE DEMO
# ========================================

def demo_validador():
    """
    Demuestra el uso del validador con datos de ejemplo.
    """
    print("\n" + "=" * 80)
    print("DEMO: VALIDADOR DE CONSISTENCIA")
    print("=" * 80 + "\n")

    # Caso 1: Datos correctos
    print("📋 CASO 1: Documento correcto\n")
    datos_correctos = {
        'numero': 'CTDG-GE-2022-0487',
        'fecha': '2022-12-28',
        'infraccion': {
            'tipo': 'garantia_gfc_tardia',
            'fecha_vencimiento_gfc': '2022-11-01',
            'fecha_maxima_entrega_gfc': '2022-10-17',  # 15 días antes ✓
            'fecha_real_entrega': '2022-10-21',
            'dias_retraso_extraido': 4  # (21-17) = 4 ✓
        }
    }

    validador = ValidadorInformeTecnico()
    reporte = validador.validar(datos_correctos)
    validador.imprimir_reporte(reporte)

    # Caso 2: Documento con errores
    print("\n📋 CASO 2: Documento con errores de cálculo\n")
    datos_incorrectos = {
        'numero': 'CTDG-GE-2023-0123',
        'fecha': '2023-05-15',
        'infraccion': {
            'tipo': 'garantia_gfc_tardia',
            'fecha_vencimiento_gfc': '2023-06-01',
            'fecha_maxima_entrega_gfc': '2023-05-20',  # Debería ser 2023-05-17 ✗
            'fecha_real_entrega': '2023-05-25',
            'dias_retraso_extraido': 3  # Debería ser 8 ✗
        }
    }

    validador2 = ValidadorInformeTecnico()
    reporte2 = validador2.validar(datos_incorrectos)
    validador2.imprimir_reporte(reporte2)

    # Caso 3: Documento incompleto
    print("\n📋 CASO 3: Documento incompleto (falta dias_retraso)\n")
    datos_incompletos = {
        'numero': 'CTDG-GE-2024-0456',
        'fecha': '2024-08-10',
        'infraccion': {
            'tipo': 'garantia_gfc_tardia',
            'fecha_vencimiento_gfc': '2024-09-01',
            'fecha_maxima_entrega_gfc': '2024-08-17',
            'fecha_real_entrega': '2024-08-22',
            'dias_retraso_extraido': None  # No aparece en documento
        }
    }

    validador3 = ValidadorInformeTecnico()
    reporte3 = validador3.validar(datos_incompletos)
    validador3.imprimir_reporte(reporte3)


if __name__ == "__main__":
    demo_validador()
