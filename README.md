# 🏕️ ChatTropa | Agente IA de Gestión Scout

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-APIs-4285F4.svg)
![Gemini](https://img.shields.io/badge/Gemini-AI-8E75B2.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)

**ChatTropa** es un agente de Inteligencia Artificial diseñado para automatizar la gestión administrativa y de asistencia de la Tropa Scout Waconda 194. Utilizando Modelos de Lenguaje Grande (LLMs) y la suite de APIs de Google, el sistema procesa correos electrónicos en lenguaje natural, extrae intenciones y entidades, actualiza bases de datos en la nube y gestiona notificaciones en tiempo real.

## 🚀 Características Principales

* **Procesamiento de Lenguaje Natural (NLP):** Integración mediante peticiones HTTP REST a la API de **Google Gemini** (`gemini-flash-lite`) para clasificar correos en 4 casos de uso (Solo Asistencia, Asistencia + Pregunta, Solo Pregunta, Irrelevante).
* **RAG Básico (Inyección de Contexto):** Descarga en tiempo real los nombres de los scouts y los eventos planificados desde Google Sheets y los inyecta en el *prompt* del modelo. Esto fuerza coincidencias exactas y elimina el riesgo de alucinaciones por parte de la IA.
* **Control de Concurrencia (Race Conditions):** Sistema de etiquetado dinámico en Gmail (`Procesado_IA`). Evita que el agente lea correos duplicados o procese hilos ya leídos por operadores humanos, asegurando la integridad del estado.
* **Filtro de Ruido Saliente:** La consulta a la API de Gmail (`in:inbox -label:Procesado_IA newer_than:15d -from:me`) ignora automáticamente las respuestas enviadas por el propio equipo de gestión.
* **Ordenación Cronológica de Estados:** Los correos se leen en reverso cronológico (del más antiguo al más nuevo). Si un usuario cambia de opinión en correos sucesivos (ej. de "Sí asiste" a "No asiste"), la base de datos reflejará siempre el estado más reciente.
* **Tolerancia a Fallos y Rate Limiting:** Implementación de un patrón de *Retry/Backoff* (reintentos automáticos) para sobrevivir a caídas del servidor (Error 503) o superación de cuotas (Error 429) de la API gratuita de Google.
* **Alertas Push Automatizadas:** Conexión con la API de Telegram para derivar únicamente las dudas administrativas no triviales al Kraal (equipo de monitores), filtrando el ruido de las confirmaciones simples.



## 🏗️ Arquitectura del Sistema

El flujo de ejecución del script sigue un *pipeline* secuencial y robusto:

1. **Autenticación OAuth 2.0:** Validación segura de credenciales para acceder a Google Workspace (Gmail, Drive, Sheets).
2. **Extracción de Dominio (Fetch):** Recuperación de las dimensiones válidas (Scouts y Eventos) desde la hoja de cálculo.
3. **Ingesta de Datos:** Búsqueda en Gmail de correos no procesados en los últimos 15 días. Extracción y decodificación en Base64 de las cabeceras (Asunto) y el cuerpo del mensaje.
4. **Inferencia (AI Agent):** Petición directa a la API de Gemini instruyendo una respuesta estricta en formato JSON.
5. **Enrutamiento (Lógica de Negocio):**
   * Actualización bidimensional (Fila=Scout, Columna=Evento) en Google Sheets vía `gspread`.
   * Disparo de *webhooks* a Telegram.
6. **Mutación de Estado:** Etiquetado del correo original en Gmail como completado.

## 🛠️ Stack Tecnológico

* **Lenguaje:** Python 3.11+
* **Integraciones Core:** `google-api-python-client`, `google-auth-oauthlib`, `gspread`.
* **Motor IA:** Google Gemini REST API.
* **Notificaciones:** API de Telegram (mediante `requests`).
* **Seguridad:** Gestión de secretos locales con `python-dotenv`.

## ⚙️ Requisitos Previos

1. Python 3.11 o superior instalado en el sistema.
2. Un proyecto en **Google Cloud Console** con las siguientes APIs habilitadas:
   * Google Drive API
   * Google Sheets API
   * Gmail API
3. Un archivo `credentials.json` generado mediante credenciales OAuth 2.0 (Desktop App) descargado en la raíz del proyecto.
4. Una API Key de **Google AI Studio** (Gemini).
5. Un bot de Telegram creado a través de *BotFather* y el ID del chat de destino.

## 🚀 Instalación y Despliegue

**1. Clonar el repositorio:**
```bash
git clone [https://github.com/rodriiiiiiiiiii/ChatTropa.git](https://github.com/rodriiiiiiiiiii/ChatTropa.git)
cd ChatTropa
```

**2. Instalar dependencias:**
Se recomienda el uso de un entorno virtual (venv).

```bash
pip install -r requirements.txt

```

**3. Configurar variables de entorno:**
Crea un archivo `.env` en el directorio raíz del proyecto con la siguiente estructura (no utilices comillas):

```env
GEMINI_API_KEY=tu_api_key_de_gemini
TELEGRAM_BOT_TOKEN=tu_token_del_bot_de_telegram
TELEGRAM_CHAT_ID=tu_id_de_chat_o_grupo

```

**4. Ejecución:**

```bash
python asistente.py

```


## 👨‍💻 Autor

**Rodrigo Mendoza**
Estudiante de Ingeniería de Datos e Inteligencia Artificial.
