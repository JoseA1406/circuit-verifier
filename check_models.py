import google.generativeai as genai
import toml

try:
    # Cargar API Key
    secrets = toml.load(".streamlit/secrets.toml")
    api_key = secrets["general"]["gemini_api_key"]
    genai.configure(api_key=api_key)

    print("--- Modelos Disponibles para tu API Key ---")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Nombre: {m.name}")
            
except Exception as e:
    print(f"Error al listar modelos: {e}")
