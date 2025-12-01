import google.generativeai as genai
import toml
from PIL import Image
import io
import json

def initialize_ai():
    """Configura la API de Gemini desde secrets.toml."""
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        api_key = secrets["general"]["gemini_api_key"]
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"Error AI Init: {e}")
        return False

def start_auditor_session(page_text, page_image_bytes, chapter_index=None):
    """
    Inicia una sesión de chat con contexto HÍBRIDO (Índice Global + Página Local).
    """
    
    # Serializar el índice para que la IA lo entienda
    index_str = "No disponible"
    if chapter_index:
        # Convertimos a JSON formateado para claridad
        index_str = json.dumps(chapter_index, indent=2, ensure_ascii=False)

    system_instruction = f"""
    Eres "CircuitAI", un Asistente Académico Avanzado con dos roles principales:

    ROL 1: NAVEGADOR (Acceso Global)
    Tienes acceso al ÍNDICE COMPLETO del libro en formato JSON:
    {index_str}
    
    Si el usuario pregunta por un tema (ej: "Localiza Potencia CA", "¿Dónde habla de OpAmps?"):
    1.  Analiza el índice JSON.
    2.  Identifica el capítulo más relevante.
    3.  Responde indicando el capítulo y la página de inicio.
    4.  IMPORTANTE: Si encuentras una página destino clara, termina tu respuesta con este tag exacto:
        [[IR_A_PAGINA: <numero_pagina>]]
        (Ejemplo: "El tema está en el Cap 5. [[IR_A_PAGINA: 120]]")

    ROL 2: AUDITOR (Acceso Local)
    Tienes acceso visual y textual a la PÁGINA ACTUAL que el usuario está viendo.
    CONTEXTO DE TEXTO DE LA PÁGINA ACTUAL:
    {page_text[:4000]}... (truncado para eficiencia)

    Si el usuario pide validar un ejercicio o comparar su trabajo:
    1.  **ENFOQUE EN COMPONENTES:** Tu tarea principal es verificar el INVENTARIO DE COMPONENTES.
    2.  **NO ANALICES LA TOPOLOGÍA:** No intentes interpretar nodos, mallas, series o paralelos, ya que es propenso a errores visuales.
    3.  **COMPARACIÓN:** Verifica si la imagen del usuario contiene los mismos elementos con los mismos valores que la imagen del libro (ej: "¿Hay una fuente de 12V? ¿Hay una resistencia de 10kΩ?").
    4.  Si los valores y tipos de componentes coinciden, asume que es el ejercicio correcto y valida los resultados numéricos finales si están visibles.

    REGLA DE ORO:
    - Si la pregunta es "¿Dónde está X?", usa el ROL 1.
    - Si la pregunta es "¿Está bien este ejercicio?", usa el ROL 2 centrándote en los VALORES de los componentes.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        system_instruction=system_instruction
    )
    
    history = []
    
    # Inyectar la imagen de la página actual como contexto inicial del ROL 2
    if page_image_bytes:
        img = Image.open(io.BytesIO(page_image_bytes))
        history.append({
            "role": "user", 
            "parts": ["Esta es la IMAGEN de la página actual que estoy viendo. Úsala para el ROL de Auditor.", img]
        })
        history.append({
            "role": "model", 
            "parts": ["Entendido. Tengo el índice global para navegar y la imagen de esta página para auditar. ¿En qué te ayudo?"]
        })
    
    chat = model.start_chat(history=history)
    return chat

def extract_problem_signature(image_bytes):
    """
    Usa Gemini Vision para extraer una 'Firma Digital' del problema.
    Implementa 'Smart Scan': Si falla, rota la imagen y reintenta.
    """
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        original_img = Image.open(io.BytesIO(image_bytes))
        
        prompt = """
        ACTÚA COMO: Extractor de Datos OCR de Alta Precisión para Ingeniería.
        TAREA: Analiza este diagrama de circuito o problema.
        OBJETIVO: Extraer una lista de los valores alfanuméricos ÚNICOS y DISTINTIVOS.
        
        REGLAS DE EXTRACCIÓN:
        1. Extrae valores numéricos con sus unidades (ej: "12V", "4.7k", "100mH", "0.2F").
        2. Extrae nombres de variables únicas (ej: "Vx", "Io", "Vth", "3vx").
        3. IGNORA texto genérico.
        4. IGNORA valores extremadamente comunes si están solos (ej: "0", "1").
        
        FORMATO DE SALIDA:
        Devuelve SOLO una lista de strings separados por comas. NADA MÁS.
        """
        
        # Función auxiliar para llamar al modelo
        def scan_image(img_obj):
            try:
                response = model.generate_content([prompt, img_obj])
                text = response.text.strip()
                # Limpieza básica
                return [x.strip() for x in text.split(',') if x.strip()]
            except:
                return []

        # INTENTO 1: Orientación Original
        signature = scan_image(original_img)
        
        if signature:
            return signature
            
        # INTENTO 2: Rotación 90° (Sentido Horario - Típico de fotos móviles)
        # print("⚠️ Firma débil. Activando Smart Scan (Rotación 90°)...")
        rotated_img = original_img.rotate(-90, expand=True)
        signature = scan_image(rotated_img)
        
        if signature:
            return signature

        # INTENTO 3: Rotación 90° (Sentido Anti-horario - Por si acaso)
        rotated_img_2 = original_img.rotate(90, expand=True)
        return scan_image(rotated_img_2)
        
    except Exception as e:
        print(f"Error en extracción de firma: {e}")
        return []

def send_message(chat_session, user_text, context_images=None):
    """
    Envía mensaje al auditor.
    Args:
        chat_session: Sesión de chat activa.
        user_text: Texto del usuario.
        context_images: Lista de bytes de imágenes (o una sola imagen en bytes) para analizar.
    """
    try:
        content = []
        if user_text:
            content.append(user_text)
            
        if context_images:
            # Normalizar a lista si es un solo objeto de bytes
            if isinstance(context_images, bytes):
                context_images = [context_images]
                
            for i, img_bytes in enumerate(context_images):
                img = Image.open(io.BytesIO(img_bytes))
                content.append(img)
                content.append(f"--- Adjunto {i+1}: Documento/Imagen del usuario ---")
            
        if not content:
            return "Por favor envía texto o adjunta un archivo."
            
        response = chat_session.send_message(content)
        return response.text
    except Exception as e:
        return f"Error de comunicación con la IA: {e}"
