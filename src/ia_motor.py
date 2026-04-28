import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional


def analizar_correo_unico(
    texto_correo: str,
    nombres_familia: List[str],
    eventos_validos: List[str],
    evento_detectado: Optional[str],
    active_keys: List[str],
) -> List[Dict[str, Any]]:
    """
    Inferencia enfocada: Gemini ya sabe de quién es el correo.
    Su misión es solo extraer la intención para esos niños.
    """
    instruccion_evento = (
        f'El evento es "{evento_detectado}".'
        if evento_detectado
        else f"Selecciona de: {eventos_validos}."
    )

    prompt = f"""
    Eres el secretario de la Tropa Waconda. Extrae la intención de asistencia de este correo enviado por la familia de: {nombres_familia}.
    
    REGLAS ESTRICTAS:
    1. MAPEO DE NOMBRES: Los padres usarán el nombre de pila o apodos (ej: "Bruno"). Debes deducir a quién se refieren y usar ÚNICAMENTE el nombre completo exacto que aparece en tu lista: {nombres_validos}.
    2. ASISTENCIA: "Sí" o "No". Si en el correo no dicen explícitamente si van o no, pon null obligatoriamente.
    3. EVENTO: {instruccion_evento}
    4. COMENTARIO: Extrae dudas reales o avisos (ej: "Llegaremos tarde a Buitrago"). Si es un saludo, una firma o dicen "Gracias", pon null.

    CORREO:
    {texto_correo}
    """

    esquema_respuesta = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "nombre": {"type": "STRING"},
                "asistencia": {
                    "type": "STRING",
                    "enum": ["Sí", "No"],
                    "nullable": True,
                },
                "evento": {"type": "STRING", "nullable": True},
                "comentario_relevante": {"type": "STRING", "nullable": True},
            },
            "required": ["nombre"],
        },
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": esquema_respuesta,
        },
    }

    intentos_fallidos = 0
    MAX_INTENTOS = 3

    while active_keys:
        key = active_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"

        try:
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                texto = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(texto)
            elif res.status_code == 429:
                logging.warning("Cuota agotada (429). Rotando clave...")
                active_keys.pop(0)
                intentos_fallidos = 0
                continue
            else:
                logging.error(f"Error API ({res.status_code}): {res.text}")
                intentos_fallidos += 1
        except Exception as e:
            logging.error(f"Error conexión: {e}")
            intentos_fallidos += 1

        if intentos_fallidos >= MAX_INTENTOS:
            active_keys.pop(0)
            intentos_fallidos = 0
        else:
            time.sleep(2)

    return [{"error_api": "CUOTA_AGOTADA"}]
