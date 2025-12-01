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
    initial_sidebar_state="auto" # Auto-colapsar en móvil
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
    """Genera el índice de capítulos y lo guarda en caché."""
    return backend.generate_chapter_index(_doc)

@st.cache_data
def convert_file_cached(file_path, suffix):
    """Cachea la conversión de archivos pesados."""
    return converter.convert_to_pdf(file_path, suffix)

# --- Inicializar IA ---
ai_ready = ai_chat.initialize_ai()

# --- Estilos CSS Personalizados (Mobile-First Dark Glassmorphism) ---
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
        padding: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 1.5rem;
        border: 1px solid #333;
    }

    /* 6. Buttons (Neon Blue Accent & Touch Friendly) */
    .stButton > button {
        background-color: rgba(0, 123, 255, 0.1);
        color: #007bff;
        border: 1px solid #007bff;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        padding: 0.75rem 1rem; /* Más padding para dedos */
        min-height: 48px; /* Altura mínima táctil */
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
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        background-color: #1e1e1e;
        border-radius: 20px; /* Tabs redondeados tipo botón */
        border: 1px solid #333;
        padding: 0 20px;
        margin-right: 5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #007bff;
        color: white;
        border-color: #007bff;
    }

    /* --- MOBILE RESPONSIVE TWEAKS --- */
    @media only screen and (max-width: 768px) {
        /* Reducir padding del contenedor principal */
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        /* Títulos más pequeños */
        h1 { font-size: 1.8rem !important; }
        h2 { font-size: 1.5rem !important; }
        h3 { font-size: 1.2rem !important; }
        
        /* Tarjetas más compactas */
        .stCard {
            padding: 1rem;
            border-radius: 12px;
        }
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

# --- SIDEBAR: Configuración Global (Solo carga) ---
with st.sidebar:
    st.title("📚 Configuración")
    
    # Widget de carga
    uploaded_file = st.file_uploader(
        "Cargar Libro Base", 
        type=["pdf", "png", "jpg", "jpeg", "docx", "xlsx"],
        on_change=reset_state,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_file:
        if st.session_state.doc is None or uploaded_file.name != st.session_state.filename:
            with st.spinner("Procesando archivo..."):
                suffix = "." + uploaded_file.name.split('.')[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                final_pdf_path = tmp_path
                if suffix.lower() not in ['.pdf']:
                    with st.spinner(f"Convirtiendo {suffix}..."):
                        final_pdf_path = convert_file_cached(tmp_path, suffix)
                
                if final_pdf_path:
                    doc = load_cached_pdf(final_pdf_path)
                    if doc:
                        st.session_state.doc = doc
                        st.session_state.filename = uploaded_file.name
                        st.session_state.chapter_index = get_cached_chapter_index(doc, uploaded_file.name)
                        st.success(f"✅ Libro Cargado ({doc.page_count} págs)")
                    else:
                        st.error("Error al leer documento.")
                else:
                    st.error("Formato no soportado.")

    # Filtro de Capítulos (En Sidebar para no estorbar)
    selected_range = None
    if st.session_state.doc and st.session_state.chapter_index:
        st.markdown("---")
        chapter_names = ["Todo el Libro"] + list(st.session_state.chapter_index.keys())
        selected_chapter = st.selectbox("Filtro de Capítulo:", chapter_names)
        
        if selected_chapter != "Todo el Libro":
            selected_range = get_chapter_range(selected_chapter, st.session_state.chapter_index, st.session_state.doc.page_count)

    st.markdown("---")
    if st.button("🗑️ Reset App", use_container_width=True):
        new_key = st.session_state.uploader_key + 1
        st.session_state.clear()
        st.session_state.uploader_key = new_key
        st.rerun()

# --- MAIN AREA: Dashboard Responsivo ---
st.markdown("## ⚡ Circuit Verifier")

if st.session_state.doc is None:
    st.info("👈 Abre el menú lateral (arriba izquierda) para cargar tu libro primero.")
else:
    # --- ZONA DE BÚSQUEDA (Top Main) ---
    # Usamos Tabs para cambiar rápido entre Texto e Imagen sin ir a la sidebar
    tab_text, tab_img = st.tabs(["🔍 Búsqueda Texto", "📸 Búsqueda Imagen"])
    
    with tab_text:
        with st.form("search_form_main"):
            col_in, col_btn = st.columns([3, 1])
            with col_in:
                query = st.text_input("Valores Clave", placeholder="Ej: 10k, 12V", label_visibility="collapsed")
            with col_btn:
                search_submitted = st.form_submit_button("Buscar", use_container_width=True)
                
        if search_submitted and query:
            keywords = [k.strip() for k in query.split(',') if k.strip()]
            if keywords:
                with st.spinner("Buscando..."):
                    results = search_engine.search_by_unique_values(
                        st.session_state.doc, keywords, page_range=selected_range
                    )
                    st.session_state.search_results = results
                    if results:
                        st.session_state.current_page = results[0][0]
                    else:
                        st.warning("Sin resultados.")

    with tab_img:
        search_img = st.file_uploader("Subir Foto Ejercicio", type=["png", "jpg", "jpeg"], key="main_img_search")
        if search_img:
            # Blur Check
            img_bytes = search_img.getvalue()
            is_blurry, blur_score = image_shield.detect_blur(img_bytes)
            
            if is_blurry:
                st.warning(f"⚠️ Imagen borrosa (Score: {int(blur_score)}).")
            
            if st.button("🔍 Escanear Foto", use_container_width=True):
                with st.spinner("Procesando visión..."):
                    clean_bytes = image_shield.clean_image(img_bytes)
                    raw_sig = ai_chat.extract_problem_signature(clean_bytes)
                    signature = image_shield.sanitize_ocr(raw_sig)
                
                if signature:
                    st.success(f"Detectado: {signature}")
                    results = search_engine.search_by_unique_values(st.session_state.doc, signature)
                    st.session_state.search_results = results
                    if results:
                        st.session_state.current_page = results[0][0]
                        st.rerun()
                    else:
                        st.error("No encontrado en el libro.")
                else:
                    st.error("No se detectaron valores.")

    # --- ZONA DE RESULTADOS ---
    if st.session_state.search_results:
        st.markdown(f"### 🎯 Resultados ({len(st.session_state.search_results)})")
        # Scroll horizontal de botones
        res_cols = st.columns(min(5, len(st.session_state.search_results)))
        for i, (p_num, score) in enumerate(st.session_state.search_results[:5]):
            with res_cols[i]:
                if st.button(f"Pág {p_num+1}\n{int(score)}%", key=f"btn_res_{i}", use_container_width=True):
                    st.session_state.current_page = p_num

    st.markdown("---")

    # --- TARJETA PRINCIPAL: FUENTE DE LA VERDAD ---
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    
    # Header con Navegación Compacta
    col_head, col_nav = st.columns([2, 1])
    with col_head:
        st.markdown(f"### ✅ Pág {st.session_state.current_page + 1}")
    with col_nav:
        c_prev, c_next = st.columns(2)
        with c_prev:
            if st.button("⬅️", use_container_width=True):
                if st.session_state.current_page > 0:
                    st.session_state.current_page -= 1
                    st.rerun()
        with c_next:
            if st.button("➡️", use_container_width=True):
                if st.session_state.current_page < st.session_state.doc.page_count - 1:
                    st.session_state.current_page += 1
                    st.rerun()

    # Renderizado
    txt, img_bytes = backend.extract_page_data(st.session_state.doc, st.session_state.current_page)
    
    # Expander para la imagen (Ahorra espacio en móvil)
    with st.expander("📸 Ver Página Original", expanded=True):
        if img_bytes:
            st.image(img_bytes, use_column_width=True)
        else:
            st.error("Error visual.")

    # Verificación de Componentes
    detected_components = search_engine.extract_circuit_components(txt)
    if detected_components:
        with st.expander("📋 Componentes Detectados", expanded=False):
            df_comps = pd.DataFrame(detected_components, columns=["Valor"])
            st.dataframe(df_comps, use_container_width=True, hide_index=True)
            
    st.markdown('</div>', unsafe_allow_html=True)

    # --- CHAT CON IA ---
    if ai_ready:
        st.markdown("---")
        with st.expander("💬 Chat Auditoría (Gemini)", expanded=True):
            # Inicializar chat
            if "chat_session" not in st.session_state or st.session_state.get("last_page_context") != st.session_state.current_page:
                st.session_state.chat_session = ai_chat.start_auditor_session(
                    txt, img_bytes, st.session_state.chapter_index
                )
                st.session_state.last_page_context = st.session_state.current_page
                st.session_state.messages = []

            # Historial
            for i, msg in enumerate(st.session_state.messages):
                st.chat_message(msg["role"]).write(msg["content"])
                if msg["role"] == "assistant":
                    match = re.search(r"\[\[IR_A_PAGINA:\s*(\d+)\]\]", msg["content"])
                    if match:
                        target_page = int(match.group(1))
                        if st.button(f"🚀 Ir a Pág {target_page}", key=f"nav_{i}", use_container_width=True):
                            st.session_state.current_page = target_page - 1
                            st.rerun()

            # Input
            user_input = st.chat_input("Pregunta al auditor...")
            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.write(user_input)
                
                with st.spinner("Pensando..."):
                    response = ai_chat.send_message(st.session_state.chat_session, user_input)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()
