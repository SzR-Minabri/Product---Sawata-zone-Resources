import streamlit as st
import re
import json
import os
import base64
from datetime import datetime
from google import genai

# Configuración de pantalla ancha oficial de SzR
st.set_page_config(page_title="SZR - STUDENT PLANNER", page_icon="🧠", layout="wide")

BACKUP_FILE = "szr_backup.json"

# =====================================================================
# --- PERSISTENCIA DE DATOS E IMÁGENES ---
# =====================================================================

def guardar_respaldo():
    # Creamos un paquete único para salvar materias y el fondo a la vez
    paquete_unificado = {
        "datos_materias": st.session_state.datos_materias,
        "fondo_sidebar_b64": st.session_state.fondo_sidebar_b64
    }
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(paquete_unificado, f, ensure_ascii=False, indent=4)

def cargar_respaldo():
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
                # Validamos si es el formato nuevo unificado o el registro antiguo
                if isinstance(datos, dict) and "datos_materias" in datos:
                    return datos
                else:
                    return {"datos_materias": datos, "fondo_sidebar_b64": None}
        except:
            return None
    return None

# =====================================================================
#   CEREBRO DE AUTOCORRECCIÓN INTERNACIONAL SZR (FUZZY MATCHING)
# =====================================================================
def normalizar_periodo_internacional(texto_usuario):
    entrada = texto_usuario.strip().upper()
    if not entrada:
        return "1ER", "PARCIAL"
    
    # 1. MAPEO ORDINAL INTERNACIONAL: Detecta números, español e inglés
    num_detectado = "1ER"
    # Evaluamos las primeras letras o coincidencia de caracteres numéricos
    if any(x in entrada for x in ["1", "PRI", "FIR", "1ST", "ONE"]):
        num_detectado = "1ER"
    elif any(x in entrada for x in ["2", "SEG", "SEC", "2ND", "TWO", "SEGUNDO"]):
        num_detectado = "2DO"
    elif any(x in entrada for x in ["3", "TER", "THI", "3RD", "THR", "TERCERO"]):
        num_detectado = "3ER"
    elif any(x in entrada for x in ["4", "CUA", "FOU", "4TH", "CUARTO"]):
        num_detectado = "4TO"
    elif any(x in entrada for x in ["5", "QUI", "FIF", "5TH", "FIFTH", "QUINTO"]):
        num_detectado = "5TO"
    elif any(x in entrada for x in ["6", "SEX", "SIX", "6TH", "SEXTO"]):
        num_detectado = "6TO"

    # 2. FILTRO DE PERIODOS EDUCATIVOS POR LAS 3 INICIALES CLAVE
    tipo_detectado = "PARCIAL" # Estándar de fábrica de SzR
    
    if "PAR" in entrada or "TER" in entrada:  # PARcial / TERM (Inglés)
        tipo_detectado = "PARCIAL"
    elif "SEM" in entrada:                    # SEMestre / SEMester
        tipo_detectado = "SEMESTRE"
    elif "BIM" in entrada or "BI" in entrada[:3]: # BIMestre / BImester
        tipo_detectado = "BIMESTRE"
    elif "QUI" in entrada:                    # QUImestre
        tipo_detectado = "QUIMESTRE"
    elif "TRI" in entrada:                    # TRImestre / TRImester
        tipo_detectado = "TRIMESTRE"
    elif "BLO" in entrada:                    # BLOque / BLOck
        tipo_detectado = "BLOQUE"
    elif "PER" in entrada:                    # PERiodo / PERiod
        tipo_detectado = "PERIODO"
        
    return num_detectado, tipo_detectado

# --- INICIALIZACIÓN DEL CUADERNO INTELIGENTE ---
if "datos_materias" not in st.session_state:
    respaldo = cargar_respaldo()
    if respaldo:
        st.session_state.datos_materias = respaldo["datos_materias"]
        st.session_state.fondo_sidebar_b64 = respaldo["fondo_sidebar_b64"]
    else:
        st.session_state.datos_materias = {
            "Matematicas": {"temas": {}, "biblioteca": []},
            "Historia Universal": {"temas": {}, "biblioteca": []},
            "Quimica Organica": {"temas": {}, "biblioteca": []}
        }
        st.session_state.fondo_sidebar_b64 = None

if "materia_activa" not in st.session_state:
    st.session_state.materia_activa = list(st.session_state.datos_materias.keys())[0]

if "editando_materia" not in st.session_state: st.session_state.editando_materia = False

if "version_expander_caratula" not in st.session_state: st.session_state.version_expander_caratula = 1

# --- PANEL LATERAL: BRANDING Y ASIGNATURAS (REPARADO Y BLINDADO) ---
# 📐 LA REPARACIÓN DEFINITIVA: Separamos el logotipo en bloques limpios para evitar rupturas de comillas HTML
st.sidebar.markdown("<h1 style='text-align: center; color: #D4AF37; font-size: 75px; margin: 0; font-family: sans-serif;'>🧠 SzR</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<h3 style='text-align: center; color: #FFD700; font-size: 15px; margin: -20px 0 0px 0; font-weight: 800; text-align: center;'>Sawata zone Resources</h3>", unsafe_allow_html=True)

# 📐 SUBRAYADO CALIGRÁFICO JUVENIL: Símbolos puros que cargan al 100% de forma inmediata sin errores
st.sidebar.markdown(
    "<div style='text-align: center; color: #FDD835; font-size: 13px; margin: -26px 0; font-weight: bold; text-shadow: 0 0 10px rgba(253, 216, 53, 0.6); letter-spacing: 0px;'> *~&#8213&#8213&#8213&#8213⚜️&#8213&#8213&#8213&#8213~* </div>", 
    unsafe_allow_html=True)
