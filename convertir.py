import base64

def convertir_a_base64(nombre_archivo):
    with open(nombre_archivo, "rb") as archivo:
        codificado = base64.b64encode(archivo.read()).decode("utf-8")
        print(f"\n--- Copia todo el texto debajo de esta línea para {nombre_archivo} ---\n")
        print(codificado)
        print("\n--------------------------------------------------\n")

# Asegúrate de tener token.json y credentials.json en la misma carpeta
convertir_a_base64("credentials.json")
convertir_a_base64("token.json")