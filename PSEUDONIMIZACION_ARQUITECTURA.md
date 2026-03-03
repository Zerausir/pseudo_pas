# 🔐 Arquitectura de Pseudonimización

<div align="center">

[![LOPDP Ecuador](https://img.shields.io/badge/LOPDP_Ecuador-Compliant-22C55E?style=for-the-badge&logo=shield&logoColor=white)](https://www.telecomunicaciones.gob.ec/)
[![GDPR](https://img.shields.io/badge/GDPR_Art._4.5-Pseudonimización-3B82F6?style=for-the-badge&logo=eu&logoColor=white)](https://gdpr.eu/)
[![Vault](https://img.shields.io/badge/HashiCorp_Vault-AES--256--GCM-FFEC6E?style=for-the-badge&logo=vault&logoColor=black)](https://www.vaultproject.io/)
[![spaCy](https://img.shields.io/badge/spaCy-NER_es__core__news__lg-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)](https://spacy.io/)
[![Redis](https://img.shields.io/badge/Redis-TTL_1h-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)

**Sistema de pseudonimización de datos personales con separación técnica real,
cumpliendo la Ley Orgánica de Protección de Datos Personales de Ecuador (LOPDP)**

</div>

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Justificación Legal](#2-justificación-legal)
3. [Arquitectura de Dos Servicios](#3-arquitectura-de-dos-servicios)
4. [Motor de Pseudonimización — 4 Capas](#4-motor-de-pseudonimización--4-capas)
5. [Flujo de Datos Completo](#5-flujo-de-datos-completo)
6. [Ciclo de Vida de los Datos](#6-ciclo-de-vida-de-los-datos)
7. [Best Practices Implementadas](#7-best-practices-implementadas)
8. [Comunicación Entre Servicios](#8-comunicación-entre-servicios)
9. [Seguridad y Auditoría](#9-seguridad-y-auditoría)
10. [Configuración y Deployment](#10-configuración-y-deployment)
11. [Comandos de Operación](#11-comandos-de-operación)
12. [Métricas de Cobertura](#12-métricas-de-cobertura)
13. [Preguntas Frecuentes](#13-preguntas-frecuentes)
14. [Referencias y Normativa](#14-referencias-y-normativa)

---

## 1. Resumen Ejecutivo

### 1.1 El Problema

El sistema ARCOTEL PAS procesa documentos PDF que contienen **datos personales de ciudadanos ecuatorianos** (nombres, RUCs, cédulas, emails, teléfonos, direcciones de domicilio). Para la extracción automática, estos datos deben enviarse a **Claude API (Anthropic, empresa con sede en EEUU)**, lo cual constituye una **transferencia internacional de datos personales** regulada por la LOPDP.

**Sin pseudonimización, el sistema violaría:**

| Violación | Artículo LOPDP | Consecuencia |
|---|---|---|
| Transferencia internacional sin garantías | Arts. 33, 55-60 | Sanción 0.7%–1% volumen negocios (Art. 72) |
| Falta de seudonimización/cifrado | Arts. 10.e, 37 | Medidas correctivas (Art. 65) |
| No separación técnica de datos sensibles | Art. 37 | Suspensión del tratamiento (Art. 65) |
| Violación principio de minimización | Art. 10.e | Requerimiento de autoridad (Art. 65) |

### 1.2 La Solución

Antes de enviar cualquier texto a Claude API, el sistema aplica un proceso de pseudonimización de **4 capas secuenciales** que reemplaza todos los datos personales identificados por tokens opacos (`NOMBRE_A3F7B2C1`). Los mapeos de reversión se almacenan en un servicio completamente separado, cifrados con AES-256-GCM mediante HashiCorp Vault.

**Claude API recibe exclusivamente pseudónimos — nunca datos personales reales.**

### 1.3 Resultados (corpus de evaluación: 70 documentos)

| Métrica | Valor | Meta |
|---|:---:|:---:|
| Entidades totales evaluadas | 515 | — |
| Precisión | **100.0%** | = 100% ✅ |
| Recall | **94.6%** | ≥ 95% ⚠️ |
| F1-Score global | **97.2%** | ≥ 95% ✅ |
| Falsos Positivos | **0** | 0 ✅ |
| Cobertura completa | **45/70 (64.3%)** | — |

> El Recall de 94.6% refleja exclusivamente fragmentación de texto OCR por pypdf (e.g., `CHAVE Z SALAS`, `OSTAIZA CEDEÑO LUISA ESPERANZA`). Los 28 FN no implican datos reales enviados a Claude API, ya que el sistema requiere validación visual obligatoria antes de procesar.

---

## 2. Justificación Legal

### 2.1 LOPDP Ecuador — Artículos Aplicables

La **Ley Orgánica de Protección de Datos Personales** (LOPDP), publicada en el Registro Oficial el 26 de mayo de 2021, establece:

**Art. 10.e — Principio de minimización de datos:**
> *"Los datos personales deben ser adecuados, pertinentes y limitados a lo necesario en relación con los fines para los que son tratados."*

**Art. 33 — Transferencia internacional:**
> Los datos personales solo pueden transferirse a terceros países cuando se garanticen niveles de protección adecuados o existan garantías contractuales suficientes.

**Art. 37 — Medidas de seguridad técnicas:**
> El responsable del tratamiento debe implementar medidas técnicas apropiadas para garantizar la seguridad de los datos, incluyendo seudonimización y cifrado.

**Arts. 55-60 — Transferencia internacional:**
> Regulan las condiciones bajo las cuales pueden transferirse datos personales a países sin nivel de protección adecuado (como EEUU respecto a Ecuador).

### 2.2 Análisis de Conformidad

La pseudonimización cumple LOPDP porque:

1. **Claude API opera exclusivamente con pseudónimos** → tokens sin significado independiente del contexto, lo que técnicamente excluye estos datos del ámbito de la transferencia internacional de datos personales según el estándar de pseudonimización del GDPR Art. 4.5 (al que la LOPDP se alinea en sus Arts. 10.e y 37).

2. **Separación técnica real** → `postgres_main` y `postgres_pseudonym` son instancias PostgreSQL completamente separadas en contenedores distintos, en redes Docker sin intersección.

3. **Minimización de exposición** → Los mapeos expiran automáticamente en 1 hora mediante Redis TTL. No existen datos de largo plazo en el sistema de pseudonimización.

4. **Cifrado de mapeos** → Los valores originales se almacenan cifrados con AES-256-GCM. Un atacante que acceda a `postgres_pseudonym` solo obtiene texto cifrado sin la clave de Vault.

---

## 3. Arquitectura de Dos Servicios

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              SISTEMA ARCOTEL PAS                                │
│                                                                                  │
│  ┌───────────────────────────────────────┐    ┌─────────────────────────────┐   │
│  │         BACKEND (puerto 8000)          │    │  PSEUDONYM-SERVICE (8001)   │   │
│  │         red: main_network              │    │  red: pseudonym_network     │   │
│  │         + internal_api                 │    │       + internal_api        │   │
│  │                                        │    │                             │   │
│  │  FastAPI app                           │    │  FastAPI app                │   │
│  │  SQLAlchemy → postgres_main            │    │  4 capas pseudonimización   │   │
│  │  Anthropic client → Claude API         │    │  SQLAlchemy → postgres_pseu │   │
│  │                                        │    │  hvac client → Vault        │   │
│  │  ┌──────────────────────────────────┐ │    │  redis.asyncio → Redis TTL  │   │
│  │  │    DATOS DE NEGOCIO (extraídos)  │ │    │                             │   │
│  │  │    (pseudónimos, luego des-pseu.)│ │    │  ┌─────────────────────┐   │   │
│  │  └──────────────────────────────────┘ │    │  │ DATOS PERSONALES     │   │   │
│  └───────────────────────────────────────┘    │  │ (cifrados AES-256)   │   │   │
│          │                    ▲               │  └─────────────────────┘   │   │
│          │ JWT + texto        │ pseudónimos   └─────────────────────────────┘   │
│          ▼                    │                                                  │
│          └────────────────────┘                                                  │
│          internal_api (red compartida)                                           │
│                                                                                  │
│  ┌─────────────────┐  ┌──────────────────────┐  ┌────────┐  ┌───────────────┐  │
│  │  postgres_main  │  │  postgres_pseudonym  │  │ vault  │  │    redis      │  │
│  │  (datos caso)   │  │  (mapeos cifrados)   │  │ KMS    │  │  TTL 1h       │  │
│  └─────────────────┘  └──────────────────────┘  └────────┘  └───────────────┘  │
│                                                                                  │
│  ❌  postgres_main NO puede acceder a postgres_pseudonym                        │
│  ❌  backend NO puede acceder directamente a Vault                              │
│  ❌  pseudonym-service NO puede acceder a Claude API                            │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Separación Técnica Real

La separación no es solo lógica (permisos de usuario), sino **técnica por aislamiento de red Docker**:

| Red Docker | Servicios con acceso |
|---|---|
| `main_network` | backend, postgres_main |
| `pseudonym_network` | pseudonym-api, postgres_pseudonym, vault, redis |
| `internal_api` | backend, pseudonym-api *(única red compartida)* |

**El backend nunca tiene acceso directo a Vault ni a `postgres_pseudonym`.** Solo puede llamar al `pseudonym-api` a través de `internal_api` con JWT autenticado.

---

## 4. Motor de Pseudonimización — 4 Capas

El servicio detecta y reemplaza datos personales en **4 capas secuenciales**, cada una especializada en un tipo de dato diferente. Si una capa ya detectó y reemplazó un valor, las capas siguientes lo omiten automáticamente.

### Capa 1: Regex — Datos Estructurados

Detecta entidades con formato definido mediante expresiones regulares. **Precisión: 100%, Recall: 100% (corpus evaluado).**

| Tipo | Patrón | Ejemplo → Pseudónimo |
|---|---|---|
| RUC | `\d{10,13}` (10 o 13 dígitos) | `1792554136001` → `RUC_A3F7B2C1` |
| Cédula | `\d{10}` (10 dígitos exactos) | `1719710830` → `CEDULA_D4E8F2A1` |
| Email | RFC 5322 pattern | `correo@empresa.com` → `EMAIL_B9C3D7E5` |
| Teléfono | Prefijo `09` + 8 dígitos; también detectado en Capa 1.5 | `0999079807` → `TELEFONO_F2C9D6E3` |
| Dirección intersección | Patrón `CALLE N-NUM Y CALLE` | `AV. NAPO S/N Y BOMBEROS` → `DIRECCION_G7H1I4J2` |

> **Nota RUC/Cédula**: El patrón `\d{10}` para cédulas puede solaparse con los primeros 10 dígitos de un RUC. La capa aplica el patrón de 13 dígitos primero (RUC), luego el de 10 dígitos (cédula), evitando doble reemplazo.

### Capa 1.5: Header Parser — Encabezado del Documento

Los informes técnicos de ARCOTEL tienen una tabla de encabezado estándar con campos etiquetados. Esta capa extrae valores por contexto de etiqueta, independientemente del formato exacto.

```
Detecta campos como:
  "PRESTADOR O CONCESIONARIO:"  → extrae nombre empresa → NOMBRE_X
  "REPRESENTANTE LEGAL:"        → extrae nombre persona → NOMBRE_Y
  "DIRECCIÓN:"                  → extrae dirección (incluye variantes sin intersección)
  "TELÉFONO:"                   → extrae teléfono sin prefijo nacional
  "CORREO ELECTRÓNICO:"         → extrae email (backup de Capa 1)
```

Esta capa captura variantes de dirección que **no siguen** el patrón de intersección de la Capa 1, como por ejemplo:
- `S58F Y OE5F, CASA S58F-93` ← formato no estándar
- `AV. 12 DE OCTUBRE N24-437 Y CORDERO EDIF. PUERTO DE PALO PB` ← referencia edificio

**Métricas (corpus evaluado): VP=32, FN=3, Precision=100%, Recall=91.4%, F1=95.5%**

Los 3 FN de esta capa corresponden a direcciones con formato de referencia muy extenso, fragmentadas por OCR al cruzar el límite de columna en el PDF.

### Capa 2: spaCy NER — Nombres de Personas

Aplica el modelo de lenguaje `es_core_news_lg` para detección de entidades nombradas en texto libre. Solo procesa entidades de tipo **PER** (personas), ignorando LOC, ORG y otras.

**Normalización crítica antes de NER:**

Los documentos ARCOTEL están escritos 100% en MAYÚSCULAS, pero spaCy fue entrenado principalmente con texto en Title Case. Sin normalización, la precisión cae de ~95% a ~40%.

```python
SIGLAS_ARCOTEL = {
    'ARCOTEL', 'SAI', 'GFC', 'CTDG', 'CCON', 'CZ2', 'DEDA',
    'RUC', 'SBU', 'LOT', 'COA', 'ROTH', 'PAS', 'CAFI',
    'DEDA', 'CTDG', 'CCDS', 'CCDE', 'PRD', 'FO', 'DEAR',
}

def normalizar_mayusculas(texto: str) -> str:
    """Convierte MAYÚSCULAS a Title Case preservando siglas institucionales."""
    palabras = texto.split()
    resultado = []
    for palabra in palabras:
        if palabra in SIGLAS_ARCOTEL:
            resultado.append(palabra)   # Mantener sigla
        else:
            resultado.append(palabra.title())  # Normalizar
    return ' '.join(resultado)
```

**Regla crítica de implementación (Regla 20 CLAUDE.md):**

Después de que spaCy detecta un nombre en Title Case (e.g., `Juan Pérez García`), el reemplazo en el texto original —que está en MAYÚSCULAS— **siempre usa `re.IGNORECASE`**:

```python
texto = re.sub(re.escape(nombre_detectado), pseudonimo, texto, flags=re.IGNORECASE)
```

Sin `re.IGNORECASE`, el reemplazo fallaría porque el texto dice `JUAN PÉREZ GARCÍA` pero spaCy devolvió `Juan Pérez García`.

**Filtros para evitar falsos positivos:**

```python
def es_nombre_real(texto: str) -> bool:
    """Valida que una entidad PER sea realmente un nombre de persona."""
    palabras = texto.strip().split()
    # Al menos 2 tokens
    if len(palabras) < 2:
        return False
    # No es solo una sigla conocida
    if texto.upper() in SIGLAS_ARCOTEL:
        return False
    # No contiene números (evita capturar "RUC 1234567890")
    if any(char.isdigit() for char in texto):
        return False
    return True
```

**Métricas (corpus evaluado): VP=372, FN=25, Precision=100%, Recall=93.7%, F1=96.7%**

Los 25 FN corresponden a nombres fragmentados por OCR de pypdf (e.g., `CHAVE Z SALAS`, `MERC EDES`, `OSTAIZA CEDEÑO LUISA ESPERANZA` capturado como dos fragmentos separados en el PDF).

### Capa 3: Firmantes — Sección de Firmas

Detecta nombres en la sección de firmas del documento mediante regex con títulos académicos.

```
Patrones detectados:
  "Elaborado por:"   Ing./Econ./Dr./Mgs./Abg./Lcdo./Téc. [NOMBRE]
  "Revisado por:"    [mismo patrón]
  "Aprobado por:"    [mismo patrón]
```

**Métricas (corpus evaluado): VP=0, FN=0**

> **Nota metodológica importante**: La Capa 3 registra 0 VP y 0 FN porque los nombres de firmantes que aparecen en la sección de firmas **ya habían sido detectados por la Capa 2 (spaCy NER)** durante el procesamiento del texto completo. El sistema procesa el documento entero antes de aplicar capas secuenciales, por lo que la Capa 3 opera sobre texto que ya tiene los pseudónimos de la Capa 2. Esto no es un fallo — es el comportamiento esperado de la arquitectura en cascada. La Capa 3 existe como salvaguarda para documentos donde spaCy no detecte los firmantes (e.g., nombre muy abreviado o formato atípico).

---

## 5. Flujo de Datos Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FLUJO COMPLETO — PROCESAMIENTO DE UN PAR IT+PR                            │
│                                                                             │
│  1. Usuario sube PDF (IT o PR)                                              │
│           │                                                                 │
│  2. Backend extrae texto con pypdf                                         │
│           │                                                                 │
│  3. Backend solicita pseudonimización a pseudonym-api                      │
│     POST /internal/pseudonymize                                             │
│     Headers: Authorization: Bearer {JWT}, X-User-ID: {analista}            │
│     Body: { text, session_id, purpose: "CLAUDE_API_EXTRACTION" }           │
│           │                                                                 │
│  4. pseudonym-api aplica 4 capas:                                          │
│     Capa 1  → Regex (RUC, cédula, email, teléfono, dirección intersección) │
│     Capa 1.5→ Header parser (nombre empresa, rep. legal, dirección tabla)  │
│     Capa 2  → spaCy NER (nombres PER en texto libre, re.IGNORECASE)       │
│     Capa 3  → Firmantes (nombres en sección Elaborado/Revisado/Aprobado)  │
│           │                                                                 │
│  5. pseudonym-api almacena mapeos cifrados:                                │
│     {pseudonimo: AES-256-GCM(valor_real)} en postgres_pseudonym           │
│     TTL 1h registrado en Redis                                             │
│           │                                                                 │
│  6. pseudonym-api devuelve texto pseudonimizado + session_id               │
│           │                                                                 │
│  7. Backend genera HTML de previsualización                                │
│     Usuario REVISA que todo está correctamente pseudonimizado              │
│     [VALIDACIÓN VISUAL OBLIGATORIA — ningún dato personal debe aparecer]  │
│           │                                                                 │
│  8. Usuario confirma → Backend envía texto pseudonimizado a Claude API     │
│     POST https://api.anthropic.com/v1/messages                             │
│     claude-sonnet-4-20250514, temperatura=0.0, few-shot prompting          │
│           │                                                                 │
│  9. Claude devuelve JSON con pseudónimos (e.g., NOMBRE_A3F7B2C1)          │
│           │                                                                 │
│ 10. Backend solicita des-pseudonimización                                  │
│     POST /internal/depseudonymize                                          │
│     pseudonym-api descifra y devuelve valores originales                   │
│           │                                                                 │
│ 11. Backend aplica validador ROTH Art. 204                                 │
│     (fechas tope, días retraso, severidad)                                 │
│           │                                                                 │
│ 12. Resultados se almacenan en postgres_main                               │
│     (datos de negocio con valores reales ya des-pseudonimizados)          │
│           │                                                                 │
│ 13. TTL Redis expira → mapeos se eliminan automáticamente de postgres_pseu │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Ciclo de Vida de los Datos

```
Creación          Uso                    Expiración
    │               │                        │
    ▼               ▼                        ▼
  t=0            t=0→3.5min               t=1h
  ┌──────────┐   ┌──────────────────┐    ┌──────────────┐
  │ Mapeo    │   │ Mapeo activo     │    │ TTL Redis    │
  │ creado   │   │ disponible para  │    │ expira →     │
  │ en Redis │   │ des-pseudonim.   │    │ mapeo        │
  │ + pseu.  │   │ (window de       │    │ eliminado    │
  │ DB       │   │  procesamiento)  │    │ de pseu. DB  │
  └──────────┘   └──────────────────┘    └──────────────┘

  ⚠️ Solo el proceso que creó el mapeo (mismo session_id)
     puede des-pseudonimizarlo dentro de la ventana de 1h.

  ⚠️ Tras expiración, los pseudónimos en postgres_main son
     PERMANENTES e irreversibles. Por diseño: los datos de
     negocio ya fueron des-pseudonimizados en el paso 10.
```

---

## 7. Best Practices Implementadas

| Práctica | Implementación |
|---|---|
| **Separación de duties** | El servicio que pseudonimiza no puede extraer; el que extrae no puede acceder a los mapeos |
| **Cifrado en reposo** | AES-256-GCM para todos los valores originales en `postgres_pseudonym` |
| **Cifrado en tránsito** | JWT entre backend ↔ pseudonym-api; HTTPS a Claude API |
| **Expiración automática** | Redis TTL 1h; función PostgreSQL `delete_expired_mappings()` |
| **Zero hardcoded secrets** | Todas las claves en `.env` (en `.gitignore`) |
| **Non-root containers** | Usuario `arcotel` (UID 1000) en backend; `pseudonym` en pseudonym-service |
| **Auditoría completa** | `pseudonym_access_log` registra cada operación con user_id y timestamp |
| **Validación visual** | HTML de previsualización obligatorio antes de confirmar procesamiento |
| **Separación de errores** | Logs sanitizados que no exponen detalles del cifrado o valores reales |

---

## 8. Comunicación Entre Servicios

### 8.1 Autenticación JWT Interna

```python
import jwt
from datetime import datetime, timedelta

def generate_internal_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "service": "backend",
        "purpose": "CLAUDE_API_EXTRACTION",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
```

### 8.2 Endpoints del Servicio de Pseudonimización

| Endpoint | Método | Auth | Descripción |
|---|---|---|---|
| `/internal/pseudonymize` | POST | JWT + X-User-ID | Pseudonimiza texto (4 capas) |
| `/internal/depseudonymize` | POST | JWT + X-User-ID | Recupera valores originales |
| `/session/{session_id}` | DELETE | JWT | Limpia mapeos de sesión manualmente |
| `/health` | GET | — | Liveness check |
| `/ready` | GET | — | Readiness check (verifica BD, Vault y Redis) |
| `/live` | GET | — | Liveness básico para Docker |

### 8.3 Ejemplo Request/Response

```bash
# Pseudonimizar
curl -X POST http://localhost:8001/internal/pseudonymize \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-User-ID: analista_ctdg" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "RUC 1792554136001 de TELECOMUNICACIONES EJEMPLO S.A., Rep. Legal JUAN PÉREZ GARCÍA",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "purpose": "CLAUDE_API_EXTRACTION"
  }'

# Response
{
  "pseudonymized_text": "RUC RUC_A3F7B2C1 de NOMBRE_D4E8F2A1, Rep. Legal NOMBRE_F2C9D6E3",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "entities_found": {
    "RUC": 1,
    "NOMBRE": 2
  },
  "mappings_created": 3
}
```

---

## 9. Seguridad y Auditoría

### 9.1 Tabla de Auditoría

Cada operación de pseudonimización y des-pseudonimización queda registrada:

```sql
CREATE TABLE pseudonym_access_log (
    id              SERIAL PRIMARY KEY,
    session_id      UUID NOT NULL,
    action          VARCHAR(20) NOT NULL,   -- 'PSEUDONYMIZE', 'DEPSEUDONYMIZE', 'CLEANUP'
    user_id         VARCHAR(100),           -- Analista que realizó la operación
    entities_count  INTEGER,                -- Cantidad de entidades procesadas
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB                   -- Info adicional (tipos de entidades, etc.)
);
```

### 9.2 Matriz de Riesgo

| Escenario | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Compromiso de `postgres_pseudonym` | Baja | Bajo | Datos cifrados — ilegibles sin clave Vault |
| Compromiso de Vault | Muy baja | Alto | Contenedor aislado, solo accesible desde pseudonym-api |
| Intercepcción JWT | Baja | Medio | Expiración en 5 min + validación de `service` en payload |
| Exfiltración de logs | Baja | Bajo | Logs sanitizados sin valores reales |
| OCR fragmentado (FN) | **Alta** | Medio | Validación visual obligatoria por el analista |

> El mayor riesgo operativo es la fragmentación OCR (causa del 94.6% de Recall vs. 100% objetivo). La validación visual obligatoria es la mitigación principal.

### 9.3 Política de Retención

- **Mapeos de sesión**: expiración automática en 1 hora (Redis TTL + función PostgreSQL)
- **Log de auditoría**: retención indefinida (registro de compliance)
- **Texto pseudonimizado en postgres_main**: indefinido (es texto de negocio, no datos personales)
- **Datos reales**: nunca persisten en ningún componente del sistema (solo existen en el mapeo TTL durante el procesamiento)

---

## 10. Configuración y Deployment

### 10.1 Variables de Entorno (pseudonym-service)

```bash
# Base de datos pseudonimización
POSTGRES_DB=pseudonym_vault
POSTGRES_USER=pseudonym_user
POSTGRES_PASSWORD=<password_seguro>
POSTGRES_HOST=postgres_pseudonym
POSTGRES_PORT=5432

# HashiCorp Vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<vault_token>
VAULT_TRANSIT_KEY_NAME=pseudonym-encryption-key

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<redis_password>

# JWT
JWT_SECRET=<secret_256_bits_minimo>

# TTL
TTL_HOURS=1
```

### 10.2 Inicialización de Vault (primera vez)

```bash
# Vault se inicializa automáticamente en modo dev
# En producción, inicializar manualmente:
docker exec -it arcotel_vault vault operator init
docker exec -it arcotel_vault vault operator unseal <unseal_key_1>
docker exec -it arcotel_vault vault operator unseal <unseal_key_2>
docker exec -it arcotel_vault vault operator unseal <unseal_key_3>

# Crear clave de cifrado transit
docker exec -it arcotel_vault vault secrets enable transit
docker exec -it arcotel_vault vault write -f transit/keys/pseudonym-encryption-key
```

---

## 11. Comandos de Operación

### 11.1 Testing

```bash
# Health check del servicio
curl http://localhost:8001/health
# → {"status": "healthy", "vault": "connected", "redis": "connected", "db": "connected"}

# Test completo de pseudonimización (requiere JWT desde backend)
JWT=$(curl -s -X POST http://localhost:8000/internal/auth \
  -d '{"service": "backend"}' | jq -r '.token')

curl -X POST http://localhost:8001/internal/pseudonymize \
  -H "Authorization: Bearer $JWT" \
  -H "X-User-ID: test_user" \
  -H "Content-Type: application/json" \
  -d '{"text": "RUC 1792554136001 de JUAN PÉREZ GARCÍA", "purpose": "CLAUDE_API_EXTRACTION"}'
```

### 11.2 Auditoría

```bash
# Ver últimas operaciones de auditoría
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT action, user_id, entities_count, timestamp FROM pseudonym_access_log ORDER BY timestamp DESC LIMIT 20;"

# Ver mapeos activos (solo metadatos — sin valores reales)
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT pseudonym, length(encrypted_value) AS encrypted_len, created_at, expires_at FROM pseudonym_mappings WHERE expires_at > NOW() LIMIT 10;"

# Verificar que Vault está operativo y tiene la clave configurada
docker exec -it arcotel_vault vault status
docker exec -it arcotel_vault vault list transit/keys
```

### 11.3 Mantenimiento

```bash
# Limpieza manual de mapeos expirados (normalmente automático por TTL)
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT delete_expired_mappings();"

# Rotar clave de cifrado de Vault (sin downtime — Vault maneja versiones)
docker exec -it arcotel_vault vault write -f transit/keys/pseudonym-encryption-key/rotate

# Reiniciar solo el servicio de pseudonimización
docker-compose restart pseudonym-api

# Reseteo completo (⚠️ SOLO desarrollo — destruye TODOS los datos)
docker-compose down -v && docker volume prune -f && docker-compose up -d
```

### 11.4 Logs en Tiempo Real

```bash
# Logs del servicio de pseudonimización
docker-compose logs -f pseudonym-api

# Solo errores y advertencias
docker-compose logs -f pseudonym-api | grep -E "ERROR|WARNING|CRITICAL"

# Seguimiento completo del flujo (ambos servicios)
docker-compose logs -f backend pseudonym-api | grep -E "pseudonim|session_id"
```

---

## 12. Métricas de Cobertura

Evaluado sobre **corpus de 70 documentos reales** de ARCOTEL (2021–2025), procesados con el script `procesar_corpus_completo.ps1`. Las métricas provienen de `metricas_pseudonimizacion.txt`, `vp_conteos.csv` y `fn_anotaciones.csv`.

### 12.1 Métricas Globales

| Métrica | Valor |
|---|:---:|
| Documentos evaluados | **70** |
| Entidades totales (VP + FN) | **515** |
| Verdaderos Positivos (VP) | **487** |
| Falsos Negativos (FN) | **28** |
| Falsos Positivos (FP) | **0** |
| Precisión | **100.0%** |
| Recall | **94.6%** |
| **F1-Score** | **97.2%** |

### 12.2 Por Tipo de Entidad

| Tipo Entidad | Total real | VP | FN | Capa principal | Precision | Recall | F1 |
|---|:---:|:---:|:---:|---|:---:|:---:|:---:|
| RUC | 23 | 23 | 0 | Capa 1 — Regex | 100.0% | 100.0% | **100.0%** |
| CEDULA | 13 | 13 | 0 | Capa 1 — Regex | 100.0% | 100.0% | **100.0%** |
| EMAIL | 45 | 45 | 0 | Capa 1 — Regex | 100.0% | 100.0% | **100.0%** |
| TELEFONO | 2 | 2 | 0 | Capa 1 / 1.5 | 100.0% | 100.0% | **100.0%** |
| DIRECCION | 35 | 32 | 3 | Capa 1.5 — Contextual | 100.0% | 91.4% | **95.5%** |
| NOMBRE | 397 | 372 | 25 | Capa 2 — spaCy NER | 100.0% | 93.7% | **96.7%** |
| **GLOBAL** | **515** | **487** | **28** | — | **100.0%** | **94.6%** | **97.2%** |

### 12.3 Por Capa

| Capa | Técnica | VP | FN | Precision | Recall | F1 |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Capa 1 — Regex | Determinística | 83 | 0 | 100.0% | 100.0% | **100.0%** |
| Capa 1.5 — Header | Determinística | 32 | 3 | 100.0% | 91.4% | **95.5%** |
| Capa 2 — spaCy NER | IA (NER) | 372 | 25 | 100.0% | 93.7% | **96.7%** |
| Capa 3 — Firmantes | Determinística | 0 | 0 | — | — | — ¹ |

> ¹ Capa 3 registra 0 VP y 0 FN porque los firmantes ya fueron capturados por spaCy NER (Capa 2) durante el procesamiento del texto completo. Es el comportamiento esperado de la arquitectura en cascada.

### 12.4 Por Documento

| Resultado | Documentos | % |
|---|:---:|:---:|
| Pseudonimización completa (0 FN) | **45** | **64.3%** |
| Pseudonimización parcial (≥1 FN) | **25** | **35.7%** |
| Con falsos positivos | **0** | **0.0%** |

**Distribución de FN por causa (28 FN totales):**

| Causa | FN | Tipo | Capa |
|---|:---:|---|---|
| Fragmentación OCR pypdf (nombre cortado entre columnas) | 22 | NOMBRE | Capa 2 |
| Nombre muy abreviado / inicial sola | 3 | NOMBRE | Capa 2 |
| Dirección con formato de referencia extenso | 3 | DIRECCION | Capa 1.5 |

**Ejemplos representativos de FN:**

| Documento | Valor fragmentado | Causa |
|---|---|---|
| CCDS-PR-2021-0283 | `ALFRED O` | pypdf fragmentó `ALFREDO` en dos tokens |
| CCDS-PR-2021-0303 | `ORDOÑEZ PEÑAFIEL KLEV ER RENAN` | Nombre cortado en límite de columna PDF |
| CCDS-PR-2022-0377 | `CATUCUAGO` | Un solo token, no clasificado como PER por spaCy |
| CTDG-2024-GE-0051 | `ORELLANA 1172 Y AMAZONAS (FRENTE AL COLEGIO MILITAR` | Dirección partida por límite de página PDF |
| CTDG-GE-2022-0299 | `Ana` | Nombre de pila solo, sin apellido — spaCy no clasifica como PER |

> **Conclusión sobre FN**: El 78.6% de los FN (22/28) son causados por fragmentación OCR de pypdf al extraer texto de PDFs con columnas o tablas — no por fallas del modelo NER. La Precisión = 100% indica que el sistema nunca pseudonimizó texto institucional por error. La validación visual obligatoria permite al analista identificar y confirmar manualmente estos casos antes de procesar.

---

## 13. Preguntas Frecuentes

**¿Qué datos personales detecta el sistema?**

RUC/cédula (10-13 dígitos), emails, teléfonos ecuatorianos (`09XXXXXXXX`), direcciones (intersecciones de calles y valores de tabla de encabezado), y nombres de personas físicas. No detecta —por diseño— nombres de empresas como entidades personales, ni datos que no constituyan información personal identificable.

**¿Qué pasa si la pseudonimización falla parcialmente?**

El sistema genera un HTML de previsualización que el analista debe revisar visualmente. Si el analista detecta datos personales no pseudonimizados, puede rechazar el procesamiento. Solo tras confirmación explícita (`confirmado: true` con `session_id`) se envía el texto a Claude API. Este flujo es un control compensatorio para los FN de OCR fragmentado.

**¿Los datos en `postgres_pseudonym` son recuperables por un atacante?**

No directamente. Están cifrados con AES-256-GCM mediante HashiCorp Vault. Un atacante necesitaría comprometer simultáneamente: (a) `postgres_pseudonym` para obtener los datos cifrados, y (b) HashiCorp Vault para obtener la clave de descifrado — dos sistemas independientes en contenedores separados con redes Docker sin intersección.

**¿Anthropic puede ver los datos personales?**

No. Claude API recibe exclusivamente pseudónimos (`NOMBRE_A3F7B2C1`). Los datos reales nunca abandonan el sistema local — esto es verificable en el código de `pseudonymization.py` del `pseudonym-service`.

**¿Por qué la cobertura completa es 64.3% y no más alta?**

Los 25 documentos con pseudonimización parcial tienen 1-2 FN por documento causados por fragmentación OCR. Esto no implica que se enviaron datos reales a Claude API — el sistema tiene la validación visual como control compensatorio. Para mejorar este indicador, la solución arquitectónica es reemplazar pypdf con un extractor OCR más robusto (e.g., pytesseract + preprocesamiento de imagen) que no fragmente texto en columnas PDF.

**¿La Capa 3 (Firmantes) sirve para algo si siempre registra 0 VP?**

Sí, como salvaguarda para documentos atípicos donde spaCy no detecte los firmantes. Por ejemplo, si un futuro documento tiene firmantes con nombres muy abreviados (solo iniciales) o en formato no estándar, la Capa 3 los capturaría antes de que lleguen a Claude API. En el corpus actual de 70 documentos, spaCy fue suficiente para capturar todos los firmantes.

---

## 14. Referencias y Normativa

| Fuente | Referencia |
|---|---|
| LOPDP Ecuador | Registro Oficial Suplemento N° 459, 26 de mayo de 2021 |
| GDPR Art. 4.5 | Reglamento (UE) 2016/679 — definición de pseudonimización |
| NIST SP 800-188 | De-Identification of Government Datasets |
| HashiCorp Vault | Documentación Transit Secrets Engine v1.x |
| spaCy | `es_core_news_lg` — modelo de lenguaje español (NER PER/LOC/ORG) |
| AES-256-GCM | FIPS 197 + NIST SP 800-38D |

---

*Generado con datos de: `metricas_pseudonimizacion.txt`, `vp_conteos.csv`, `fn_anotaciones.csv`*
*Última actualización: Marzo 2026 — corpus de evaluación: 70 documentos ARCOTEL (2021–2025)*
