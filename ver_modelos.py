import os
import requests
from dotenv import load_dotenv

# Cargar tu API Key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ ERROR: No encuentro la API Key en el .env")
    exit()

print("🔍 Preguntando a Google qué modelos tienes disponibles...\n")

# Llamada a la API ListModels
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
respuesta = requests.get(url)

if respuesta.status_code == 200:
    datos = respuesta.json()
    modelos = datos.get('models', [])
    
    print("✅ MODELOS DISPONIBLES PARA GENERAR TEXTO:")
    print("-" * 50)
    for m in modelos:
        # Filtramos solo los que sirven para lo que queremos (generateContent)
        metodos = m.get('supportedGenerationMethods', [])
        if 'generateContent' in metodos:
            # Quitamos el prefijo 'models/' para que veas el nombre exacto
            nombre_limpio = m['name'].replace('models/', '')
            print(f"👉 {nombre_limpio}")
            print(f"   Descripción: {m.get('description', 'Sin descripción')}")
            print("-" * 50)
else:
    print(f"❌ Error al consultar la API: {respuesta.status_code}")
    print(respuesta.text)