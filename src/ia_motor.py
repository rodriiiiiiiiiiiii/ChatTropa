import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional


def analizar_correo_unico(
    texto_correo: str,
    nombres_validos: List[str],
    eventos_validos: List[str],
    evento_detectado: Optional[str],
    active_keys: List[str],
) -> List[Dict[str, Any]]:
    """
    Envía un correo a la API de Google Gemini para extraer su intención estructurada.
    """
    instruccion_evento = (
        f'El evento es "{evento_detectado}".'
        if evento_detectado
        else f"Selecciona de: {eventos_validos}."
    )

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

    esquema_respuesta = {
        "type": "ARRAY",
        "description": "Lista de objetos con la intención de cada scout.",
        "items": {
            "type": "OBJECT",
            "properties": {
                "nombre": {"type": "STRING"},
                "asistencia": {"type": "STRING", "enum": ["Sí", "No"]},
                "evento": {"type": "STRING"},
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"

        try:
            res = requests.post(url, json=payload, timeout=30)

            if res.status_code == 200:
                texto = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(texto)

            elif res.status_code == 429:
                logging.warning("Cuota agotada (429). Rotando a la siguiente clave...")
                active_keys.pop(0)
                intentos_fallidos = 0  # Reseteamos los intentos para la nueva llave
                continue

            else:
                logging.error(
                    f"Error API ({res.status_code}): {res.text}. Intento {intentos_fallidos + 1}/{MAX_INTENTOS}"
                )
                intentos_fallidos += 1

        except Exception as e:
            logging.error(
                f"Error de conexión: {e}. Intento {intentos_fallidos + 1}/{MAX_INTENTOS}"
            )
            intentos_fallidos += 1

        # LÓGICA ANTI-BUCLES INFINITOS
        if intentos_fallidos >= MAX_INTENTOS:
            logging.error("Límite de intentos superado. Descartando llave y rotando...")
            active_keys.pop(0)
            intentos_fallidos = 0
        else:
            time.sleep(2)  # Pausa antes del siguiente reintento

    return [{"error_api": "CUOTA_AGOTADA_O_ERROR_CRITICO"}]
