import streamlit as st
import backend
import search_engine
import ai_chat
import converter
import image_shield # Módulo de Robustez
import os
import tempfile
import pandas as pd
import importlib
import re

# Forzar recarga de módulos críticos para desarrollo en caliente
importlib.reload(backend)
importlib.reload(search_engine)
importlib.reload(ai_chat)
importlib.reload(converter)
importlib.reload(image_shield)

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Circuit Verifier",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FASE 1: Gestión de Estado (Reset) ---
def reset_state():
    """Limpia el estado de la sesión al cambiar de archivo."""
    keys_to_reset = ['doc', 'chapter_index', 'search_results', 'current_page', 'chat_session', 'messages']
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

# --- FASE 2: Capa de Caché (Optimización) ---
@st.cache_resource
def load_cached_pdf(file_path):
    """Carga el PDF y lo mantiene en memoria caché (RAM)."""
    return backend.load_pdf(file_path)

@st.cache_data
def get_cached_chapter_index(_doc, doc_name):
    """
    Genera el índice de capítulos y lo guarda en caché.
    IMPORTANTE: 'doc_name' se usa como llave de caché para diferenciar documentos.
    """
    return backend.generate_chapter_index(_doc)

@st.cache_data
def convert_file_cached(file_path, suffix):
    """Cachea la conversión de archivos pesados."""
    return converter.convert_to_pdf(file_path, suffix)

# --- Inicializar IA ---
ai_ready = ai_chat.initialize_ai()

