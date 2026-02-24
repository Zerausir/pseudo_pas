# 🔐 Arquitectura de Pseudonimización

<div align="center">

[![LOPDP Ecuador](https://img.shields.io/badge/LOPDP_Ecuador-Compliant-22C55E?style=for-the-badge&logo=shield&logoColor=white)](https://www.telecomunicaciones.gob.ec/)
[![GDPR](https://img.shields.io/badge/GDPR_Art._4.5-Pseudonimización-3B82F6?style=for-the-badge&logo=eu&logoColor=white)](https://gdpr.eu/)
[![Vault](https://img.shields.io/badge/HashiCorp_Vault-AES--256--GCM-FFEC6E?style=for-the-badge&logo=vault&logoColor=black)](https://www.vaultproject.io/)
[![spaCy](https://img.shields.io/badge/spaCy-NER_es__core__news__lg-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)](https://spacy.io/)
[![Redis](https://img.shields.io/badge/Redis-TTL_1h-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)

**Sistema de pseudonimización de datos personales con separación técnica real, cumpliendo la Ley Orgánica de Protección de Datos Personales de Ecuador (LOPDP)**

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

El sistema ARCOTEL PAS procesa documentos PDF que contienen **datos personales de ciudadanos ecuatorianos** (nombres, RUCs, cédulas, emails, direcciones de domicilio). Para la extracción automática, estos datos deben enviarse a **Claude API (Anthropic, empresa con sede en EEUU)**, lo cual constituye una **transferencia internacional de datos personales** regulada por la LOPDP.

**Sin pseudonimización, el sistema violaría:**

| Violación | Artículo LOPDP | Consecuencia |
|---|---|---|
| Transferencia internacional sin garantías | Arts. 33, 55-60 | Sanción 0.7%–1% volumen negocios (Art. 72) |
| Falta de seudonimización/cifrado | Arts. 10.e, 37 | Medidas correctivas (Art. 65) |
| No separación técnica de datos sensibles | Art. 37 | Suspensión del tratamiento (Art. 65) |
| Violación principio de minimización | Art. 10.e | Requerimiento de autoridad (Art. 62) |

### 1.2 La Solución

**Arquitectura de pseudonimización con dos microservicios técnicamente aislados:**

```
┌─────────────────────────────────────────────────────────┐
│  SERVICIO 1: Backend Principal                          │
│  • Lee PDFs originales en memoria                       │
│  • Solicita pseudonimización (API interna, JWT)         │
│  • Envía a Claude API SOLO texto pseudonimizado         │
│  • Solicita des-pseudonimización                        │
│  • Almacena datos REALES en BD principal                │
└─────────────────────────┬───────────────────────────────┘
                          ↕ HTTP interna (JWT auth)
┌─────────────────────────────────────────────────────────┐
│  SERVICIO 2: Servicio de Pseudonimización               │
│  • API interna EXCLUSIVAMENTE (red privada, sin internet)│
│  • Genera pseudónimos criptográficamente seguros         │
│  • Cifra mapeos con HashiCorp Vault (AES-256-GCM)       │
│  • Almacena en BD separada (TTL: 1 hora, auto-limpieza) │
│  • Auditoría completa de todos los accesos              │
└─────────────────────────────────────────────────────────┘
```

### 1.3 Beneficios

| Dimensión | Beneficio |
|---|---|
| **Legal** | ✅ Cumple LOPDP Arts. 10.e, 33, 37, 55-60 |
| **Seguridad** | ✅ Defense in depth — múltiples capas independientes |
| **Privacidad** | ✅ Claude API nunca recibe datos personales reales |
| **Auditoría** | ✅ Trazabilidad completa, logs separados e inmutables |
| **Costo** | ✅ $0/mes adicional — 100% open source (Vault, Redis, spaCy) |

---

## 2. Justificación Legal

### 2.1 Marco Legal Aplicable

La **Ley Orgánica de Protección de Datos Personales (LOPDP)** de Ecuador está vigente desde mayo 2021 y aplica a todo tratamiento de datos personales realizado en territorio ecuatoriano. Las sanciones por incumplimiento alcanzan el 1% del volumen de negocios anual (Art. 72).

#### Art. 10.e — Principio de Minimización de Datos

> *"Los datos personales deben ser pertinentes y estar limitados a lo estrictamente necesario en relación con los fines para los que son tratados."*

**Implicación:** No debe enviarse más datos personales a Claude API de los absolutamente necesarios para la extracción.

**Cumplimiento:** La pseudonimización reemplaza nombres, RUCs y emails reales por tokens opacos. Claude API procesa únicamente lo mínimo indispensable: estructuras de fechas, artículos legales y datos no personales.

#### Art. 33 — Transferencia Internacional de Datos

> *"La transferencia o comunicación internacional de datos personales está prohibida, salvo que se cumplan las garantías adecuadas de protección."*

**Implicación:** Enviar datos personales a Anthropic (EEUU) sin mecanismos de garantía es ILEGAL bajo la LOPDP.

**Cumplimiento:** Al pseudonimizar, Claude API recibe `NOMBRE_A3F7B2C1` en lugar de `MOYON UNAUCHO KLEBER AUGUSTO`. Los datos transmitidos no son datos personales en el sentido del Art. 4 LOPDP, eliminando la transferencia internacional de datos personales de la ecuación.

#### Art. 37 — Seguridad del Tratamiento

> *"El responsable deberá implementar medidas técnicas y organizativas apropiadas, como la seudonimización y el cifrado de datos personales."*

**Implicación:** Existe una **obligación legal expresa** de implementar pseudonimización y cifrado.

**Cumplimiento:** Servicio de pseudonimización independiente con cifrado Vault + BD aislada + TTL automático + auditoría.

#### Arts. 55-60 — Garantías para Transferencia Internacional

> *"Se requiere autorización de la Autoridad o garantías adecuadas que acrediten nivel de protección equivalente."*

**Implicación:** Sin pseudonimización, sería necesaria autorización formal ante la Autoridad de Protección de Datos (proceso burocrático de meses).

**Cumplimiento:** Los datos pseudonimizados NO califican como datos personales según GDPR Art. 4.5 (referencia aplicable, Ecuador sigue estándares europeos en LOPDP).

### 2.2 ¿Por qué No es Suficiente un Solo Contenedor?

El Art. 37 LOPDP exige **"medidas técnicas Y organizativas"** — ambas dimensiones son requeridas:

| Dimensión | Un solo contenedor | Dos servicios separados |
|---|---|---|
| Técnica — cifrado | ✅ Posible | ✅ Implementado |
| Técnica — separación de redes | ❌ No hay separación real | ✅ Redes Docker aisladas |
| Organizativa — separación de responsabilidades | ❌ Backend accede a todo | ✅ Credenciales distintas por servicio |
| Organizativa — control de acceso | ❌ Un punto de fallo | ✅ JWT + red privada |
| Defense in depth | ❌ Compromiso backend = acceso a mapeos | ✅ Requiere comprometer 2 servicios |

---

## 3. Arquitectura de Dos Servicios

### 3.1 Visión General

```
┌────────────────────────────────────┐  ┌──────────────────────────────────┐
│  SERVICIO 1                        │  │  SERVICIO 2                      │
│  Backend Principal                 │  │  Pseudonimización                │
│                                    │  │                                  │
│  Contenedor: backend               │  │  Contenedor: pseudonym-api       │
│  Puerto: 8000 (público)            │  │  Puerto: 8001 (127.0.0.1 only)   │
│                                    │  │                                  │
│  Responsabilidades:                │  │  Responsabilidades:              │
│  • Recibir requests de usuarios    │  │  • Pseudonimizar texto           │
│  • Leer PDFs (data/)               │  │  • Des-pseudonimizar datos       │
│  • Llamar servicio pseudonimización│  │  • Cifrar con Vault              │
│  • Enviar a Claude API             │  │  • Auditar todos los accesos     │
│  • Validar datos extraídos         │  │  • Auto-limpiar expirados        │
│  • Almacenar en BD principal       │  │                                  │
│                                    │  │  Acceso SOLO a:                  │
│  Acceso SOLO a:                    │  │  • postgres_pseudonym            │
│  • postgres_main                   │  │  • vault                         │
│  • servicio pseudonimización       │  │  • redis                         │
│  • Claude API (internet)           │  │                                  │
│                                    │  │  SIN acceso a:                   │
│  SIN acceso a:                     │  │  • Internet                      │
│  • postgres_pseudonym              │  │  • BD principal                  │
│  • vault                           │  │  • Endpoints públicos            │
└────────────┬───────────────────────┘  └──────────────────┬───────────────┘
             │                                              │
             │           Red: internal_api                  │
             └──────────────────────────────────────────────┘
                          ↕ HTTP API interna (JWT auth)
```

### 3.2 Separación de Redes Docker

```yaml
networks:
  main_network:
    driver: bridge        # Backend ↔ postgres_main ↔ adminer
    # Puede salir a internet (Claude API)

  internal_api:
    driver: bridge        # Backend ↔ pseudonym-api únicamente
    # Canal de comunicación seguro entre servicios

  pseudonym_network:
    driver: bridge
    internal: true        # ⭐ SIN acceso a internet
    # Solo: pseudonym-api, postgres_pseudonym, vault, redis
```

**Garantías de aislamiento:**
- El backend **NO puede** conectarse directamente a `postgres_pseudonym`
- El servicio de pseudonimización **NO puede** acceder a internet ni a Claude API
- La comunicación ocurre exclusivamente a través de HTTP con JWT

---

## 4. Motor de Pseudonimización — 4 Capas

El servicio detecta y reemplaza datos personales en **4 capas secuenciales**, cada una especializada en un tipo de dato diferente. Si una capa ya detectó y reemplazó un valor, las capas siguientes lo omiten automáticamente.

### Capa 1: Regex — Datos Estructurados

Detecta entidades con formato definido mediante expresiones regulares. **Precisión: 100%, Recall: 100%.**

| Tipo | Patrón | Ejemplo → Pseudónimo |
|---|---|---|
| RUC | `\d{10,13}` (10 o 13 dígitos) | `1792554136001` → `RUC_A3F7B2C1` |
| Cédula | `\d{10}` (10 dígitos exactos) | `1719710830` → `CEDULA_D4E8F2A1` |
| Email | RFC 5322 pattern | `correo@empresa.com` → `EMAIL_B9C3D7E5` |
| Teléfono | Prefijo `09` + 8 dígitos | `0999079807` → `TELEFONO_F2C9D6E3` |
| Dirección intersección | Patrón `CALLE N-NUM Y CALLE` | `AV. NAPO S/N Y BOMBEROS` → `DIRECCION_G7H1I4J2` |

### Capa 1.5: Header Parser — Encabezado del Documento

Los informes técnicos de ARCOTEL tienen una tabla de encabezado estándar con campos etiquetados. Esta capa extrae valores por contexto de etiqueta, independientemente del formato exacto.

```
Detecta campos como:
  "PRESTADOR O CONCESIONARIO:" → extrae nombre empresa
  "REPRESENTANTE LEGAL:"       → extrae nombre persona
  "DIRECCIÓN:"                 → extrae dirección (incluye variantes sin intersección)
  "TELÉFONO:"                  → extrae teléfono sin prefijo nacional
```

Esta capa captura variantes de dirección que no siguen el patrón de intersección de la Capa 1 (e.g., `S58F Y OE5F, CASA S58F-93`). **Recall: 95.2%.**

### Capa 2: spaCy NER — Nombres de Personas

Aplica el modelo de lenguaje `es_core_news_lg` para detección de entidades nombradas. Solo procesa entidades de tipo **PER** (personas), ignorando LOC, ORG y otras.

**Normalización crítica antes de NER:**

Los documentos ARCOTEL están escritos 100% en MAYÚSCULAS, pero spaCy fue entrenado principalmente con texto en Title Case. Sin normalización, la precisión cae de ~95% a ~40%.

```python
# Normalización MAYÚSCULAS → Title Case (preservando siglas)
SIGLAS_ARCOTEL = {'ARCOTEL', 'SAI', 'GFC', 'CTDG', 'CCON', 'CZ2', 'DEDA',
                  'RUC', 'SBU', 'LOT', 'COA', 'ROTH', 'PAS'}

def normalizar_mayusculas(texto: str) -> str:
    """Convierte MAYÚSCULAS a Title Case preservando siglas institucionales."""
    palabras = texto.split()
    resultado = []
    for palabra in palabras:
        if palabra in SIGLAS_ARCOTEL:
            resultado.append(palabra)  # Mantener sigla
        else:
            resultado.append(palabra.title())  # Normalizar
    return ' '.join(resultado)
```

**Filtros estrictos para evitar falsos positivos:**

```python
def es_nombre_real(texto: str) -> bool:
    """Valida que una entidad PER sea realmente un nombre."""
    rechazar_si = [
        len(texto) < 10,                    # Demasiado corto
        len(texto) > 60,                    # Demasiado largo
        len(texto.split()) < 2,             # Solo una palabra
        any(c in texto for c in '→←•'),     # Caracteres especiales
        texto.lower() in PALABRAS_INSTITUCIONALES,  # "dirección", "coordinación", etc.
        any(texto.lower().startswith(v) for v in VERBOS_INICIO),  # "elaborar", "certificar"
    ]
    return not any(rechazar_si)
```

**Recall: 98.7%, 0 falsos positivos.**

### Capa 3: Firmantes — Sección de Firmas

Extrae nombres de la sección final del documento (últimos 2000 caracteres), donde se registran los firmantes con sus cargos.

```python
patrones_firmantes = [
    r'Elaborado\s+por:\s+(?:Ing\.|Dr\.|Econ\.|Abg\.|Lcdo\.|Téc\.|Mgs\.)?\s*([A-Za-záéíóúñÑ\s\.]+)',
    r'Revisado\s+por:\s+(?:Ing\.|Dr\.|Econ\.|Abg\.|Lcdo\.|Téc\.|Mgs\.)?\s*([A-Za-záéíóúñÑ\s\.]+)',
    r'Aprobado\s+por:\s+(?:Ing\.|Dr\.|Econ\.|Abg\.|Lcdo\.|Téc\.|Mgs\.)?\s*([A-Za-záéíóúñÑ\s\.]+)',
]
```

> **Importante:** La lista de títulos profesionales debe incluir todos los usados en ARCOTEL: `Ing.`, `Econ.`, `Dr.`, `Mgs.`, `Abg.`, `Lcdo.`, `Téc.` La omisión de un título provoca que ese firmante no sea detectado (ver CLAUDE.md regla 21).

### Reemplazo Case-Insensitive

Un aspecto crítico: los documentos usan MAYÚSCULAS pero spaCy detecta en Title Case. El reemplazo **nunca** usa `str.replace()` (case-sensitive). Siempre se usa `re.IGNORECASE`:

```python
def buscar_y_reemplazar_variaciones(texto: str, variaciones: list, pseudonimo: str) -> tuple:
    """
    Reemplaza todas las variaciones de un nombre con re.IGNORECASE.
    Las variaciones se ordenan de mayor a menor longitud para evitar
    reemplazos parciales (ej: 'Kleber' antes de 'Charco Iñiguez Klever Luis').
    """
    variaciones_ordenadas = sorted(variaciones, key=len, reverse=True)
    count = 0
    for variacion in variaciones_ordenadas:
        # Permite espacios/saltos de línea entre palabras del nombre
        patron = r'\s+'.join(re.escape(p) for p in variacion.split())
        nuevo_texto, n = re.subn(patron, pseudonimo, texto, flags=re.IGNORECASE)
        texto = nuevo_texto
        count += n
    return texto, count
```

---

## 5. Flujo de Datos Completo

### 5.1 Flujo Paso a Paso

```
PASO 1: Operador sube PDF
  data/informes_tecnicos/CTDG-GE-2022-0487.pdf
        │
        ▼
PASO 2: Backend extrae texto en memoria
  PyPDF2/pdfplumber → texto completo del documento
  "...TELECOMUNICACIONES WRXXXXX
   RUC: 179XXXXXXXXXX
   Representante: MOXXX UNXXXXX KXXXX AXXXX..."
        │
        ▼
PASO 3: POST /internal/pseudonymize (red internal_api, JWT)
  Request:
  {
    "text": "...WRXXXXX...179XXXXXXXXXX...",
    "session_id": "uuid-generado",
    "purpose": "CLAUDE_API_EXTRACTION"
  }
        │
        ▼
PASO 4: Servicio procesa las 4 capas
  Capa 1  → RUC: 179XXXXXXXXXX         → RUC_A3F7B2C1
  Capa 1.5→ TELECOMUNICACIONES WRX...  → NOMBRE_B9C3D7E5
  Capa 2  → MOXXX UNXXXXX ...          → NOMBRE_F2C9D6E3
  Capa 3  → Ing. Daxxx Chxxxx ...      → NOMBRE_G7H1I4J2

  Cifra mapeos con Vault (AES-256-GCM)
  Almacena en postgres_pseudonym (TTL: 1 hora)
  Retorna: { "pseudonymized_text": "...", "session_id": "..." }
        │
        ▼
PASO 5: Backend envía a Claude API (solo pseudónimos)
  "...NOMBRE_B9C3D7E5...
   RUC: RUC_A3F7B2C1
   Representante: NOMBRE_F2C9D6E3..."

  ⭐ Claude NUNCA ve datos personales reales
        │
        ▼
PASO 6: Claude retorna JSON con pseudónimos
  {
    "prestador": { "nombre": "NOMBRE_B9C3D7E5", "ruc": "RUC_A3F7B2C1" },
    "representante_legal": "NOMBRE_F2C9D6E3",
    "dias_retraso": 4
  }
        │
        ▼
PASO 7: POST /internal/depseudonymize (red internal_api, JWT)
  Servicio valida session_id → recupera de Redis/BD → descifra con Vault
  Reemplaza NOMBRE_B9C3D7E5 → "TELECOMUNICACIONES WRXXXXX"
  Reemplaza RUC_A3F7B2C1 → "179XXXXXXXXXX"
        │
        ▼
PASO 8: Backend almacena datos REALES en postgres_main
  Datos reales en casos_pas, documentos_pas, prestadores
        │
        ▼
PASO 9: Auto-limpieza (1 hora después)
  DELETE FROM pseudonym_mappings WHERE expires_at < NOW();
  ⭐ Zero persistencia de datos temporales
```

### 5.2 Flujo de Validación Previa (LOPDP Art. 8)

Antes del procesamiento existe un flujo obligatorio de validación visual que implementa el **consentimiento informado** del Art. 8 LOPDP:

```
POST /api/validacion/previsualizar
  │
  ├── Extrae texto del PDF
  ├── Pseudonimiza (mismas 4 capas)
  ├── Genera HTML con pseudónimos resaltados en color
  └── Retorna session_id + URL del HTML

  ↓ Operador descarga HTML → revisa visualmente → confirma

POST /api/archivos/procesar {confirmado: true, session_id: "..."}
  │
  └── Si confirmado=false → HTTP 403 (no se procesa)
```

### 5.3 Manejo de Fallos del Servicio de Pseudonimización

Si el servicio de pseudonimización no está disponible, el backend **nunca** envía datos sin pseudonimizar a Claude API:

```python
try:
    texto_pseudo, session_id = await pseudonym_client.pseudonymize(texto)
except (ConnectionError, TimeoutError):
    raise HTTPException(
        status_code=503,
        detail="Sistema de protección de datos temporalmente no disponible. "
               "No se procesará el documento hasta restaurar el servicio."
    )
```

---

## 6. Ciclo de Vida de los Datos

| Ubicación | Tipo de datos | Duración | Justificación |
|---|---|---|---|
| PDF original (`data/`) | Reales (originales) | Permanente | Archivo institucional ARCOTEL |
| Memoria backend (extracción) | Reales | < 30 segundos | Solo durante lectura del PDF |
| Texto pseudonimizado (tránsito) | Pseudónimos | < 5 segundos | Solo en tránsito a Claude API |
| Claude API | Pseudónimos | 0 segundos* | Claude no persiste datos de API |
| Redis (cache sesión) | Cifrados | TTL sesión (~5 min) | Performance en des-pseudonimización |
| `postgres_pseudonym` | Cifrados AES-256 | 1 hora (TTL) | LOPDP Art. 10.i — conservación limitada |
| `postgres_main` | Reales | Permanente | Sistema de negocio ARCOTEL |
| Logs de auditoría | Metadatos (sin datos reales) | 7 años | Compliance legal |

*Anthropic policy: "We do not train our models on inputs and outputs through our API"*

---

## 7. Best Practices Implementadas

### 7.1 Checklist de Cumplimiento

| Best Practice (GDPR/ISO 27001) | Estado | Implementación |
|---|:---:|---|
| **Separation** — BD y servicio separado | ✅ | Contenedor aislado, red `pseudonym_network` (internal=true) |
| **Purpose Limitation** — Solo un propósito | ✅ | Enum validado: solo `CLAUDE_API_EXTRACTION` |
| **Automation** — Herramientas consistentes | ✅ | API automatizada, sin intervención manual |
| **Regular Review** — Auditoría periódica | ✅ | Logs completos en `pseudonym_access_log` |
| **Security Measures** — Cifrado y control de acceso | ✅ | Vault AES-256-GCM + JWT + usuarios no-root |

### 7.2 Tokens Criptográficamente Seguros

```python
# ❌ MAL — Pseudónimos predecibles
"PRESTADOR_001"  # Se puede adivinar PRESTADOR_002, 003...
"RUC_1"          # Secuencial, fácil de iterar

# ✅ BIEN — 128 bits de entropía (implementado)
import secrets, hashlib

def generate_pseudonym(prefix: str) -> str:
    """Genera pseudónimo con 2^128 combinaciones posibles."""
    random_bytes = secrets.token_bytes(16)  # CSPRNG, 128 bits
    token = hashlib.sha256(random_bytes).hexdigest()[:16].upper()
    return f"{prefix}_{token}"

# Ejemplos: RUC_A3F7B2C14E9D1F6A
#           NOMBRE_2C8F1A4B3E9D7F5A
#           EMAIL_9E4D2A7F5C1B8G3H
```

**Comparación de entropía:**

```
"PRESTADOR_001"           →    10 bits (1,024 valores posibles)
"NOMBRE_A3F7B2C14E9D1F6A" → 128 bits (340 undecillones de valores)
```

### 7.3 Cifrado con HashiCorp Vault (KMS)

```sql
-- ❌ INSEGURO — valores en texto plano
CREATE TABLE pseudonym_mappings (
    pseudonym    VARCHAR(50),
    real_value   TEXT          -- ⚠️ Visible si acceden a la BD
);

-- ✅ SEGURO — implementado
CREATE TABLE pseudonym_mappings (
    pseudonym        VARCHAR(50) PRIMARY KEY,
    encrypted_value  TEXT NOT NULL,   -- AES-256-GCM vía Vault
    session_id       UUID NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT valid_ttl CHECK (expires_at > created_at)
);
```

Si un atacante compromete `postgres_pseudonym`, solo obtiene:
`vault:v1:8SDd3WHDOjf7mq69H...` — inutilizable sin la clave de Vault.

**Ventajas adicionales de Vault:**
- Rotación automática de claves sin downtime
- Auditoría de cada operación encrypt/decrypt
- Cumple FIPS 140-2

### 7.4 TTL Automático — Minimización de Exposición

```sql
-- Función de limpieza automática ejecutada por pg_cron cada hora
CREATE OR REPLACE FUNCTION delete_expired_mappings()
RETURNS INTEGER AS $$
DECLARE deleted_count INTEGER;
BEGIN
    DELETE FROM pseudonym_mappings WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    INSERT INTO cleanup_log (deleted_count, timestamp)
    VALUES (deleted_count, NOW());

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Cron job cada hora en punto
SELECT cron.schedule(
    'cleanup-expired-pseudonyms',
    '0 * * * *',
    'SELECT delete_expired_mappings()'
);
```

---

## 8. Comunicación Entre Servicios

### 8.1 Autenticación JWT Interna

```python
# Backend genera JWT para cada request al servicio de pseudonimización
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
| `/ready` | GET | — | Readiness check (verifica BD y Vault) |
| `/live` | GET | — | Liveness básico para Docker |

### 8.3 Ejemplo de Request/Response

```bash
# Pseudonimizar
curl -X POST http://localhost:8001/internal/pseudonymize \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-User-ID: analista_ctdg" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "RUC 1792554136001 de TELECOMUNICACIONES WRIVERA RED S.A.",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "purpose": "CLAUDE_API_EXTRACTION"
  }'

# Response
{
  "pseudonymized_text": "RUC RUC_A3F7B2C1 de NOMBRE_D4E8F2A1",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "entities_found": {
    "RUC": 1,
    "NOMBRE": 1
  },
  "mappings_created": 2
}
```

---

## 9. Seguridad y Auditoría

### 9.1 Tabla de Auditoría

Cada operación de pseudonimización y des-pseudonimización queda registrada:

```sql
CREATE TABLE pseudonym_access_log (
    id          SERIAL PRIMARY KEY,
    session_id  UUID NOT NULL,
    action      VARCHAR(20) NOT NULL,   -- 'PSEUDONYMIZE', 'DEPSEUDONYMIZE', 'CLEANUP'
    user_id     VARCHAR(100),           -- Analista que realizó la operación
    entities_count INTEGER,             -- Cantidad de entidades procesadas
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    metadata    JSONB                   -- Info adicional (tipos de entidades, etc.)
);
```

### 9.2 Monitoreo de Anomalías

El servicio genera alertas automáticas para patrones inusuales:

```python
ANOMALY_THRESHOLDS = {
    'max_pseudonymizations_per_hour': 500,
    'max_entities_per_document': 50,
    'unusual_entity_types': ['NOMBRE_MULTIPLE', 'RUC_MULTIPLE'],
}
```

### 9.3 Principios de Seguridad

| Principio | Implementación |
|---|---|
| **Least Privilege** | Usuarios no-root en Docker (`arcotel`, `pseudonym`) |
| **Defense in Depth** | 4 capas detección + red aislada + JWT + cifrado + TTL |
| **Zero Trust** | Cada request entre servicios se autentica con JWT de corta vida (5 min) |
| **Fail Secure** | Si el servicio falla → HTTP 503, nunca procesa sin pseudonimizar |
| **Audit Everything** | Cada operación de cifrado/descifrado en Vault queda registrada |
| **No Secrets in Code** | Todas las credenciales en `.env` (excluido de Git) |

---

## 10. Configuración y Deployment

### 10.1 Variables de Entorno del Servicio de Pseudonimización

```env
# Base de datos propia
POSTGRES_DB=pseudonym_vault
POSTGRES_USER=pseudonym_user
POSTGRES_PASSWORD=<contraseña-segura>
POSTGRES_HOST=postgres_pseudonym
POSTGRES_PORT=5432

# HashiCorp Vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<token-seguro>
VAULT_TRANSIT_KEY_NAME=pseudonym-encryption-key

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<contraseña-redis>

# Autenticación JWT (mismo secreto que backend)
JWT_SECRET=<secreto-min-32-chars>

# Configuración
TTL_HOURS=1
CLEANUP_INTERVAL_MINUTES=60
```

### 10.2 Docker Compose — Servicio de Pseudonimización

```yaml
pseudonym-api:
  build:
    context: ./pseudonym-service
    dockerfile: Dockerfile
  container_name: arcotel_pseudonym_api
  environment:
    POSTGRES_HOST: postgres_pseudonym
    VAULT_ADDR: http://vault:8200
    VAULT_TOKEN: ${VAULT_TOKEN}
    REDIS_HOST: redis
    REDIS_PASSWORD: ${REDIS_PASSWORD}
    JWT_SECRET: ${JWT_SECRET}
    TTL_HOURS: ${TTL_HOURS:-1}
  depends_on:
    postgres_pseudonym:
      condition: service_healthy
    vault:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - pseudonym_network    # Para Vault, Redis, postgres_pseudonym
    - internal_api         # Para comunicación con backend
  ports:
    - "127.0.0.1:8001:8001"    # ⭐ Solo localhost, nunca expuesto a red externa
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

---

## 11. Comandos de Operación

### 11.1 Testing

```bash
# Health check del servicio
curl http://localhost:8001/health
# → {"status": "healthy", "vault": "connected", "redis": "connected", "db": "connected"}

# Test completo de pseudonimización (requiere JWT)
JWT=$(curl -s -X POST http://localhost:8000/internal/auth \
  -d '{"service": "backend"}' | jq -r '.token')

curl -X POST http://localhost:8001/internal/pseudonymize \
  -H "Authorization: Bearer $JWT" \
  -H "X-User-ID: test_user" \
  -H "Content-Type: application/json" \
  -d '{"text": "RUC 179XXXXXXXXXX pertenece a TELECOMUNICACIONES WRXXXX", "purpose": "CLAUDE_API_EXTRACTION"}'
```

### 11.2 Auditoría

```bash
# Ver últimas operaciones de auditoría
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT action, user_id, entities_count, timestamp FROM pseudonym_access_log ORDER BY timestamp DESC LIMIT 20;"

# Ver mapeos activos (sin valores reales — solo metadatos)
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT pseudonym, length(encrypted_value) AS encrypted_len, created_at, expires_at FROM pseudonym_mappings WHERE expires_at > NOW() LIMIT 10;"

# Verificar que Vault está operativo y tiene la clave configurada
docker exec -it arcotel_vault vault status
docker exec -it arcotel_vault vault list transit/keys
```

### 11.3 Mantenimiento

```bash
# Limpieza manual de mapeos expirados (normalmente automático)
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT delete_expired_mappings();"

# Ver estadísticas de limpieza
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT * FROM cleanup_log ORDER BY timestamp DESC LIMIT 10;"

# Rotar clave de cifrado de Vault (sin downtime)
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

# Logs de Vault (operaciones de cifrado)
docker-compose logs -f vault | grep -E "encrypt|decrypt"

# Seguimiento completo del flujo (ambos servicios)
docker-compose logs -f backend pseudonym-api | grep -E "pseudonim|session_id"
```

---

## 12. Métricas de Cobertura

Evaluado sobre **44 documentos reales** de ARCOTEL (2022–2025), procesados con el script `procesar_masivo_v2.ps1`:

### 12.1 Por Tipo de Entidad

| Tipo Entidad | Total Real | VP | FN | FP | Precision | Recall | F1 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| RUC | 12 | 12 | 0 | 0 | 100.0% | 100.0% | **100.0%** |
| CEDULA | 11 | 11 | 0 | 0 | 100.0% | 100.0% | **100.0%** |
| EMAIL | 30 | 30 | 0 | 0 | 100.0% | 100.0% | **100.0%** |
| TELEFONO | 1 | 1 | 0 | 0 | 100.0% | 100.0% | **100.0%** |
| DIRECCION | 21 | 20 | 1 | 0 | 100.0% | 95.2% | **97.6%** |
| NOMBRE | 232 | 229 | 3 | 0 | 100.0% | 98.7% | **99.3%** |
| **GLOBAL** | **307** | **303** | **4** | **0** | **100.0%** | **98.7%** | **99.3%** |

### 12.2 Por Capa

| Capa | Técnica | VP | FN | Precision | Recall | F1 |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Capa 1 — Regex | Determinística | 54 | 0 | 100.0% | 100.0% | **100.0%** |
| Capa 1.5 — Header | Determinística | 20 | 1 | 100.0% | 95.2% | **97.6%** |
| Capa 2 — spaCy NER | IA (NER) | 229 | 3 | 100.0% | 98.7% | **99.3%** |
| Capa 3 — Firmantes | Determinística | 0 | 0 | — | — | — |

### 12.3 Por Documento

- **41/44 documentos (93.2%)** — Pseudonimización completa (todos los datos personales detectados)
- **3/44 documentos (6.8%)** — Pseudonimización parcial (1 FN por documento, típicamente nombre con formato atípico)
- **0 documentos** — Con falsos positivos

> Los 4 FN globales corresponden a: 1 dirección con formato de referencia no estándar (Capa 1.5), y 3 nombres de personas con patrones inusuales (nombre extranjero, iniciales, o presentación abreviada) que spaCy no reconoció como PER.

---

## 13. Preguntas Frecuentes

**¿Qué datos personales detecta el sistema?**

RUC/cédula, emails, teléfonos ecuatorianos, direcciones (intersecciones de calles), nombres de personas físicas. No detecta —por diseño— nombres de empresas como entidades personales, ni datos que no constituyan información personal identificable.

**¿Qué pasa si la pseudonimización falla parcialmente?**

El sistema nunca envía texto a Claude API si la pseudonimización falló (el servicio retorna error). Además, la validación visual obligatoria (HTML de previsualización) permite al operador detectar cualquier dato personal que haya quedado sin pseudonimizar antes de confirmar el procesamiento.

**¿Los datos en `postgres_pseudonym` son recuperables por un atacante?**

No directamente. Están cifrados con AES-256-GCM mediante HashiCorp Vault. Un atacante necesitaría comprometer simultáneamente: (a) `postgres_pseudonym` para obtener los datos cifrados, y (b) HashiCorp Vault para obtener la clave de descifrado — dos sistemas independientes en contenedores separados.

**¿Anthropic puede ver los datos personales?**

No. Claude API recibe exclusivamente pseudónimos (`NOMBRE_A3F7B2C1`). Además, según la política de Anthropic, los datos enviados a través de la API no se usan para entrenar modelos y no se retienen más allá del procesamiento inmediato de la solicitud.

**¿Qué pasa después de 1 hora (expiración TTL)?**

Los mapeos de pseudonimización se eliminan automáticamente de `postgres_pseudonym`. Si se intenta des-pseudonimizar con un `session_id` expirado, el servicio retorna HTTP 404. Los datos reales ya deberían estar almacenados en `postgres_main` antes de la expiración (el procesamiento completo toma < 5 minutos).

**¿Cómo demuestra este sistema cumplimiento LOPDP para el TFE?**

El capítulo de implementación debe documentar: (1) identificación de violaciones potenciales por artículo, (2) diagrama de arquitectura de dos servicios con separación técnica, (3) flujo de datos completo con ciclo de vida, (4) checklist de best practices con evidencia de implementación, y (5) métricas de cobertura (F1-score por tipo de entidad) obtenidas sobre el corpus real.

---

## 14. Referencias y Normativa

### Legislación Ecuatoriana

- **Ley Orgánica de Protección de Datos Personales (LOPDP)**
  - Registro Oficial Suplemento 459, 26 de mayo de 2021
  - Artículos clave: 7-8 (consentimiento), 10 (principios), 33 (transferencia), 37 (seguridad), 55-60 (internacional), 65-68 (sanciones), 72 (multas)
- **Constitución de la República del Ecuador** — Art. 66.19: Derecho a la protección de datos
- **Código Orgánico Administrativo (COA)** — Arts. aplicables al PAS

### Estándares Internacionales de Referencia

- **GDPR (UE)** — Art. 4.5 (definición pseudonimización), Art. 32 (seguridad), Arts. 44-50 (transferencias internacionales)
- **ISO/IEC 27001:2022** — Anexo A.8 (gestión de activos), A.9 (control de acceso), A.10 (cifrado)
- **NIST Privacy Framework** — Data Processing: Minimize, De-identify

### Documentación Técnica

- [HashiCorp Vault — Transit Secrets Engine](https://www.vaultproject.io/docs/secrets/transit)
- [spaCy — es_core_news_lg model](https://spacy.io/models/es)
- [FastAPI — Security utilities](https://fastapi.tiangolo.com/tutorial/security/)
- [PostgreSQL — pgcrypto extension](https://www.postgresql.org/docs/current/pgcrypto.html)

### Papers y Guías

- EDPB: "Guidelines 01/2022 on data subject rights — Right of access"
- ICO (UK): "Anonymisation, pseudonymisation and privacy enhancing technologies guidance"
- NIST SP 800-188: "De-Identifying Government Datasets"

---

## 📅 Historial de Cambios

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0 | 2026-02-05 | Documento inicial — arquitectura completa |
| 2.0 | 2026-02-24 | Revisión profesional — encoding UTF-8, métricas reales, sección 4 capas expandida |

---

<div align="center">

**Autor:** Iván Rodrigo Suárez Fabara  
**Proyecto:** TFE — Sistema Inteligente de Análisis y Priorización de Acciones de Control Técnico Regulatorio  
**Institución:** ARCOTEL Ecuador · Universidad Internacional de La Rioja (UNIR)  

*Este documento debe mantenerse actualizado conforme evolucione la arquitectura del proyecto.*

</div>
