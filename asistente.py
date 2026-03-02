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
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
    os.getenv("GEMINI_API_KEY_6")
]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k] 

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets', 
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify'
]

if not GEMINI_API_KEYS:
    print("[ERROR] No se han encontrado API Keys en el archivo .env")
    exit(1)

# --- 2. FUNCIONES DE SERVICIO ---

def avisar_telegram(mensaje):
    """Envia notificaciones al grupo de TROPA AVISOS."""
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
        cabeceras = payload.get('headers', [])
        asunto = "Sin Asunto"
        for cabecera in cabeceras:
            if cabecera['name'].lower() == 'subject':
                asunto = cabecera['value']
                break
                
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

def analizar_lote_con_ia(texto_lote, nombres_validos, eventos_validos, active_keys):
    """Llamada a Gemini con JSON Mode forzado y Filtros Apagados"""
    prompt = f"""
    Eres el secretario scout de la Tropa Waconda 194. Vas a leer un LOTE DE CORREOS.
    Tu objetivo es registrar asistencias y avisar a los jefes SOLO si hay dudas reales.

    RECIBIRÁS VARIOS CORREOS. CADA UNO EMPIEZA CON '--- CORREO ID: [ID] ---'.
    DEBES DEVOLVER UN ARRAY JSON DONDE CADA OBJETO INCLUYA EL 'correo_id' EXACTO.

    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. PROCESAR TODOS: Debes leer todos los correos del lote. Si un correo es irrelevante, devuelve un objeto con su 'correo_id' y los demás campos en 'null'.
    2. IGNORAR HISTORIAL: Lee SOLO lo que ha escrito el padre arriba del todo.
    3. SEPARACIÓN DE HERMANOS: Si mencionan varios niños, crea un registro SEPARADO para cada uno, repitiendo el mismo 'correo_id'.
    4. NOMBRES EXACTOS: Empareja con esta lista: {nombres_validos}. (Ej. "Clara y Julia" -> "Julia Torrens").
    5. EVENTOS: Elige exactamente uno de esta lista basándote en el ASUNTO: {eventos_validos}.
    6. ASISTENCIA: "Sí" o "No". "Irá", "confirma", "contad con él" significan "Sí". Si no hay, pon null.
    7. COMENTARIO RELEVANTE: Solo extrae texto si es una duda explícita o un cambio de plan ("llegará tarde"). IGNORA saludos, hora oficial ("a las 8:30") y pon null.

    Formato esperado (ejemplo con 2 correos):
    [
      {{"correo_id": "19c123...", "nombre": "Pablo Robledo", "evento": "Acampada", "asistencia": "Sí", "comentario_relevante": "¿Qué es el cuaderno?"}},
      {{"correo_id": "19c456...", "nombre": null, "evento": null, "asistencia": null, "comentario_relevante": null}}
    ]

    CORREOS A ANALIZAR:
    {texto_lote}
    """
    
    headers = {'Content-Type': 'application/json'}
    
    # TRUCO MÁGICO: responseMimeType fuerza a Gemini a devolver SOLO un JSON válido
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json" 
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    max_reintentos_por_llave = 3
    
    while active_keys:
        llave_actual = active_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={llave_actual}"
        
        for intento in range(max_reintentos_por_llave):
            try:
                response = requests.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    try:
                        datos = response.json()
                        
                        if 'candidates' in datos and datos['candidates'] and 'content' in datos['candidates'][0]:
                            texto_respuesta = datos['candidates'][0]['content']['parts'][0]['text']
                            return json.loads(texto_respuesta)
                        else:
                            # EL CHIVATO: Si viene vacío, imprimimos por qué
                            print(f"\n[DEBUG RAW] Google bloqueó la respuesta. Motivo interno: {datos}\n")
                            raise ValueError("Respuesta vacía o bloqueada por Google.")

                    except Exception as json_err:
                        print(f"[AVISO] Fallo procesando JSON. Reintentando... Detalle: {json_err}")
                        time.sleep(2)
                        continue 

                elif response.status_code == 429:
                    print(f"[ALERTA] Límite de Cuota (429) en la llave actual. Descartándola por hoy...")
                    active_keys.pop(0)
                    break 
                    
                elif response.status_code == 503:
                    print(f"[AVISO] Servidor 503. Esperando 10s...")
                    time.sleep(10)
                    continue
                    
                else:
                    print(f"[ERROR API] Respuesta inesperada: {response.status_code} - {response.text}")
                    time.sleep(5)
                    continue 
                    
            except Exception as e:
                print(f"[ERROR RED] Fallo de conexión: {e}")
                time.sleep(5)
                continue
                
        if active_keys:
            llave_fallida = active_keys.pop(0)
            active_keys.append(llave_fallida)

    return [{"error_api": "CUOTA_AGOTADA"}]

