"""
FastAPI main application.
Versión: 4.0 - Validación obligatoria + Static files
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text

from backend.app.database import get_db  # ⬅️ CAMBIADO: solo get_db
from backend.app.api import procesador, validacion

# Crear app
app = FastAPI(
    title="ARCOTEL PAS API",
    description="Sistema de Automatización de Procedimientos Administrativos Sancionadores",
    version="4.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar directorio de outputs para servir HTMLs de validación
outputs_dir = Path("/app/outputs")
outputs_dir.mkdir(parents=True, exist_ok=True)

app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")

# Incluir routers
app.include_router(
    procesador.router,
    tags=["procesador"]
)

app.include_router(
    validacion.router,
    tags=["validacion"]
)


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "mensaje": "ARCOTEL PAS API v4.0 - Validación Obligatoria",
        "docs": "/docs",
        "endpoints": {
            "validacion": "/api/validacion/previsualizar",
            "procesamiento": "/api/archivos/procesar",
            "outputs": "/outputs/",
            "estadisticas": "/estadisticas",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """
    Health check endpoint.
    Verifica conexión a base de datos.
    """
    db_status = "unknown"
    db_connected = False

    try:
        # Test de conexión a BD
        db = next(get_db())
        result = db.execute(text("SELECT 1")).fetchone()
        db.close()

        if result and result[0] == 1:
            db_status = "connected"
            db_connected = True
        else:
            db_status = "error"

    except Exception as e:
        db_status = f"error: {str(e)}"
        db_connected = False

    return {
        "status": "ok" if db_connected else "degraded",
        "database": db_status,
        "version": "4.0.0",
        "features": {
            "pseudonymization": True,
            "validation_required": True,
            "static_files": True
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
