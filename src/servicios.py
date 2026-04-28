import base64
import requests
import re
from typing import Optional, Dict, Any
from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def avisar_telegram(mensaje: str) -> None:
    """
    Envía un mensaje de texto plano o con formato Markdown al chat del Kraal
    utilizando la API REST de Telegram.
    Si la petición falla, la ignora silenciosamente para no detener el pipeline.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    datos = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=datos)
    except Exception:
        pass


def limpiar_texto_correo(texto_sucio: str) -> str:
    """
    Limpia el cuerpo del correo mediante Expresiones Regulares (Regex).
    Corta firmas de aplicaciones móviles ("Enviado desde mi iPhone") e historiales
    de respuestas largas ("El 12 de abr. escribió:") para enviar a la IA
    únicamente el texto nuevo, ahorrando tokens y reduciendo distracciones.
    """
    if not texto_sucio:
        return ""
    patrones_corte = [
        r"Enviado desde",
        r"El\s+.*?escribió:",
        r"De:\s+Tropa Waconda",
        r"On\s+.*?wrote:",
        r"_{10,}",
    ]

    texto_limpio = texto_sucio
    for patron in patrones_corte:
        texto_limpio = re.split(patron, texto_limpio, maxsplit=1, flags=re.IGNORECASE)[
            0
        ]
    return texto_limpio.strip()


def decodificar_correo(mensaje_gmail: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Toma un objeto de mensaje crudo de la API de Gmail y extrae su información clave.
    Busca las cabeceras de Asunto y Remitente, y decodifica el cuerpo del correo
    desde su formato Base64 original a texto legible (UTF-8).

    Retorna un diccionario con los datos estructurados, o None si ocurre un fallo.
    """
    try:
        payload = mensaje_gmail.get("payload", {})
        cabeceras = payload.get("headers", [])
        asunto = next(
            (c["value"] for c in cabeceras if c["name"].lower() == "subject"),
            "Sin Asunto",
        )
        remitente = next(
            (c["value"] for c in cabeceras if c["name"].lower() == "from"),
            "Desconocido",
        )

        partes = payload.get("parts", [])
        cuerpo = (
            payload.get("body", {}).get("data", "")
            if not partes
            else next(
                (
                    p["body"].get("data", "")
                    for p in partes
                    if p["mimeType"] == "text/plain"
                ),
                "",
            )
        )

        texto_crudo = base64.urlsafe_b64decode(cuerpo).decode("utf-8") if cuerpo else ""
        texto_limpio = limpiar_texto_correo(texto_crudo)

        return {
            "asunto": asunto,
            "remitente": remitente,
            "cuerpo": texto_limpio,
            "raw": f"REMITENTE: {remitente}\nASUNTO: {asunto}\nCUERPO:\n{texto_limpio}",
        }
    except Exception:
        return None
