import time
import re
import gspread
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import SCOPES, GEMINI_API_KEYS, BLACKLIST_SUBJECTS, BLACKLIST_SENDERS
from src.servicios import avisar_telegram, decodificar_correo
from src.google_sheets_manager import GoogleSheetsManager
from src.ia_motor import analizar_correo_unico

# Configuración de Logging Profesional
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def extraer_email_puro(remitente_raw: str) -> str:
    """Extrae 'usuario@dominio.com' de un formato 'Nombre <usuario@dominio.com>'."""
    match = re.search(r"[\w\.-]+@[\w\.-]+", remitente_raw)
    return match.group(0).lower() if match else remitente_raw.lower()


def es_spam_tecnico(asunto: str, remitente: str) -> bool:
    """Verifica si el mensaje coincide con la lista negra de asuntos o remitentes."""
    asunto_l, remit_l = asunto.lower(), remitente.lower()
    return any(s in asunto_l for s in BLACKLIST_SUBJECTS) or any(
        r in remit_l for r in BLACKLIST_SENDERS
    )


def obtener_id_etiqueta(servicio_gmail, nombre_etiqueta: str) -> str:
    """Busca una etiqueta por nombre y devuelve su ID interno. Si no existe, la crea."""
    etiquetas = (
        servicio_gmail.users().labels().list(userId="me").execute().get("labels", [])
    )
    for etiqueta in etiquetas:
        if etiqueta["name"].lower() == nombre_etiqueta.lower():
            return etiqueta["id"]
    nueva_etiqueta = {
        "name": nombre_etiqueta,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    return (
        servicio_gmail.users()
        .labels()
        .create(userId="me", body=nueva_etiqueta)
        .execute()["id"]
    )


def ejecutar_asistente() -> None:
    """Proceso principal de lectura, análisis y registro de correos."""
    logging.info("Iniciando ciclo de Chat Tropa...")

    # 1. Autenticación
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    gc = gspread.authorize(creds)
    gmail = build("gmail", "v1", credentials=creds)

    # 2. Inicializar Manager (Carga el log de idempotencia automáticamente)
    gs_manager = GoogleSheetsManager(gc, "Asistencia_pruebas_IA")
    nombres_master, eventos_master = gs_manager.obtener_datos_maestros()
    mapa_correos = gs_manager.obtener_mapeo_correos()

    # 3. Etiquetas Gmail
    id_etiq_bot = obtener_id_etiqueta(gmail, "Procesado_IA")
    id_etiq_rev = obtener_id_etiqueta(gmail, "Revision_Manual")

    # 3. Obtener mensajes recientes
    query = "in:inbox newer_than:7d -from:me"
    mensajes = (
        gmail.users()
        .messages()
        .list(userId="me", q=query)
        .execute()
        .get("messages", [])
    )

    active_keys = GEMINI_API_KEYS.copy()

    for msg_ref in reversed(mensajes):
        m_id = msg_ref["id"]

        # COMPROBACIÓN DE IDEMPOTENCIA
        if gs_manager.esta_procesado(m_id):
            logging.info(f"Mensaje {m_id} ya procesado previamente. Saltando...")
            continue

        m_full = gmail.users().messages().get(userId="me", id=m_id).execute()
        datos = decodificar_correo(m_full)
        if not datos:
            continue

        # FILTRO ANTI-SPAM
        if es_spam_tecnico(datos["asunto"], datos["remitente"]):
            logging.info(f"Spam técnico detectado: {datos['asunto']}. Archivando...")
            gs_manager.registrar_procesado(m_id)
            gmail.users().messages().modify(
                userId="me", id=m_id, body={"addLabelIds": [id_etiq_bot]}
            ).execute()
            continue

        # CRUCE DE IDENTIDAD
        email_limpio = extraer_email_puro(datos["remitente"])
        nombres_para_ia = mapa_correos.get(email_limpio)

        if not nombres_para_ia:
            cuerpo_l = (datos["asunto"] + " " + datos["cuerpo"]).lower()
            nombres_para_ia = [
                n for n in nombres_master if n.split()[0].lower() in cuerpo_l
            ]

        if not nombres_para_ia:
            nombres_para_ia = nombres_master

        # ANÁLISIS IA (Structured Output)
        evento_local = next(
            (e for e in eventos_master if e.lower() in datos["asunto"].lower()), None
        )
        resultados = analizar_correo_unico(
            datos["raw"], nombres_para_ia, eventos_master, evento_local, active_keys
        )

        tuvo_exito, resumen_tg = False, []

        for res in resultados:
            if "error_api" in res:
                break

            nombre = res.get("nombre")
            asistencia = res.get("asistencia")
            evento = res.get("evento") or evento_local

            if nombre and asistencia and evento:
                if gs_manager.actualizar_asistencia(nombre, evento, asistencia):
                    resumen_tg.append(f"✅ {nombre}: {asistencia}")
                    tuvo_exito = True

            if res.get("comentario_relevante"):
                avisar_telegram(
                    f"💬 *Duda de {nombre or 'familia'}:*\n_{res['comentario_relevante']}_"
                )

        # REGISTRO Y CIERRE DE TAREA
        if tuvo_exito:
            if resumen_tg:
                avisar_telegram(
                    f"🏕️ *Actualización {evento_local or ''}*\n" + "\n".join(resumen_tg)
                )
            gs_manager.registrar_procesado(m_id)
            label_final = id_etiq_bot
        else:
            avisar_telegram(f"⚠️ *Revisión Manual necesaria:* {datos['asunto']}")
            label_final = id_etiq_rev

        # Intentamos etiquetar en Gmail (el log nos protege de fallos aquí)
        try:
            gmail.users().messages().modify(
                userId="me", id=m_id, body={"addLabelIds": [label_final]}
            ).execute()
        except Exception as e:
            logging.error(f"Error al poner etiqueta en Gmail para {m_id}: {e}")

        time.sleep(2)  # Rate limiting para Sheets API


if __name__ == "__main__":
    ejecutar_asistente()
