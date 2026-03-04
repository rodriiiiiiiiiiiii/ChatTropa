# servicios.py
import base64
import requests
import re
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def avisar_telegram(mensaje):
    """Envia notificaciones al grupo de Kraal definido en config."""
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

def limpiar_texto_correo(texto_sucio):
    """Detecta historiales de Gmail, Outlook y firmas, y le corta la cola al mensaje."""
    if not texto_sucio:
        return ""
        
    # Patrones clásicos donde empieza la "basura" de respuestas o firmas móviles
    patrones_corte = [
        r"Enviado desde",                         # Firmas de Outlook/iPhone
        r"El\s+\d{1,2}.*?escribió:",              # Historial clásico de Gmail (Ej: El 26 feb 2026... escribió:)
        r"De:\s+Tropa Waconda",                   # Historial de Outlook/Hotmail
        r"On\s+.*?wrote:",                        # Historiales en inglés
        r"_{10,}"                                 # Líneas largas (_________________) que separan correos
    ]
    
    texto_limpio = texto_sucio
    for patron in patrones_corte:
        partes = re.split(patron, texto_limpio, maxsplit=1, flags=re.IGNORECASE)
        texto_limpio = partes[0]

    return texto_limpio.strip()

def decodificar_correo(mensaje_gmail):
    """Extrae el asunto y el cuerpo decodificado de un payload de Gmail."""
    try:
        payload = mensaje_gmail.get('payload', {})
        
        # Extraer Asunto
        cabeceras = payload.get('headers', [])
        asunto = next((cab['value'] for cab in cabeceras if cab['name'].lower() == 'subject'), "Sin Asunto")
                
        # Extraer Cuerpo
        partes = payload.get('parts', [])
        cuerpo = ""
        if not partes:
            cuerpo = payload.get('body', {}).get('data', '')
        else:
            for parte in partes:
                if parte['mimeType'] == 'text/plain':
                    cuerpo = parte['body'].get('data', '')
                    break
        
        texto_crudo = base64.urlsafe_b64decode(cuerpo).decode('utf-8') if cuerpo else ""

        texto_limpio = limpiar_texto_correo(texto_crudo)
            
        return f"ASUNTO: {asunto}\nCUERPO:\n{texto_limpio}"
    except Exception as e:
        print(f"[ERROR] Fallo al decodificar el correo: {e}")
        return ""