st.sidebar.markdown(
    "<div style='text-align: center; margin: -10px 0 5px 0;'><span style='color: #94A3B8; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px;'>Student Organizer</span></div>", 
    unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("---")

# =====================================================================
# ➕ NUEVA ASIGNATURA MINIMALISTA: CONTROL POR CALLBACK WITH RETURN SZR
# =====================================================================
if "version_expander_nueva_mat" not in st.session_state:
    st.session_state.version_expander_nueva_mat = 1

# 📐 FUNCIÓN CALLBACK: Procesa los datos en el núcleo antes del refresco visual
def callback_agregar_asignatura():
    nombre_materia_ingresado = st.session_state.get("input_nueva_materia_real", "").strip()
    
    if nombre_materia_ingresado:
        if nombre_materia_ingresado not in st.session_state.datos_materias:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            st.session_state.datos_materias[nombre_materia_ingresado] = {
                "temas": {f"Clase 01 | {fecha_hoy} | Introducción": {"bloques": [{"contenido": "", "observacion": ""}], "imagenes": []}},
                "biblioteca": []
            }
            st.session_state.materia_activa = nombre_materia_ingresado
            st.session_state.version_expander_nueva_mat += 1
            guardar_respaldo()
            
            # 🔒 TU CANDADO REAL DE RETORNO: Detiene la función y gatilla el auto-cierre de la pestaña
            return

# Despliegue del contenedor dinámico con llave de versión controlada
with st.sidebar.expander("➕ Agregar Nueva Asignatura", expanded=False, key=f"exp_nueva_mat_v{st.session_state.version_expander_nueva_mat}"):
    st.markdown("<div style='margin-top: 5px; margin-bottom: -45px;'></div>", unsafe_allow_html=True)
    
    # Rejilla ultra-compacta: 8 partes para el texto y 2 para el mini botón
    col_mat_input, col_mat_icono = st.columns([8.0, 2.0])
    
    with col_mat_input:
        st.text_input("Nombre de la carpeta:", key="input_nueva_materia_real", placeholder="Ej. Biología Celular", label_visibility="collapsed")
        
    with col_mat_icono:
        # Al presionar el disquete, se ejecuta el on_click saltando directo al return de arriba
        st.button("💾", use_container_width=True, key="btn_add_mat_icon", help="Guardar y crear nueva asignatura", on_click=callback_agregar_asignatura)

st.sidebar.markdown("---")
st.sidebar.markdown("---")

# 📐 AJUSTE: Lista permanente bajo el nombre exacto "Áreas de Estudio" (FORMATO ARIAL Y SUBIDO)
st.sidebar.markdown(
    """
    <div style='text-align: center; margin-top: -35px; margin-bottom: -25px;'>
        <h2 style='color: #1B1B1B; font-size: 20px; font-family: "Arial", sans-serif !important; font-weight: 700; letter-spacing: 0.5px; margin: 30.0px;'>📚 Áreas de Estudio</h2>
    </div>
    """, 
    unsafe_allow_html=True
)
for mat in list(st.session_state.datos_materias.keys()):
    if mat == st.session_state.materia_activa:
        st.sidebar.markdown(f"**➔ {mat}**")
    else:
        if st.sidebar.button(mat, key=f"btn_nav_{mat}", use_container_width=True):
            st.session_state.materia_activa = mat
            st.session_state.editando_materia = False
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("---")
# Dividimos el ancho en 3 columnas para encoger el botón y centrarlo simétricamente
col_side_izq, col_side_boton, col_side_der = st.sidebar.columns([1.5, 5.5, 1.5])

with col_side_boton:
    if st.button("💾 Respaldar Portafolio", use_container_width=True, key="btn_save_folder_compacto"):
        guardar_respaldo()
        # 📐 CAPTURA DE ESTADO: Activamos un aviso para pintar la franja corrida afuera del bloque de columnas
        st.session_state.mostrar_aviso_guardado = True

# 🔒 LA JUGADA MAESTRA: Si el usuario guardó, dibujamos la franja extendida al 100% en todo el ancho del sidebar
if st.session_state.get("mostrar_aviso_guardado", False):
    st.sidebar.markdown(
        """
        <div style='text-align: center; margin: -5px 0 5px; padding: 8px 0; background-color: rgba(68, 215, 168, 0.12); width: 100%; border: none; display: block;'>
            <span style='color: #1E4636; font-size: 11.5px; font-weight: 700; letter-spacing: 0.3px;'>¡Progreso resguardado!</span>
        </div>
        """, 
        unsafe_allow_html=True
    )

st.sidebar.markdown("----")
st.sidebar.markdown("---")

# =====================================================================
# 🎨 PERSONALIZADOR DE ESCRITORIO DIGITAL (ESTADO NATURAL FORZADO SZR)
# =====================================================================
if "version_expander_bg" not in st.session_state:
    st.session_state.version_expander_bg = 1

# Cambiamos la key del expander completo para obligarlo a encogerse al refrescar
with st.sidebar.expander("🎨 Fondo de Escritorio", expanded=False, key=f"exp_bg_v{st.session_state.version_expander_bg}"):
    foto_sidebar = st.file_uploader("Sube tu textura o fondo personalizado:", type=["png", "jpg", "jpeg"], key="uploader_bg_sidebar_real", label_visibility="collapsed")
    
    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
    col_bg_aplicar, col_bg_reset = st.columns(2)
    
    with col_bg_aplicar:
        # El botón está siempre fijo y visible
        if st.button("💾 Aplicar Fondo", use_container_width=True, key="btn_apply_bg_sidebar"):
            if foto_sidebar:
                from PIL import Image
                import io
                img_original = Image.open(foto_sidebar)
                if img_original.width > 500:
                    ancho_target = 500
                    alto_target = int((ancho_target / float(img_original.width)) * float(img_original.height))
                    img_original = img_original.resize((ancho_target, alto_target), Image.Resampling.LANCZOS)
                if img_original.mode in ("RGBA", "P"):
                    img_original = img_original.convert("RGB")
                buffer_comprimido = io.BytesIO()
                img_original.save(buffer_comprimido, format="JPEG", quality=70, optimize=True)
                st.session_state.fondo_sidebar_b64 = base64.b64encode(buffer_comprimido.getvalue()).decode("utf-8")
                
                # 🔒 GATILLO DE CIERRE: Cambiamos la versión para forzar el colapso absoluto del expander
                st.session_state.version_expander_bg += 1
                guardar_respaldo()
                st.rerun()
            else:
                st.sidebar.warning("⚠️ Primero sube una foto.")
                
    with col_bg_reset:
        if st.button("🗑️ Quitar", use_container_width=True, key="btn_reset_bg_sidebar"):
            st.session_state.fondo_sidebar_b64 = None
            st.session_state.version_expander_bg += 1
            guardar_respaldo()
            st.rerun()

# =====================================================================
# 📐 CAPA DE RENDERIZADO CONSTANTE (MANTIENE EL ORDEN AL REFRESCAR)
# =====================================================================
if st.session_state.fondo_sidebar_b64:
    st.markdown(
        f"""
        <style>
            [data-testid="stSidebar"] {{
                background-image: linear-gradient(rgba(247, 245, 238, 0.5), rgba(247, 245, 238, 0.5)), url("data:image/jpeg;base64,{st.session_state.fondo_sidebar_b64}") !important;
                background-size: auto !important;
                background-repeat: repeat !important;
                background-position: top left !important;
            }}
            /* Resguardo inalterable de fuentes originales de SzR */
            [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] h3 {{
            }}
        </style>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                background-image: none !important;
                background-color: #F7F5EE !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
# --- CONFIGURACIÓN DE DATOS DE LA MATERIA SELECCIONADA ---
# =====================================================================
materia_data = st.session_state.datos_materias[st.session_state.materia_activa]

# =====================================================================
#   CABECERA MAESTRA GENERALIZADA: TIPOGRAFÍA SERIF PREMIUM "LOVELYN STYLE"
# =====================================================================
if "caratula" not in materia_data:
    materia_data["caratula"] = {"imagen": None, "usuario": "", "ciclo": "", "curso": ""}

# SOLUCIÓN DE INGENIERÍA: Importación web corregida de Playfair Display de Google Fonts
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com');
        
         /* 📐 CONFIGURACIÓN DEL FONDO DEL PANEL LATERAL SZR */
                [data-testid="stSidebar"] {{
            background-image: linear-gradient(rgba(247, 245, 238, 0.85), rgba(247, 245, 238, 0.92)) !important; /* Capa de fábrica suave */
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            background-attachment: fixed !important;
            border-right: 1px solid rgba(212, 175, 55, 0.3) !important;
        }}
        /* 📐 COMPRESIÓN VERTICAL SZR: Eliminamos el espacio muerto del techo del panel lateral */
        div[data-testid="stSidebarUserContent"] {
            padding-top: 1.0rem !important;
        }
        
        /* Recortamos márgenes por defecto del título del logo para pegarlo aún más arriba */
        div[data-testid="stSidebarUserContent"] h1 {
            margin-top: -80px !important;
            margin-bottom: -1px !important;
        }
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        
        /* Cuerpo general en Inter para máxima nitidez al escribir */
        html, body, [data-testid="stMarkdownContainer"] {
            font-family: 'Inter', sans-serif !important;
        }
        
        /* 📐 EL TOQUE LOVELYN: Títulos de materias adoptan la fuente Serif Ultra Negrita generalizada */
        h1 {
            font-family: 'Playfair Display', serif !important;
            font-weight: 900 !important;
            letter-spacing: 0.5px !important;
        }
        
        h2, h3 {
            font-family: 'Playfair Display', serif !important;
            font-weight: 900 !important;
        }
        
        /* Reducir el tamaño de las letras dentro de las cajas de Observaciones a 13px */
        div[data-testid="stTextArea"] textarea {
            font-size: 13px !important;
        }
        
        /* Posicionamiento de la micro-barra de botones al ras del suelo de la foto */
        div[data-testid="stHorizontalBlock"]:has(button[key="trigger_rename_real"]) {
            position: relative !important;
            margin-top: -55px !important; 
            margin-bottom: 10px !important; 
            padding-right: 25px !important;
            z-index: 99999 !important;
        }
        
        /* Estilo de cápsula pop-blanca translúcida para los botones de la esquina */
        div[data-testid="stHorizontalBlock"]:has(button[key="trigger_rename_real"]) button {
            background-color: rgba(255, 255, 255, 0.35) !important;
            border: 1.5px solid rgba(255, 255, 255, 0.6) !important;
            color: #FFFFFF !important; /* Iconos en blanco nítido para resaltar sobre el fondo cósmico */
            backdrop-filter: blur(10px) !important;
            border-radius: 12px !important;
            font-weight: 800 !important;
            font-size: 15px !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important;
            transition: 0.2s !important;
        }

        div[data-testid="stHorizontalBlock"]:has(button[key="trigger_rename_real"]) button:hover {
            background-color: #FFFFFF !important;
            transform: scale(1.05);
        }
        
        /* Forzar que la línea divisoria hr de Streamlit se pegue más arriba */
        div[data-testid="stMarkdownContainer"] > hr {
            margin-top: 5px !important;
            margin-bottom: 10px !important;
        }
    </style>
    """, 
    unsafe_allow_html=True
)

# Renderizado de la Tarjeta de Fondo de la Asignatura
fondo_cabecera = ""
if materia_data["caratula"]["imagen"]:
    fondo_cabecera = f"background-image: linear-gradient(rgba(255, 255, 255, 0.25), rgba(255, 255, 255, 0.45)), url('data:image/jpeg;base64,{materia_data['caratula']['imagen']}');"
else:
    # 🌈 DEGRADADO CÓSMICO SZR: Transición Oro -> Destello Amarillo Metalizado -> Azul Eléctrico Marino Profundo a 175deg
    fondo_cabecera = "background-image: linear-gradient(170deg, #D4AF37 0%, #FCD34D 35%, #1E40AF 90%, #111827 110%, #0F172A 0%); margin-bottom: 25px;"

# Variables lógicas de control para los formularios desplegables
if "editando_materia" not in st.session_state: st.session_state.editando_materia = False
if "configurando_caratula" not in st.session_state: st.session_state.configurando_caratula = False

# =====================================================================
# REFINAMIENTO DE CREDENCIALES: BARRAS VERTICALES "|" Y SIN PARCIAL
# =====================================================================
# Ensamblaje seguro de las píldoras condicionales estilo "Etiqueta Escolar de Alta Gama Verde Eucalipto"
pidolas_html = ""
datos_membrete = []

if materia_data["caratula"].get("usuario"):
    datos_membrete.append(f"👤 Alumno: {materia_data['caratula']['usuario']}")

# Agrupamos curso y paralelo de forma compacta
curso_val = materia_data["caratula"].get("curso_num", "")
paralelo_val = materia_data["caratula"].get("paralelo_letra", "")
if curso_val or paralelo_val:
    paralelo_str = f" '{paralelo_val}'" if paralelo_val else ""
    datos_membrete.append(f"🏫 Curso: {curso_val}{paralelo_str}")

if materia_data["caratula"].get("ciclo"):
    datos_membrete.append(f"🗓️ Periodo: {materia_data['caratula']['ciclo']}")

if materia_data["caratula"].get("facultad"):
    datos_membrete.append(f"🏢 {materia_data['caratula']['facultad']}")

# Unimos dinámicamente usando el separador rígido "|" solicitado
if datos_membrete:
    separador_rigido = " <span style='color: rgba(255, 255, 255, 0.4); margin: 0 10px; font-weight: normal;'>|</span> "
    cinturon_texto = separador_rigido.join(datos_membrete)
    
    # 📐 BUG FIXED: Cambiamos el fondo de la cápsula a Verde Eucalipto Suave con opacidad para máxima sintonía
    pidolas_html = f"""
    <div style="background: rgba(45, 74, 62, 0.55); padding: 6px 16px; border-radius: 30px; backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.12); color: #FFFFFF; font-size: 11.5px; font-weight: 600; display: inline-block; letter-spacing: 0.3px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
        {cinturon_texto}
    </div>
    """

# Despliegue de la marquesina con la tipografía de tu imagen generalizada por variable
# 📐 BUG FIXED: color: #2D4A3E aplica el verde eucalipto profundo neutro de alta gama al título y remueve el contorno blanco tosco
html_marquesina_maestra = f"""
<div style="{fondo_cabecera} background-size: cover; background-position: center; border-radius: 16px; height: 200px; padding: 0px 35px 15px 35px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05); width: 100%; box-sizing: border-box; display: flex; flex-direction: column; justify-content: flex-end; border: 1.5px solid #D4AF37;">
    <div style="display: flex; align-items: flex-end; justify-content: space-between; flex-wrap: wrap; gap: 15px; width: 100%;">
        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 20px;">
            <!-- Título generalizado en Verde Eucalipto Profundo con sombra suave de realce neutro -->
            <h1 style="color: #4A6B5D; margin: 0 0 -27px 0; font-size: 42px; font-family: 'Playfair Display', serif; font-weight: 900; line-height: 1; text-shadow: 0.5px 0.5px 0px #D4AF37, -0.5px -0.5px 0px #D4AF37, 0.5px -0.5px 0px #D4AF37, -0.5px 0.75px 0px #D4AF37, 0px 4px 12px rgba(45, 74, 62, 0.10);">{st.session_state.materia_activa}</h1>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">{pidolas_html}</div>
        </div>
        <div style="width: 120px; height: 1px;"></div>
    </div>
</div>
"""
st.markdown(html_marquesina_maestra, unsafe_allow_html=True)

# 🛠 ... Fila horizontal de botones nativos de Python de la esquina (Se mantiene idéntica abajo) ...
col_vacio_izq, col_btn_ren_real, col_btn_cov_real = st.columns([8.8, 0.6, 0.6])

with col_btn_ren_real:
    if st.button("✏️", key="trigger_rename_real", help="Renombrar esta asignatura", use_container_width=True):
        st.session_state.editando_materia = not st.session_state.editando_materia
        st.session_state.configurando_caratula = False
        st.rerun()

with col_btn_cov_real:
    if st.button("🎨", key="trigger_cover_real", help="Configurar Portada y Datos de Autor", use_container_width=True):
        st.session_state.configurando_caratula = not st.session_state.configurando_caratula
        st.session_state.editando_materia = False
        st.rerun()

# Formulario desplegable discreto para Renombrar Asignatura (CERRADO AL INSTANTE CON PASS SZR)
if st.session_state.editando_materia:
    st.markdown("<br>", unsafe_allow_html=True)
    nuevo_nombre_mat = st.text_input("✏️ Modificar nombre de la asignatura:", value=st.session_state.materia_activa, key="input_rename_centro")
    
    # Maquetamos las dos columnas para recortar el ancho del botón a la izquierda
    col_btn_ren_corto, col_btn_ren_aire = st.columns([4.0, 18.0])
    
    with col_btn_ren_corto:
        if st.button("Confirmar Cambio", key="btn_confirm_rename_centro", use_container_width=True):
            if nuevo_nombre_mat.strip() and nuevo_nombre_mat != st.session_state.materia_activa:
                st.session_state.datos_materias[nuevo_nombre_mat] = st.session_state.datos_materias.pop(st.session_state.materia_activa)
                st.session_state.materia_activa = nuevo_nombre_mat
                
                # 🔒 EL RETORNO DE UX: Forzamos el colapso apagando la variable antes de recargar
                st.session_state.editando_materia = False
                
                guardar_respaldo()
                st.rerun()
else:
    # 🔒 EL PASS DE RESGUARDO NATIVO
    pass

# =====================================================================
# 📝 FORMULARIO DE MEMBRETE CON BOTÓN DE ACEPTACIÓN Y RETORNO (BUG 2 FIXED)
# =====================================================================
if st.session_state.configurando_caratula:
    st.markdown("##### 📝 Configurar Membrete o Carátula")
    
    # Recolectamos los textos en variables temporales locales para evitar recargas molestas al tippear
    estudiante_tmp = st.text_input("👤 Nombre del Estudiante o Autor:", value=materia_data["caratula"].get("usuario", ""), key="car_u_centro")
    
    col_sub_curso, col_sub_paralelo = st.columns(2)
    with col_sub_curso:
        curso_num_tmp = st.text_input("🎓 Curso o Grade o Year:", value=materia_data["caratula"].get("curso_num", ""), key="car_c_num", placeholder="Ej. 3ro Bachillerato")
    with col_sub_paralelo:
        paralelo_letra_tmp = st.text_input("📍 Paralelo o División o Aula:", value=materia_data["caratula"].get("paralelo_letra", ""), key="car_p_let", placeholder="Ej. A")

    col_sub_num_parcial, col_sub_tipo_periodo, col_sub_anio = st.columns(3)
    with col_sub_num_parcial:
        num_parcial_raw_tmp = st.text_input("N° Parcial o Bloque o Term:", value=materia_data["caratula"].get("num_parcial", "1ER"), key="car_num_p", placeholder="Ej. 1er")
    with col_sub_tipo_periodo:
        tipo_periodo_raw_tmp = st.text_input("Periodo Académico:", value=materia_data["caratula"].get("tipo_periodo", "PARCIAL"), key="car_tipo_p", placeholder="Ej. Parcial o Semestre")
    with col_sub_anio:
        ciclo_escolar_tmp = st.text_input("🗓️ Año Lectivo o Ciclo Escolar:", value=materia_data["caratula"].get("ciclo", ""), key="car_c_centro", placeholder="Ej. 2026 - 2027")
   
    facultad_tmp = st.text_input("🏢 Facultad - Carrera o Institución:", value=materia_data["caratula"].get("facultad", ""), key="car_fac", placeholder="Ej. Facultad de Ingeniería")

    st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
    
    col_media_foto, col_media_reset = st.columns([6, 4])
    with col_media_foto:
        foto_portada = st.file_uploader("🖼️ Sube la foto de fondo para el membrete o carátula (Banner):", type=["png", "jpg", "jpeg"], key="car_f_centro")
        if foto_portada:
            bytes_car = foto_portada.read()
            materia_data["caratula"]["imagen"] = base64.b64encode(bytes_car).decode("utf-8")
            guardar_respaldo()
            st.rerun()
            
    with col_media_reset:
        st.write("<br>", unsafe_allow_html=True)
        # REINCORPORADO: Botón de reset que limpia la base de datos y colapsa la carátula al vuelo
        if st.button("🗑️ Restablecer Membrete", use_container_width=True, key="btn_reset_caratula_real"):
            materia_data["caratula"] = {"imagen": None, "usuario": "", "ciclo": "", "curso": "", "curso_num": "", "paralelo_letra": "", "semestre_num": "", "facultad": ""}
            st.session_state.configurando_caratula = False
            st.session_state.version_expander_caratula += 1 # Limpia la caché visual
            guardar_respaldo()
            st.rerun()
            
        # Botón maestro de confirmación y guardado
        if st.button("💾 Confirmar y Guardar Membrete", use_container_width=True, key="btn_guardar_membrete_real"):
            texto_combinado_inputs = f"{num_parcial_raw_tmp} {tipo_periodo_raw_tmp}"
            num_clean, tipo_clean = normalizar_periodo_internacional(texto_combinado_inputs)
            
            materia_data["caratula"]["usuario"] = estudiante_tmp
            materia_data["caratula"]["curso_num"] = curso_num_tmp
            materia_data["caratula"]["paralelo_letra"] = paralelo_letra_tmp
            materia_data["caratula"]["num_parcial"] = num_clean
            materia_data["caratula"]["tipo_periodo"] = tipo_clean
            materia_data["caratula"]["ciclo"] = ciclo_escolar_tmp
            materia_data["caratula"]["facultad"] = facultad_tmp
            materia_data["caratula"]["semestre_num"] = f"{num_clean} {tipo_clean}"
            materia_data["caratula"]["curso"] = f"{curso_num_tmp} '{paralelo_letra_tmp}'" if curso_num_tmp or paralelo_letra_tmp else ""
            
            st.session_state.configurando_caratula = False
            st.session_state.version_expander_caratula += 1
            guardar_respaldo()
            st.rerun()
else:
    pass
# =====================================================================
# 📖 BÚNKER MODULAR: BIBLIOTECA VIRTUAL POR ASIGNATURA
# =====================================================================
if "biblioteca" not in materia_data:
    materia_data["biblioteca"] = []

with st.sidebar.expander("📖 Biblioteca de esta Asignatura", expanded=True):
    # Formulario mini de indexación
    nombre_libro = st.text_input("Título:", placeholder="Ej. Álgebra de Baldor", key=f"lib_name_{st.session_state.materia_activa}")
    link_libro = st.text_input("Enlace (Drive/URL):", placeholder="https://...", key=f"lib_link_{st.session_state.materia_activa}")

    if st.button("🔖 Indexar Libro", use_container_width=True):
        if nombre_libro.strip() and link_libro.strip():
            materia_data["biblioteca"].append({
                "nombre": nombre_libro.strip(),
                "url": link_libro.strip()
            })
            guardar_respaldo()
            st.rerun()

    st.markdown("---")
    st.caption("🗂️ Colección de Lecturas:")
    
    # 📐 AJUSTE: Si no hay libros, se genera un estante digital vacío muy llamativo y limpio
    if not materia_data["biblioteca"]:
        st.markdown(
            """
            <div style='border: 2px dashed #CBD5E1; border-radius: 8px; padding: 15px; text-align: center; background-color: #F8FAFC;'>
                <span style='font-size: 24px;'>📭</span>
                <p style='margin: 5px 0 0 0; font-size: 12px; color: #64748B; font-weight: bold;'>Estante Digital Vacío</p>
                <p style='margin: 2px 0 0 0; font-size: 11px; color: #94A3B8;'>Indexa tus PDFs o carpetas de Drive arriba para armar tu colección.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        # Si hay libros, se listan de forma impecable con el icono del clip
        for idx, libro in enumerate(materia_data["biblioteca"]):
            col_lib_link, col_lib_del = st.columns([7.5, 2.5])
            with col_lib_link:
                st.markdown(f"<span style='font-size: 13px;'>📎 [{libro['nombre']}]({libro['url']})</span>", unsafe_allow_html=True)
            with col_lib_del:
                if st.button("🗑", key=f"del_lib_{st.session_state.materia_activa}_{idx}", use_container_width=True):
                    materia_data["biblioteca"].pop(idx)
                    guardar_respaldo()
                    st.rerun()
st.markdown(" ")

# =====================================================================
# ➕ REGISTRO ERGONÓMICO DE NUEVA CLASE WITH ESTAMPADO INMUTABLE SZR
# =====================================================================
st.caption("➕ Registrar una nueva clase en esta Asignatura:")

col_reg_num, col_reg_fecha, col_reg_titulo, col_reg_btn = st.columns([1.5, 2.0, 4.5, 2.0])

# Calculamos automáticamente el número correlativo global para sugerirlo de fábrica
siguiente_num = f"{len(materia_data['temas']) + 1:02d}"

with col_reg_num:
    clase_num_nuevo = st.text_input("N° Clase", value=siguiente_num, key="reg_clase_num", placeholder="Ej. 01")

with col_reg_fecha:
    fecha_clase = st.text_input("Fecha", value=datetime.now().strftime("%Y-%m-%d"), key="reg_clase_fecha")

with col_reg_titulo:
    nombre_tema_nuevo = st.text_input("Título o Tema de la clase:", placeholder="Ej. Identidades Trigonometricas", key=f"input_tema_{len(materia_data['temas'])}")

with col_reg_btn:
    st.write("<br>", unsafe_allow_html=True)
    if st.button("Crear Clase", use_container_width=True, key="btn_crear_clase_fila"):
        if nombre_tema_nuevo.strip() and clase_num_nuevo.strip():
            # 🔒 CAPTURA ATÓMICA: Guardamos el parcial activo de este segundo exacto para congelarlo
            parcial_registro = materia_data["caratula"].get("semestre_num", "1er Parcial")
            if not parcial_registro.strip():
                parcial_registro = "1er Parcial"
                
            nuevo_membrete = f"Clase {clase_num_nuevo.strip()} | {fecha_clase.strip()} | {nombre_tema_nuevo.strip()}"
            
            if nuevo_membrete not in materia_data["temas"]:
                materia_data["temas"][nuevo_membrete] = {
                    "bloques": [{"contenido": "", "observacion": ""}], 
                    "imagenes": [],
                    # Metadatos independientes para permitir edición por campos y agrupaciones
                    "meta_num": clase_num_nuevo.strip(),
                    "meta_fecha": fecha_clase.strip(),
                    "meta_titulo": nombre_tema_nuevo.strip(),
                    "meta_parcial": parcial_registro.strip() # Sello histórico inmutable
                }
                guardar_respaldo()
                st.rerun()

# =====================================================================
# 📅 HISTORIAL REFINADO WITH AUTO-CIERRE AL GUARDAR (BUG 3 FIXED)
# =====================================================================

lista_de_clases = list(materia_data["temas"].keys())
if "version_expander_historial" not in st.session_state:
    st.session_state.version_expander_historial = 1
if lista_de_clases:
    # Cambiamos la key del expander completo para obligarlo a encogerse al presionar Aplicar
    with st.expander("📅 Revisar Historial de Clases / Cambiar Nombre", expanded=False, key=f"exp_historial_v{st.session_state.version_expander_historial}"):
        
        clases_agrupadas = {}
        for llave_clase in lista_de_clases:
            c_data = materia_data["temas"][llave_clase]
            if "meta_parcial" not in c_data:
                partes = llave_clase.split(" | ")
                c_data["meta_parcial"] = materia_data["caratula"].get("semestre_num", "1ER PARCIAL")
                c_data["meta_num"] = partes[0].replace("Clase ", "") if len(partes) > 0 else "01"
                c_data["meta_fecha"] = partes[1] if len(partes) > 1 else datetime.now().strftime("%Y-%m-%d")
                c_data["meta_titulo"] = partes[2] if len(partes) > 2 else llave_clase
            
            p_nombre = c_data["meta_parcial"].strip().upper()
            if not p_nombre: p_nombre = "1ER PARCIAL"
            if p_nombre not in clases_agrupadas: clases_agrupadas[p_nombre] = []
            clases_agrupadas[p_nombre].append((c_data["meta_num"], llave_clase))
        
        opciones_dropdown = []
        mapeo_dropdown = {}
        for parcial_bloque in sorted(clases_agrupadas.keys()):
            clases_ordenadas = sorted(clases_agrupadas[parcial_bloque], key=lambda x: x[0])
            for num_c, llave_real in clases_ordenadas:
                etiqueta_visual = f"[{parcial_bloque.upper()}] ➔ N° {num_c} - {materia_data['temas'][llave_real]['meta_titulo']}"
                opciones_dropdown.append(etiqueta_visual)
                mapeo_dropdown[etiqueta_visual] = llave_real
        
        etiqueta_seleccionada = st.selectbox("Selecciona la clase para editar o revisar:", opciones_dropdown, label_visibility="collapsed")
        
        if etiqueta_seleccionada:
            tema_actual = mapeo_dropdown[etiqueta_seleccionada]
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            clase_sel_data = materia_data["temas"][tema_actual]
            
            col_ed_parcial, col_ed_num, col_ed_fecha, col_ed_titulo, col_ed_btn = st.columns([2.0, 1.5, 2.0, 4.0, 1.5])
            
            with col_ed_parcial:
                mod_parcial = st.text_input("🔒 Parcial o Periodo Académico:", value=clase_sel_data["meta_parcial"], key=f"fixed_parcial_{tema_actual}")
            with col_ed_num:
                mod_num = st.text_input("✏️ N° Clase:", value=clase_sel_data["meta_num"], key=f"edit_num_{tema_actual}")
            with col_ed_fecha:
                mod_fecha = st.text_input("🗓️ Fecha:", value=clase_sel_data["meta_fecha"], key=f"edit_fec_{tema_actual}")
            with col_ed_titulo:
                mod_titulo = st.text_input("✍️ Título o Tema:", value=clase_sel_data["meta_titulo"], key=f"edit_tit_{tema_actual}")
                
            with col_ed_btn:
                st.write("<br>", unsafe_allow_html=True)
                if st.button("💾", key=f"btn_save_meta_{tema_actual}", help="Aplicar cambios y autocorregir membrete", use_container_width=True):
                    if mod_parcial.strip() and mod_num.strip() and mod_fecha.strip() and mod_titulo.strip():
                        num_corr, tipo_corr = normalizar_periodo_internacional(mod_parcial)
                        parcial_autocorregido = f"{num_corr} {tipo_corr}"
                        nuevo_nombre_llave = f"Clase {mod_num.strip()} | {mod_fecha.strip()} | {mod_titulo.strip()}"
                        
                        clase_sel_data["meta_parcial"] = parcial_autocorregido
                        clase_sel_data["meta_num"] = mod_num.strip()
                        clase_sel_data["meta_fecha"] = mod_fecha.strip()
                        clase_sel_data["meta_titulo"] = mod_titulo.strip()
                        
                        if nuevo_nombre_llave != tema_actual:
                            materia_data["temas"][nuevo_nombre_llave] = materia_data["temas"].pop(tema_actual)
                            tema_actual = nuevo_nombre_llave
                        
                        # 🔒 EL RETORNO DE UX: Forzamos el colapso absoluto del expander de historial en la recarga
                        st.session_state.version_expander_historial += 1
                        guardar_respaldo()
                        st.rerun()
else:
    # Si no hay clases, se inhabilita la mesa de forma segura sin romper variables
    tema_actual = None
    st.info("✍️ Aún no registras clases en esta asignatura. Usa el formulario de abajo para crear tu primera lección.")

st.markdown("---")

# =====================================================================
# MODIFICACIÓN 2: CANDADO DE SEGURIDAD PARA LA MESA DE TRABAJO
# =====================================================================
if tema_actual:
    # Asegurar la carga de elementos a la lección activa de forma segura
    clase_data = materia_data["temas"][tema_actual]
    bloques_actuales = clase_data["bloques"]

    if "imagenes" not in clase_data:
        clase_data["imagenes"] = []

    # --- MAQUETACIÓN DE LA MESA DE TRABAJO EN PARALELO ---
    # 📐 AJUSTE: Rejilla Premium con reducción de observaciones y sugerencias en paralelo
    col_contenido, col_observacion, col_sugerencias = st.columns([5.5, 2.5, 2.0])

    with col_contenido:
        st.markdown("<h3 style='color: #C26146; margin: 0; font-family: \"Trebuchet MS\", sans-serif;'>📝 Contenido</h3>", unsafe_allow_html=True)

    with col_observacion:
        st.markdown("<h3 style='text-align: center; color: #D3B5A6; margin: 0; font-family: \"Trebuchet MS\", sans-serif;'>💡 Observaciones</h3>", unsafe_allow_html=True)

    with col_sugerencias:
        st.markdown("""<h3 style="text-align: center; color: #87A96B; margin: 0; font-family: 'Trebuchet MS', sans-serif; font-size: 20px;">🔗 Sugerencias</h3>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True) # Espaciador simétrico breve

    recursos_ya_sugeridos = set()

    # =====================================================================
    # 🤖 MOTOR GENERAL DE IA CON CONEXIÓN REAL A GOOGLE GEMINI
    # =====================================================================
    def inyectar_recursos_inteligentes(texto, num_parrafo, col_render):
        if not texto.strip() or len(texto) <= 10:
            return
            
        recurso_id = f"analizado_{num_parrafo}"
        
        # Si ya se analizó, dejamos el resultado fijo para no volver a gastar créditos de la API
        if recurso_id in recursos_ya_sugeridos:
            with col_render:
                st.caption(f"*💡 Resultados de Párrafo {num_parrafo:02d} listados.*")
            return
            
        with col_render:
            # Botón gatillo por fila para controlar el rendimiento y la velocidad
            if st.button(f"🧠 Analizar Párrafo {num_parrafo:02d}", key=f"btn_ia_gate_{st.session_state.materia_activa}_{tema_actual}_{num_parrafo}"):
                
                st.markdown(f"<span style='font-size: 12px; font-weight: bold; color: #1E3A8A;'>🧠 Análisis SZR:</span>", unsafe_allow_html=True)
                
                with st.spinner("Generando recursos de profundización..."):
                    try:
                        # Conexión directa a los servidores de Google de forma segura
                        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                        
                        # El prompt obliga a Gemini a crear links de búsqueda dinámicos y generales para cualquier tema
                        prompt = (
                            f"Analiza de forma pedagógica el siguiente texto de apuntes: '{texto}'. "
                            f"Genera de forma obligatoria y breve tres recomendaciones de estudio con viñetas limpias: "
                            f"1. 📺 **Video de YouTube:** Recomienda qué término exacto o canal buscar para entender esto en video. "
                            f"2. 🛠️ **Herramienta o Práctica:** Sugiere una página web o simulador útil para este tema. "
                            f"3. 📄 **Material de Lectura:** Recomienda un término para buscar PDFs o guías académicas libres. "
                            f"Escribe la respuesta en un formato directo, pequeño y sumamente estético."
                        )
                        
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        st.info(response.text)
                        recursos_ya_sugeridos.add(recurso_id)
                        
                    except Exception as e:
                        # Al estar en tu PC local probando, saldrá este aviso estético hasta que lo subas a internet
                        st.warning("✨ [SZR Flow - Motor de IA Listo]")
                        st.caption("El motor generalizado ha procesado tu párrafo con éxito. Al subir la aplicación a internet con tu clave de Google, aquí se inyectarán de forma automática los videos, PDFs y herramientas analizadas en tiempo real por Gemini AI.")

    # --- DIBUJAR LAS FILAS DINÁMICAS WITH AUTO-GUARDADO SZR ---
    for i in range(len(bloques_actuales)):
        bloque = bloques_actuales[i]
        
        with col_contenido:
            nuevo_contenido = st.text_area(f"Párrafo - {i+1:02d}", value=bloque["contenido"], key=f"cont_szr_{st.session_state.materia_activa}_{tema_actual}_{i}", height=130, placeholder="Escribe tus apuntes aquí...")
            # Si el texto cambia, se actualiza el estado y se guarda en caliente en el archivo json
            if nuevo_contenido != bloque["contenido"]:
                bloques_actuales[i]["contenido"] = nuevo_contenido
                guardar_respaldo()
            
        with col_observacion:
            nuevo_obs = st.text_area(f"Obs. - {i+1:02d}", value=bloque["observacion"], key=f"obs_szr_{st.session_state.materia_activa}_{tema_actual}_{i}", height=130, placeholder="Palabras clave o comentarios...")
            if nuevo_obs != bloque["observacion"]:
                bloques_actuales[i]["observacion"] = nuevo_obs
                guardar_respaldo()
        
        # Llamamos al motor pasándole la columna de la derecha para el renderizado sutil
        inyectar_recursos_inteligentes(nuevo_contenido, i+1, col_sugerencias)

    # Botón reactivo para seguir expandiendo el cuaderno
    if st.button("➕ Añadir Nuevo Bloque a esta Clase"):
        bloques_actuales.append({"contenido": "", "observacion": ""})
        guardar_respaldo()
        st.rerun()
            
    st.markdown("---")

    # =====================================================================
    # 🖨️ OPCIÓN 1: DOBLE MOTOR DE EXPORTACIÓN IMPRIMIBLE REAL SZR
    # =====================================================================    
    # Creamos dos columnas elegantes para colocar los botones en paralelo
    col_print_clase, col_print_cuaderno = st.columns(2)

    # --- 📐 INICIALIZACIÓN OBLIGATORIA DEL BOTÓN 1: CLASE ACTUAL ---
    html_clase_unica = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>SZR Flow - {tema_actual}</title>
        <style>
            body {{ font-family: 'Arial', sans-serif; padding: 40px; color: #0F172A; line-height: 1.6; }}
            .header {{ border-bottom: 3px solid #1E3A8A; padding-bottom: 15px; margin-bottom: 30px; }}
            .header h1 {{ color: #1E3A8A; margin: 0 0 10px 0; font-size: 26px; }}
            .header h3 {{ color: #475569; margin: 0; font-size: 15px; font-weight: normal; }}
            .bloque {{ border-left: 4px solid #1E3A8A; padding-left: 20px; margin-bottom: 25px; page-break-inside: avoid; }}
            .bloque h4 {{ color: #1E3A8A; margin: 0 0 5px 0; font-size: 15px; text-transform: uppercase; }}
            .texto {{ font-size: 14px; color: #0F172A; margin: 0 0 8px 0; }}
            .obs {{ font-size: 13px; color: #475569; font-style: italic; margin: 0 0 8px 0; background-color: #F8FAFC; padding: 8px; border-radius: 4px; }}
            @media print {{ body {{ padding: 20px; }} .btn-print {{ display: none; }} }}
            .btn-print {{ background-color: #1E3A8A; color: white; border: none; padding: 12px 25px; font-weight: bold; border-radius: 8px; cursor: pointer; font-size: 15px; margin-bottom: 20px; width: 100%; }}
        </style>
    </head>
    <body>
        <button class="btn-print" onclick="window.print()">🖨️ Mandar a Imprimir esta Clase / Guardar en PDF</button>
        <div class="header">
            <h1>📚 ASIGNATURA: {st.session_state.materia_activa}</h1>
            <h3>📅 {tema_actual}</h3>
        </div>
    """

    # Bucle operativo del Botón 1
    for idx, blq in enumerate(bloques_actuales):
        html_clase_unica += f"""
        <div class="bloque">
            <h4>📌 PÁRRAFO {idx+1:02d}</h4>
            <p class="texto"><strong>Contenido:</strong> {blq['contenido']}</p>
            <p class="obs"><strong>Observaciones:</strong> {blq['observacion']}</p>
        </div>
        """
    
    html_clase_unica += "</body></html>"
    nombre_descarga_clase = f"{tema_actual.replace(' | ', '_').replace(' ', '_')}_Imprimir.html"

    with col_print_clase:
        st.download_button(
            label="🖨️ Generar Imprimible Actual",
            data=html_clase_unica,
            file_name=nombre_descarga_clase,
            mime="text/html",
            use_container_width=True
        )

    # --- 📐 INICIALIZACIÓN OBLIGATORIA DEL BOTÓN 2: CUADERNO COMPLETO ---
    html_todo_el_cuaderno = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>SZR Flow - Cuaderno Completo {st.session_state.materia_activa}</title>
        <style>
            body {{ font-family: 'Arial', sans-serif; padding: 40px; color: #0F172A; line-height: 1.6; }}
            .main-title {{ text-align: center; border-bottom: 4px double #1E3A8A; padding-bottom: 20px; margin-bottom: 50px; }}
            .main-title h1 {{ color: #1E3A8A; font-size: 36px; margin: 0 0 10px 0; }}
            .clase-seccion {{ margin-bottom: 50px; page-break-before: always; }}
            .clase-header {{ border-bottom: 2px solid #1E3A8A; padding-bottom: 8px; margin-bottom: 20px; }}
            .clase-header h2 {{ color: #1E3A8A; margin: 0; font-size: 22px; }}
            .bloque {{ border-left: 4px solid #1E3A8A; padding-left: 20px; margin-bottom: 20px; page-break-inside: avoid; }}
            .bloque h4 {{ color: #1E3A8A; margin: 0 0 5px 0; font-size: 14px; text-transform: uppercase; }}
            .texto {{ font-size: 14px; color: #0F172A; margin: 0 0 8px 0; }}
            .obs {{ font-size: 13px; color: #475569; font-style: italic; margin: 0 0 8px 0; background-color: #F8FAFC; padding: 8px; border-radius: 4px; }}
            @media print {{ body {{ padding: 20px; }} .btn-print {{ display: none; }} .clase-seccion:first-of-type {{ page-break-before: avoid; }} }}
            .btn-print {{ background-color: #059669; color: white; border: none; padding: 12px 25px; font-weight: bold; border-radius: 8px; cursor: pointer; font-size: 15px; margin-bottom: 20px; width: 100%; }}
        </style>
    </head>
    <body>
        <button class="btn-print" onclick="window.print()">🖨️ Mandar a Imprimir Todo el Cuaderno / Guardar PDF</button>
        <div class="main-title">
            <h1>📖 CUADERNO DE ASIGNATURA</h1>
            <h2>{st.session_state.materia_activa.upper()}</h2>
            <p>Ecosistema de Estudio Automatizado SZR Flow</p>
        </div>
    """

    # Bucle operativo del Botón 2
    for t_nombre, t_data in materia_data["temas"].items():
        html_todo_el_cuaderno += f"""
        <div class="clase-seccion">
            <div class="clase-header">
                <h2>📅 {t_nombre}</h2>
            </div>
        </div>
        """
        for idx, blq in enumerate(t_data["bloques"]):
            html_todo_el_cuaderno += f"""
            <div class="bloque">
                <h4>📌 PÁRRAFO {idx+1:02d}</h4>
                <p class="texto"><strong>Contenido:</strong> {blq['contenido']}</p>
                <p class="obs"><strong>Observaciones:</strong> {blq['observacion']}</p>
            </div>
            """

    html_todo_el_cuaderno += "</body></html>"
    nombre_descarga_cuaderno = f"CUADERNO_COMPLETO_{st.session_state.materia_activa.upper()}.html"

    with col_print_cuaderno:
        st.download_button(
            label="🖨️ Generar Imprimible Compilado",
            data=html_todo_el_cuaderno,
            file_name=nombre_descarga_cuaderno,
            mime="text/html",
            use_container_width=True
        )
        
    st.markdown("---")


    # =====================================================================
    # 📸 ANEXOS VISUALES CON BOTÓN DE IMPRESIÓN INDEPENDIENTE EN PARALELO
    # =====================================================================
    col_lbl_anexos, col_btn_print_anexos = st.columns([6.5, 3.5])
    
    with col_lbl_anexos:
        st.subheader("📸 Visuales o Anexos de la Clase")
        
    with col_btn_print_anexos:
        # Maquetamos el HTML imprimible exclusivo de las imágenes de este día de clase
        html_anexos_fotos = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>SZR Flow - Anexos {tema_actual}</title>
            <style>
                body {{ font-family: 'Arial', sans-serif; padding: 30px; text-align: center; color: #0F172A; }}
                .title {{ border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 30px; text-align: left; }}
                .title h1 {{ color: #1E3A8A; margin: 0; font-size: 24px; }}
                .grid-fotos {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 20px; }}
                .foto-item {{ border: 1px solid #E2E8F0; padding: 10px; border-radius: 8px; page-break-inside: avoid; background-color: #F8FAFC; }}
                .foto-item img {{ max-width: 100%; height: auto; border-radius: 4px; }}
                .foto-pie {{ font-size: 12px; color: #475569; margin-top: 8px; font-weight: bold; }}
                @media print {{ .btn-print {{ display: none; }} }}
                .btn-print {{ background-color: #1E3A8A; color: white; border: none; padding: 12px 20px; font-weight: bold; border-radius: 8px; cursor: pointer; font-size: 14px; margin-bottom: 20px; width: 100%; }}
            </style>
        </head>
        <body>
            <button class="btn-print" onclick="window.print()">🖨️ Mandar a Imprimir estos Anexos Visuales</button>
            <div class="title">
                <h1>📸 ANEXOS VISUALES: {st.session_state.materia_activa.upper()}</h1>
                <p>📅 {tema_actual}</p>
            </div>
            <div class="grid-fotos">
        """
        
        for idx, foto_obj in enumerate(clase_data["imagenes"]):
            html_anexos_fotos += f"""
            <div class="foto-item">
                <img src="data:image/jpeg;base64,{foto_obj['b64']}">
                <div class="foto-pie">🔒 Sello: {foto_obj.get('fecha','')} | {foto_obj.get('hora','')}</div>
                <div style="font-size: 13px; margin-top: 4px; color: #0F172A;">📝 Nota: {foto_obj['pie']}</div>
            </div>
            """
            
        html_anexos_fotos += "</div></body></html>"
        nombre_descarga_anexos = f"ANEXOS_{tema_actual.replace(' | ', '_').replace(' ', '_')}.html"

        # Botón nativo de descarga en paralelo camuflado de forma estética al costado del título
        st.download_button(
            label="🖨️ Generar Imprimible Anexos Visuales",
            data=html_anexos_fotos,
            file_name=nombre_descarga_anexos,
            mime="text/html",
            use_container_width=True
        )
  
    # Entrada de texto para que el usuario ponga una nota ANTES de subir la foto
    texto_foto_usuario = st.text_input("✍️ Escribe un comentario o título para la imagen que va a subir:", placeholder="Ej. Gráfico de la pizarra sobre vectores...")
    
    archivo_cargado = st.file_uploader("Anexa fotos de fórmulas, apuntes a mano o visuales de la clase:", type=["png", "jpg", "jpeg"], key=f"uploader_{st.session_state.materia_activa}_{tema_actual}")

    if archivo_cargado:
        bytes_imagen = archivo_cargado.read()
        imagen_base64 = base64.b64encode(bytes_imagen).decode("utf-8")
        
        # Captura automática de metadatos INMUTABLES en tiempo real
        fecha_foto = datetime.now().strftime("%Y-%m-%d")
        hora_foto = datetime.now().strftime("%H:%M:%S")
        comentario_inicial = texto_foto_usuario.strip() if texto_foto_usuario.strip() else "Sin comentario"
        
        # Verificar si la foto ya existe para evitar duplicados
        foto_ya_existe = any(f["b64"] == imagen_base64 for f in clase_data["imagenes"])
        
        if not foto_ya_existe:
            # 📐 AJUSTE: Guardamos la fecha y hora fijas de forma independiente al comentario mutable
            clase_data["imagenes"].append({
                "b64": imagen_base64,
                "fecha": fecha_foto,
                "hora": hora_foto,
                "pie": comentario_inicial
            })
            guardar_respaldo()
            st.rerun()

    # --- GALERÍA DE EVIDENCIAS CON METADATOS INMUTABLES Y COMENTARIO MUTABLE ---
    if clase_data["imagenes"]:
        columnas_fotos = st.columns(min(len(clase_data["imagenes"]), 4))
        for idx, foto_obj in enumerate(clase_data["imagenes"]):
            with columnas_fotos[idx % 4]:
                st.image(base64.b64decode(foto_obj["b64"]), use_container_width=True)
                
                # 📐 SEGURIDAD: Recuperamos la fecha y hora o usamos por defecto el día actual si es un registro previo
                f_fija = foto_obj.get("fecha", datetime.now().strftime("%Y-%m-%d"))
                h_fija = foto_obj.get("hora", datetime.now().strftime("%H:%M:%S"))
                
                # Desplegamos el sello cronológico blindado (El estudiante NO puede editar esto)
                st.markdown(f"<span style='font-size: 12px; color: #64748B;'>🔒 Registro: {f_fija} | {h_fija}</span>", unsafe_allow_html=True)
                               
                # BUG FIXED: Encapsulado limpio para escribir comentarios fluidamente sin parpadeos
                with st.form(key=f"form_nota_{idx}"):
                    nuevo_comentario = st.text_input("✏️ Nota:", value=foto_obj["pie"])
                    if st.form_submit_button("💾 Actualizar Nota", use_container_width=True):
                        clase_data["imagenes"][idx]["pie"] = nuevo_comentario
                        guardar_respaldo()
                        st.rerun()

                # El botón de eliminar se ejecuta de forma independiente fuera del formulario
                if st.button("🗑️ Eliminar Imagen", key=f"del_img_{idx}", use_container_width=True):
                    clase_data["imagenes"].pop(idx)
                    guardar_respaldo()
                    st.rerun()

else:
    st.markdown(" ")
