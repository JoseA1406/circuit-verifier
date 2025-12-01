import fitz  # PyMuPDF
import re
import io
import os
from PIL import Image

def load_pdf(filepath):
    """
    Carga un documento PDF en memoria de manera segura.
    
    Args:
        filepath (str): Ruta absoluta al archivo PDF.
        
    Returns:
        fitz.Document: Objeto del documento si la carga es exitosa.
        None: Si ocurre un error.
    """
    if not os.path.exists(filepath):
        print(f"Error: El archivo no existe en la ruta: {filepath}")
        return None

    try:
        doc = fitz.open(filepath)
        print(f"Éxito: Documento cargado. Total páginas: {doc.page_count}")
        return doc
    except Exception as e:
        print(f"Error crítico al cargar el PDF: {e}")
        return None

def extract_page_data(doc, page_number):
    """
    Extrae texto e imagen de una página específica.
    
    Args:
        doc (fitz.Document): Objeto del documento cargado.
        page_number (int): Número de página (0-indexed).
        
    Returns:
        tuple: (text, image_bytes)
            - text (str): Texto crudo de la página.
            - image_bytes (bytes): Imagen renderizada en formato PNG.
            Retorna (None, None) si hay error.
    """
    try:
        # Validar rango de página
        if page_number < 0 or page_number >= doc.page_count:
            print(f"Error: Página {page_number} fuera de rango.")
            return None, None

        page = doc.load_page(page_number)
        
        # 1. Extraer texto
        text = page.get_text("text")
        
        # 2. Renderizar imagen (Zoom 2.0 para alta resolución)
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convertir a bytes (PNG) para uso en UI
        image_bytes = pix.tobytes("png")
        
        return text, image_bytes

    except Exception as e:
        print(f"Error al extraer datos de la página {page_number}: {e}")
        return None, None

def generate_chapter_index(doc):
    """
    Genera un índice de navegación (Capítulo -> Página).
    
    Estrategias:
    1. Metadatos internos (TOC).
    2. Búsqueda Regex en encabezados de página.
    3. Fallback: Bloques de 50 páginas.
    
    Args:
        doc (fitz.Document): Documento cargado.
        
    Returns:
        dict: { "Título Capítulo": int_pagina_inicio (0-indexed) }
    """
    chapter_map = {}
    
    # --- Estrategia 1: TOC Interno ---
    try:
        toc = doc.get_toc()
        if toc:
            print(f"Info: TOC interno detectado con {len(toc)} entradas.")
            for entry in toc:
                title = entry[1]
                page_num = entry[2]
                if page_num > 0:
                    chapter_map[title] = page_num - 1
            return chapter_map
        else:
            print("Info: El PDF no tiene TOC interno estructurado. Iniciando escaneo Regex...")
    except Exception as e:
        print(f"Advertencia: Falló la lectura del TOC interno: {e}")

    # --- Estrategia 2: Escaneo Regex ---
    print("Iniciando escaneo de patrones de capítulos (Regex)...")
    patterns = [r"^(Chapter|Capítulo)\s+\d+", r"^(Problems|Problemas)$"]
    compiled_patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
    
    try:
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text", clip=None, flags=0)[:1000]
            
            for pattern in compiled_patterns:
                match = pattern.search(text)
                if match:
                    title = match.group(0).strip()
                    if title not in chapter_map:
                        chapter_map[title] = page_num
                    break
        
        if chapter_map:
            print(f"Éxito: Se detectaron {len(chapter_map)} capítulos vía Regex.")
            return chapter_map
            
    except Exception as e:
        print(f"Error durante el escaneo Regex: {e}")

    # --- Estrategia 3: Fallback (Bloques de 50 páginas) ---
    print("Aviso: No se detectaron capítulos. Generando índice por bloques...")
    block_size = 50
    for i in range(0, doc.page_count, block_size):
        end_page = min(i + block_size, doc.page_count)
        label = f"Páginas {i+1} - {end_page}"
        chapter_map[label] = i
        
    return chapter_map

if __name__ == "__main__":
    # Bloque de prueba para ejecución directa
    print("--- Test de Backend ---")
    # Simulación: Intenta cargar un PDF si existe en la carpeta actual
    test_files = [f for f in os.listdir('.') if f.endswith('.pdf')]
    if test_files:
        test_path = os.path.abspath(test_files[0])
        print(f"Probando con archivo: {test_path}")
        
        doc = load_pdf(test_path)
        if doc:
            index = generate_chapter_index(doc)
            print("Índice generado:", list(index.keys())[:5]) # Mostrar primeros 5
            
            txt, img = extract_page_data(doc, 0)
            print(f"Extracción Pág 0: Texto ({len(txt)} chars), Imagen ({len(img)} bytes)")
            doc.close()
    else:
        print("No se encontraron archivos PDF en el directorio para probar.")