# --- Estilos CSS Personalizados (Dark Glassmorphism Theme) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

    /* 1. Global Reset & Font */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* 2. App Background (Deep Dark) */
    .stApp {
        background-color: #121212;
        color: #e0e0e0;
    }

    /* 3. Headers */
    h1, h2, h3, .stHeader {
        color: #ffffff !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px;
    }

    /* 4. Sidebar (Clean Navigation) */
    section[data-testid="stSidebar"] {
        background-color: #181818;
        border-right: 1px solid #2d2d2d;
    }

    /* 5. Custom Card Class (Glassmorphism Panel) */
    .stCard {
        background-color: #1e1e1e;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 1.5rem;
        border: 1px solid #333;
    }

    /* 6. Buttons (Neon Blue Accent) */
    .stButton > button {
        background-color: rgba(0, 123, 255, 0.1);
        color: #007bff;
        border: 1px solid #007bff;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        padding: 0.5rem 1rem;
    }
    .stButton > button:hover {
        background-color: #007bff;
        color: white;
        box-shadow: 0 0 20px rgba(0, 123, 255, 0.4);
        transform: translateY(-2px);
        border-color: #007bff;
    }

    /* 7. Inputs (Floating Pill Style) */
    .stTextInput > div > div > input {
        border-radius: 50px;
        background-color: #252525;
        border: 1px solid #444;
        color: white;
        padding: 12px 25px;
        transition: border-color 0.3s;
    }
    .stTextInput > div > div > input:focus {
        border-color: #007bff;
        box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
    }

    /* 8. Hide Native Elements for Pro Look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 9. Selectbox & Tabs */
    .stSelectbox > div > div {
        background-color: #252525;
        border-radius: 12px;
        border: 1px solid #444;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1e1e1e;
        border-radius: 10px 10px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #252525;
        color: #007bff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Estado de la Sesión ---
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'doc' not in st.session_state:
    st.session_state.doc = None
if 'chapter_index' not in st.session_state:
    st.session_state.chapter_index = None
if 'filename' not in st.session_state:
    st.session_state.filename = ""
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# --- Lógica de Rangos de Capítulos ---
def get_chapter_range(chapter_name, index, total_pages):
    if not index or chapter_name not in index:
        return None
    
    start_page = index[chapter_name]
    
    # Encontrar la siguiente página de inicio para saber dónde termina este capítulo
    sorted_starts = sorted(index.values())
    try:
        current_idx = sorted_starts.index(start_page)
        if current_idx + 1 < len(sorted_starts):
            end_page = sorted_starts[current_idx + 1]
        else:
            end_page = total_pages
    except ValueError:
        end_page = total_pages
        
    return (start_page, end_page)

# --- SIDEBAR: Panel de Control ---
with st.sidebar:
    st.title("📚 Circuitos\nVerificador")
    st.markdown("---")
    
    tab_load, tab_search_img = st.tabs(["📂 Libro", "🕵️ Buscar IMG"])
    
    with tab_load:
        # Widget de carga con Callback de limpieza y Key Dinámica
        uploaded_file = st.file_uploader(
            "Cargar Archivo Base", 
            type=["pdf", "png", "jpg", "jpeg", "docx", "xlsx"],
            on_change=reset_state,
            key=f"uploader_{st.session_state.uploader_key}"
        )

        if uploaded_file:
            # Usamos el nombre del archivo como clave para detectar cambios reales
            if st.session_state.doc is None or uploaded_file.name != st.session_state.filename:
                with st.spinner("Procesando archivo..."):
                    # 1. Guardar archivo original temporalmente
                    suffix = "." + uploaded_file.name.split('.')[-1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    # 2. Convertir a PDF (Usando Caché)
                    final_pdf_path = tmp_path
                    if suffix.lower() not in ['.pdf']:
                        with st.spinner(f"Convirtiendo {suffix} a PDF estandarizado..."):
                            final_pdf_path = convert_file_cached(tmp_path, suffix)
                    
                    if final_pdf_path:
                        # 3. Cargar Backend (Usando Caché)
                        doc = load_cached_pdf(final_pdf_path)
                        if doc:
                            st.session_state.doc = doc
                            st.session_state.filename = uploaded_file.name
                            # 4. Generar Índice (Usando Caché)
                            st.session_state.chapter_index = get_cached_chapter_index(doc, uploaded_file.name)
                            st.success(f"✅ Listo: {doc.page_count} páginas")
                        else:
                            st.error("Error al leer el documento procesado.")
                    else:
                        st.error("Formato no soportado o error de conversión.")

    with tab_search_img:
        st.markdown("### 📸 Búsqueda Inversa (Blindada)")
        st.info("Sube una foto del ejercicio para localizarlo en el libro.")
        
        if st.session_state.doc is None:
            st.warning("Primero carga un libro en la pestaña anterior.")
        else:
            search_img = st.file_uploader("Subir Recorte", type=["png", "jpg", "jpeg"], key="search_img_uploader")
            
            if search_img:
                # 1. Análisis de Calidad (Blur Detection)
                img_bytes = search_img.getvalue()
                is_blurry, blur_score = image_shield.detect_blur(img_bytes)
                
                col_qual, col_proc = st.columns(2)
                with col_qual:
                    st.caption(f"Nitidez: {int(blur_score)}")
                    if is_blurry:
                        st.warning("⚠️ Imagen borrosa. Resultados inciertos.")
                    else:
                        st.success("✅ Imagen nítida.")
                
                if st.button("🔍 Escanear y Buscar"):
                    with st.spinner("Aplicando filtros de visión artificial..."):
                        # 2. Limpieza de Imagen (CLAHE)
                        clean_bytes = image_shield.clean_image(img_bytes)
                        
                        # Mostrar imagen procesada (Debug visual para el usuario)
                        with col_proc:
                            st.image(clean_bytes, caption="Visión de la IA", width=150)

                    with st.spinner("Extrayendo firma digital del circuito..."):
                        # 3. Extraer firma con IA (usando imagen limpia)
                        raw_signature = ai_chat.extract_problem_signature(clean_bytes)
                        
                        # 4. Sanitización de Datos
                        signature = image_shield.sanitize_ocr(raw_signature)
                        
                    if signature:
                        st.success(f"Firma detectada: {signature}")
                        
                        with st.spinner(f"Buscando {len(signature)} huellas en el libro..."):
                            # 5. Buscar en el libro
                            results = search_engine.search_by_unique_values(
                                st.session_state.doc, 
                                signature
                            )
                            st.session_state.search_results = results
                            
                            if results:
                                best_page = results[0][0]
                                score = results[0][1]
                                st.session_state.current_page = best_page
                                st.balloons()
                                st.success(f"¡Encontrado! Pág {best_page+1} (Coincidencia: {int(score)}%)")
                                st.rerun()
                            else:
                                st.error("No se encontró ninguna página con esos valores.")
                    else:
                        st.error("No se pudieron detectar valores legibles en la imagen.")

    # Filtro de Capítulos
    selected_range = None
    if st.session_state.doc and st.session_state.chapter_index:
        st.markdown("### 🎯 Filtro de Búsqueda")
        chapter_names = ["Todo el Libro"] + list(st.session_state.chapter_index.keys())
        selected_chapter = st.selectbox("Limitar búsqueda a:", chapter_names)
        
        if selected_chapter != "Todo el Libro":
            selected_range = get_chapter_range(selected_chapter, st.session_state.chapter_index, st.session_state.doc.page_count)
            if selected_range:
                st.caption(f"Rango: Pág {selected_range[0]+1} - {selected_range[1]}")

    # --- FASE 4: Botón de Hard Reset ---
    st.markdown("---")
    if st.button("🗑️ Limpiar Todo"):
        # 1. Guardar la siguiente clave para forzar un uploader nuevo
        new_key = st.session_state.uploader_key + 1
        
        # 2. Borrar ABSOLUTAMENTE TODO de la memoria
        st.session_state.clear()
        
        # 3. Restaurar solo la clave necesaria para el reinicio limpio
        st.session_state.uploader_key = new_key
        
        # 4. Reiniciar la app
        st.rerun()

# --- MAIN LAYOUT: Asimétrico 1:2 ---
st.markdown("## ⚡ Dashboard de Auditoría")

col_left, col_right = st.columns([1, 2])

# --- COLUMNA IZQUIERDA: Inputs y Control ---
with col_left:
    st.markdown("### 🛠️ Parámetros")
    
    if st.session_state.doc is None:
        st.info("👈 Carga un PDF para activar los controles.")
    else:
        with st.form("search_form"):
            query = st.text_input("Valores Clave", placeholder="Ej: 10k, 12V, 0.5A")
            st.caption("Separa los valores por comas.")
            
            search_submitted = st.form_submit_button("🔍 LOCALIZAR EJERCICIO")
            
        if search_submitted and query:
            keywords = [k.strip() for k in query.split(',') if k.strip()]
            if keywords:
                with st.spinner("Triangulando ejercicio..."):
                    # Ejecutar búsqueda con o sin rango
                    results = search_engine.search_by_unique_values(
                        st.session_state.doc, 
                        keywords, 
                        page_range=selected_range
                    )
                    st.session_state.search_results = results
                    
                    if not results:
                        st.warning("No se encontraron coincidencias.")
                    else:
                        # Auto-seleccionar el mejor resultado
                        st.session_state.current_page = results[0][0]

# --- COLUMNA DERECHA: Display y Resultados ---
with col_right:
    if st.session_state.doc:
        # 1. Visor de Resultados (Lista Horizontal Rápida)
        if st.session_state.search_results:
            st.markdown(f"### 🎯 Resultados ({len(st.session_state.search_results)})")
            
            # Scroll horizontal de botones para resultados
            res_cols = st.columns(min(5, len(st.session_state.search_results)))
            for i, (p_num, score) in enumerate(st.session_state.search_results[:5]):
                with res_cols[i]:
                    label = f"Pág {p_num+1}"
                    if st.button(f"{label}\n{int(score)}%", key=f"btn_res_{i}"):
                        st.session_state.current_page = p_num

        st.markdown("---")

        # 2. La Fuente de la Verdad (Tarjeta de Verdad)
        st.markdown('<div class="stCard">', unsafe_allow_html=True) # <--- INICIO TARJETA
        st.markdown(f"### ✅ Ejercicio en Página {st.session_state.current_page + 1}")
        
        # Renderizado y Extracción
        txt, img_bytes = backend.extract_page_data(st.session_state.doc, st.session_state.current_page)
        
        # Componente 1: Tabla de Verificación Automática
        detected_components = search_engine.extract_circuit_components(txt)
        if detected_components:
            with st.expander("📋 Verificación de Componentes (Detectados)", expanded=True):
                # Crear DataFrame simple para visualización limpia
                df_comps = pd.DataFrame(detected_components, columns=["Valor Detectado"])
                st.dataframe(df_comps, use_container_width=True, hide_index=True)
        else:
            st.info("No se detectaron componentes eléctricos estándar en el texto.")

        # Componente 2: Evidencia Visual
        if img_bytes:
            st.image(img_bytes, caption="Fuente de la Verdad: Resultado Oficial", use_column_width=True)
        else:
            st.error("Error de renderizado.")
            
        # Navegación manual local
        st.markdown("---")
        c_prev, c_next = st.columns(2)
        with c_prev:
            if st.button("⬅️ Anterior"):
                if st.session_state.current_page > 0:
                    st.session_state.current_page -= 1
                    st.rerun()
        with c_next:
            if st.button("Siguiente ➡️"):
                if st.session_state.current_page < st.session_state.doc.page_count - 1:
                    st.session_state.current_page += 1
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True) # <--- FIN TARJETA

        # --- SECCIÓN: AUDITORÍA CON IA ---
        if ai_ready:
            st.markdown("---")
            with st.expander("💬 Auditoría con IA (Gemini 1.5 Flash)", expanded=False):
                # Inicializar chat si no existe o si cambió la página
                if "chat_session" not in st.session_state or st.session_state.get("last_page_context") != st.session_state.current_page:
                    with st.spinner("Conectando con el Auditor..."):
                        st.session_state.chat_session = ai_chat.start_auditor_session(
                            txt, 
                            img_bytes,
                            st.session_state.chapter_index # Inyectamos el índice global
                        )
                        st.session_state.last_page_context = st.session_state.current_page
                        st.session_state.messages = []

                # Mostrar historial con botones de acción interactivos
                for i, msg in enumerate(st.session_state.messages):
                    st.chat_message(msg["role"]).write(msg["content"])
                    
                    # Detectar tag de navegación en mensajes del asistente
                    if msg["role"] == "assistant":
                        match = re.search(r"\[\[IR_A_PAGINA:\s*(\d+)\]\]", msg["content"])
                        if match:
                            target_page = int(match.group(1))
                            # Key única para que cada botón funcione independientemente
                            btn_key = f"nav_btn_{i}_{target_page}"
                            if st.button(f"🚀 Saltar a Pág {target_page}", key=btn_key):
                                st.session_state.current_page = target_page - 1 # Ajuste 0-indexed
                                st.rerun()

                # Input del Usuario
                user_input = st.chat_input("Pregunta al auditor o valida tu resultado...")
                
                # Widget de carga de contexto adicional
                uploaded_proof = st.file_uploader(
                    "📎 Adjuntar ejercicio o documento (PDF, Word, Excel, Imagen)", 
                    type=["png", "jpg", "jpeg", "pdf", "docx", "xlsx"], 
                    key="chat_doc_upload"
                )
                
                if user_input:
                    # Mostrar mensaje usuario inmediatamente
                    msg_data = {"role": "user", "content": user_input}
                    
                    # Procesar archivo adjunto si existe
                    processed_images = []
                    if uploaded_proof:
                        with st.spinner("Procesando documento adjunto..."):
                            # 1. Guardar temporalmente
                            suffix = "." + uploaded_proof.name.split('.')[-1]
                            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                                tmp_path = tmp_file.name
                            
                            # Escribir contenido
                            with open(tmp_path, "wb") as f:
                                f.write(uploaded_proof.getvalue())

                            # 2. Convertir a PDF si no es imagen directa
                            final_pdf_path = None
                            if suffix.lower() in ['.png', '.jpg', '.jpeg']:
                                processed_images.append(uploaded_proof.getvalue())
                                msg_data["image"] = uploaded_proof.getvalue() # Mostrar en chat local
                            else:
                                # Convertir Docs/Excel/PDF a PDF estandarizado
                                final_pdf_path = tmp_path
                                if suffix.lower() not in ['.pdf']:
                                    final_pdf_path = converter.convert_to_pdf(tmp_path, suffix)
                                
                                # 3. Renderizar primera página del PDF a imagen para la IA
                                if final_pdf_path:
                                    doc_temp = backend.load_pdf(final_pdf_path)
                                    if doc_temp:
                                        _, page_img = backend.extract_page_data(doc_temp, 0)
                                        if page_img:
                                            processed_images.append(page_img)
                                            msg_data["image"] = page_img # Mostrar render en chat local
                            
                    st.session_state.messages.append(msg_data)
                    
                    with st.chat_message("user"):
                        st.write(user_input)
                        if "image" in msg_data:
                            st.image(msg_data["image"], width=200, caption="Documento Adjunto")

                    # Enviar a Gemini
                    with st.spinner("El auditor está analizando tu documento..."):
                        response_text = ai_chat.send_message(
                            st.session_state.chat_session, 
                            user_input, 
                            processed_images
                        )
                        
                        # Guardar y mostrar respuesta
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
                        st.rerun()
    else:
        # Placeholder visual cuando no hay doc
        st.markdown("""
        <div style='text-align: center; padding: 50px; color: #555;'>
            <h3>Esperando Documento...</h3>
            <p>El visualizador se activará automáticamente.</p>
        </div>
        """, unsafe_allow_html=True)
