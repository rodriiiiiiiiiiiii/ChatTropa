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
    os.getenv("GEMINI_API_KEY_5")
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

def analizar_con_ia(texto_correo, nombres_validos, eventos_validos):
    """Llamada a Gemini con Retry sofisticado y Rotación por 429"""
    prompt = f"""
    Eres el secretario scout de la Tropa Waconda 194. Lee este correo (Asunto y Cuerpo) y extrae la información.
    Tu objetivo es registrar asistencias y avisar a los jefes SOLO si hay dudas o cambios de planes reales.

    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. IGNORAR HISTORIAL: Lee SOLO lo que ha escrito el padre. Ignora todo el texto citado debajo de "De: Tropa Waconda", "Enviado el:", o similares.
    2. SEPARACIÓN DE HERMANOS: Si mencionan varios niños (ej. "Diana y Vega", "los niños", "Clara y Julia"), crea un registro SEPARADO para cada uno. Devuelve siempre un ARRAY JSON.
    3. NOMBRES EXACTOS: Empareja el nombre del correo con el más lógico de esta lista: {nombres_validos}. 
       - Si dicen "Leo", "Víctor" o "Ainhoa", busca su nombre completo en la lista.
       - REGLA JULIA: Si el correo menciona "Clara y Julia", es "Julia Torrens".
    4. EVENTOS: Elige exactamente uno de esta lista basándote en el ASUNTO: {eventos_validos}.
    5. ASISTENCIA: "Sí" o "No". "Irá", "confirma", "contad con Joaquín/él" significan "Sí". Si no mencionan asistencia, pon null.
    6. COMENTARIO RELEVANTE (FILTRO ANTI-RUIDO): ¡CRÍTICO! Solo extrae texto si es una duda explícita ("¿qué es el cuaderno?", "¿a qué hora?") o un aviso que cambie el plan ("llegará más tarde", "tiene partido"). 
       - IGNORA y pon `null` a: saludos, despedidas ("aventura maravillosa"), disculpas vacías ("perdón por el correo"), o confirmaciones de la hora oficial de la acampada (ej. "a las 8:30 en Plaza Castilla", "desde la mañana").

    Formato esperado:
    [
      {{"nombre": "Pablo Robledo", "evento": "Acampada", "asistencia": "Sí", "comentario_relevante": "¿Qué es el cuaderno de entregas?"}},
      {{"nombre": "Clara Torrens", "evento": "Acampada", "asistencia": "Sí", "comentario_relevante": null}}
    ]

    Correo a analizar:
    "{texto_correo}"
    """
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }

    max_reintentos_por_llave = 5
    
    # Bucle EXTERIOR: Itera sobre las llaves disponibles
    for idx_llave, llave_actual in enumerate(GEMINI_API_KEYS):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={llave_actual}"
        
        # Bucle INTERIOR: Reintentos para errores temporales (JSON roto, 503, Red)
        for intento in range(max_reintentos_por_llave):
            try:
                response = requests.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    try:
                        datos = response.json()
                        texto_respuesta = datos['candidates'][0]['content']['parts'][0]['text']
                        
                        texto_respuesta = texto_respuesta.strip()
                        if texto_respuesta.startswith('```'):
                            texto_respuesta = texto_respuesta.split('\n', 1)[-1] 
                        if texto_respuesta.endswith('```'):
                            texto_respuesta = texto_respuesta.rsplit('\n', 1)[0]
                        texto_respuesta = texto_respuesta.replace('json', '', 1).strip()
                        
                        return json.loads(texto_respuesta)
                    except Exception as json_err:
                        print(f"[AVISO] Llave {idx_llave+1}, Intento {intento+1}: JSON mal formado. Reintentando... Detalle: {json_err}")
                        time.sleep(2)
                        continue 

                elif response.status_code == 429:
                    print(f"[AVISO] Rate Limit (429) detectado en Llave {idx_llave+1}. Saltando a la siguiente llave...")
                    break # ROMPE el bucle interior, salta a la siguiente llave en el bucle exterior
                    
                elif response.status_code == 503:
                    print(f"[AVISO] Llave {idx_llave+1}, Intento {intento+1}: Servidor 503. Esperando 20s...")
                    time.sleep(20)
                    continue
                    
                else:
                    print(f"[ERROR API] Llave {idx_llave+1}, Intento {intento+1}: {response.status_code} - {response.text}")
                    time.sleep(5)
                    continue 
                    
            except Exception as e:
                print(f"[ERROR RED] Llave {idx_llave+1}, Intento {intento+1}: {e}")
                time.sleep(5)
                continue
                
        # Si llega aquí sin que un 'break' lo haya interrumpido (y no ha retornado), 
        # significa que agotó los 5 intentos de esta llave con errores temporales. 
        # El bucle exterior seguirá probando con la siguiente llave.

    print("[CRÍTICO] Se agotaron todas las llaves y sus reintentos para este correo.")
    return [{"error_api": True}]

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
    print("[SISTEMA] Iniciando Agente de Asistencia Tropa 194...")
    
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
    print(f"[INFO] Procesando lote de {total_mensajes} correos...")

    for i, msg in enumerate(mensajes, start=1):
        correo_id = msg['id']
        print(f"\n[INFO] Procesando item {i}/{total_mensajes} (ID: {correo_id})")
        
        mensaje_completo = gmail_service.users().messages().get(userId='me', id=correo_id, format='full').execute()
        texto_correo = decodificar_correo(mensaje_completo)
        
        datos_ia_lista = analizar_con_ia(texto_correo, nombres_validos, eventos_validos)
        
        if isinstance(datos_ia_lista, dict):
            datos_ia_lista = [datos_ia_lista]
            
        procesado_con_exito = True 
        
        # Variables para agrupar notificaciones de hermanos en 1 solo mensaje
        nombres_para_telegram = []
        duda_para_telegram = None
        evento_para_telegram = None
            
        for datos_ia in datos_ia_lista:
            # Comprobación de error crítico de API
            if datos_ia.get('error_api'):
                print(f"[AVISO] Error crítico de la IA. El correo se dejará sin etiquetar para reintentarlo luego.")
                procesado_con_exito = False
                break 

            nombre = datos_ia.get('nombre')
            asistencia = datos_ia.get('asistencia')
            comentario = datos_ia.get('comentario_relevante')
            evento = datos_ia.get('evento')
            
            print(f"[DEBUG] Extraído -> Nombre: {nombre} | Evento: {evento} | Asistencia: {asistencia} | Comentario: {comentario}")
            
            # Filtro de seguridad anti-none
            if str(comentario).strip().lower() in ['none', 'null', '']:
                comentario = None
                
            # Lógica 1: Guardar el nombre para Telegram, aunque no haya asistencia confirmada (para dudas puras)
            if nombre:
                asist_texto = f" ({asistencia})" if asistencia else ""
                nombres_para_telegram.append(f"{nombre}{asist_texto}")
                
            # Lógica 2: Apuntar en Excel SOLO si han dicho Sí o No
            if nombre and asistencia:
                if apuntar_en_excel(hoja, nombre, evento, asistencia):
                    print(f"[EXITO] Asistencia '{asistencia}' registrada para '{nombre}'.")
            
            # Lógica 3: Capturar dudas importantes para Telegram
            if comentario:
                duda_para_telegram = comentario
                evento_para_telegram = evento

        # Lógica 4: Enviar 1 solo Telegram por correo (agrupando hermanos)
        if procesado_con_exito and duda_para_telegram and nombres_para_telegram:
            nombres_str = ", ".join(nombres_para_telegram)
            evt_texto = f" ({evento_para_telegram})" if evento_para_telegram else ""
            
            mensaje_tg = f"🏕️ *Aviso / Duda{evt_texto}*\nFamilia de {nombres_str}:\n\n💬 Mensaje: _{duda_para_telegram}_"
            avisar_telegram(mensaje_tg)
            print("[EXITO] Notificación única agrupada enviada al Kraal.")

        # Etiquetar si todo fue bien
        if procesado_con_exito:
            marcar_como_procesado(gmail_service, correo_id, id_etiqueta_bot)
            print("[INFO] Etiqueta 'Procesado_IA' añadida con éxito.")

        if i < total_mensajes:
            time.sleep(12)

    print("\n[SISTEMA] Ejecución finalizada correctamente. ¡Buena caza!")

if __name__ == '__main__':
    ejecutar_asistente()