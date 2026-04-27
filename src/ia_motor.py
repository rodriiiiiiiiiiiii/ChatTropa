import json
import time
import requests

def analizar_correo_unico(texto_correo, nombres_validos, eventos_validos, evento_detectado, active_keys):
    instruccion_evento = f'El evento es "{evento_detectado}".' if evento_detectado else f'Selecciona de: {eventos_validos}.'
    
    prompt = f"""
    Eres el secretario de la Tropa Waconda. Analiza este correo.
    
    REGLAS:
    1. Identifica a los niños mencionados de forma explícita.
    2. Usa SOLO estos nombres exactos: {nombres_validos}.
    3. Si el correo dice "mis hijos" o similar, genera un objeto por cada nombre de la lista de validación.
    4. Evento: {instruccion_evento}
    5. Asistencia: "Sí" o "No". Si no se aclara, null.
    6. Comentario: Extrae SOLO dudas o peticiones reales (ej: "¿hay que llevar saco?").

    CORREO:
    {texto_correo}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
    }

    while active_keys:
        key = active_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={key}"
        
        try:
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                return json.loads(texto)
            elif res.status_code == 429:
                print(f"[IA] Key agotada, rotando...")
                active_keys.pop(0)
                continue
        except Exception:
            time.sleep(2)
            continue
            
    return [{"error_api": "CUOTA_AGOTADA"}]