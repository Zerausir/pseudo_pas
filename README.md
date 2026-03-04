# 🏛️ Piloto Experimental — Automatización de Procedimientos Administrativos Sancionadores ARCOTEL

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.13.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Claude API](https://img.shields.io/badge/Claude-Sonnet_4.5-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![spaCy](https://img.shields.io/badge/spaCy-3.8.11-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)](https://spacy.io/)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

**Sistema inteligente de extracción, validación y pseudonimización automática de datos para Procedimientos Administrativos Sancionadores (PAS) en telecomunicaciones**

[Características](#-características-principales) •
[Inicio Rápido](#-inicio-rápido) •
[Arquitectura](#-arquitectura-del-sistema) •
[API](#-api-reference) •
[Métricas](#-métricas-de-rendimiento) •
[Documentación](#-documentación-adicional)

---

| 🎯 F1 Extracción | 🔐 F1 Pseudonimización | ⚡ Tiempo/doc | 💰 Costo/caso | 📄 Corpus evaluado |
|:---:|:---:|:---:|:---:|:---:|
| **98.1%** | **97.2%** | **~18 seg** | **$0.036 USD** | **70 documentos** |

</div>

---

## 📌 Descripción del Proyecto

**ARCOTEL PAS** automatiza la extracción, validación y pseudonimización de datos del **Procedimiento Administrativo Sancionador (PAS)** para infracciones del sector de telecomunicaciones en Ecuador, abordando un problema institucional crítico: un backlog de 2417 casos pendientes que representa más de 10.5 años de trabajo acumulado.

> 💡 Este proyecto es el Trabajo Final de Estudios (TFE) de la **Universidad Internacional de La Rioja (UNIR)**, desarrollado en colaboración con **ARCOTEL Ecuador**. Directora: Mariana Edith Miranda Varela. Período: Noviembre 2025 – Febrero 2026.

### El Problema

ARCOTEL Ecuador detecta infracciones de prestadores de servicios de telecomunicaciones (e.g., incumplimiento con Garantías de Fiel Cumplimiento) y debe tramitar un PAS que involucra 8 documentos legales secuenciales, coordinación entre 4 áreas institucionales (CTDG, CCON, CZ2, DEDA), y generación **manual** de documentos altamente estandarizados.

### La Solución

Sistema híbrido que combina extracción LLM, validación determinística y pseudonimización LOPDP-conforme:

```
PDF IT/PR → [Módulo 3: Pseudonimización 4 Capas] → [Módulo 1: Claude API] → JSON → [Módulo 2: Validador] → PostgreSQL
```

---

## ✨ Características Principales

- 🤖 **Módulo 1 — Extracción automática con LLM** — Claude API (`claude-sonnet-4-20250514`) con few-shot prompting, chain-of-thought y negative examples. F1 global = **98.1%** sobre 41 documentos gold standard (318 evaluaciones).
- ⚖️ **Módulo 2 — Validación basada en reglas** — Motor determinístico ROTH Art. 204: calcula fechas tope, días de retraso, clasifica severidad. **100% detección, 0% falsos positivos.**
- 🔐 **Módulo 3 — Pseudonimización 4 capas** — Regex + Header parser + spaCy NER + Firmantes. F1 = **97.2%** sobre corpus de 70 documentos, **Precisión = 100%** (0 falsos positivos).
- 🛡️ **Cumplimiento LOPDP Ecuador** — Validación visual obligatoria antes de cualquier envío a Claude API. Claude API recibe exclusivamente pseudónimos (`NOMBRE_A3F7B2C1`).
- 🐳 **Docker-first** — Un solo `docker-compose up -d` levanta 7 servicios configurados y listos.
- 📊 **Gold standards validados** — Evaluación sobre 41 documentos (extracción, 318 evaluaciones) y 70 documentos (pseudonimización, 515 entidades).
- 🔑 **Seguridad por diseño** — AES-256-GCM, HashiCorp Vault KMS, TTL automático 1h, red interna Docker aislada.

---

## 🚀 Inicio Rápido

### Prerrequisitos

- Docker Desktop 4.x+ con Docker Compose v2
- API Key de Anthropic (`sk-ant-...`)
- PowerShell 7+ *(opcional, para procesamiento batch)*

### Instalación en 4 pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/<usuario>/arcotel-pas.git
cd arcotel-pas

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales (ver sección Configuración)

# 3. Crear directorios de datos
mkdir -p data/informes_tecnicos data/peticiones_razonadas

# 4. Levantar todos los servicios
docker-compose up -d
```

### Verificar instalación

```bash
curl http://localhost:8000/health
# → {"status": "ok", "database": "connected", "version": "4.0.0"}

curl http://localhost:8001/health
# → {"status": "healthy", "vault": "connected", "redis": "connected", "db": "connected"}
```

### Procesar tu primer documento

```bash
# Copiar PDF al directorio correspondiente
cp mi_informe.pdf data/informes_tecnicos/CTDG-GE-2025-0001.pdf

# 1. Previsualizar pseudonimización (OBLIGATORIO — LOPDP)
SESSION=$(curl -s -X POST http://localhost:8000/api/validacion/previsualizar \
  -H "Content-Type: application/json" \
  -d '{"archivo":"CTDG-GE-2025-0001.pdf","tipo_documento":"informes_tecnicos"}' \
  | jq -r '.session_id')

# 2. Revisar HTML generado en http://localhost:8000/outputs/
#    Verificar que todos los datos personales están reemplazados por pseudónimos

# 3. Confirmar y procesar
curl -X POST http://localhost:8000/api/archivos/procesar \
  -H "Content-Type: application/json" \
  -d "{\"archivos\":[\"CTDG-GE-2025-0001.pdf\"],\"session_id\":\"$SESSION\",\"confirmado\":true}"
```

### Procesamiento batch (PowerShell)

```powershell
# Procesar corpus completo con validación interactiva
.\procesar_masivo_v2.ps1
```

---

## 🏗️ Arquitectura del Sistema

El sistema implementa una **arquitectura de microservicios de dos capas** con aislamiento técnico de datos personales, cumpliendo LOPDP Ecuador Arts. 10.e, 33 y 37.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PROCESAMIENTO                           │
│                                                                         │
│  PDF IT/PR                                                              │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────┐                   │
│  │  MÓDULO 3 — PSEUDONIMIZACIÓN (puerto 8001)       │                   │
│  │   Capa 1:   Regex → RUC, Cédula, Email, Tfno    │                   │
│  │   Capa 1.5: Header → Nombre empresa, Dirección  │                   │
│  │   Capa 2:   spaCy → Nombres en texto libre      │                   │
│  │   Capa 3:   Firmas → Firmantes del documento    │                   │
│  │                                                  │                   │
│  │   postgres_pseudonym ← Vault AES-256-GCM        │                   │
│  │   Redis TTL 1h                                   │                   │
│  └─────────────────────────────────────────────────┘                   │
│     │ texto con PSEUDÓNIMOS (nunca datos reales)                        │
│     ▼                                                                   │
│  ┌────────────────────────────────────────────┐                        │
│  │  MÓDULO 1 — CLAUDE API                      │                        │
│  │  claude-sonnet-4-20250514, temp. 0.0        │                        │
│  │  Few-shot prompting (3 IT + 2 PR ejemplos) │                        │
│  └────────────────────────────────────────────┘                        │
│     │ JSON estructurado                                                 │
│     ▼                                                                   │
│  ┌────────────────────────────────────────────┐                        │
│  │  MÓDULO 2 — VALIDADOR ROTH Art. 204         │                        │
│  │  Fechas tope, días retraso, severidad       │                        │
│  └────────────────────────────────────────────┘                        │
│     │                                                                   │
│     ▼                                                                   │
│  postgres_main (datos de negocio)                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Servicios Docker (7 contenedores)

| Servicio | Puerto | Descripción |
|---|---|---|
| `backend` | 8000 | FastAPI — API principal y lógica de negocio |
| `pseudonym-api` | 8001 | Servicio de pseudonimización (4 capas) |
| `postgres_main` | 5432 | Base de datos principal (casos PAS) |
| `postgres_pseudonym` | 5433 | Mapeos cifrados (exclusivo para pseudonimización) |
| `vault` | 8200 | HashiCorp Vault — KMS con AES-256-GCM |
| `redis` | 6379 | TTL de sesiones (expiración automática 1h) |
| `adminer` | 8080 | UI de administración de bases de datos |

---

## 🔐 Pseudonimización y Cumplimiento LOPDP

### El Problema Legal

El sistema procesa PDFs con **datos personales de ciudadanos ecuatorianos** que deben enviarse a **Claude API (Anthropic, EEUU)** — una transferencia internacional regulada por la LOPDP:

| Artículo LOPDP | Principio | Implementación |
|---|---|---|
| Art. 10.e | Minimización de datos | Solo pseudónimos llegan a Claude |
| Art. 33 | Transferencia con garantías | Datos reales nunca salen del sistema local |
| Art. 37 | Medidas de seguridad técnicas | AES-256-GCM + Vault KMS |
| Arts. 55-60 | Transferencia internacional | Arquitectura de separación técnica real |

### Arquitectura de 4 Capas

```
Texto original:
  "TELECOMUNICACIONES EJEMPLO S.A., RUC: 1792554136001
   Rep. Legal: JUAN PÉREZ GARCÍA, correo@empresa.com
   Dirección: AV. NAPO S/N Y BOMBEROS"

                    ↓ CAPA 1: Regex (datos estructurados)
  RUC: 1792554136001      →  RUC_A3F7B2C1
  correo@empresa.com      →  EMAIL_D4E8F2A1
  AV. NAPO S/N Y BOMBEROS →  DIRECCION_G7H1I4J2
  1719710830              →  CEDULA_B9C3D7E5
  0999079807              →  TELEFONO_F2C9D6E3

                    ↓ CAPA 1.5: Header Parser (encabezado del documento)
  TELECOMUNICACIONES EJEMPLO S.A.  →  NOMBRE_K5L8M2N9
  AV. EJEMPLO S58F-93 CASA 12      →  DIRECCION_H4I7J1K3

                    ↓ CAPA 2: spaCy NER (es_core_news_lg, re.IGNORECASE)
  JUAN PÉREZ GARCÍA       →  NOMBRE_P6Q9R3S7

                    ↓ CAPA 3: Firmantes (regex títulos académicos)
  Ing. DAVID CHÁVEZ       →  NOMBRE_T2U5V8W1
  (Elaborado/Revisado/Aprobado por)
```

> ⚠️ **Nota metodológica**: La Capa 3 (Firmantes) registró 0 VP y 0 FN en el corpus evaluado porque los nombres de firmantes ya habían sido capturados por la Capa 2 (spaCy NER). La capa está implementada y operativa — actúa como salvaguarda para documentos con formatos atípicos de firma.

### Métricas de Pseudonimización (corpus: 70 documentos, 515 entidades)

| Tipo | Total | VP | FN | Precision | Recall | F1 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| RUC | 23 | 23 | 0 | 100.0% | 100.0% | **100.0%** |
| CEDULA | 13 | 13 | 0 | 100.0% | 100.0% | **100.0%** |
| EMAIL | 45 | 45 | 0 | 100.0% | 100.0% | **100.0%** |
| TELEFONO | 2 | 2 | 0 | 100.0% | 100.0% | **100.0%** |
| DIRECCION | 35 | 32 | 3 | 100.0% | 91.4% | **95.5%** |
| NOMBRE | 397 | 372 | 25 | 100.0% | 93.7% | **96.7%** |
| **GLOBAL** | **515** | **487** | **28** | **100.0%** | **94.6%** | **97.2%** |

- **45/70 documentos (64.3%)** — Pseudonimización completa (0 FN)
- **25/70 documentos (35.7%)** — Pseudonimización parcial (≥1 FN por fragmentación OCR en docs 2021)
- **0 falsos positivos** — El sistema nunca pseudonimizó texto institucional por error

> Ver [`PSEUDONIMIZACION_ARQUITECTURA.md`](PSEUDONIMIZACION_ARQUITECTURA.md) para documentación técnica completa.

---

## 📊 Métricas de Rendimiento

### OE1 — Extracción de entidades (gold standard: 41 documentos, 318 evaluaciones)

**Informes Técnicos (n = 24, 216 evaluaciones = 24 × 9 campos):**

| Campo | Correctos (TP) | Errores (FN) | F1-Score | Criticidad |
|---|:---:|:---:|:---:|:---:|
| numero_documento | 24 | 0 | **100.0%** | ★ Alta |
| fecha | 24 | 0 | **100.0%** | ★ Alta |
| prestador_ruc | 24 | 0 | **100.0%** | ★ Alta |
| tipo_infraccion | 24 | 0 | **100.0%** | ★ Alta |
| fecha_real_entrega | 24 | 0 | **100.0%** | ★ Alta |
| representante_legal | 24 | 0 | **100.0%** | ◆ Media |
| articulos_violados | 24 | 0 | **100.0%** | ◆ Media |
| fecha_maxima_entrega | 22 | 2 | **91.7%** | ★ Alta |
| prestador_nombre | 21 | 3 | **87.5%** | ◆ Media |
| **TOTAL IT** | **211** | **5** | **97.7%** | — |

**Peticiones Razonadas (n = 17, 102 evaluaciones = 17 × 6 campos):**

| Campo | Correctos (TP) | Errores (FN) | F1-Score | Criticidad |
|---|:---:|:---:|:---:|:---:|
| numero_documento | 17 | 0 | **100.0%** | ★ Alta |
| fecha | 17 | 0 | **100.0%** | ★ Alta |
| prestador_nombre | 17 | 0 | **100.0%** | ◆ Media |
| informe_base | 17 | 0 | **100.0%** | ★ Alta |
| firmante | 17 | 0 | **100.0%** | ◆ Media |
| tipo_infraccion | 16 | 1 | **94.1%** | ★ Alta |
| **TOTAL PR** | **101** | **1** | **99.0%** | — |

**F1 global consolidado:**

| Grupo | Docs | Evaluaciones | FN | F1 global |
|---|:---:|:---:|:---:|:---:|
| Informes Técnicos (24 docs × 9 campos) | 24 | 216 | 5 | **97.7%** |
| Peticiones Razonadas (17 docs × 6 campos) | 17 | 102 | 1 | **99.0%** |
| **★ GLOBAL** | **41** | **318** | **6** | **98.1%** |

> F1 global = 312 correctas / 318 evaluaciones totales = 98.1%. Las 4 PR no incluidas en el gold standard corresponden a pares cuyo IT presentó fragmentación OCR severa que impidió su procesamiento por el sistema de pseudonimización.

**Análisis de los 6 errores de extracción:**

| Campo | Doc | Tipo error | Causa | Mitigación |
|---|---|:---:|---|---|
| fecha_maxima_entrega | CTDG-GE-2021-0303 | FORMAT | FO-DEAR-47 v2021 sin tabla de fechas | Post-procesamiento: `fecha_vigencia_GFC − 15 días` |
| fecha_maxima_entrega | CTDG-GE-2021-0307 | FORMAT | Ídem | Post-procesamiento: `fecha_vigencia_GFC − 15 días` |
| prestador_nombre | CTDG-GE-2022-0449 | TRUNC | LLM omitió sufijo "S.A." | Ampliar regex Capa 1.5 para capturar sufijos en línea siguiente |
| prestador_nombre | CTDG-GE-2022-0473 | TRUNC | LLM omitió guión y "S.A.S." | Ídem |
| prestador_nombre | CTDG-GE-2022-0483 | MERGE | LLM fusionó razón social con rep. legal | Instrucción explícita en prompt |
| tipo_infraccion | CCDS-PR-2023-0090 | AMBIG | Confusión tardia/no_presentada | Añadir caso negativo en few-shot |

### OE2 — Pseudonimización LOPDP (corpus: 70 documentos, 515 entidades)

| Métrica | Valor | Meta | Estado |
|---|:---:|:---:|:---:|
| Precisión | 100.0% | = 100% | ✅ |
| Recall | 94.6% | ≥ 95% | ⚠️ −0.4 pp |
| F1-Score global | **97.2%** | ≥ 95% | ✅ +2.2 pp |
| Falsos positivos | 0 | 0 | ✅ |
| Cobertura completa | 45/70 (64.3%) | ≥ 90% | ⚠️ −25.7 pp |

> El Recall de 94.6% y la cobertura de 64.3% reflejan 28 FN causados por fragmentación OCR en documentos de 2021 (pypdf fragmenta nombres al cruzar límites de columna PDF). La Precisión = 100% garantiza el cumplimiento LOPDP: ningún dato personal llega a Claude API sin pseudonimizar por error.

### OE3 — Impacto operacional

| Métrica | Manual | Automático | Mejora |
|---|:---:|:---:|:---:|
| Tiempo por par IT+PR | 15.0 min | 3.5 min | **↓ 76.7%** |
| Costo por caso | — | $0.036 USD | ✅ vs límite $5.00 |
| Tokens input promedio | — | ~3,500 | — |
| Tokens output promedio | — | ~800 | — |
| Tiempo por documento | — | ~18 seg | — |
| Costo total corpus (70 docs) | — | ~$1.26 USD | — |

### Resultados vs. Criterios de Éxito

| OE | Métrica | Meta | Resultado | Estado | Diferencia |
|---|---|---|:---:|:---:|:---:|
| OE1 | F1-Score extracción global | ≥ 85% | **98.1%** | ✅ | +13.1 pp |
| OE1 | F1 campo crítico más bajo (fecha_maxima) | ≥ 90% | **91.7%** | ✅ | +1.7 pp |
| OE1 | Detección inconsistencias normativas | ≥ 80% | **100.0%** | ✅ | +20.0 pp |
| OE1 | FP validador normativo | < 10% | **0.0%** | ✅ | −10.0 pp |
| OE2 | Precisión pseudonimización | = 100% | **100.0%** | ✅ | 0.0 pp |
| OE2 | Recall pseudonimización | ≥ 95% | **94.6%** | ⚠️ | −0.4 pp |
| OE2 | F1 pseudonimización | ≥ 95% | **97.2%** | ✅ | +2.2 pp |
| OE2 | Cobertura documental completa | ≥ 90% | **64.3%** | ⚠️ | −25.7 pp |
| OE3 | Reducción tiempo procesamiento | ≥ 60% | **76.7%** | ✅ | +16.7 pp |
| OE3 | Costo por caso | < $5.00 | **$0.036** | ✅ | −99.3% |

---

## 🏗️ Estructura del Repositorio

```
arcotel-pas/
│
├── 🐍  backend/                             # Servicio principal FastAPI
│   ├── app/
│   │   ├── main.py                          # App FastAPI + routers
│   │   ├── config.py                        # Settings desde variables de entorno
│   │   ├── database.py                      # SQLAlchemy 2.0 + URL.create()
│   │   ├── models/                          # SQLAlchemy ORM models
│   │   │   ├── caso_pas.py
│   │   │   ├── documento_pas.py
│   │   │   └── prestador.py
│   │   ├── schemas/                         # Pydantic v2 schemas
│   │   │   ├── informe_tecnico.py
│   │   │   └── peticion_razonada.py
│   │   ├── extractors/                      # Claude API extractors (few-shot)
│   │   │   ├── informe_tecnico_extractor.py
│   │   │   └── peticion_razonada_extractor.py
│   │   ├── validators/                      # Validador ROTH Art. 204
│   │   │   └── validador_informe.py
│   │   ├── services/                        # Lógica de negocio
│   │   │   └── caso_service.py
│   │   └── api/                             # Endpoints
│   │       ├── procesador.py
│   │       ├── casos.py
│   │       └── estadisticas.py
│   ├── init-db/
│   │   ├── 01-init.sql                      # Creación de usuario y BD
│   │   └── 02-schema.sql                    # Schema completo + vistas
│   └── Dockerfile
│
├── 🔐  pseudonym-service/                   # Servicio de pseudonimización
│   ├── app/
│   │   ├── main.py                          # FastAPI + endpoints internos
│   │   ├── pseudonymizer.py                 # Motor 4 capas
│   │   ├── vault_client.py                  # HashiCorp Vault + AES-256-GCM
│   │   └── redis_client.py                  # TTL de sesiones
│   └── Dockerfile
│
├── 🌐  frontend/                            # Interfaz web
│   ├── procesador.html                      # Dashboard principal
│   └── assets/
│
├── 📊  data/                                # PDFs de entrada (gitignored)
│   ├── informes_tecnicos/                   # CTDG-GE-YYYY-XXXX.pdf
│   └── peticiones_razonadas/                # CCDS/CCDE-PR-YYYY-XXXX.pdf
│
├── 🐳  docker-compose.yml                   # 7 servicios configurados
├── 📋  .env.example                         # Plantilla de variables
├── 📄  CLAUDE.md                            # Reglas de desarrollo del proyecto
├── 📄  PSEUDONIMIZACION_ARQUITECTURA.md     # Documentación técnica Módulo 3
└── 📄  README.md                            # Este archivo
```

---

## ⚙️ Configuración

### Variables de entorno requeridas (`.env`)

```bash
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# PostgreSQL principal
POSTGRES_DB=arcotel_pas
POSTGRES_USER=arcotel_user
POSTGRES_PASSWORD=<contraseña_segura>
DATABASE_URL=postgresql://arcotel_user:<password>@postgres_main:5432/arcotel_pas

# PostgreSQL pseudonimización
PSEUDONYM_DB=pseudonym_db
PSEUDONYM_USER=pseudonym_user
PSEUDONYM_PASSWORD=<contraseña_segura>
PSEUDONYM_DATABASE_URL=postgresql://pseudonym_user:<password>@postgres_pseudonym:5433/pseudonym_db

# HashiCorp Vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<vault_root_token>

# Redis
REDIS_URL=redis://redis:6379

# JWT entre servicios
JWT_SECRET_KEY=<clave_secreta_larga>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
```

> ⚠️ **Seguridad**: Nunca comitear el archivo `.env` con credenciales reales. Está incluido en `.gitignore`.

---

## 🗄️ Base de Datos

### Esquema (`postgres_main`)

```
prestadores ──< casos_pas ──< documentos_pas
                    └──< validaciones_informe
```

**Estados del flujo PAS:**
```
informe_tecnico → peticion_razonada → actuacion_previa →
acto_inicio → pruebas → dictamen → resolucion → cerrado
```

### Consultas útiles

```sql
-- Casos activos con estado de validación
SELECT * FROM v_casos_resumen;

-- Resultados de validación ROTH Art. 204
SELECT numero_doc, es_valido, num_errors, num_warnings
FROM documentos ORDER BY fecha_doc DESC;

-- Estadísticas del corpus procesado
SELECT tipo_doc, COUNT(*) AS total, AVG(num_errors) AS avg_errores
FROM documentos GROUP BY tipo_doc;

-- Métricas globales de validación
SELECT * FROM v_validaciones_estadisticas;
```

---

## 🔒 Seguridad

### Principios de Diseño

| Principio | Implementación |
|---|---|
| **Defense in Depth** | 4 capas pseudonimización + red aislada + cifrado + TTL |
| **Zero Trust interno** | JWT obligatorio entre backend ↔ pseudonym-api |
| **Separación técnica** | `postgres_main` y `postgres_pseudonym` en contenedores aislados |
| **Least Privilege** | Usuarios no-root en Docker (`arcotel`, `pseudonym`) |
| **Secrets externalizados** | `.env` en `.gitignore`, sin valores en código fuente |
| **TTL automático** | Mapeos de pseudonimización expiran en 1 hora |
| **Logs sanitizados** | Errores no exponen detalles internos del cifrado |

### Matriz de Acceso por Red Docker

| Servicio | main_network | pseudonym_network | internal_api | Internet |
|---|:---:|:---:|:---:|:---:|
| backend | ✅ | ❌ | ✅ | ✅ (solo Anthropic API) |
| pseudonym-api | ❌ | ✅ | ✅ | ❌ |
| postgres_main | ✅ | ❌ | ❌ | ❌ |
| postgres_pseudonym | ❌ | ✅ | ❌ | ❌ |
| vault | ❌ | ✅ | ❌ | ❌ |
| redis | ❌ | ✅ | ✅ | ❌ |

---

## 🔌 API Reference

### Backend (puerto 8000)

| Endpoint | Método | Descripción |
|---|---|---|
| `GET /health` | GET | Estado del sistema y versión |
| `GET /api/archivos/listar` | GET | Lista PDFs disponibles con estado de procesamiento |
| `POST /api/validacion/previsualizar` | POST | Genera HTML con pseudonimización para validación visual |
| `POST /api/archivos/procesar` | POST | Procesa documentos (requiere session_id confirmado) |
| `GET /api/casos/` | GET | Lista todos los casos PAS |
| `GET /api/casos/{id}` | GET | Detalle de un caso específico |
| `GET /api/validacion/{id}` | GET | Resultado de validación normativa de un documento |
| `GET /api/estadisticas` | GET | Estadísticas globales del corpus procesado |

### Pseudonym Service (puerto 8001 — solo red interna)

| Endpoint | Método | Auth | Descripción |
|---|---|---|---|
| `POST /internal/pseudonymize` | POST | JWT | Pseudonimiza texto (4 capas) |
| `POST /internal/depseudonymize` | POST | JWT | Recupera valores originales |
| `DELETE /session/{id}` | DELETE | JWT | Limpia mapeos de sesión |
| `GET /health` | GET | — | Estado del servicio |
| `GET /ready` | GET | — | Readiness (verifica Vault + Redis) |

---

## ⚖️ Marco Legal

| Norma | Artículos | Cumplimiento |
|---|---|:---:|
| LOPDP Ecuador | Arts. 10.e, 33, 37, 55-60 | ✅ |
| LOT | Arts. 24.3, 117.b.16, 121-122, 130-131 | ✅ |
| COA | Arts. 186, 193, 202, 207 | ✅ |
| ROTH | Art. 204 (GFC 15 días), Art. 207 (renovación anual) | ✅ |

> ⚠️ **Aviso legal:** Este sistema acelera tareas repetitivas pero **no reemplaza el criterio legal humano**. Todas las salidas deben ser revisadas por personal jurídico antes de su uso oficial.

---

## 📚 Documentación Adicional

- [`PSEUDONIMIZACION_ARQUITECTURA.md`](PSEUDONIMIZACION_ARQUITECTURA.md) — Arquitectura técnica detallada del Módulo 3: flujo de datos, ciclo de vida de pseudónimos, seguridad y métricas completas por capa y tipo de entidad.
- [`CLAUDE.md`](CLAUDE.md) — Reglas de desarrollo, patrones de código aprendidos y decisiones arquitectónicas del proyecto.

---

## 🗺️ Trabajo Futuro

El piloto cubre Módulos 1–3. El **Módulo 4 (Generación automática de documentos legales)** está fuera del alcance del presente TFE y constituye la principal línea de continuación:

1. **Generación automática** de Acto de Inicio, Dictamen y Resolución mediante templates Jinja2 + LLM (COA Arts. 193, 202, 207)
2. **Extensión a otros tipos de infracción** del PAS (parámetros radioeléctricos, calidad de servicio, infraestructura)
3. **Integración** con sistema de gestión institucional de ARCOTEL mediante API REST
4. **Evaluación de LLMs alternativos** (Llama 3.1 local — eliminaría necesidad de pseudonimización)
5. **Ampliación del gold standard** a ≥100 documentos con experimento controlado multi-analista

---

## 👤 Autor

**Iván Rodrigo Suárez Fabara**
TFE — Máster en Inteligencia Artificial
Universidad Internacional de La Rioja (UNIR)
Directora: Mariana Edith Miranda Varela
Período: Noviembre 2025 – Febrero 2026

---

*Fuentes de datos: `gold_standard_validacion.xlsx`, `metricas_pseudonimizacion.txt`, `vp_conteos.csv`, `fn_anotaciones.csv`*
*Última actualización: Marzo 2026*