def apuntar_en_excel(hoja, nombre_scout, evento, valor_asistencia):
    if not nombre_scout or not evento:
        return False
    try:
        celda_nombre = hoja.find(nombre_scout, in_column=1)
        celda_evento = hoja.find(evento, in_row=2)
        if celda_nombre and celda_evento:
            hoja.update_cell(celda_nombre.row, celda_evento.col, valor_asistencia)
            return True
        return False
    except Exception as e:
        return False

def obtener_id_etiqueta(servicio_gmail, nombre_etiqueta="Procesado_IA"):
    resultados = servicio_gmail.users().labels().list(userId='me').execute()
    etiquetas = resultados.get('labels', [])
    for etiqueta in etiquetas:
        if etiqueta['name'].lower() == nombre_etiqueta.lower():
            return etiqueta['id']
            
    nueva_etiqueta = {'name': nombre_etiqueta, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
    etiqueta_creada = servicio_gmail.users().labels().create(userId='me', body=nueva_etiqueta).execute()
    return etiqueta_creada['id']

def marcar_como_procesado(servicio_gmail, id_mensaje, id_etiqueta):
    servicio_gmail.users().messages().modify(userId='me', id=id_mensaje, body={'addLabelIds': [id_etiqueta]}).execute()

# --- 3. ORQUESTADOR PRINCIPAL ---

def ejecutar_asistente():
    print("[SISTEMA] Iniciando Agente de IA de asistencia y avisos de Tropa 194...")
    
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
    hoja = gc.open("Asistencia_pruebas_IA").worksheet("ASISTENCIA")
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    print("[SISTEMA] Descargando estructuras de datos de Google Sheets...")
    print("[SISTEMA] Descargando nombres y apellidos de los troperos...")
    print("[SISTEMA] Descargando reuniones y acampadas...")
    nombres_validos = [n for n in hoja.col_values(1)[2:] if n.strip()] 
    eventos_validos = [e for e in hoja.row_values(2)[1:] if e.strip()]

    id_etiqueta_bot = obtener_id_etiqueta(gmail_service, "Procesado_IA")

    print("[SISTEMA] Consultando bandeja de entrada...")
    query = 'in:inbox -label:Procesado_IA newer_than:15d -from:me'
    resultados = gmail_service.users().messages().list(userId='me', q=query).execute()
    mensajes = resultados.get('messages', [])
    
    if not mensajes:
        print("[INFO] No existen correos nuevos pendientes de procesar.")
        return

    mensajes.reverse()
    total_mensajes = len(mensajes)
    print(f"[INFO] Se han encontrado {total_mensajes} correos pendientes.")

    # ---------------------------------------------------------
    # LÓGICA DE MICRO-BATCHING (LOTES DE 5)
    # ---------------------------------------------------------
    lote_size = 5
    active_keys = GEMINI_API_KEYS.copy() # Llaves disponibles para hoy

    for i in range(0, total_mensajes, lote_size):
        lote_actual = mensajes[i : i + lote_size]
        print(f"\n[SISTEMA] Preparando LOTE de {len(lote_actual)} correos...")
        
        # 1. Empaquetar el texto de todos los correos del lote
        texto_empaquetado = ""
        for msg in lote_actual:
            correo_id = msg['id']
            msg_completo = gmail_service.users().messages().get(userId='me', id=correo_id, format='full').execute()
            texto_correo = decodificar_correo(msg_completo)
            texto_empaquetado += f"--- CORREO ID: {correo_id} ---\n{texto_correo}\n\n"

        # 2. Enviar el lote completo a la IA
        datos_ia_lista = analizar_lote_con_ia(texto_empaquetado, nombres_validos, eventos_validos, active_keys)
        
        if isinstance(datos_ia_lista, dict):
            datos_ia_lista = [datos_ia_lista]
            
        # 3. Comprobar si nos hemos quedado sin llaves por completo (Freno de emergencia)
        if any(d.get('error_api') == "CUOTA_AGOTADA" for d in datos_ia_lista):
            aviso_fatal = "*Alerta del Sistema*\nTodas las API Keys han agotado su cuota (Error 429). El procesamiento se ha pausado hasta mañana."
            print(aviso_fatal)
            print("[CRÍTICO] Ejecución abortada. Se ha avisado por Telegram.")
            return # Detiene el script entero
            
        # 4. Procesar la respuesta de la IA (agrupada por el ID de cada correo original del lote)
        for msg in lote_actual:
            correo_id = msg['id']
            print(f"\n[INFO] Desempaquetando resultados del correo (ID: {correo_id})")
            
            # Filtramos de la respuesta global solo los registros que pertenecen a este correo
            registros_de_este_correo = [r for r in datos_ia_lista if r.get('correo_id') == correo_id]
            
            # Si hubo un error general (no de cuota) y no hay datos, saltamos la etiqueta
            if any(r.get('error_api') for r in registros_de_este_correo) or not registros_de_este_correo:
                print(f"[AVISO] Error de procesado o datos vacíos. Se dejará sin etiquetar para reintentarlo.")
                continue

            # Variables para Telegram de este correo en concreto
            nombres_para_telegram = []
            duda_para_telegram = None
            evento_para_telegram = None
            
            for datos_ia in registros_de_este_correo:
                nombre = datos_ia.get('nombre')
                asistencia = datos_ia.get('asistencia')
                comentario = datos_ia.get('comentario_relevante')
                evento = datos_ia.get('evento')
                
                # Ignorar registros completamente nulos (correos irrelevantes)
                if not nombre and not comentario:
                    continue
                    
                print(f"[DEBUG] Extraído -> Nombre: {nombre} | Evento: {evento} | Asistencia: {asistencia} | Comentario: {comentario}")
                
                if str(comentario).strip().lower() in ['none', 'null', '']:
                    comentario = None
                    
                if nombre:
                    asist_texto = f" ({asistencia})" if asistencia else ""
                    nombres_para_telegram.append(f"{nombre}{asist_texto}")
                    
                if nombre and asistencia:
                    if apuntar_en_excel(hoja, nombre, evento, asistencia):
                        print(f"[EXITO] Asistencia '{asistencia}' registrada para '{nombre}'.")
                
                if comentario:
                    duda_para_telegram = comentario
                    evento_para_telegram = evento

            if duda_para_telegram and nombres_para_telegram:
                nombres_str = ", ".join(nombres_para_telegram)
                evt_texto = f" ({evento_para_telegram})" if evento_para_telegram else ""
                mensaje_tg = f"🏕️ *Aviso / Duda{evt_texto}*\nFamilia de {nombres_str}:\n\n💬 Mensaje: _{duda_para_telegram}_"
                avisar_telegram(mensaje_tg)
                print("[EXITO] Notificación agrupada enviada al Kraal.")

            # Etiquetar individualmente cada correo que se haya procesado bien dentro del lote
            marcar_como_procesado(gmail_service, correo_id, id_etiqueta_bot)
            print(f"[INFO] Etiqueta 'Procesado_IA' añadida con éxito.")

        # Pausa entre LOTES (en lugar de entre correos individuales)
        time.sleep(10)

    print("\n[SISTEMA] Ejecución finalizada correctamente. ¡Buena caza!")

if __name__ == '__main__':
    ejecutar_asistente()