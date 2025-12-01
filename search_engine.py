import re
import fitz  # PyMuPDF

try:
    import backend
except ImportError:
    pass

def build_flexible_regex(keyword):
    """
    Convierte una keyword simple (ej: '10k') en una Regex flexible.
    """
    keyword = keyword.strip()
    match = re.match(r"^([\d\.]+)([a-zA-Z%]+)$", keyword)
    
    if match:
        number_part = match.group(1)
        unit_part = match.group(2)
        number_part = number_part.replace('.', r'\.')
        pattern = f"{number_part}\\s*{unit_part}"
        return pattern
    else:
        return re.escape(keyword)

def normalize_text(text):
    """
    Limpia y normaliza el texto extraído.
    """
    if not text:
        return ""
    text = text.replace('\n', ' ').replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_circuit_components(text):
    """
    Extrae valores con unidades eléctricas del texto para verificación.
    Patrón: Número + Espacio(opcional) + Unidad (V, A, Ω, etc.)
    """
    if not text:
        return []
        
    # Regex para capturar valores: 
    # \d+\.?\d*  -> Número (entero o decimal)
    # \s*        -> Espacio opcional
    # (...)      -> Grupo de unidades comunes en circuitos
    # Nota: Incluimos variaciones comunes.
    pattern = r"(\d+\.?\d*)\s*(V|A|Ω|kΩ|mΩ|MΩ|H|mH|µH|F|µF|nF|pF|Hz|kHz|MHz|W|kW)"
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    # Formatear resultados como lista de strings "10 kΩ"
    components = []
    for val, unit in matches:
        components.append(f"{val}{unit}")
        
    return list(set(components)) # Eliminar duplicados

def calculate_page_score(page_text, compiled_patterns):
    """
    Calcula el score de relevancia de una página basado en coincidencias únicas.
    """
    if not page_text:
        return 0.0
        
    matches_found = 0
    total_keywords = len(compiled_patterns)
    
    if total_keywords == 0:
        return 0.0

    for pattern in compiled_patterns:
        if pattern.search(page_text):
            matches_found += 1
            
    score = (matches_found / total_keywords) * 100.0
    return score

def search_by_unique_values(doc, keywords_list, page_range=None):
    """
    Busca páginas que contengan múltiples valores clave simultáneamente.
    
    Args:
        doc (fitz.Document): Documento PDF cargado.
        keywords_list (list): Lista de strings a buscar (ej: ['10k', '12V']).
        page_range (tuple, optional): (start_page, end_page) indices 0-based. 
                                      Si es None, busca en todo el documento.
        
    Returns:
        list: Lista de tuplas (page_number, score) ordenada por relevancia.
    """
    results = []
    
    if not doc or not keywords_list:
        return []

    # 1. Preparar Regexes
    regex_strings = [build_flexible_regex(k) for k in keywords_list]
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in regex_strings]
    
    # Definir rango de iteración
    start_p = 0
    end_p = doc.page_count
    
    if page_range:
        start_p = max(0, page_range[0])
        end_p = min(doc.page_count, page_range[1])
        print(f"Buscando en rango restringido: {start_p} a {end_p}")
    else:
        print(f"Buscando en todo el documento: {doc.page_count} páginas")
    
    # 2. Iterar sobre páginas
    for page_num in range(start_p, end_p):
        try:
            page = doc.load_page(page_num)
            raw_text = page.get_text("text")
            clean_text = normalize_text(raw_text)
            score = calculate_page_score(clean_text, compiled_patterns)
            
            if score > 0:
                results.append((page_num, score))
                
        except Exception as e:
            print(f"Error procesando página {page_num}: {e}")
            continue

    results.sort(key=lambda x: x[1], reverse=True)
    return results

if __name__ == "__main__":
    # Bloque de prueba simplificado
    pass
