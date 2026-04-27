# 🏕️ ChatTropa | Agente IA de Gestión Scout

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-APIs-4285F4.svg)
![Gemini](https://img.shields.io/badge/Gemini-AI-8E75B2.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)
![Pytest](https://img.shields.io/badge/Testing-Pytest-FCC624.svg)

**ChatTropa** es un agente autónomo de Inteligencia Artificial diseñado para la automatización de la carga administrativa en la Tropa Scout Waconda 194. Integrando Modelos de Lenguaje Grande (LLMs) con la suite de Google Cloud, el sistema lee correos electrónicos en lenguaje natural, extrae intenciones, actualiza bases de datos en la nube y notifica al equipo de monitores en tiempo real.

---

## 🚀 Características Principales

* **Mapeo Dinámico y Prevención de Alucinaciones:** El sistema extrae el email limpio del remitente mediante expresiones regulares (Regex) y lo cruza con una base de datos local. Esto entrega a la IA un contexto estricto del individuo, eliminando las alucinaciones y minimizando el uso de tokens.
* **Structured Outputs (IA Avanzada):** En lugar de depender de *prompt engineering*, el sistema inyecta un *JSON Schema* estricto directamente en la API de **Google Gemini** (`gemini-1.5-flash`). Esto fuerza matemáticamente a la IA a devolver estructuras de datos exactas, respetando *Enums* ("Sí" o "No") y tipos de datos nativos.
* **Idempotencia y Tolerancia a Fallos:** Implementación de una caché de estado en Google Sheets (`LOG_PROCESADOS`). El sistema registra el `message_id` de cada correo procesado con éxito, garantizando que una caída de red o reinicio del servidor jamás duplique escrituras ni envíe alertas repetidas a Telegram.
* **Filtro Anti-Spam Silencioso:** Implementación de una *blacklist* de asuntos y remitentes técnicos (ej. "Almacenamiento lleno", "Delivery Status"). Estos correos se procesan internamente sin generar interrupciones ni alertas.
* **Rotación de API Keys y Rate Limiting:** Pool de hasta 8 claves de Gemini con rotación automática ante errores de cuota (HTTP 429). Incluye *sleep delays* para cumplir con los límites de escritura de la API de Google Sheets.
* **Despliegue Serverless con CI/CD y Testing:** Ejecución programada en la nube mediante **GitHub Actions**. Antes de cada ejecución en producción, el pipeline lanza una batería de **Tests Unitarios (`pytest`)** para prevenir regresiones. Las credenciales OAuth se inyectan en tiempo de ejecución decodificando variables Base64.
* **Calidad de Código Empresarial:** Arquitectura modular (`src/` layout), tipado estático (*Type Hinting*), gestión de eventos (*Logging* nativo) y formateo automatizado mediante **Ruff**.

---

## 🏗️ Arquitectura del Sistema

El proyecto sigue una estructura profesional aplicando principios SOLID para separar las responsabilidades del dominio:

* `main.py`: Orquestador principal y punto de entrada de la aplicación.
* `src/config.py`: Definición de variables de entorno, *scopes* y filtros Anti-Spam.
* `src/google_sheets_manager.py`: Abstracción de la capa de persistencia de datos, mapeo relacional y control de idempotencia.
* `src/ia_motor.py`: Generación de esquemas de datos y llamadas REST al modelo de lenguaje.
* `src/servicios.py`: Utilidades auxiliares (notificaciones de Telegram, decodificación MIME, limpieza de firmas con Regex).
* `tests/`: Batería de pruebas unitarias para asegurar la fiabilidad del pre-procesado.

### Flujo de Ejecución

1.  **Autenticación OAuth 2.0:** Validación segura de credenciales en la API de Google.
2.  **Extracción de Dimensiones:** Carga del estado actual (Scouts, Eventos, mapa de Correos e Historial de Procesados) desde Sheets.
3.  **Ingesta y Control de Estado:** Lectura de la bandeja de entrada. Se descartan instantáneamente los correos cuyo ID ya exista en la caché (*Idempotencia*).
4.  **Cruce de Identidad Local:** Emparejamiento del email del remitente con los datos de los tutores.
5.  **Inferencia IA:** Petición aislada a Gemini bajo un *JSON Schema* para extraer intenciones estructuradas.
6.  **Mutación de Estado:** Volcado de datos en Sheets, registro del ID en el log de completados, Webhooks a Telegram y etiquetado final en Gmail.

---

## 🛠️ Stack Tecnológico

* **Lenguaje:** Python 3.11+
* **Integraciones Core:** `google-api-python-client`, `google-auth-oauthlib`, `gspread`
* **Motor IA:** Google Gemini REST API (Structured Outputs)
* **Calidad y Testing:** `pytest`, `ruff`, `logging`, `typing`
* **Notificaciones:** API de Telegram
* **Infraestructura:** GitHub Actions (Ubuntu runner)

---

## ⚙️ Requisitos Previos

1.  Python 3.11 o superior instalado.
2.  Un proyecto activo en **Google Cloud Console** (Drive API, Sheets API y Gmail API habilitadas).
3.  Credenciales OAuth 2.0 descargadas como `credentials.json`.
4.  Entre 1 y 8 API Keys generadas desde **Google AI Studio**.
5.  Un bot creado a través de *BotFather* en Telegram y el ID del chat de destino.
6.  Un documento de Google Sheets estructurado con tres pestañas:
    * `ASISTENCIA`: Columna A (Nombres), Fila 2 (Eventos).
    * `CORREOS`: Columna A (Nombre exacto), Columna B en adelante (Correos de los tutores).
    * `LOG_PROCESADOS`: Historial de `message_id` para control de idempotencia.

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

**4. Ejecutar los Tests de Seguridad:**
Asegúrate de que la lógica central funciona correctamente antes de arrancar.
```bash
pytest -v
```

**5. Autenticación Inicial y Ejecución:**
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
4.  El workflow configurado en `.github/workflows/ejecucion_diaria.yml` validará los tests unitarios, reconstruirá el entorno y ejecutará el pipeline según la expresión cronográfica definida.

---

## 👨‍💻 Autor

**Rodrigo Mendoza**
Estudiante de Ingeniería de Datos e Inteligencia Artificial (UCM).
