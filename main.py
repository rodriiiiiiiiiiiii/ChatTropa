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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def extraer_email_puro(remitente_raw: str) -> str:
    match = re.search(r"[\w\.-]+@[\w\.-]+", remitente_raw)
    return match.group(0).lower() if match else remitente_raw.lower()


def es_spam_tecnico(asunto: str, remitente: str) -> bool:
    asunto_l, remit_l = asunto.lower(), remitente.lower()
    return any(s in asunto_l for s in BLACKLIST_SUBJECTS) or any(
        r in remit_l for r in BLACKLIST_SENDERS
    )


def obtener_id_etiqueta(servicio_gmail, nombre_etiqueta: str) -> str:
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
    logging.info("Iniciando ciclo de Chat Tropa...")
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    gc = gspread.authorize(creds)
    gmail = build("gmail", "v1", credentials=creds)

    gs_manager = GoogleSheetsManager(gc, "Asistencia_pruebas_IA")
    nombres_master, eventos_master = gs_manager.obtener_datos_maestros()
    mapa_correos = gs_manager.obtener_mapeo_correos()

    id_etiq_bot = obtener_id_etiqueta(gmail, "Procesado_IA")
    id_etiq_rev = obtener_id_etiqueta(gmail, "Revision_Manual")

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
        if gs_manager.esta_procesado(m_id):
            continue

        m_full = gmail.users().messages().get(userId="me", id=m_id).execute()
        datos = decodificar_correo(m_full)
        if not datos:
            continue

        if es_spam_tecnico(datos["asunto"], datos["remitente"]):
            gs_manager.registrar_procesado(m_id)
            gmail.users().messages().modify(
                userId="me", id=m_id, body={"addLabelIds": [id_etiq_bot]}
            ).execute()
            continue

        # --- LÓGICA DE IDENTIDAD (TUS CAMBIOS) ---
        email_limpio = extraer_email_puro(datos["remitente"])
        nombres_para_ia = mapa_correos.get(email_limpio)
        remitente_desconocido = False

        if not nombres_para_ia:
            # Fallback: Buscar por primer nombre si no tenemos el correo mapeado
            cuerpo_l = (datos["asunto"] + " " + datos["cuerpo"]).lower()
            nombres_para_ia = [
                n for n in nombres_master if n.split()[0].lower() in cuerpo_l
            ]
            remitente_desconocido = True

        if not nombres_para_ia:
            nombres_para_ia = (
                nombres_master  # Último recurso: pasarle todos (riesgo de alucinación)
            )

        # Análisis IA
        evento_local = next(
            (e for e in eventos_master if e.lower() in datos["asunto"].lower()), None
        )
        resultados = analizar_correo_unico(
            datos["raw"], nombres_para_ia, eventos_master, evento_local, active_keys
        )

        logging.info(f"📧 Asunto: {datos['asunto']} | 🤖 Respuesta IA: {resultados}")

        procesado_con_exito = False
        resumen_tg = []

        if isinstance(resultados, list):
            for res in resultados:
                if "error_api" in res:
                    break

                nombre = res.get("nombre")
                asistencia = res.get("asistencia")
                evento = res.get("evento") or evento_local
                comentario = res.get("comentario_relevante")

                if nombre:
                    procesado_con_exito = (
                        True  # Si Gemini entendió de quién hablamos, el pipeline fluye
                    )

                if nombre and asistencia and evento:
                    if gs_manager.actualizar_asistencia(nombre, evento, asistencia):
                        resumen_tg.append(f"✅ {nombre}: {asistencia}")

                if comentario:
                    avisar_telegram(
                        f"💬 *Duda de {nombre or 'familia'}:*\n_{comentario}_"
                    )

        if procesado_con_exito:
            if resumen_tg:
                avisar_telegram(
                    f"🏕️ *Actualización {evento_local or ''}*\n" + "\n".join(resumen_tg)
                )

            # Si el remitente es nuevo, avisamos para que lo registres en el Excel
            if remitente_desconocido and (resumen_tg or comentario):
                avisar_telegram(
                    f"👤 *Aviso:* Correo de {email_limpio} procesado pero no está en tu lista de 'CORREOS'."
                )

            gs_manager.registrar_procesado(m_id)
            label_final = id_etiq_bot
        else:
            cuerpo_corto = (
                datos["cuerpo"][:300] + "..."
                if len(datos["cuerpo"]) > 300
                else datos["cuerpo"]
            )

            mensaje_alerta = (
                f"⚠️ *Revisión Manual Necesaria*\n"
                f"👤 *De:* {datos['remitente']}\n"
                f"📧 *Asunto:* {datos['asunto']}\n"
                f"💬 *Mensaje:* _{cuerpo_corto}_"
            )

            avisar_telegram(mensaje_alerta)
            label_final = id_etiq_rev

        try:
            gmail.users().messages().modify(
                userId="me", id=m_id, body={"addLabelIds": [label_final]}
            ).execute()
        except Exception:
            pass

        time.sleep(2)


if __name__ == "__main__":
    ejecutar_asistente()
