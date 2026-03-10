# 🛡️ Email Phishing Detection Agent

> Agente de IA que monitoriza un buzón de correo, analiza los emails reenviados y detecta intentos de phishing en tiempo real.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![MariaDB](https://img.shields.io/badge/MariaDB-SQLAlchemy-003545?logo=mariadb&logoColor=white)
![Keycloak](https://img.shields.io/badge/Auth-Keycloak-4D8ECF?logo=keycloak&logoColor=white)

---

## 📋 Descripción

Este proyecto implementa un **agente autónomo de detección de phishing** que:

1. **Monitoriza** un buzón IMAP (INBOX + Spam) buscando correos no leídos
2. **Valida** que el remitente está en la lista de dominios/emails autorizados
3. **Analiza** el contenido del email con IA (LLaMA 3.3 70B vía Groq o OpenRouter)
4. **Responde automáticamente** al remitente con el veredicto y la explicación
5. **Registra** todo en base de datos con historial paginado accesible desde un dashboard web protegido por Keycloak

El flujo de uso típico es: el usuario **reenvía** un email sospechoso a la dirección del agente, y recibe de vuelta un informe automático indicando si es phishing o seguro.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                         │
│                                                             │
│  ┌──────────────────────┐    ┌──────────────────────────┐  │
│  │   Frontend (Nginx)   │    │   Backend (FastAPI)       │  │
│  │   React + Vite       │───▶│   Python 3.11             │  │
│  │   Port: 8080         │    │   Port: 8000              │  │
│  └──────────────────────┘    └────────────┬─────────────┘  │
│                                           │                 │
│                              ┌────────────▼─────────────┐  │
│                              │   MariaDB (external)      │  │
│                              │   SQLAlchemy ORM          │  │
│                              └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                              │
         │                              │
   ┌─────▼──────┐              ┌────────▼───────┐
   │  Keycloak  │              │  IMAP Server   │
   │  SSO Auth  │              │  (IONOS/Gmail) │
   └────────────┘              └────────────────┘
                                        │
                               ┌────────▼───────┐
                               │  Groq / OpenRouter│
                               │  LLaMA 3.3 70B  │
                               └─────────────────┘
```

### Componentes principales

| Componente | Tecnología | Descripción |
|---|---|---|
| **Backend** | FastAPI + Python 3.11 | API REST, agente de polling IMAP, motor IA |
| **Frontend** | React 18 + Vite + TailwindCSS | Dashboard SPA |
| **Base de datos** | MariaDB + SQLAlchemy | Persistencia de logs y configuración |
| **Autenticación** | Keycloak (OIDC/JWT) | SSO para el dashboard |
| **IA** | Groq API (LLaMA 3.3 70B) | Análisis de phishing con fallback a OpenRouter |
| **Email** | IMAP (imaplib) + SMTP | Lectura y respuesta de correos |
| **Scheduler** | APScheduler | Polling periódico (configurable, por defecto 5 min) |

---

## ✨ Características

- 🔍 **Detección IA** — Análisis con LLaMA 3.3 70B, respuesta en JSON estructurado con nivel de confianza
- 🔄 **Failover automático** — Si Groq falla, el sistema recurre automáticamente a OpenRouter
- 📁 **Multi-carpeta** — Monitoriza INBOX y Spam simultáneamente
- 🔐 **Autenticación SSO** — Login con Keycloak, tokens JWT validados en el backend
- 📊 **Dashboard paginado** — Historial de análisis con filtros, paginación y expansión de explicación IA
- 🗑️ **Reprocesado** — Borrar una entrada del log marca el email como no leído en IMAP para reprocesarlo
- 📤 **Copia en Enviados** — Las respuestas enviadas se guardan en la carpeta "Enviados" del IMAP
- ⚡ **Trigger manual** — Botón "Check Emails Now" en el dashboard para no esperar al ciclo periódico
- 👥 **Lista de remitentes** — ACL de dominios/emails autorizados gestionable desde la UI
- 🐳 **100% Dockerizado** — Un `docker compose up` levanta todo el sistema

---

## 🚀 Instalación y puesta en marcha

### Requisitos previos

- [Docker](https://www.docker.com/get-started) y Docker Compose v2
- Una instancia de **Keycloak** con un realm y cliente configurado
- Una instancia de **MariaDB** accesible (puede ser externa)
- Cuenta en **IONOS** u otro proveedor IMAP/SMTP (o Gmail con App Password)
- Clave API de **Groq** (gratuita en [console.groq.com](https://console.groq.com)) y/o **OpenRouter**

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/email-phishing-agent.git
cd email-phishing-agent
```

### 2. Configurar las variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus valores reales (ver sección [Variables de entorno](#variables-de-entorno) más abajo).

> ⚠️ **El archivo `.env` nunca debe subirse al repositorio.** Está incluido en `.gitignore`.

### 3. Configurar Keycloak

En tu realm de Keycloak:

1. Crea un cliente con ID `email-agent-ui` (o el que pongas en `KEYCLOAK_CLIENT_ID`)
2. Tipo de acceso: `public`
3. Redirect URIs: `http://tu-dominio:8080/*`
4. Web Origins: `http://tu-dominio:8080`

### 4. Levantar los servicios

```bash
docker compose up -d --build
```

El sistema arranca en:

- **Frontend:** `http://localhost:8080`
- **Backend API:** `http://localhost:8000`
- **API Docs:** `http://localhost:8000/docs`

### 5. Configurar remitentes autorizados

Una vez logado en el dashboard, añade los **dominios** o **emails** desde los que se aceptarán reenvíos (panel "Allowed Senders").

Ejemplo: añadir el dominio `miempresa.com` para que cualquier usuario de esa empresa pueda reenviar emails al agente.

---

## 📧 Uso del agente

El agente funciona por **reenvío**:

1. El usuario recibe un email sospechoso
2. Lo **reenvía** a la dirección del buzón del agente (configurada en `IMAP_USER`)
3. El agente lo detecta automáticamente (cada 5 minutos, o pulsando "Check Emails Now")
4. La IA analiza el contenido original
5. El agente envía una respuesta automática al usuario con el veredicto

### Veredictos posibles

| Veredicto | Significado |
|---|---|
| 🚨 **Phishing** | El email es fraudulento con alta probabilidad |
| ✅ **Clean** | El email parece legítimo |
| confidence: `high/medium/low` | Nivel de confianza del modelo |

---

## 🗂️ Estructura del proyecto

```
email-phishing-agent/
├── backend/
│   ├── main.py              # Entrypoint FastAPI, endpoint /check-emails
│   ├── agent_loop.py        # Scheduler APScheduler + lógica de procesado
│   ├── email_client.py      # Cliente IMAP (imaplib, UID-based)
│   ├── ai_engine.py         # Motor de análisis IA (Groq + OpenRouter fallback)
│   ├── responder.py         # Envío de respuestas SMTP + guardado en Enviados
│   ├── auth.py              # Validación JWT con python-keycloak
│   ├── database.py          # Modelos SQLAlchemy + init_db
│   ├── schemas.py           # Schemas Pydantic para la API
│   ├── routers/
│   │   ├── logs.py          # GET /logs/emails (paginado), DELETE /logs/emails/{id}
│   │   └── senders.py       # CRUD /senders/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   └── Dashboard.tsx          # Vista principal con navbar y botón check
│   │   ├── components/
│   │   │   ├── EmailLogs.tsx          # Tabla paginada + borrado + expansión IA
│   │   │   └── AllowedSenders.tsx     # Gestión de ACL de remitentes
│   │   ├── providers/
│   │   │   └── AuthProvider.tsx       # ReactKeycloakProvider
│   │   ├── api.ts                     # fetchWithAuth (refresco automático de token)
│   │   └── keycloak.ts                # Configuración Keycloak-js
│   ├── public/
│   │   └── silent-check-sso.html      # Página para SSO silencioso (evita login loop en F5)
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Variables de entorno

Todas las variables se definen en el archivo `.env` (copia desde `.env.example`).

| Variable | Descripción | Ejemplo |
|---|---|---|
| `IMAP_HOST` | Servidor IMAP | `imap.ionos.es` |
| `IMAP_PORT` | Puerto IMAP SSL | `993` |
| `IMAP_USER` | Email del buzón del agente | `agente@midominio.com` |
| `IMAP_PASSWORD` | Contraseña del buzón | `tu_contraseña` |
| `SMTP_HOST` | Servidor SMTP | `smtp.ionos.es` |
| `SMTP_PORT` | Puerto SMTP (`465` SSL, `587` STARTTLS) | `465` |
| `SMTP_USER` | Usuario SMTP (normalmente igual a IMAP) | `agente@midominio.com` |
| `SMTP_PASSWORD` | Contraseña SMTP | `tu_contraseña` |
| `SMTP_FROM_ADDRESS` | Dirección del remitente en respuestas | `agente@midominio.com` |
| `DB_HOST` | Host de MariaDB | `mariadb` |
| `DB_PORT` | Puerto MariaDB | `3306` |
| `DB_USER` | Usuario de la BD | `email_agent` |
| `DB_PASSWORD` | Contraseña de la BD | `secreto_bd` |
| `DB_NAME` | Nombre de la base de datos | `email_phishing_agent` |
| `GROQ_API_KEY` | API Key de Groq (principal) | `gsk_...` |
| `OPENROUTER_API_KEY` | API Key de OpenRouter (fallback) | `sk-or-v1-...` |
| `CHECK_INTERVAL_MINUTES` | Intervalo de polling IMAP | `5` |
| `AI_MODEL_GROQ` | Modelo a usar en Groq | `llama-3.3-70b-versatile` |
| `AI_MODEL_OPENROUTER` | Modelo a usar en OpenRouter | `meta-llama/llama-3.3-70b-instruct` |
| `KEYCLOAK_SERVER_URL` | URL base de Keycloak | `https://auth.midominio.com/` |
| `KEYCLOAK_REALM` | Nombre del realm | `MiRealm` |
| `KEYCLOAK_CLIENT_ID` | ID del cliente Keycloak | `email-agent-ui` |

---

## 🔌 API Endpoints

La documentación interactiva completa está disponible en `http://localhost:8000/docs`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | No | Health check |
| `POST` | `/api/check-emails` | ✅ JWT | Lanza un ciclo de comprobación inmediato |
| `GET` | `/api/logs/emails` | ✅ JWT | Historial paginado (`?page=1&page_size=20`) |
| `DELETE` | `/api/logs/emails/{id}` | ✅ JWT | Borra log y restaura UNSEEN en IMAP |
| `GET` | `/api/logs/stats` | ✅ JWT | Estadísticas globales de uso |
| `GET` | `/api/senders/` | ✅ JWT | Lista remitentes autorizados |
| `POST` | `/api/senders/` | ✅ JWT | Añade remitente/dominio autorizado |
| `DELETE` | `/api/senders/{id}` | ✅ JWT | Elimina remitente autorizado |

---

## 🔒 Seguridad

- **JWT validation** — Todos los endpoints de la API validan el token Bearer emitido por Keycloak
- **Allowlist de remitentes** — Solo se procesan emails provenientes de dominios/emails explícitamente autorizados
- **Variables de entorno** — Ningún secreto está en el código; todo se lee del `.env`
- **`.gitignore` exhaustivo** — `.env`, logs, scripts de debug y artefactos de build excluidos del VCS

---

## 🧩 Proveedores de IA configurables

El sistema implementa un patrón de **failover automático**:

```
Email recibido → Groq (LLaMA 3.3 70B)
                    └─ ¿Falla? → OpenRouter (LLaMA 3.3 70B)
                                      └─ ¿Falla? → Error en log, email ignorado
```

Puedes cambiar los modelos editando `AI_MODEL_GROQ` y `AI_MODEL_OPENROUTER` en el `.env`.

---

## 🛠️ Desarrollo local (sin Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
# Crea un .env.local con las variables VITE_*
echo "VITE_KEYCLOAK_URL=https://tu-keycloak.com/" > .env.local
echo "VITE_KEYCLOAK_REALM=TuRealm" >> .env.local
echo "VITE_KEYCLOAK_CLIENT_ID=email-agent-ui" >> .env.local
npm run dev
```

---

## 📝 Licencia

MIT License — libre para uso personal y comercial.

---

## 🤝 Contribuciones

Las pull requests son bienvenidas. Para cambios importantes, abre primero un issue para discutir lo que te gustaría cambiar.
