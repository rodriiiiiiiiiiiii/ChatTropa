# asistente.py
import os
import time
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Importamos nuestros propios módulos
from config import SCOPES, GEMINI_API_KEYS
from servicios import avisar_telegram, decodificar_correo
from ia_motor import analizar_correo_unico

def apuntar_en_excel(hoja, nombre_scout, evento, valor_asistencia):
    if not nombre_scout or not evento: return False
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
    
    print("[SISTEMA] Descargando listas oficiales desde Sheets...")
    nombres_validos = [n for n in hoja.col_values(1)[2:] if n.strip()] 
    eventos_validos = [e for e in hoja.row_values(2)[1:] if e.strip()]

    id_etiqueta_bot = obtener_id_etiqueta(gmail_service, "Procesado_IA")

    query = 'in:inbox -label:Procesado_IA newer_than:15d -from:me'
    resultados = gmail_service.users().messages().list(userId='me', q=query).execute()
    mensajes = resultados.get('messages', [])
    
    if not mensajes:
        print("[INFO] No existen correos nuevos.")
        return

    mensajes.reverse()
    total_mensajes = len(mensajes)
    print(f"[INFO] Se procesarán {total_mensajes} correos INDIVIDUALMENTE.")

    active_keys = GEMINI_API_KEYS.copy()

    for i, msg in enumerate(mensajes, start=1):
        correo_id = msg['id']
        print(f"\n[INFO] Leyendo Correo {i}/{total_mensajes} (ID: {correo_id})")
        
        msg_completo = gmail_service.users().messages().get(userId='me', id=correo_id, format='full').execute()
        texto_correo = decodificar_correo(msg_completo)

        datos_ia_lista = analizar_correo_unico(texto_correo, nombres_validos, eventos_validos, active_keys)
        
        if isinstance(datos_ia_lista, dict):
            datos_ia_lista = [datos_ia_lista]
            
        if any(d.get('error_api') == "CUOTA_AGOTADA" for d in datos_ia_lista):
            aviso_fatal = "⚠️ *Alerta*\nTodas las API Keys (8) agotadas. Se pausa hasta mañana."
            avisar_telegram(aviso_fatal)
            print("[CRÍTICO] Ejecución abortada por Cuota 429.")
            return

        procesado_con_exito = True
        nombres_vistos = set() 
        nombres_para_telegram = []
        duda_para_telegram = None
        evento_para_telegram = None
        
        for datos_ia in datos_ia_lista:
            if datos_ia.get('error_api'):
                print(f"[AVISO] Error interno en este correo. Se saltará la etiqueta.")
                procesado_con_exito = False
                break 

            nombre = datos_ia.get('nombre')
            asistencia = datos_ia.get('asistencia')
            comentario = datos_ia.get('comentario_relevante')
            evento = datos_ia.get('evento')
            
            if nombre in nombres_vistos: continue 
            if nombre: nombres_vistos.add(nombre)

            if str(comentario).strip().lower() in ['none', 'null', '']:
                comentario = None
                
            print(f"[DEBUG] Extraído -> {nombre} | {evento} | {asistencia} | Duda: {bool(comentario)}")
            
            if nombre and asistencia:
                if apuntar_en_excel(hoja, nombre, evento, asistencia):
                    print(f"  -> Sheets OK: {nombre}")
                asist_texto = f" ({asistencia})"
                nombres_para_telegram.append(f"{nombre}{asist_texto}")
            elif nombre:
                nombres_para_telegram.append(f"{nombre} (Sin confirmar)")
            
            if comentario and not duda_para_telegram:
                duda_para_telegram = comentario
                evento_para_telegram = evento

        if procesado_con_exito and duda_para_telegram and nombres_para_telegram:
            nombres_str = ", ".join(nombres_para_telegram)
            evt_texto = f" ({evento_para_telegram})" if evento_para_telegram else ""
            mensaje_tg = f"🏕️ *Aviso / Duda{evt_texto}*\nFamilia de {nombres_str}:\n\n💬 Mensaje: _{duda_para_telegram}_"
            avisar_telegram(mensaje_tg)
            print("[EXITO] Telegram enviado.")

        if procesado_con_exito:
            marcar_como_procesado(gmail_service, correo_id, id_etiqueta_bot)
            print("[INFO] Etiquetado con éxito.")

        time.sleep(3)

    print("\n[SISTEMA] Ejecución finalizada correctamente. ¡Buena caza!")

if __name__ == '__main__':
    ejecutar_asistente()