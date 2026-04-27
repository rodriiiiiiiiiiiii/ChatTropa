import time
from collections import defaultdict

class GoogleSheetsManager:
    def __init__(self, gspread_client, spreadsheet_name):
        self.gc = gspread_client
        self.libro = self.gc.open(spreadsheet_name)
        self.hoja_asistencia = self.libro.worksheet("ASISTENCIA")

    def obtener_datos_maestros(self):
        """Retorna lista de scouts y eventos válidos."""
        nombres = [n for n in self.hoja_asistencia.col_values(1)[2:] if n.strip()]
        eventos = [e for e in self.hoja_asistencia.row_values(2)[1:] if e.strip()]
        return nombres, eventos

    def obtener_mapeo_correos(self):
        """Construye el diccionario de correo -> [scouts]."""
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
        except Exception as e:
            print(f"[AVISO] Pestaña CORREOS no encontrada o inaccesible: {e}")
        return mapa

    def actualizar_asistencia(self, nombre_scout, evento, valor):
        """Marca la celda correspondiente. Retorna True si tuvo éxito."""
        try:
            # Re-obtenemos para evitar desajustes de índices si la hoja cambia
            nombres = self.hoja_asistencia.col_values(1)
            eventos = self.hoja_asistencia.row_values(2)
            
            fila = nombres.index(nombre_scout) + 1
            columna = eventos.index(evento) + 1
            
            self.hoja_asistencia.update_cell(fila, columna, valor)
            return True
        except (ValueError, Exception) as e:
            print(f"[ERROR SHEETS] No se pudo actualizar a {nombre_scout}: {e}")
            return False