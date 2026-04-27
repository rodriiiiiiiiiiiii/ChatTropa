import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional

def analizar_correo_unico(texto_correo: str, nombres_validos: List[str], eventos_validos: List[str], evento_detectado: Optional[str], active_keys: List[str]) -> List[Dict[str, Any]]:
    """
    Envía un correo a la API de Google Gemini para extraer su intención estructurada.
    Utiliza 'Structured Outputs' pasándole un responseSchema estricto a la API.
    Esto garantiza matemáticamente que el JSON de salida tiene las claves correctas
    y respeta los tipos de datos (Enum, String, Nullable).
    
    Implementa un sistema de rotación de API Keys para evitar errores 429.
    """
    instruccion_evento = f'El evento es "{evento_detectado}".' if evento_detectado else f'Selecciona de: {eventos_validos}.'
    
    # 1. El Prompt ahora es mucho más limpio. Ya no le suplicamos que formatee el JSON
    # ni le damos ejemplos, porque la estructura se fuerza en la configuración.
    prompt = f"""
    Eres el secretario de la Tropa Waconda. Analiza este correo.
    
    REGLAS:
    1. Identifica a los niños mencionados de forma explícita.
    2. Usa SOLO estos nombres exactos: {nombres_validos}.
    3. Si el correo dice "mis hijos" o similar, genera un objeto por cada nombre de la lista de validación.
    4. Evento: {instruccion_evento}
    5. Comentario: Extrae SOLO dudas o peticiones reales (ej: "¿hay que llevar saco?").

    CORREO:
    {texto_correo}
    """
    
    # 2. Definimos el Esquema Estricto (Structured Output)
    esquema_respuesta = {
        "type": "ARRAY",
        "description": "Lista de objetos con la intención de cada scout mencionado en el correo.",
        "items": {
            "type": "OBJECT",
            "properties": {
                "nombre": {
                    "type": "STRING",
                    "description": "Nombre exacto del scout tal y como aparece en la lista permitida."
                },
                "asistencia": {
                    "type": "STRING",
                    "description": "Confirmación de si el scout asiste o no asiste.",
                    "enum": ["Sí", "No"]  # Gemini SOLO podrá devolver uno de estos dos valores exactos
                },
                "evento": {
                    "type": "STRING",
                    "description": "Nombre del evento al que se refiere el correo."
                },
                "comentario_relevante": {
                    "type": "STRING",
                    "description": "Duda, solicitud o comentario vital. Null si es solo un saludo o firma.",
                    "nullable": True
                }
            },
            # Hacemos obligatorio que al menos deduzca el nombre.
            "required": ["nombre"]
        }
    }
    
    # 3. Añadimos el esquema al payload
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0, 
            "responseMimeType": "application/json",
            "responseSchema": esquema_respuesta
        }
    }

    # 4. Rotación de Keys (Se mantiene intacta)
    while active_keys:
        key = active_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={key}"
        
        try:
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                return json.loads(texto)
            elif res.status_code == 429:
                logging.warning("Cuota de API Key agotada (429). Rotando a la siguiente clave...")
                active_keys.pop(0)
                continue
            else:
                logging.error(f"Error inesperado de la API: {res.status_code} - {res.text}")
                time.sleep(2)
                continue
        except Exception as e:
            logging.error(f"Fallo de conexión en rotación de keys: {e}")
            time.sleep(2)
            continue
            
    return [{"error_api": "CUOTA_AGOTADA"}]