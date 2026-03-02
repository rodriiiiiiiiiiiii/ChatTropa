import os
import json
import base64
import time
import requests
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# --- 1. CARGA DE CONFIGURACION ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets', 
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify'
]

if not GEMINI_API_KEY:
    print("[ERROR] No se ha encontrado la GEMINI_API_KEY en el archivo .env")
    exit(1)

# --- 2. FUNCIONES DE SERVICIO ---

def avisar_telegram(mensaje):
    """Envia notificaciones al grupo de Kraal."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    datos = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=datos)
    except Exception as e:
        print(f"[ERROR] Fallo al contactar con la API de Telegram: {e}")

def decodificar_correo(mensaje_gmail):
    """Extrae el asunto y el cuerpo decodificado del correo."""
    try:
        payload = mensaje_gmail.get('payload', {})
        
        # 1. Extraer el Asunto
        cabeceras = payload.get('headers', [])
        asunto = "Sin Asunto"
        for cabecera in cabeceras:
            if cabecera['name'].lower() == 'subject':
                asunto = cabecera['value']
                break
                
        # 2. Extraer el cuerpo
        partes = payload.get('parts', [])
        cuerpo = ""
        if not partes:
            cuerpo = payload.get('body', {}).get('data', '')
        else:
            for parte in partes:
                if parte['mimeType'] == 'text/plain':
                    cuerpo = parte['body'].get('data', '')
                    break
        
        texto_limpio = ""
        if cuerpo:
            texto_limpio = base64.urlsafe_b64decode(cuerpo).decode('utf-8')
            
        return f"ASUNTO: {asunto}\nCUERPO:\n{texto_limpio}"
    except Exception as e:
        print(f"[ERROR] Fallo al decodificar el correo: {e}")
    return ""

def analizar_con_ia(texto_correo, nombres_validos, eventos_validos):
    """Llamada DIRECTA a la API REST de Gemini con sistema de REINTENTOS"""
    prompt = f"""
    Eres el secretario scout de la Tropa Waconda 194. Lee este correo (Asunto y Cuerpo) y extrae la información en formato JSON estricto.
    
    Clasifica CADA NIÑO mencionado en UNO de estos 4 tipos ("tipo"):
    - "SOLO_ASISTENCIA": Confirman asistencia o ausencia, sin dudas.
    - "ASISTENCIA_Y_PREGUNTA": Confirman asistencia/ausencia Y ADEMÁS hacen una pregunta a los jefes.
    - "SOLO_PREGUNTA": Solo hacen una pregunta, no mencionan asistencia.
    - "IRRELEVANTE": Publicidad, spam, o correos que no encajan.

    REGLAS Y CONSTRICCIONES ESTRICTAS:
    1. MULTIPLES NIÑOS (HERMANOS): Si el correo habla de varios niños, extrae un registro SEPARADO para cada uno. Devuelve SIEMPRE una LISTA de objetos JSON.
    2. NOMBRES: Para "nombre", DEBES elegir exactamente uno de esta lista: {nombres_validos}. Infiérelo si es único. Si no, pon null.
    3. EVENTOS: Para "evento", DEBES elegir exactamente uno de esta lista: {eventos_validos}. Presta MUCHA ATENCIÓN al "ASUNTO".
    4. ASISTENCIA: "Sí" o "No". IMPORTANTE: Expresiones como "el niño irá", "sí irá", "confirma", o "contad con él/ella" significan estrictamente "Sí". Si no se menciona asistencia, pon null.

    Ejemplo de formato esperado (Devuelve ÚNICAMENTE un ARRAY JSON válido, sin Markdown):
    [
      {{"tipo": "...", "nombre": "...", "evento": "...", "asistencia": "Sí", "pregunta": "..."}},
      {{"tipo": "...", "nombre": "...", "evento": "...", "asistencia": "No", "pregunta": null}}
    ]

    Correo a analizar:
    "{texto_correo}"
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }
    
    max_reintentos = 3
    for intento in range(max_reintentos):
        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                datos = response.json()
                texto_respuesta = datos['candidates'][0]['content']['parts'][0]['text']
                texto_respuesta = texto_respuesta.replace('```json', '').replace('```', '').strip()
                return json.loads(texto_respuesta)
                
            elif response.status_code in [503, 429]:
                print(f"[AVISO] Servidor saturado (Error {response.status_code}). Esperando 20s... (Intento {intento+1}/{max_reintentos})")
                time.sleep(20)
                continue
                
            else:
                print(f"[ERROR API GEMINI] Código {response.status_code}: {response.text}")
                return [{"tipo": "IRRELEVANTE", "error": f"HTTP {response.status_code}"}]
                
        except Exception as e:
            print(f"[ERROR] Fallo en la conexión directa con Gemini: {e}")
            return [{"tipo": "IRRELEVANTE", "error": str(e)}]

    print("[ERROR] Múltiples reintentos fallidos. Saltando correo.")
    return [{"tipo": "IRRELEVANTE", "error": "Servidor no disponible tras 3 intentos"}]

def apuntar_en_excel(hoja, nombre_scout, evento, valor_asistencia):
    """Actualiza la celda en Sheets buscando coordenadas exactas."""
    if not nombre_scout or not evento:
        print("[AVISO] Datos incompletos (Nombre o Evento es nulo). No se puede registrar.")
        return False
        
    try:
        celda_nombre = hoja.find(nombre_scout, in_column=1)
        celda_evento = hoja.find(evento, in_row=2)
        
        if celda_nombre and celda_evento:
            hoja.update_cell(celda_nombre.row, celda_evento.col, valor_asistencia)
            return True
        else:
            print(f"[ERROR] Registros no encontrados: Nombre='{nombre_scout}', Evento='{evento}'")
            return False
    except Exception as e:
        print(f"[ERROR] Excepción al modificar el Sheets: {e}")
        return False

