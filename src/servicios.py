import base64
import requests
import re
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def avisar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    datos = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=datos)
    except Exception:
        pass

def limpiar_texto_correo(texto_sucio):
    if not texto_sucio: return ""
    patrones_corte = [
        r"Enviado desde", r"El\s+\d{1,2}.*?escribió:", 
        r"De:\s+Tropa Waconda", r"On\s+.*?wrote:", r"_{10,}"
    ]
    texto_limpio = texto_sucio
    for patron in patrones_corte:
        texto_limpio = re.split(patron, texto_limpio, maxsplit=1, flags=re.IGNORECASE)[0]
    return texto_limpio.strip()

def decodificar_correo(mensaje_gmail):
    try:
        payload = mensaje_gmail.get('payload', {})
        cabeceras = payload.get('headers', [])
        asunto = next((c['value'] for c in cabeceras if c['name'].lower() == 'subject'), "Sin Asunto")
        remitente = next((c['value'] for c in cabeceras if c['name'].lower() == 'from'), "Desconocido")
                
        partes = payload.get('parts', [])
        cuerpo = payload.get('body', {}).get('data', '') if not partes else next((p['body'].get('data', '') for p in partes if p['mimeType'] == 'text/plain'), "")
        
        texto_crudo = base64.urlsafe_b64decode(cuerpo).decode('utf-8') if cuerpo else ""
        texto_limpio = limpiar_texto_correo(texto_crudo)
            
        return {
            "asunto": asunto,
            "remitente": remitente,
            "cuerpo": texto_limpio,
            "raw": f"REMITENTE: {remitente}\nASUNTO: {asunto}\nCUERPO:\n{texto_limpio}"
        }
    except Exception:
        return None