# 🏕️ ChatTropa | Agente IA de Gestión Scout

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-APIs-4285F4.svg)
![Gemini](https://img.shields.io/badge/Gemini-AI-8E75B2.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)

**ChatTropa** es un agente de Inteligencia Artificial diseñado para automatizar la gestión administrativa y de asistencia de la Tropa Scout Waconda 194. Utilizando Modelos de Lenguaje Grande (LLMs) y la suite de APIs de Google, el sistema procesa correos electrónicos en lenguaje natural, extrae intenciones y entidades, actualiza bases de datos en la nube y gestiona notificaciones en tiempo real.

## 🚀 Características Principales

  * **Pre-filtrado Algorítmico y Mapeo Dinámico (Zero-Hallucination):** Antes de invocar a la IA, el sistema cruza el remitente del correo con una base de datos de correos de padres (`CORREOS`). Esto resuelve colisiones de nombres idénticos, reduce drásticamente el uso de tokens y elimina las alucinaciones de la IA al entregarle un contexto cerrado de un solo individuo.
  * **Procesamiento de Lenguaje Natural (NLP):** Integración mediante peticiones HTTP REST a la API de **Google Gemini** (`gemini-flash-lite`) para extraer la asistencia (Sí/No/Null) y aislar únicamente dudas reales o comentarios relevantes, ignorando el ruido habitual (saludos, firmas).
  * **Limpieza de Datos con Regex:** Expresiones regulares en Python que cortan automáticamente historiales de respuestas de Gmail, Outlook y firmas de dispositivos móviles antes de enviar el prompt al LLM.
  * **Rotación de API Keys y Backoff (Rate Limiting):** Implementación de un pool de hasta 8 API Keys de Gemini con rotación automática y *Backoff* (reintentos espaciados) para absorber bloqueos temporales (503) y agotar cuotas (429) de la capa gratuita, asegurando alta disponibilidad.
  * **Control de Concurrencia y Cuarentena:** Sistema de etiquetado dinámico en Gmail (`Procesado_IA`). Si la IA detecta un correo ambiguo o irrelevante, no lo descarta permanentemente, sino que lo envía a cuarentena (`Revision_Manual`) para aplicar un patrón *Human-in-the-Loop*.
  * **Despliegue Serverless (CI/CD):** Ejecución 100% automatizada en la nube mediante **GitHub Actions** (Cron Jobs), con gestión de credenciales OAuth de Google inyectadas en tiempo de ejecución mediante decodificación Base64 en un entorno *headless*.
  * **Alertas Push Automatizadas:** Conexión con la API de Telegram para derivar únicamente las dudas administrativas al Kraal (equipo de monitores), con un buffer anti-spam para evitar alertas duplicadas.

## 🏗️ Arquitectura del Sistema (Modular)

El proyecto sigue una arquitectura separada en 4 módulos principales para facilitar su escalabilidad:

1.  `config.py`: Ingestión de variables de entorno y definición de *scopes*.
2.  `servicios.py`: Lógica de interacción con APIs externas (Telegram) y limpieza pura de texto (Regex, Base64 Decode).
3.  `ia_motor.py`: Aislamiento del *prompt engineering*, apagado de filtros de seguridad restrictivos y gestión de peticiones REST al LLM con rotación de llaves.
4.  `asistente.py`: *Core* del negocio, orquestación de Google Sheets/Gmail y enrutamiento lógico.

**Flujo de ejecución:**

1.  **Autenticación OAuth 2.0:** Validación segura de credenciales.
2.  **Extracción de Dimensiones:** Recuperación de Scouts, Eventos y mapa de Correos desde Google Sheets.
3.  **Ingesta y Limpieza:** Búsqueda en Gmail, decodificación y Regex.
4.  **Cruce Local:** Emparejamiento del `remitente` del email con la hoja de Sheets.
5.  **Inferencia (IA):** Petición aislada (1 correo = 1 request) a Gemini en `JSON Mode`.
6.  **Mutación de Estado:** Actualización en Sheets, Webhooks a Telegram y etiquetado en Gmail.

## 🛠️ Stack Tecnológico

  * **Lenguaje:** Python 3.11+
  * **Integraciones Core:** `google-api-python-client`, `google-auth-oauthlib`, `gspread`.
  * **Motor IA:** Google Gemini REST API.
  * **Notificaciones:** API de Telegram (mediante `requests`).
  * **Infraestructura:** GitHub Actions (Ubuntu runner).

## ⚙️ Requisitos Previos

1.  Python 3.11 o superior instalado.
2.  Un proyecto en **Google Cloud Console** (En modo "Producción") con las APIs habilitadas: Drive API, Sheets API, Gmail API.
3.  Un archivo `credentials.json` generado mediante credenciales OAuth 2.0 (Desktop App).
4.  Entre 1 y 8 API Keys de **Google AI Studio** (Gemini).
5.  Un bot de Telegram creado a través de *BotFather* y el ID del chat de destino.
6.  Un Google Sheets con dos pestañas:
      * `ASISTENCIA`: Columna A (Nombres), Fila 2 (Eventos).
      * `CORREOS`: Columna A (Nombre exacto), Columna B en adelante (Correos de los tutores).

## 🚀 Instalación (Entorno Local)

**1. Clonar el repositorio:**

```bash
git clone https://github.com/rodriiiiiiiiiii/ChatTropa.git
cd ChatTropa
```

**2. Instalar dependencias:**

```bash
pip install -r requirements.txt
```

**3. Configurar variables de entorno:**
Crea un archivo `.env` en el directorio raíz del proyecto:

```env
GEMINI_API_KEY_1=tu_api_key_1
GEMINI_API_KEY_2=tu_api_key_2
# ... hasta GEMINI_API_KEY_8
TELEGRAM_BOT_TOKEN=tu_token_del_bot_de_telegram
TELEGRAM_CHAT_ID=tu_id_de_chat_o_grupo
```

**4. Autenticación Inicial y Ejecución:**
Al ejecutar por primera vez, se abrirá el navegador para autorizar la app y generar el archivo `token.json`.

```bash
python asistente.py
```

## ☁️ Despliegue en GitHub Actions

Para que el bot se ejecute de manera autónoma en la nube todos los días:

1.  Convierte tus archivos `credentials.json` y `token.json` a Base64.
2.  En tu repositorio de GitHub, ve a **Settings \> Secrets and variables \> Actions**.
3.  Añade los siguientes *Repository Secrets*:
      * `GOOGLE_CREDENTIALS_B64`: Contenido de tu credentials.json en Base64.
      * `GOOGLE_TOKEN_B64`: Contenido de tu token.json en Base64.
      * `GEMINI_API_KEY_1` al `8`: Tus claves de Gemini.
      * `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
4.  El workflow `.github/workflows/ejecucion_diaria.yaml` reconstruirá los tokens en el servidor virtual y ejecutará el pipeline automáticamente según el *cron* configurado.

## 👨‍💻 Autor

**Rodrigo Mendoza**
Estudiante de Ingeniería de Datos e Inteligencia Artificial.