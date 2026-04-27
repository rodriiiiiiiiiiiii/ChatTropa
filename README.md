# 🏕️ ChatTropa | Agente IA de Gestión Scout

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-APIs-4285F4.svg)
![Gemini](https://img.shields.io/badge/Gemini-AI-8E75B2.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)

**ChatTropa** es un agente autónomo de Inteligencia Artificial diseñado para la automatización de la carga administrativa en la Tropa Scout Waconda 194. Integrando Modelos de Lenguaje Grande (LLMs) con la suite de Google Cloud, el sistema lee correos electrónicos en lenguaje natural, extrae intenciones, actualiza bases de datos en la nube y notifica al equipo de monitores en tiempo real.

---

## 🚀 Características Principales

* **Mapeo Dinámico y Prevención de Alucinaciones:** El sistema extrae el email limpio del remitente mediante expresiones regulares (Regex) y lo cruza con una base de datos local. Esto entrega a la IA un contexto estricto del individuo, eliminando las alucinaciones y minimizando el uso de tokens.
* **Procesamiento de Lenguaje Natural (NLP):** Integración REST con la API de **Google Gemini** (`gemini-1.5-flash`) en *JSON Mode* para deducir la asistencia y extraer únicamente comentarios o dudas relevantes, filtrando el ruido conversacional (saludos, firmas).
* **Filtro Anti-Spam Silencioso:** Implementación de una *blacklist* de asuntos y remitentes técnicos (ej. "Almacenamiento lleno", "Delivery Status"). Estos correos se procesan internamente sin generar interrupciones ni alertas en Telegram.
* **Rotación de API Keys y Rate Limiting:** Pool de hasta 8 claves de Gemini con rotación automática ante errores de cuota (HTTP 429). Incluye *sleep delays* para cumplir con los límites de escritura de la API de Google Sheets.
* **Cuarentena y Human-in-the-Loop:** Etiquetado inteligente en Gmail. Los correos procesados exitosamente se marcan como `Procesado_IA`. Si la extracción falla o es ambigua, se envían a `Revision_Manual` para atención humana.
* **Despliegue Serverless (CI/CD):** Ejecución programada en la nube mediante **GitHub Actions** (Cron Jobs). Las credenciales OAuth se inyectan en tiempo de ejecución decodificando variables Base64.
* **Alertas Push Automatizadas:** Integración con la API de Telegram para enviar resúmenes de asistencia y dudas directas al Kraal, optimizando la comunicación logística.

---

## 🏗️ Arquitectura del Sistema

El proyecto sigue una estructura profesional basada en el patrón `src/ layout`, aplicando principios SOLID para separar las responsabilidades del dominio:

* `main.py`: Orquestador principal y punto de entrada de la aplicación.
* `src/config.py`: Definición de variables de entorno, *scopes* y filtros Anti-Spam.
* `src/google_sheets_manager.py`: Abstracción de la capa de persistencia de datos y mapeo.
* `src/ia_motor.py`: Aislamiento del *prompt engineering* y llamadas REST al modelo de lenguaje.
* `src/servicios.py`: Utilidades auxiliares (notificaciones de Telegram, decodificación de mensajes MIME).

### Flujo de Ejecución

1.  **Autenticación OAuth 2.0:** Validación segura de credenciales en la API de Google.
2.  **Extracción de Dimensiones:** Carga del estado actual (Scouts, Eventos y mapa de Correos) desde Sheets.
3.  **Ingesta y Pre-procesamiento:** Lectura de la bandeja de entrada, limpieza de HTML y filtro Anti-Spam.
4.  **Cruce de Identidad Local:** Emparejamiento del email del remitente con los datos de los tutores.
5.  **Inferencia IA:** Petición aislada a Gemini para extraer intenciones estructuradas en JSON.
6.  **Mutación de Estado:** Volcado de datos en Sheets, Webhooks a Telegram y etiquetado final en Gmail.

---

## 🛠️ Stack Tecnológico

* **Lenguaje:** Python 3.11+
* **Integraciones Core:** `google-api-python-client`, `google-auth-oauthlib`, `gspread`
* **Motor IA:** Google Gemini REST API
* **Notificaciones:** API de Telegram (mediante `requests`)
* **Infraestructura:** GitHub Actions (Ubuntu runner)

---

## ⚙️ Requisitos Previos

1.  Python 3.11 o superior instalado.
2.  Un proyecto activo en **Google Cloud Console** (Drive API, Sheets API y Gmail API habilitadas).
3.  Credenciales OAuth 2.0 descargadas como `credentials.json`.
4.  Entre 1 y 8 API Keys generadas desde **Google AI Studio**.
5.  Un bot creado a través de *BotFather* en Telegram y el ID del chat de destino.
6.  Un documento de Google Sheets estructurado con las pestañas "ASISTENCIA" y "CORREOS".

---

## 💻 Instalación (Entorno Local)

**1. Clonar el repositorio e ingresar al directorio:**

```bash
git clone https://github.com/tu-usuario/ChatTropa.git
cd ChatTropa
```

**2. Crear un entorno virtual e instalar dependencias:**

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configurar variables de entorno:**
Crea un archivo `.env` en la raíz del proyecto con la siguiente estructura:

```env
GEMINI_API_KEY_1=tu_api_key_1
GEMINI_API_KEY_2=tu_api_key_2
TELEGRAM_BOT_TOKEN=tu_token_telegram
TELEGRAM_CHAT_ID=tu_id_chat
```

**4. Autenticación Inicial y Ejecución:**
Ejecuta el orquestador. En el primer uso, se abrirá el navegador para autorizar la aplicación y generar el archivo `token.json`.

```bash
python main.py
```

---

## ☁️ Despliegue Automatizado (GitHub Actions)

Para mantener el agente operativo en la nube sin intervención manual:

1.  Convierte tus archivos `credentials.json` y `token.json` a Base64.
2.  En GitHub, navega a **Settings > Secrets and variables > Actions**.
3.  Registra los siguientes *Repository Secrets*: `GOOGLE_CREDENTIALS_B64`, `GOOGLE_TOKEN_B64`, `GEMINI_API_KEY_1` (etc.), `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
4.  El workflow configurado en `.github/workflows/ejecucion_diaria.yml` reconstruirá el entorno y ejecutará el pipeline según la expresión cronográfica definida.

---

## 👨‍💻 Autor

**Rodrigo Mendoza**
Estudiante de Ingeniería de Datos e Inteligencia Artificial (UCM).
