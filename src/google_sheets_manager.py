import logging
from collections import defaultdict
from typing import List, Tuple, Dict, Any, Set


class GoogleSheetsManager:
    """
    Gestiona la interacción con Google Sheets, centralizando la lectura de
    datos maestros, el registro de logs de procesamiento y la actualización de asistencia.
    """

    def __init__(self, gspread_client: Any, spreadsheet_name: str) -> None:
        """
        Inicializa el cliente de Sheets y carga la caché de IDs procesados.
        """
        self.gc = gspread_client
        self.libro = self.gc.open(spreadsheet_name)
        self.hoja_asistencia = self.libro.worksheet("ASISTENCIA")
        self.hoja_log = self.libro.worksheet("LOG_PROCESADOS")

        # Cargamos los IDs en un set para búsqueda O(1)
        self._cache_procesados: Set[str] = self._cargar_log_procesados()

    def _cargar_log_procesados(self) -> Set[str]:
        """
        Lee la columna A de la hoja LOG_PROCESADOS para obtener los IDs ya gestionados.
        """
        try:
            # Obtiene todos los valores de la primera columna
            ids = self.hoja_log.col_values(1)
            logging.info(
                f"Cargados {len(ids)} IDs de correos procesados anteriormente."
            )
            return set(ids)
        except Exception as e:
            logging.error(f"Error al cargar el historial de LOG_PROCESADOS: {e}")
            return set()

    def esta_procesado(self, message_id: str) -> bool:
        """
        Comprueba si un ID de mensaje ya ha sido registrado en el sistema.
        """
        return message_id in self._cache_procesados

    def registrar_procesado(self, message_id: str) -> None:
        """
        Registra un nuevo ID en la hoja de Google Sheets y en la caché local.
        """
        try:
            self.hoja_log.append_row([message_id])
            self._cache_procesados.add(message_id)
            logging.info(f"ID {message_id} registrado como procesado con éxito.")
        except Exception as e:
            logging.error(
                f"Error crítico al registrar el ID {message_id} en Sheets: {e}"
            )

    def obtener_datos_maestros(self) -> Tuple[List[str], List[str]]:
        """
        Retorna los nombres de los scouts (Columna A) y los nombres de eventos (Fila 2).
        """
        nombres = [n for n in self.hoja_asistencia.col_values(1)[2:] if n.strip()]
        eventos = [e for e in self.hoja_asistencia.row_values(2)[1:] if e.strip()]
        return nombres, eventos

    def obtener_mapeo_correos(self) -> Dict[str, List[str]]:
        """
        Crea un diccionario donde cada email de padre apunta a una lista de sus hijos.
        """
        mapa = defaultdict(list)
        try:
            hoja_correos = self.libro.worksheet("CORREOS")
            datos = hoja_correos.get_all_values()
            for fila in datos:
                if len(fila) >= 2:
                    nombre_scout = fila[0].strip()
                    for email in fila[1:]:
                        if email.strip():
                            mapa[email.strip().lower()].append(nombre_scout)
        except Exception:
            logging.warning(
                "No se pudo leer la pestaña CORREOS. Se usará fallback por texto."
            )
        return dict(mapa)

    def actualizar_asistencia(self, nombre_scout: str, evento: str, valor: str) -> bool:
        """
        Encuentra la celda correcta y marca la asistencia (Sí/No).
        """
        try:
            nombres = self.hoja_asistencia.col_values(1)
            eventos = self.hoja_asistencia.row_values(2)

            fila = nombres.index(nombre_scout) + 1
            columna = eventos.index(evento) + 1

            self.hoja_asistencia.update_cell(fila, columna, valor)
            return True
        except (ValueError, Exception) as e:
            logging.error(
                f"Error al escribir asistencia para {nombre_scout} en {evento}: {e}"
            )
            return False
