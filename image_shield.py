import cv2
import numpy as np
import re
import io
from PIL import Image

def detect_blur(image_bytes, threshold=100.0):
    """
    Detecta si una imagen está borrosa usando la varianza del Laplaciano.
    Retorna: (is_blurry: bool, score: float)
    Score < 100 suele indicar borrosidad.
    """
    try:
        # Convertir bytes a array numpy
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if img is None:
            return False, 0.0

        # Calcular varianza del Laplaciano
        score = cv2.Laplacian(img, cv2.CV_64F).var()
        is_blurry = score < threshold
        
        return is_blurry, score
    except Exception as e:
        print(f"Error en detect_blur: {e}")
        return False, 999.0

def clean_image(image_bytes):
    """
    Aplica pre-procesamiento avanzado para mejorar OCR:
    1. Escala de grises
    2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    3. Thresholding adaptativo suave
    Retorna: bytes de la imagen procesada (PNG)
    """
    try:
        # 1. Decodificar
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return image_bytes # Retornar original si falla

        # 2. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. CLAHE (Mejora contraste local)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 4. Thresholding (Opcional: Binarización suave para resaltar texto)
        # Usamos Adaptive Gaussian Thresholding que maneja bien iluminación irregular
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Mezclar un poco con la original mejorada para no perder detalles finos
        # (A veces el binario puro rompe letras delgadas)
        final_img = cv2.addWeighted(enhanced, 0.7, binary, 0.3, 0)

        # 5. Codificar de vuelta a bytes
        is_success, buffer = cv2.imencode(".png", final_img)
        if is_success:
            return buffer.tobytes()
        else:
            return image_bytes
            
    except Exception as e:
        print(f"Error en clean_image: {e}")
        return image_bytes

def sanitize_ocr(ocr_list):
    """
    Limpia y normaliza la lista de valores extraídos por la IA.
    Corrige errores comunes de OCR y normaliza unidades.
    """
    cleaned_list = []
    
    # Mapeo de correcciones comunes
    replacements = {
        r'l0': '10',  # l0V -> 10V
        r'O': '0',    # 5O -> 50 (si parece número)
        r'uF': 'µF',
        r'uf': 'µF',
        r'microF': 'µF',
        r'ohm': 'Ω',
        r'Ohm': 'Ω'
    }
    
    for item in ocr_list:
        item = item.strip()
        if not item:
            continue
            
        # Aplicar reemplazos
        for pattern, repl in replacements.items():
            # Reemplazo simple si es match exacto o parcial seguro
            if pattern in ['uF', 'uf', 'microF', 'ohm', 'Ohm']:
                item = item.replace(pattern, repl)
            else:
                # Para l0 -> 10, usar regex para evitar falsos positivos
                if pattern == 'l0':
                    item = re.sub(r'l0(?=[A-Za-z])', '10', item) # l0 seguido de letra (l0V)
        
        cleaned_list.append(item)
        
    return list(set(cleaned_list)) # Eliminar duplicados
