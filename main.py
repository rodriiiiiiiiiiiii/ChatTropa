import os
import time
import re
import gspread
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from src.config import SCOPES, GEMINI_API_KEYS, BLACKLIST_SUBJECTS, BLACKLIST_SENDERS
from src.servicios import avisar_telegram, decodificar_correo
from src.google_sheets_manager import GoogleSheetsManager
from src.ia_motor import analizar_correo_unico

def extraer_email_puro(remitente_raw):
    match = re.search(r'[\w\.-]+@[\w\.-]+', remitente_raw)
    return match.group(0).lower() if match else remitente_raw.lower()

def es_spam_tecnico(asunto, remitente):
    asunto_l = asunto.lower()
    remitente_l = remitente.lower()
    return any(s in asunto_l for s in BLACKLIST_SUBJECTS) or any(r in remitente_l for r in BLACKLIST_SENDERS)

def ejecutar_asistente():
    # 1. Auth y Clientes
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    gc = gspread.authorize(creds)
    gmail = build('gmail', 'v1', credentials=creds)
    
    # 2. Inicializar Manager y Datos
    gs_manager = GoogleSheetsManager(gc, "Asistencia_pruebas_IA")
    nombres_master, eventos_master = gs_manager.obtener_datos_maestros()
    mapa_correos = gs_manager.obtener_mapeo_correos()

    # 3. Etiquetas Gmail
    id_etiq_bot = "TU_ID_PROCESADO" 
    id_etiq_rev = "TU_ID_REVISION"

    # 4. Loop de Procesamiento
    query = 'in:inbox newer_than:7d -from:me'
    mensajes = gmail.users().messages().list(userId='me', q=query).execute().get('messages', [])
    
    active_keys = GEMINI_API_KEYS.copy()

    for msg_ref in reversed(mensajes):
        m_id = msg_ref['id']
        m_full = gmail.users().messages().get(userId='me', id=m_id).execute()
        
        if any(label in m_full.get('labelIds', []) for label in [id_etiq_bot, id_etiq_rev]):
            continue

        datos = decodificar_correo(m_full)
        if not datos: continue

        # --- FILTRO ANTI-SPAM ---
        if es_spam_tecnico(datos['asunto'], datos['remitente']):
            # Marcar como procesado pero no avisar a Telegram
            gmail.users().messages().modify(userId='me', id=m_id, body={'addLabelIds': [id_etiq_bot]}).execute()
            continue

        # --- CRUCE DE IDENTIDAD ---
        email_limpio = extraer_email_puro(datos['remitente'])
        nombres_para_ia = mapa_correos.get(email_limpio)
        
        if not nombres_para_ia:
            # Fallback por nombre en el texto si el email no está mapeado
            cuerpo_l = (datos['asunto'] + " " + datos['cuerpo']).lower()
            nombres_para_ia = [n for n in nombres_master if n.split()[0].lower() in cuerpo_l]
        
        if not nombres_para_ia: nombres_para_ia = nombres_master

        # --- ANALISIS IA ---
        evento_local = next((e for e in eventos_master if e.lower() in datos['asunto'].lower()), None)
        resultados = analizar_correo_unico(datos['raw'], nombres_para_ia, eventos_master, evento_local, active_keys)
        
        # --- PROCESAR RESULTADOS ---
        tuvo_exito = False
        resumen_tg = []
        
        for res in resultados:
            if 'error_api' in res: break
            
            nombre = res.get('nombre')
            asistencia = res.get('asistencia')
            evento = res.get('evento') or evento_local
            
            if nombre and asistencia and evento:
                if gs_manager.actualizar_asistencia(nombre, evento, asistencia):
                    resumen_tg.append(f"✅ {nombre}: {asistencia}")
                    tuvo_exito = True

            if res.get('comentario_relevante'):
                avisar_telegram(f"💬 *Duda de {nombre or 'familia'}:*\n_{res['comentario_relevante']}_")

        # Post-procesado del mensaje en Gmail
        if tuvo_exito:
            if resumen_tg: avisar_telegram(f"🏕️ *Actualización {evento_local or ''}*\n" + "\n".join(resumen_tg))
            label_final = id_etiq_bot
        else:
            avisar_telegram(f"⚠️ *Revisión Manual:* {datos['asunto']}")
            label_final = id_etiq_rev
            
        gmail.users().messages().modify(userId='me', id=m_id, body={'addLabelIds': [label_final]}).execute()
        
        # --- RATE LIMITING ---
        time.sleep(2) 

if __name__ == '__main__':
    ejecutar_asistente()