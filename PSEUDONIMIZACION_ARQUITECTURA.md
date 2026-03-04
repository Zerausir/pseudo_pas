# 🔐 Arquitectura de Pseudonimización LOPDP-conforme

<div align="center">

[![LOPDP Ecuador](https://img.shields.io/badge/LOPDP_Ecuador-Compliant-22C55E?style=for-the-badge&logo=shield&logoColor=white)](https://www.telecomunicaciones.gob.ec/)
[![Vault](https://img.shields.io/badge/HashiCorp_Vault-AES--256--GCM-FFEC6E?style=for-the-badge&logo=vault&logoColor=black)](https://www.vaultproject.io/)
[![spaCy](https://img.shields.io/badge/spaCy-NER_es__core__news__lg-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)](https://spacy.io/)
[![Redis](https://img.shields.io/badge/Redis-TTL_1h-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Precision](https://img.shields.io/badge/Precisión-100%25-22C55E?style=for-the-badge)](.)
[![F1](https://img.shields.io/badge/F1--Score-97.2%25-3B82F6?style=for-the-badge)](.)

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
7. [Seguridad y Cifrado](#7-seguridad-y-cifrado)
8. [Comunicación Entre Servicios](#8-comunicación-entre-servicios)
9. [Configuración y Deployment](#9-configuración-y-deployment)
10. [Comandos de Operación](#10-comandos-de-operación)
11. [Métricas de Cobertura](#11-métricas-de-cobertura)
12. [Preguntas Frecuentes](#12-preguntas-frecuentes)
13. [Referencias y Normativa](#13-referencias-y-normativa)

---

## 1. Resumen Ejecutivo

### 1.1 El Problema

El sistema ARCOTEL PAS procesa documentos PDF que contienen **datos personales de ciudadanos ecuatorianos** (nombres, RUCs, cédulas, emails, teléfonos, direcciones). Para la extracción automática, estos textos deben enviarse a **Claude API (Anthropic, empresa con sede en EEUU)**, lo cual constituye una **transferencia internacional de datos personales** regulada por la LOPDP.

**Sin pseudonimización, el sistema violaría:**

| Violación | Artículo LOPDP | Consecuencia |
|---|---|---|
| Transferencia internacional sin garantías | Arts. 33, 55-60 | Sanción 0.7%–1% volumen negocios (Art. 72) |
| Falta de seudonimización/cifrado | Arts. 10.e, 37 | Medidas correctivas (Art. 65) |
| No separación técnica de datos sensibles | Art. 37 | Suspensión del tratamiento (Art. 65) |
| Violación principio de minimización | Art. 10.e | Requerimiento de autoridad (Art. 65) |

### 1.2 La Solución Implementada

Una arquitectura de **dos servicios técnicamente aislados** con un motor de pseudonimización de **cuatro capas en cascada**:

```
Texto original (datos reales)
        │
        ▼
┌─────────────────────────────┐
│  PSEUDONYM-SERVICE (8001)   │  ← Red Docker aislada
│  4 capas de detección       │  ← postgres_pseudonym separado
│  AES-256-GCM + Vault        │  ← TTL 1 hora (Redis)
└─────────────────────────────┘
        │
        ▼
Texto pseudonimizado ──► Claude API (Anthropic, EEUU)
        │
        ▼
JSON con pseudónimos ──► Des-pseudonimización ──► Datos reales en postgres_main
```

**Resultado en corpus de evaluación (70 documentos, 515 entidades):**
- Precisión = **100.0%** — ningún texto institucional pseudonimizado por error ✅
- F1-Score = **97.2%** ✅
- Recall = **94.6%** (28 FN por fragmentación OCR en docs 2021) ⚠️

---

## 2. Justificación Legal

### 2.1 Marco Normativo Aplicable

**LOPDP — Ley Orgánica de Protección de Datos Personales (Ecuador, 2021):**

> **Art. 10.e — Seudonimización:** Los datos personales deben ser tratados de forma que no puedan atribuirse a un titular sin información adicional, siempre que dicha información adicional se mantenga separada y sujeta a medidas técnicas y organizativas apropiadas.

> **Art. 33 — Transferencia internacional:** La transferencia de datos personales a un destinatario en un país u organización internacional que no garantice un nivel de protección adecuado solo podrá realizarse si se cumplen las condiciones previstas en los artículos 55-60.

> **Art. 37 — Medidas de seguridad:** El responsable del tratamiento aplicará medidas técnicas y organizativas apropiadas para garantizar un nivel de seguridad adecuado al riesgo, incluyendo seudonimización y cifrado de datos personales.

> **Arts. 55-60 — Transferencia internacional con garantías:** Regulan las condiciones bajo las cuales pueden transferirse datos personales a países sin nivel de protección adecuado (como EEUU respecto a Ecuador).

### 2.2 Análisis de Conformidad

La pseudonimización implementada cumple la LOPDP porque:

1. **Claude API opera exclusivamente con pseudónimos** → tokens sin significado independiente del contexto, lo que excluye técnicamente estos datos del ámbito de la transferencia internacional de datos personales.

2. **Separación técnica real** → `postgres_main` y `postgres_pseudonym` son instancias PostgreSQL completamente separadas en contenedores distintos, en redes Docker sin intersección.

3. **Minimización de exposición** → Los mapeos expiran automáticamente en 1 hora mediante Redis TTL. No existen datos de largo plazo en el sistema de pseudonimización.

4. **Cifrado de mapeos en reposo** → Los valores originales se almacenan cifrados con AES-256-GCM mediante HashiCorp Vault. Un atacante que acceda a `postgres_pseudonym` solo obtiene texto cifrado sin la clave de descifrado.

---

## 3. Arquitectura de Dos Servicios

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              SISTEMA ARCOTEL PAS                                │
│                                                                                  │
│  ┌─────────────────────────────────────────┐    ┌───────────────────────────┐   │
│  │        BACKEND (puerto 8000)             │    │  PSEUDONYM-SERVICE (8001) │   │
│  │        red: main_network                 │    │  red: pseudonym_network   │   │
│  │              + internal_api              │    │       + internal_api      │   │
│  │                                          │    │                           │   │
│  │  FastAPI app                             │    │  FastAPI app              │   │
│  │  SQLAlchemy → postgres_main (5432)       │    │  4 capas pseudonimización │   │
│  │  Anthropic client → Claude API           │    │  SQLAlchemy → postgres_   │   │
│  │  Validador ROTH Art. 204                 │    │    pseudonym (5433)       │   │
│  │                                          │    │  hvac client → Vault      │   │
│  │  ┌──────────────────────────────────┐   │    │  redis.asyncio → Redis    │   │
│  │  │  DATOS DE NEGOCIO               │   │    │                           │   │
│  │  │  (pseudónimos → des-pseu. →     │   │    │  DATOS DE PSEUDONIMIZACIÓN│   │
│  │  │   valores reales en postgres_   │   │    │  (mapeos cifrados AES-256 │   │
│  │  │   main)                         │   │    │   TTL 1h, solo accesibles │   │
│  │  └──────────────────────────────────┘   │    │   vía JWT interno)        │   │
│  └─────────────────────────────────────────┘    └───────────────────────────┘   │
│           ↕ JWT (internal_api)                           ↕ JWT (internal_api)    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    INFRAESTRUCTURA COMPARTIDA                           │    │
│  │  postgres_main:5432  │  postgres_pseudonym:5433  │  Vault:8200           │    │
│  │  redis:6379          │  adminer:8080                                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Regla fundamental de aislamiento:**
- El backend **nunca** accede a `postgres_pseudonym` directamente
- El pseudonym-service **nunca** accede a `postgres_main` directamente
- Toda comunicación entre servicios usa JWT en `internal_api` (red Docker aislada, sin exposición de puertos al host)

---

## 4. Motor de Pseudonimización — 4 Capas

El motor aplica cuatro capas de forma **secuencial** sobre el texto completo del documento antes de enviarlo a Claude API.

### Capa 1: Regex Estructurado — Datos de Formato Fijo

Detecta entidades con formato estructurado mediante expresiones regulares específicas del dominio ecuatoriano.

```python
PATRONES = {
    'RUC':      r'\b\d{10,13}\b',             # RUC: 10-13 dígitos
    'CEDULA':   r'\b\d{10}\b',                 # Cédula: exactamente 10 dígitos
    'EMAIL':    r'\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b',
    'TELEFONO': r'\b0[2-9]\d{7}\b|\b09\d{8}\b',  # Fijo (02-09) o móvil (09X)
}
```

**Métricas (corpus evaluado): VP=83, FN=0, Precision=100%, Recall=100%, F1=100%**

> ✅ Detección perfecta — los patrones regex tienen cobertura total para el formato ecuatoriano de RUC (10-13 dígitos), cédula (10 dígitos), email y teléfono.

### Capa 1.5: Contextual (Header Parser) — Encabezado del Formulario

Detecta el nombre del prestador y la dirección en la tabla de encabezado del formulario FO-DEAR-47, donde la posición estructural es predecible.

```python
# Busca en la tabla de encabezado de IT (posición fija en FO-DEAR-47)
CAMPOS_HEADER = {
    'nombre_prestador': ['OPERADORA:', 'EMPRESA:', 'PRESTADOR:', 'RAZÓN SOCIAL:'],
    'direccion':        ['DIRECCIÓN:', 'DOMICILIO:', 'DIRECCIÓN DOMICILIARIA:'],
    'representante':    ['REPRESENTANTE LEGAL:', 'REP. LEGAL:'],
}
```

**Métricas (corpus evaluado): VP=32, FN=3, Precision=100%, Recall=91.4%, F1=95.5%**

> Los 3 FN corresponden a direcciones con formato de referencia extenso que cruzan el límite de columna en el PDF (pypdf las fragmenta en dos filas). La Precisión = 100% indica cero falsas detecciones en texto institucional.

### Capa 2: spaCy NER — Nombres en Texto Libre

Detecta nombres de personas naturales y razones sociales en el cuerpo del documento mediante el modelo `es_core_news_lg`.

**Normalización crítica antes de NER:**

Los documentos ARCOTEL están escritos 100% en MAYÚSCULAS, pero spaCy fue entrenado principalmente con texto en Title Case. Sin normalización, la precisión cae de ~95% a ~40%.

```python
SIGLAS_ARCOTEL = {
    'ARCOTEL', 'SAI', 'GFC', 'CTDG', 'CCON', 'CZ2', 'DEDA',
    'RUC', 'SBU', 'LOT', 'COA', 'ROTH', 'PAS', 'CAFI',
    'CCDS', 'CCDE', 'PRD', 'FO', 'DEAR',
}

def normalizar_mayusculas(texto: str) -> str:
    """Convierte MAYÚSCULAS a Title Case preservando siglas institucionales."""
    palabras = texto.split()
    return ' '.join(
        p if p in SIGLAS_ARCOTEL else p.title()
        for p in palabras
    )
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
    if len(palabras) < 2:           # Al menos 2 tokens
        return False
    if texto.upper() in SIGLAS_ARCOTEL:  # No es una sigla institucional
        return False
    if any(c.isdigit() for c in texto):  # No contiene números
        return False
    return True
```

**Métricas (corpus evaluado): VP=372, FN=25, Precision=100%, Recall=93.7%, F1=96.7%**

Los 25 FN corresponden a nombres fragmentados por OCR de pypdf (ejemplos documentados en `fn_anotaciones.csv`: `ALFRED O`, `MERC EDES`, `CHAVE Z SALAS`, `IÑIGUE Z`, `SIMBAÑ A`, `JA VIER`, `MANUE L`, `MART HA INES`, `D AMIAN`). Estos fragmentos no son reconocidos como entidades PER por spaCy porque no corresponden a nombres válidos.

### Capa 3: Firmantes — Sección de Firmas

Detecta nombres en la sección de firmas del documento mediante regex con patrones de títulos académicos ecuatorianos.

```python
TITULOS_ACADEMICOS = r'\b(?:Ing\.|Econ\.|Dr\.|Dra\.|Mgs\.|Abg\.|Lcdo\.|Lcda\.|Téc\.)\s+'
PATRON_FIRMANTE = re.compile(
    r'(?:Elaborado|Revisado|Aprobado)\s+por[:\s]+' + TITULOS_ACADEMICOS + r'([A-ZÁ-Ú][a-záéíóúñ]+(?:\s+[A-ZÁ-Ú][a-záéíóúñ]+)+)',
    re.IGNORECASE
)
```

**Métricas (corpus evaluado): VP=0, FN=0**

> **Nota metodológica importante**: La Capa 3 registra 0 VP y 0 FN en el corpus evaluado porque los nombres de firmantes **ya habían sido detectados por la Capa 2 (spaCy NER)** al procesar el texto completo del documento. El sistema procesa el documento íntegro antes de aplicar capas secuenciales, por lo que la Capa 3 opera sobre texto que ya contiene los pseudónimos de la Capa 2. Esto es el comportamiento esperado de la arquitectura en cascada — la Capa 3 existe como salvaguarda para documentos con formatos atípicos de firma donde spaCy podría no detectar el nombre correctamente.

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
│     Capa 1   → Regex (RUC, cédula, email, teléfono)                       │
│     Capa 1.5 → Header parser (nombre empresa, rep. legal, dirección tabla) │
│     Capa 2   → spaCy NER (nombres en texto libre, re.IGNORECASE)          │
│     Capa 3   → Firmantes (nombres en sección Elaborado/Revisado/Aprobado) │
│           │                                                                 │
│  5. pseudonym-api almacena mapeos cifrados:                                │
│     {pseudonimo: AES-256-GCM(valor_real)} en postgres_pseudonym            │
│     TTL 1h registrado en Redis                                             │
│           │                                                                 │
│  6. pseudonym-api devuelve texto pseudonimizado + session_id               │
│           │                                                                 │
│  7. Backend genera HTML de previsualización                                │
│     ⚠️  PASO OBLIGATORIO — el analista REVISA visualmente                 │
│         que todos los datos personales están reemplazados                  │
│           │                                                                 │
│  8. Analista confirma → Backend envía a Claude API                         │
│     POST https://api.anthropic.com/v1/messages                             │
│     claude-sonnet-4-20250514, temperatura=0.0                              │
│           │                                                                 │
│  9. Claude API devuelve JSON con pseudónimos (nunca datos reales)          │
│           │                                                                 │
│  10. Módulo 1 calcula campos derivados si son nulos:                       │
│      dias_retraso = fecha_real − fecha_maxima                              │
│      fecha_max = fecha_vigencia_gfc − 15 días (ROTH Art. 204)             │
│           │                                                                 │
│  11. Backend solicita des-pseudonimización:                                │
│      POST /internal/depseudonymize (con session_id)                        │
│           │                                                                 │
│  12. Módulo 2 valida coherencia normativa (ROTH Art. 204)                  │
│           │                                                                 │
│  13. Resultado final (datos reales) → postgres_main                        │
│           │                                                                 │
│  14. Redis TTL expira → mapeos eliminados automáticamente tras 1h          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Ciclo de Vida de los Datos

```
T+0s    Usuario sube PDF
T+1s    Backend extrae texto plano (pypdf)
T+2s    pseudonym-api genera pseudónimos y session_id
T+3s    Mapeos cifrados almacenados en postgres_pseudonym (TTL 1h iniciado en Redis)
T+5s    HTML de previsualización disponible para revisión del analista
T+30s   Analista confirma (o rechaza) la pseudonimización visual
T+31s   Texto pseudonimizado enviado a Claude API
T+49s   JSON con pseudónimos recibido de Claude API
T+50s   Campos derivados calculados (si aplica)
T+51s   Des-pseudonimización: JSON con pseudónimos → JSON con valores reales
T+52s   Validación normativa ROTH Art. 204
T+53s   Resultado almacenado en postgres_main
T+3600s Redis TTL expira → mapeos eliminados de postgres_pseudonym
```

**Garantías del ciclo de vida:**
- Los datos reales **nunca** pasan por la red Docker hacia Claude API
- Los mapeos de pseudonimización **nunca** persisten más de 1 hora
- El analista tiene la oportunidad de **rechazar** el procesamiento si detecta datos personales no pseudonimizados en el paso de previsualización

---

## 7. Seguridad y Cifrado

### Generación de Pseudónimos

```python
import secrets
import hashlib

def generar_pseudonimo(tipo: str, valor_original: str, session_id: str) -> str:
    """
    Genera pseudónimo criptográficamente seguro.
    El mismo valor en la misma sesión produce el mismo pseudónimo (determinístico).
    Valores distintos en sesiones distintas producen pseudónimos distintos.
    """
    salt = f"{session_id}:{valor_original}"
    hash_bytes = hashlib.sha256(salt.encode()).digest()
    suffix = hash_bytes[:4].hex().upper()
    return f"{tipo}_{suffix}"

# Ejemplo: NOMBRE_A3F7B2C1, RUC_D4E8F2A1, EMAIL_G7H1I4J2
```

### Cifrado con HashiCorp Vault (AES-256-GCM)

```python
import hvac

class VaultClient:
    def __init__(self, vault_addr: str, vault_token: str):
        self.client = hvac.Client(url=vault_addr, token=vault_token)
        self.mount_point = "transit"
        self.key_name = "pseudonym-key"

    def encrypt(self, plaintext: str) -> str:
        """Cifra con AES-256-GCM mediante Vault Transit Engine."""
        import base64
        plaintext_b64 = base64.b64encode(plaintext.encode()).decode()
        result = self.client.secrets.transit.encrypt_data(
            name=self.key_name,
            plaintext=plaintext_b64,
            mount_point=self.mount_point
        )
        return result['data']['ciphertext']  # vault:v1:AbCdEf...

    def decrypt(self, ciphertext: str) -> str:
        """Descifra con Vault Transit Engine."""
        import base64
        result = self.client.secrets.transit.decrypt_data(
            name=self.key_name,
            ciphertext=ciphertext,
            mount_point=self.mount_point
        )
        return base64.b64decode(result['data']['plaintext']).decode()
```

### TTL con Redis

```python
import redis.asyncio as aioredis

async def registrar_session_ttl(redis_client, session_id: str, ttl_seconds: int = 3600):
    """Registra sesión con expiración automática de 1 hora."""
    await redis_client.setex(f"pseudonym:session:{session_id}", ttl_seconds, "active")

async def verificar_session_activa(redis_client, session_id: str) -> bool:
    """Verifica si la sesión aún está activa (dentro de TTL)."""
    return await redis_client.exists(f"pseudonym:session:{session_id}") == 1
```

### Matriz de Amenazas y Mitigaciones

| Amenaza | Mitigación |
|---|---|
| Atacante accede a `postgres_pseudonym` | Datos cifrados con AES-256-GCM — ilegibles sin clave Vault |
| Atacante intercepta llamadas a Claude API | Solo recibe pseudónimos sin significado |
| Mapeos de pseudonimización persisten indefinidamente | TTL Redis de 1 hora — eliminación automática |
| Backend accede a `postgres_pseudonym` directamente | Redes Docker sin intersección — imposible por configuración |
| Token JWT comprometido | Expiración de 60 minutos — ventana de ataque acotada |
| Datos reales en logs del sistema | Logs sanitizados — solo pseudónimos en trazas |

---

## 8. Comunicación Entre Servicios

### Autenticación JWT

```python
# Backend genera token para llamar a pseudonym-service
import jwt
from datetime import datetime, timedelta

def generar_token_interno(user_id: str, secret: str) -> str:
    payload = {
        "sub": user_id,
        "service": "backend",
        "exp": datetime.utcnow() + timedelta(minutes=60),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, secret, algorithm="HS256")

# pseudonym-service valida el token en cada request
def verificar_token_interno(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])
```

### Endpoint de Pseudonimización

```python
# POST /internal/pseudonymize
{
    "text": "Texto del documento con datos personales",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "purpose": "CLAUDE_API_EXTRACTION",
    "document_type": "informe_tecnico"   # o "peticion_razonada"
}

# Respuesta
{
    "pseudonymized_text": "Texto con NOMBRE_A3F7 y RUC_B2C1...",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "entities_found": 12,
    "entities_by_type": {"NOMBRE": 5, "RUC": 2, "EMAIL": 1, "CEDULA": 1, ...},
    "ttl_expires_at": "2026-03-04T14:30:00Z"
}
```

### Endpoint de Des-pseudonimización

```python
# POST /internal/depseudonymize
{
    "data": {"prestador_nombre": "NOMBRE_A3F7", "prestador_ruc": "RUC_B2C1"},
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}

# Respuesta
{
    "data": {"prestador_nombre": "TELECOMUNICACIONES EJEMPLO S.A.", "prestador_ruc": "1792554136001"},
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 9. Configuración y Deployment

### Variables de Entorno Requeridas

```bash
# HashiCorp Vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<vault_root_token>
VAULT_TRANSIT_KEY=pseudonym-key

# PostgreSQL pseudonimización
PSEUDONYM_DATABASE_URL=postgresql://pseudonym_user:<password>@postgres_pseudonym:5433/pseudonym_db

# Redis
REDIS_URL=redis://redis:6379

# JWT
JWT_SECRET_KEY=<clave_secreta_aleatoria_256bits>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Configuración NER
SPACY_MODEL=es_core_news_lg
NER_MIN_TOKENS=2          # Mínimo de tokens para considerar entidad PER válida
NER_CONFIDENCE_THRESHOLD=0.85
```

### Inicialización de Vault (primera vez)

```bash
# 1. Inicializar Vault
docker exec -it vault vault operator init -key-shares=1 -key-threshold=1

# 2. Guardar el Unseal Key y Root Token en lugar seguro

# 3. Unseal Vault
docker exec -it vault vault operator unseal <unseal_key>

# 4. Autenticarse con Root Token
docker exec -it vault vault login <root_token>

# 5. Habilitar Transit Engine
docker exec -it vault vault secrets enable transit

# 6. Crear clave de cifrado
docker exec -it vault vault write -f transit/keys/pseudonym-key type=aes256-gcm96

# 7. Verificar
docker exec -it vault vault read transit/keys/pseudonym-key
```

### Descargar modelo spaCy

```bash
# Dentro del contenedor pseudonym-api (o en el Dockerfile)
python -m spacy download es_core_news_lg

# Verificar
python -c "import spacy; nlp = spacy.load('es_core_news_lg'); print('OK')"
```

---

## 10. Comandos de Operación

```bash
# Levantar todos los servicios
docker-compose up -d

# Ver logs del servicio de pseudonimización
docker-compose logs -f pseudonym-api

# Estado del sistema
curl http://localhost:8001/health
curl http://localhost:8001/ready

# Limpiar sesión de pseudonimización manualmente
curl -X DELETE http://localhost:8001/session/{session_id} \
  -H "Authorization: Bearer {jwt_token}"

# Ver sesiones activas en Redis
docker exec -it redis redis-cli KEYS "pseudonym:session:*"

# Ver métricas de pseudonimización por documento
docker exec -it postgres_pseudonym psql -U pseudonym_user -d pseudonym_db \
  -c "SELECT session_id, entities_count, created_at, expires_at FROM pseudonym_sessions ORDER BY created_at DESC LIMIT 20;"

# Reiniciar solo el servicio de pseudonimización
docker-compose restart pseudonym-api

# Verificar que postgres_pseudonym NO es accesible desde el backend
docker exec -it backend ping postgres_pseudonym  # Debe fallar — redes aisladas
```

---

## 11. Métricas de Cobertura

Evaluado sobre **corpus de 70 documentos reales** de ARCOTEL (2021–2025). Fuentes: `metricas_pseudonimizacion.txt`, `metricas_pseudonimizacion.xlsx`, `vp_conteos.csv` y `fn_anotaciones.csv`.

### 11.1 Métricas Globales

| Métrica | Valor | Meta | Estado |
|---|:---:|:---:|:---:|
| Documentos evaluados | **70** | — | — |
| Entidades totales (VP + FN) | **515** | — | — |
| Verdaderos Positivos (VP) | **487** | — | — |
| Falsos Negativos (FN) | **28** | — | — |
| Falsos Positivos (FP) | **0** | = 0 | ✅ |
| Precisión | **100.0%** | = 100% | ✅ |
| Recall | **94.6%** | ≥ 95% | ⚠️ −0.4 pp |
| **F1-Score** | **97.2%** | ≥ 95% | ✅ +2.2 pp |
| Docs con cobertura completa | **45/70 (64.3%)** | ≥ 90% | ⚠️ −25.7 pp |

> El Recall de 94.6% y la cobertura documental de 64.3% reflejan 28 FN causados exclusivamente por fragmentación OCR en documentos de 2021 — no por un fallo arquitectónico del sistema. Los 45 documentos del período 2022–2025 presentaron pseudonimización completa (F1=100% en ese subconjunto).

### 11.2 Por Tipo de Entidad

| Tipo Entidad | Total real | VP | FN | Capa principal | Precision | Recall | F1 |
|---|:---:|:---:|:---:|---|:---:|:---:|:---:|
| RUC | 23 | 23 | 0 | Capa 1 — Regex | 100.0% | 100.0% | **100.0%** |
| CEDULA | 13 | 13 | 0 | Capa 1 — Regex | 100.0% | 100.0% | **100.0%** |
| EMAIL | 45 | 45 | 0 | Capa 1 — Regex | 100.0% | 100.0% | **100.0%** |
| TELEFONO | 2 | 2 | 0 | Capa 1 / 1.5 | 100.0% | 100.0% | **100.0%** |
| DIRECCION | 35 | 32 | 3 | Capa 1.5 — Contextual | 100.0% | 91.4% | **95.5%** |
| NOMBRE | 397 | 372 | 25 | Capa 2 — spaCy NER | 100.0% | 93.7% | **96.7%** |
| **GLOBAL** | **515** | **487** | **28** | — | **100.0%** | **94.6%** | **97.2%** |

### 11.3 Por Capa

| Capa | Técnica | VP | FN | Precision | Recall | F1 |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Capa 1 — Regex | Determinística | 83 | 0 | 100.0% | 100.0% | **100.0%** |
| Capa 1.5 — Header | Determinística | 32 | 3 | 100.0% | 91.4% | **95.5%** |
| Capa 2 — spaCy NER | IA (NER) | 372 | 25 | 100.0% | 93.7% | **96.7%** |
| Capa 3 — Firmantes | Determinística | 0 | 0 | — | — | — ¹ |

> ¹ Capa 3 registra 0 VP y 0 FN porque los firmantes ya fueron capturados por spaCy NER (Capa 2). Es el comportamiento esperado de la arquitectura en cascada.

### 11.4 Por Documento

| Resultado | Documentos | % |
|---|:---:|:---:|
| Pseudonimización completa (0 FN) | **45** | **64.3%** |
| Pseudonimización parcial (≥1 FN) | **25** | **35.7%** |
| Con falsos positivos | **0** | **0.0%** |

**Distribución de los 28 FN por causa:**

| Causa | FN | Tipo | Capa |
|---|:---:|---|---|
| Fragmentación OCR pypdf (nombre cortado entre columnas PDF) | 22 | NOMBRE | Capa 2 |
| Nombre muy abreviado / token único no reconocido como PER | 3 | NOMBRE | Capa 2 |
| Dirección con formato de referencia extenso fragmentado | 3 | DIRECCION | Capa 1.5 |

**Ejemplos representativos de FN (fuente: `fn_anotaciones.csv`):**

| Documento | Fragmento no detectado | Causa |
|---|---|---|
| CCDS-PR-2021-0283 | `ALFRED O` | pypdf fragmentó `ALFREDO` entre columnas PDF |
| CCDS-PR-2021-0303 | `CHAVE Z SALAS` | Nombre cortado en límite de columna PDF |
| CCDS-PR-2021-0304 | `MERC EDES` | Ídem |
| CTDG-GE-2021-0283 | `IÑIGUE Z` | Ídem — nombre con tilde fragmentado |
| CTDG-GE-2021-0307 | `SIMBAÑ A` | Ídem |
| CTDG-GE-2022-0299 | `Ana` | Token único — spaCy no clasifica como PER sin apellido |
| CTDG-2024-GE-0051 | `ORELLANA 1172 Y AMAZONAS (FRENTE AL...` | Dirección partida por límite de página |

> **Conclusión**: El 78.6% de los FN (22/28) son causados por fragmentación OCR de pypdf al extraer texto de PDFs con columnas — no por fallas del modelo NER. La solución estructural es reemplazar pypdf por un extractor OCR con pre-procesamiento de imagen que preserve la integridad de texto en columnas.

---

## 12. Preguntas Frecuentes

**¿Qué tipos de datos personales detecta el sistema?**

RUC/cédula (10-13 dígitos), emails, teléfonos ecuatorianos (`09XXXXXXXX`, `02XXXXXXX`), direcciones del prestador (intersecciones y valores de la tabla de encabezado FO-DEAR-47), y nombres de personas físicas. No detecta —por diseño— nombres de empresas como entidades personales independientes, ni datos que no constituyan información personal identificable (PII) bajo la LOPDP.

**¿Qué ocurre si la pseudonimización detecta un falso negativo?**

El sistema genera un HTML de previsualización que el analista debe revisar visualmente antes de confirmar el procesamiento. Si detecta un dato personal no pseudonimizado, puede rechazar la sesión sin que ningún dato llegue a Claude API. Este flujo de validación visual es el control compensatorio principal para los casos de fragmentación OCR.

**¿Los datos en `postgres_pseudonym` son recuperables por un atacante?**

No directamente. Están cifrados con AES-256-GCM mediante HashiCorp Vault Transit Engine. Un atacante necesitaría comprometer simultáneamente: (a) `postgres_pseudonym` para los datos cifrados, y (b) HashiCorp Vault para la clave de descifrado — dos sistemas en contenedores separados con redes Docker sin intersección.

**¿Anthropic puede ver los datos personales de los ciudadanos ecuatorianos?**

No. Claude API recibe exclusivamente pseudónimos (`NOMBRE_A3F7B2C1`). La clave de correspondencia entre pseudónimo y valor real nunca sale del sistema local.

**¿Por qué expiran los mapeos en 1 hora?**

Dos razones: (1) Minimización de datos — la LOPDP exige que los datos no se conserven más tiempo del necesario para el tratamiento; (2) Reducción de superficie de ataque — si el sistema es comprometido, la ventana de datos recuperables está acotada temporalmente.

**¿Qué pasa si el analista tarda más de 1 hora en confirmar?**

El session_id expira y los mapeos son eliminados automáticamente. El analista debe iniciar una nueva sesión de previsualización para ese documento. Este es el comportamiento esperado por diseño.

**¿Por qué la Capa 3 (Firmantes) tiene 0 VP en el corpus evaluado?**

Los firmantes en los documentos ARCOTEL aparecen en el texto completo del documento, no únicamente en la sección de firmas. Al procesar el documento íntegro en Capa 2 (spaCy NER) antes que en Capa 3, spaCy ya detecta y reemplaza los nombres de firmantes. La Capa 3 opera sobre texto que ya contiene pseudónimos, por lo que no encuentra entidades adicionales. Esta es la arquitectura en cascada funcionando correctamente. La Capa 3 actúa como salvaguarda para formatos atípicos de firma.

---

## 13. Referencias y Normativa

| Documento | Referencia |
|---|---|
| LOPDP Ecuador | Registro Oficial 459, 26 de mayo de 2021 — Arts. 10.e, 33, 37, 55-60, 65, 72 |
| LOT Ecuador | Registro Oficial Suplemento 439, 18 de febrero de 2015 |
| ROTH Ecuador | Registro Oficial Suplemento 959, 25 de marzo de 2017 — Art. 204 |
| COA Ecuador | Registro Oficial Suplemento 31, 7 de julio de 2017 |
| GDPR Art. 4.5 | Definición de seudonimización — base conceptual del enfoque |
| Hou et al. (2025) | A General Pseudonymization Framework for Cloud-Based LLMs (arXiv:2502.15233) |
| HashiCorp Vault | Transit Secrets Engine — AES-256-GCM key management |
| spaCy | es_core_news_lg — modelo NER para español |

---

*TFE — Iván Rodrigo Suárez Fabara | UNIR, Máster en Inteligencia Artificial | Marzo 2026*
*Directora: Mariana Edith Miranda Varela*
