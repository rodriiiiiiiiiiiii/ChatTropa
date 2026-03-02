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
# Cargamos todas las keys que tengamos y filtramos las que estén vacías
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3")
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
    """Llamada DIRECTA a la API REST de Gemini con REINTENTOS, ROTACIÓN y NUEVAS REGLAS"""
    prompt = f"""
    Eres el secretario scout de la Tropa Waconda 194. Lee este correo (Asunto y Cuerpo) y extrae la información en formato JSON estricto.
    
    Clasifica CADA NIÑO mencionado en UNO de estos 4 tipos ("tipo"):
    - "SOLO_ASISTENCIA": Confirman asistencia o ausencia, sin dejar ningún comentario extra.
    - "ASISTENCIA_Y_COMENTARIO": Confirman asistencia/ausencia Y ADEMÁS añaden una duda, mensaje o aclaración de horario (ej. "llegará más tarde por partido").
    - "SOLO_COMENTARIO": Solo hacen una pregunta o comentario, no mencionan asistencia.
    - "IRRELEVANTE": Publicidad, spam, o correos que no encajan.

    REGLAS Y CONSTRICCIONES ESTRICTAS:
    1. IGNORAR HISTORIAL: Ignora TODO el texto que forme parte de un correo reenviado o historial (suele estar debajo de "De: Tropa Waconda", "Enviado el:", o "El ... escribió:"). Lee SOLO lo que ha escrito el padre arriba del todo.
    2. MULTIPLES NIÑOS (HERMANOS): Extrae un registro SEPARADO para cada niño mencionado. Devuelve SIEMPRE una LISTA de objetos JSON.
    3. NOMBRES: Elige exactamente uno de esta lista: {nombres_validos}. 
       * REGLA JULIA: Si el correo menciona juntas a "Clara y Julia", asume estrictamente que se refiere a "Julia Torrens" por ser hermanas.
    4. EVENTOS: Elige exactamente uno de esta lista: {eventos_validos}. Presta MUCHA ATENCIÓN al "ASUNTO".
    5. ASISTENCIA: "Sí" o "No". Expresiones como "irá", "sí irá", "confirma", o "contad con él/ella" significan "Sí". Si no mencionan asistencia, pon null.
    6. COMENTARIO: Extrae el texto de la duda o aclaración. Si no hay NADA extra, pon null (no pongas la palabra "None").

    Ejemplo de formato esperado (Devuelve ÚNICAMENTE un ARRAY JSON válido, sin Markdown):
    [
      {{"tipo": "ASISTENCIA_Y_COMENTARIO", "nombre": "Pablo Robledo", "evento": "Acampada", "asistencia": "Sí", "comentario": "Llegará a las 18:00 por un partido"}},
      {{"tipo": "SOLO_ASISTENCIA", "nombre": "Julia Torrens", "evento": "Acampada", "asistencia": "No", "comentario": null}}
    ]

    Correo a analizar:
    "{texto_correo}"
    """
    
    max_reintentos = 3
    for intento in range(max_reintentos):
        llave_actual = GEMINI_API_KEYS[intento % len(GEMINI_API_KEYS)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={llave_actual}"
        
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }

        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                datos = response.json()
                texto_respuesta = datos['candidates'][0]['content']['parts'][0]['text']
                texto_respuesta = texto_respuesta.replace('```json', '').replace('```', '').strip()
                return json.loads(texto_respuesta)
                
            elif response.status_code == 429:
                print(f"[AVISO] Límite de cuota (429). Rotando a la siguiente API Key... (Intento {intento+1}/{max_reintentos})")
                time.sleep(2) 
                continue
                
            elif response.status_code == 503:
                print(f"[AVISO] Servidor saturado (503). Esperando 20s... (Intento {intento+1}/{max_reintentos})")
                time.sleep(20)
                continue
                
            else:
                print(f"[ERROR API GEMINI] Código {response.status_code}: {response.text}")
                return [{"tipo": "ERROR", "error": f"HTTP {response.status_code}"}]
                
        except Exception as e:
            print(f"[ERROR] Fallo en la conexión directa con Gemini: {e}")
            return [{"tipo": "ERROR", "error": str(e)}]

    print("[ERROR] Múltiples reintentos fallidos. Saltando correo.")
    return [{"tipo": "ERROR", "error": "Servidor no disponible tras 3 intentos"}]

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
    hoja = gc.open("Asistencia_pruebas_IA").worksheet("ASISTENCIA")
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
        
        # 3.4 Inferencia de IA
        datos_ia_lista = analizar_con_ia(texto_correo, nombres_validos, eventos_validos)
        
        if isinstance(datos_ia_lista, dict):
            datos_ia_lista = [datos_ia_lista]
            
        procesado_con_exito = True 
            
        # 3.5 Lógica por cada registro/niño encontrado en el correo
        for datos_ia in datos_ia_lista:
            tipo = datos_ia.get('tipo')
            nombre = datos_ia.get('nombre')
            asistencia = datos_ia.get('asistencia')
            comentario = datos_ia.get('comentario')
            evento = datos_ia.get('evento')
            
            # FILTRO ANTI-NONE: Si el comentario dice "None" o está vacío, lo convertimos a null real
            if comentario and str(comentario).strip().lower() in ['none', 'null', '']:
                comentario = None
                
            # DEGRADACIÓN: Si era ASISTENCIA_Y_COMENTARIO pero el filtro borró el comentario, lo degradamos
            if tipo == 'ASISTENCIA_Y_COMENTARIO' and not comentario:
                tipo = 'SOLO_ASISTENCIA'
            elif tipo == 'SOLO_COMENTARIO' and not comentario:
                tipo = 'IRRELEVANTE'
            
            if tipo == 'ERROR':
                print(f"[AVISO] Error de la IA detectado. El correo se dejará sin etiquetar para reintentar luego.")
                procesado_con_exito = False
                break 
            
            print(f"[DEBUG] Clasificación: {tipo} | Nombre: {nombre} | Evento: {evento}")
            
            if tipo == 'SOLO_ASISTENCIA':
                if apuntar_en_excel(hoja, nombre, evento, asistencia):
                    print(f"[EXITO] Asistencia '{asistencia}' registrada para '{nombre}'.")
                    
            elif tipo == 'ASISTENCIA_Y_COMENTARIO':
                if apuntar_en_excel(hoja, nombre, evento, asistencia):
                    print(f"[EXITO] Asistencia registrada para '{nombre}'.")
                
                evt_texto = f" ({evento})" if evento else ""
                mensaje_tg = f"🏕️ *Asistencia y Mensaje{evt_texto}*\nFamilia de {nombre}: Confirma que *{asistencia}* asiste.\n\n💬 Mensaje: _{comentario}_"
                avisar_telegram(mensaje_tg)
                print("[EXITO] Notificación enviada al Kraal.")
                
            elif tipo == 'SOLO_COMENTARIO':
                evt_texto = f" ({evento})" if evento else ""
                mensaje_tg = f"❓ *Mensaje/Duda Administrativa{evt_texto}*\nFamilia de {nombre} comenta:\n\n💬 _{comentario}_"
                avisar_telegram(mensaje_tg)
                print("[EXITO] Notificación de duda enviada.")
                
            elif tipo == 'IRRELEVANTE':
                print("[INFO] Registro descartado por irrelevante.")
                
            else:
                print("[AVISO] Categoría desconocida. Omitiendo.")

        # SOLO PONEMOS LA ETIQUETA SI NO HUBO ERROR CRÍTICO
        if procesado_con_exito:
            marcar_como_procesado(gmail_service, correo_id, id_etiqueta_bot)
            print("[INFO] Etiqueta 'Procesado_IA' añadida con éxito.")
        else:
            print("[INFO] Saltando el etiquetado de este correo debido a errores.")

        # 3.6 Pausa de Rate Limiting
        if i < total_mensajes:
            print("[SISTEMA] Aplicando retraso de seguridad (12s)...")
            time.sleep(12)

    print("\n[SISTEMA] Ejecución finalizada correctamente. ¡Buena caza!")

if __name__ == '__main__':
    ejecutar_asistente()