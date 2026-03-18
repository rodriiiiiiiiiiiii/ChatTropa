# ia_motor.py
import json
import time
import requests

def analizar_correo_unico(texto_correo, nombres_validos, eventos_validos, active_keys):
    """Llamada a Gemini para UN SOLO correo."""
    prompt = f"""
    Eres el secretario de la Tropa Waconda. Analiza SOLO este correo.
    
    REGLAS ESTRICTAS:
    1. Lee el correo (ignora firmas o historiales).
    2. Identifica ÚNICAMENTE a los niños que se mencionen de forma explícita en el texto del correo. ¡TIENES TERMINANTEMENTE PROHIBIDO INVENTAR NOMBRES O EXTRAERLOS DE LA LISTA DE VALIDACIÓN SI NO APARECEN EN EL CORREO!
    3. NOMBRES EXACTOS (IMPORTANTE): 
       - Empareja al niño mencionado con su nombre en esta lista oficial: {nombres_validos}.
       - Escribe el nombre en el JSON EXACTAMENTE como sale en la lista.
       - IGNORA por completo los nombres de los padres o las firmas del correo (ej: si firma "Paloma" o "Sonsoles", descártalo).
    4. Identifica el evento basándote en el Asunto: {eventos_validos}.
    5. Asistencia: "Sí" o "No".
    6. Comentario: SOLO extrae dudas ("¿a qué hora?") o solicitudes ("podeis decirme la hora"). Si es:
        - Un saludo pon null.
        - Un aviso pon null.
        - Una especificación de a que hora viene pon null.
        - Una justificacion de porque no viene pon null.
        - Nada pon null.

    Ejemplo de respuesta:
    [
      {{"nombre": "Pablo Robledo", "evento": "Acampada", "asistencia": "Sí", "comentario_relevante": "¿Qué es el cuaderno?"}}
    ]

    CORREO:
    {texto_correo}
    """
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    while active_keys:
        llave_actual = active_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={llave_actual}"
        
        for intento in range(3):
            try:
                response = requests.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    try:
                        datos = response.json()
                        if 'candidates' in datos and datos['candidates'] and 'content' in datos['candidates'][0]:
                            texto = datos['candidates'][0]['content']['parts'][0]['text']
                            return json.loads(texto)
                        else:
                            raise ValueError("Respuesta vacía por filtro de Google.")
                    except Exception as e:
                        print(f"[AVISO IA] Reintentando por error interno de parsing.")
                        time.sleep(2)
                        continue 

                elif response.status_code == 429:
                    print(f"[ALERTA IA] Cuota (429) en llave actual. Rotando llave...")
                    active_keys.pop(0)
                    break 
                    
                else:
                    time.sleep(5)
                    continue 
                    
            except Exception as e:
                time.sleep(5)
                continue
                
        if active_keys:
            llave_fallida = active_keys.pop(0)
            active_keys.append(llave_fallida)

    return [{"error_api": "CUOTA_AGOTADA"}]