def obtener_id_etiqueta(servicio_gmail, nombre_etiqueta="Procesado_IA"):
    """Busca la etiqueta en Gmail. Si no existe, la crea automáticamente."""
    resultados = servicio_gmail.users().labels().list(userId='me').execute()
    etiquetas = resultados.get('labels', [])
    
    for etiqueta in etiquetas:
        if etiqueta['name'].lower() == nombre_etiqueta.lower():
            return etiqueta['id']
            
    print(f"[SISTEMA] Creando nueva etiqueta en Gmail: {nombre_etiqueta}")
    nueva_etiqueta = {
        'name': nombre_etiqueta,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    etiqueta_creada = servicio_gmail.users().labels().create(userId='me', body=nueva_etiqueta).execute()
    return etiqueta_creada['id']

def marcar_como_procesado(servicio_gmail, id_mensaje, id_etiqueta):
    """Le añade la etiqueta Procesado_IA al correo"""
    servicio_gmail.users().messages().modify(
        userId='me', 
        id=id_mensaje, 
        body={'addLabelIds': [id_etiqueta]}
    ).execute()

# --- 3. ORQUESTADOR PRINCIPAL ---

def ejecutar_asistente():
    print("[SISTEMA] Iniciando Agente de Asistencia Tropa 194...")
    
    # 3.1 Inicializacion de APIs Google
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    gc = gspread.authorize(creds)
    hoja = gc.open("Asistencia").worksheet("ASISTENCIA")
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    # 3.2 Cargar contexto de validación
    print("[SISTEMA] Descargando estructuras de datos de Google Sheets...")
    nombres_validos = [n for n in hoja.col_values(1)[2:] if n.strip()] 
    eventos_validos = [e for e in hoja.row_values(2)[1:] if e.strip()]

    id_etiqueta_bot = obtener_id_etiqueta(gmail_service, "Procesado_IA")

    # 3.3 Recuperacion de mensajes
    print("[SISTEMA] Consultando bandeja de entrada...")
    query = 'in:inbox -label:Procesado_IA newer_than:15d -from:me'
    resultados = gmail_service.users().messages().list(userId='me', q=query).execute()
    mensajes = resultados.get('messages', [])
    
    if not mensajes:
        print("[INFO] No existen correos nuevos pendientes de procesar.")
        return

    mensajes.reverse()
    total_mensajes = len(mensajes)
    print(f"[INFO] Procesando lote de {total_mensajes} correos (orden cronológico)...")

    for i, msg in enumerate(mensajes, start=1):
        correo_id = msg['id']
        print(f"\n[INFO] Procesando item {i}/{total_mensajes} (ID: {correo_id})")
        
        mensaje_completo = gmail_service.users().messages().get(userId='me', id=correo_id, format='full').execute()
        texto_correo = decodificar_correo(mensaje_completo)
        
        # 3.4 Inferencia de IA (Ahora devuelve una lista de registros)
        datos_ia_lista = analizar_con_ia(texto_correo, nombres_validos, eventos_validos)
        
        # Por seguridad, si la IA devolvió un diccionario único en vez de lista, lo envolvemos
        if isinstance(datos_ia_lista, dict):
            datos_ia_lista = [datos_ia_lista]
            
        # 3.5 Lógica por cada registro/niño encontrado en el correo
        for datos_ia in datos_ia_lista:
            tipo = datos_ia.get('tipo')
            nombre = datos_ia.get('nombre')
            asistencia = datos_ia.get('asistencia')
            pregunta = datos_ia.get('pregunta')
            evento = datos_ia.get('evento')
            
            print(f"[DEBUG] Clasificación: {tipo} | Nombre: {nombre} | Evento: {evento}")
            
            if tipo == 'SOLO_ASISTENCIA':
                if apuntar_en_excel(hoja, nombre, evento, asistencia):
                    print(f"[EXITO] Asistencia '{asistencia}' registrada para '{nombre}'.")
                    
            elif tipo == 'ASISTENCIA_Y_PREGUNTA':
                if apuntar_en_excel(hoja, nombre, evento, asistencia):
                    print(f"[EXITO] Asistencia registrada para '{nombre}'.")
                
                # Inyectamos el Evento en el título del mensaje para Telegram
                evt_texto = f" ({evento})" if evento else ""
                mensaje_tg = f"🏕️ *Asistencia y Duda{evt_texto}*\nFamilia de {nombre}: Confirma que *{asistencia}* asiste.\n\n💬 Pregunta: _{pregunta}_"
                avisar_telegram(mensaje_tg)
                print("[EXITO] Notificación enviada al Kraal.")
                
            elif tipo == 'SOLO_PREGUNTA':
                evt_texto = f" ({evento})" if evento else ""
                mensaje_tg = f"❓ *Duda Administrativa{evt_texto}*\nFamilia de {nombre} pregunta:\n\n💬 _{pregunta}_"
                avisar_telegram(mensaje_tg)
                print("[EXITO] Notificación de duda enviada.")
                
            elif tipo == 'IRRELEVANTE':
                print("[INFO] Registro descartado por irrelevante.")
                
            else:
                print("[AVISO] Categoría desconocida. Omitiendo.")

        marcar_como_procesado(gmail_service, correo_id, id_etiqueta_bot)
        print("[INFO] Etiqueta 'Procesado_IA' añadida con éxito.")

        # 3.6 Pausa de Rate Limiting
        if i < total_mensajes:
            print("[SISTEMA] Aplicando retraso de seguridad (12s)...")
            time.sleep(12)

    print("\n[SISTEMA] Ejecución finalizada correctamente. ¡Buena caza!")

if __name__ == '__main__':
    ejecutar_asistente()