import os
import time
from collections import defaultdict
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from config import SCOPES, GEMINI_API_KEYS
from servicios import avisar_telegram, decodificar_correo
from ia_motor import analizar_correo_unico

def apuntar_en_excel(hoja, nombre_scout, evento, valor_asistencia, nombres_validos, eventos_validos):
    try:
        fila = nombres_validos.index(nombre_scout) + 3
        columna = eventos_validos.index(evento) + 2
        hoja.update_cell(fila, columna, valor_asistencia)
        return True
    except ValueError:
        return False

def obtener_id_etiqueta(servicio_gmail, nombre_etiqueta):
    etiquetas = servicio_gmail.users().labels().list(userId='me').execute().get('labels', [])
    for etiqueta in etiquetas:
        if etiqueta['name'].lower() == nombre_etiqueta.lower():
            return etiqueta['id']
    nueva_etiqueta = {'name': nombre_etiqueta, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
    return servicio_gmail.users().labels().create(userId='me', body=nueva_etiqueta).execute()['id']

def marcar_como_procesado(servicio_gmail, id_mensaje, id_etiqueta):
    servicio_gmail.users().messages().modify(userId='me', id=id_mensaje, body={'addLabelIds': [id_etiqueta]}).execute()

def ejecutar_asistente():
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
    libro = None
    for intento in range(3):
        try:
            libro = gc.open("Asistencia_pruebas_IA")
            break
        except Exception as e:
            print(f"[AVISO] Fallo al conectar con Sheets. Reintentando ({intento+1}/3)...")
            time.sleep(5)
            
    if not libro:
        print("[ERROR CRÍTICO] Google Sheets no responde hoy. Abortando ejecución.")
        return
        
    hoja = libro.worksheet("ASISTENCIA")
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    nombres_validos = [n for n in hoja.col_values(1)[2:] if n.strip()] 
    eventos_validos = [e for e in hoja.row_values(2)[1:] if e.strip()]

    try:
        hoja_correos = libro.worksheet("CORREOS")
        datos_correos = hoja_correos.get_all_values()
    except Exception:
        datos_correos = []
        
    mapa_correos_padres = defaultdict(list)
    for fila in datos_correos:
        if not fila or len(fila) < 2: continue
        nombre_scout = fila[0].strip()
        for email in fila[1:]:
            if email.strip():
                mapa_correos_padres[email.strip().lower()].append(nombre_scout)

    id_etiq_bot = obtener_id_etiqueta(gmail_service, "Procesado_IA")
    id_etiq_rev = obtener_id_etiqueta(gmail_service, "Revision_Manual")

    query = 'in:inbox newer_than:15d -from:me'
    mensajes = gmail_service.users().messages().list(userId='me', q=query).execute().get('messages', [])
    
    if not mensajes: return
    mensajes.reverse()

    active_keys = GEMINI_API_KEYS.copy()
    buffer_mensajes = [] 

    for msg in mensajes:
        correo_id = msg['id']
        msg_completo = gmail_service.users().messages().get(userId='me', id=correo_id, format='full').execute()

        etiquetas_mensaje = msg_completo.get('labelIds', [])
        if id_etiq_bot in etiquetas_mensaje or id_etiq_rev in etiquetas_mensaje:
            continue # Si este mensaje concreto ya fue procesado, pasamos al siguiente
            
        datos_correo = decodificar_correo(msg_completo)
        
        if not datos_correo: continue

        texto_total_lower = f"{datos_correo['asunto']} {datos_correo['cuerpo']}".lower()
        evento_local = next((e for e in eventos_validos if e.lower() in datos_correo['asunto'].lower()), None)
        
        remitente_lower = datos_correo['remitente'].lower()
        nombres_por_correo = next((nombres for correo, nombres in mapa_correos_padres.items() if correo in remitente_lower), None)
        
        if nombres_por_correo:
            nombres_para_ia = nombres_por_correo
        else:
            posibles_nombres = [n for n in nombres_validos if n.split()[0].lower() in texto_total_lower]
            nombres_para_ia = posibles_nombres if posibles_nombres else nombres_validos

        datos_ia_lista = analizar_correo_unico(datos_correo['raw'], nombres_para_ia, eventos_validos, evento_local, active_keys)
        if isinstance(datos_ia_lista, dict): datos_ia_lista = [datos_ia_lista]
            
        if any(d.get('error_api') == "CUOTA_AGOTADA" for d in datos_ia_lista):
            if "⚠️ *Alerta*" not in buffer_mensajes: avisar_telegram("⚠️ *Alerta*\nTodas las API Keys agotadas.")
            return

        procesado_con_exito = True
        nombres_vistos = set() 
        nombres_tg, duda_tg, evento_tg = [], None, None
        
        for datos_ia in datos_ia_lista:
            if datos_ia.get('error_api'):
                procesado_con_exito = False
                break 

            nombre = datos_ia.get('nombre')
            asistencia = datos_ia.get('asistencia')
            comentario = datos_ia.get('comentario_relevante')
            evento = datos_ia.get('evento') or evento_local
            
            if nombre in nombres_vistos: continue 
            if nombre: nombres_vistos.add(nombre)
            if str(comentario).strip().lower() in ['none', 'null', '']: comentario = None
            
            if nombre and asistencia:
                apuntar_en_excel(hoja, nombre, evento, asistencia, nombres_validos, eventos_validos)
                nombres_tg.append(f"{nombre} ({asistencia})")
            elif nombre:
                nombres_tg.append(f"{nombre} (Sin confirmar)")
            
            if comentario and not duda_tg:
                duda_tg, evento_tg = comentario, evento

        if procesado_con_exito:
            if nombres_tg or duda_tg:
                if duda_tg and nombres_tg:
                    evt_texto = f" ({evento_tg})" if evento_tg else ""
                    mensaje_tg = f"🏕️ *Aviso / Duda{evt_texto}*\nFamilia de {', '.join(nombres_tg)}:\n\n💬 Mensaje: _{duda_tg}_"
                    if mensaje_tg not in buffer_mensajes:
                        avisar_telegram(mensaje_tg)
                        buffer_mensajes.append(mensaje_tg)
                        if len(buffer_mensajes) > 10: buffer_mensajes.pop(0) 
                marcar_como_procesado(gmail_service, correo_id, id_etiq_bot)
            else:
                mensaje_tg = f"⚠️ *Correo Ignorado*\n📧 *Asunto:* {datos_correo['asunto']}\n👉 Revisa Gmail."
                if mensaje_tg not in buffer_mensajes:
                    avisar_telegram(mensaje_tg)
                    buffer_mensajes.append(mensaje_tg)
                    if len(buffer_mensajes) > 10: buffer_mensajes.pop(0)
                marcar_como_procesado(gmail_service, correo_id, id_etiq_rev)
        time.sleep(3)

if __name__ == '__main__':
    ejecutar_asistente()