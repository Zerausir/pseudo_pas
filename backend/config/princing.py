"""
Configuración de precios de Claude API.

Fuente oficial: https://www.anthropic.com/pricing
Última actualización: 29 de enero de 2025

IMPORTANTE: Si los precios cambian, actualizar este archivo con los valores vigentes.
"""

from datetime import datetime
from typing import Dict, NamedTuple


class ModelPricing(NamedTuple):
    """Estructura de precios por modelo."""
    input_per_million: float  # USD por 1M tokens de entrada
    output_per_million: float  # USD por 1M tokens de salida
    last_updated: str  # Fecha de última actualización
    source_url: str  # URL de referencia oficial


# Precios actuales de Claude API
# Fuente: https://www.anthropic.com/pricing (verificado 29-ene-2025)
CLAUDE_PRICING: Dict[str, ModelPricing] = {
    "claude-sonnet-4-20250514": ModelPricing(
        input_per_million=3.00,
        output_per_million=15.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
    "claude-3-5-sonnet-20241022": ModelPricing(
        input_per_million=3.00,
        output_per_million=15.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
    "claude-3-5-sonnet-20240620": ModelPricing(
        input_per_million=3.00,
        output_per_million=15.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
    "claude-opus-4-20250514": ModelPricing(
        input_per_million=15.00,
        output_per_million=75.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
    "claude-3-opus-20240229": ModelPricing(
        input_per_million=15.00,
        output_per_million=75.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
    "claude-haiku-4-20250514": ModelPricing(
        input_per_million=0.80,
        output_per_million=4.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
    "claude-3-5-haiku-20241022": ModelPricing(
        input_per_million=0.80,
        output_per_million=4.00,
        last_updated="2025-01-29",
        source_url="https://www.anthropic.com/pricing"
    ),
}


def calcular_costo(
        model: str,
        input_tokens: int,
        output_tokens: int
) -> dict:
    """
    Calcula el costo exacto de una llamada a la API de Claude.

    Args:
        model: Nombre del modelo usado (ej: "claude-sonnet-4-20250514")
        input_tokens: Tokens de entrada (del response.usage)
        output_tokens: Tokens de salida (del response.usage)

    Returns:
        dict con:
            - costo_usd: Costo en USD (redondeado a 4 decimales)
            - input_tokens: Tokens de entrada
            - output_tokens: Tokens de salida
            - total_tokens: Suma total
            - input_cost_usd: Costo solo de input
            - output_cost_usd: Costo solo de output
            - model: Modelo usado
            - pricing_date: Fecha de precios usados

    Raises:
        ValueError: Si el modelo no está en la configuración
    """
    pricing = CLAUDE_PRICING.get(model)

    if not pricing:
        raise ValueError(
            f"Modelo '{model}' no tiene precios configurados. "
            f"Modelos disponibles: {list(CLAUDE_PRICING.keys())}"
        )

    # Calcular costos
    input_cost = (input_tokens * pricing.input_per_million) / 1_000_000
    output_cost = (output_tokens * pricing.output_per_million) / 1_000_000
    total_cost = input_cost + output_cost

    return {
        "costo_usd": round(total_cost, 4),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "model": model,
        "pricing_date": pricing.last_updated,
        "pricing_source": pricing.source_url
    }


def obtener_precios(model: str) -> ModelPricing:
    """
    Obtiene los precios configurados para un modelo.

    Args:
        model: Nombre del modelo

    Returns:
        ModelPricing con los precios del modelo

    Raises:
        ValueError: Si el modelo no está configurado
    """
    pricing = CLAUDE_PRICING.get(model)

    if not pricing:
        raise ValueError(
            f"Modelo '{model}' no tiene precios configurados. "
            f"Actualizar backend/config/pricing.py"
        )

    return pricing


def verificar_precios_actualizados(dias_max: int = 30) -> bool:
    """
    Verifica si los precios están actualizados (menos de N días).

    Args:
        dias_max: Días máximos desde última actualización

    Returns:
        True si todos los precios están actualizados
    """
    hoy = datetime.now()

    for model, pricing in CLAUDE_PRICING.items():
        fecha_precio = datetime.strptime(pricing.last_updated, "%Y-%m-%d")
        dias_antiguedad = (hoy - fecha_precio).days

        if dias_antiguedad > dias_max:
            return False

    return True


# Advertencia si los precios están desactualizados
if __name__ == "__main__":
    if verificar_precios_actualizados(30):
        print("✅ Precios actualizados (< 30 días)")
    else:
        print("⚠️  Precios desactualizados. Verificar https://www.anthropic.com/pricing")

    # Ejemplo de uso
    print("\nEjemplo de cálculo:")
    costo = calcular_costo(
        model="claude-sonnet-4-20250514",
        input_tokens=8245,
        output_tokens=1876
    )
    print(f"Input: {costo['input_tokens']:,} tokens = ${costo['input_cost_usd']}")
    print(f"Output: {costo['output_tokens']:,} tokens = ${costo['output_cost_usd']}")
    print(f"Total: {costo['total_tokens']:,} tokens = ${costo['costo_usd']}")
    print(f"Precios vigentes al: {costo['pricing_date']}")
