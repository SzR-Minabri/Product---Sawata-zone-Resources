import templates
import streamlit as st
import re
import json
import os
import base64
from datetime import datetime
from google import genai
import zipfile
from PIL import Image
import io
import urllib.parse
import time
from pydantic import BaseModel, Field
from typing import List, Literal
from google.genai import types
from google.genai.errors import APIError
import pizarra
import random

# Configuración de pantalla ancha oficial de SƨR
st.set_page_config(page_title="SƨR - STUDENT PLANNER", page_icon="🧠", layout="wide")

BACKUP_FILE = "sƨr_backup.json"

PROMPT_PLANTILLA_QUIZ = (
    "Analiza rigurosamente estos apuntes, determina si el tema pertenece a las Ciencias Exactas/Afines o a Ciencias Teóricas/Humanidades y genera una evaluación estructurada de calidad técnica con retroalimentación completa.\n\n"
    "REQUISITOS OBLIGATORIOS:\n\n"
    "Requisitos de IDIOMA:\n"
    " 1. Toda la información, enunciados, opciones, soluciones y justificaciones devueltas en el JSON deben estar estrictamente en el mismo idioma de los apuntes.\n\n"
    "Requisitos de FORMATO:\n"
    " 1. Cualquier expresión matemática, límite, derivada, integral o función en enunciados, opciones, resoluciones o soluciones, DEBE estar escrita en formato LaTeX estándar rodeada por signos de dólar - $. Ejemplo: use $f(x) = x^2$ para texto en línea y $$f'(x) = \\lim_{{h \\to 0}} \\frac{{f(x+h)-f(x)}}{{h}}$$ para ecuaciones destacadas. Se permite el uso de la barra invertida '\\' EXCLUSIVAMENTE para comandos nativos de ecuaciones de LaTeX dentro de los delimitadores $ y $$. Para texto normal o símbolos aislados, utiliza directamente su carácter Unicode (ej. '≠', '→', '∞', 'α', 'β', 'θ', etc...).\n"
    " 2. En la sección de 'ejercicios', la propiedad 'solucion' NO debe ser una sola línea corrida, debe ser un desarrollo explicativo detallado, desglosado paso a paso utilizando cuidadosamente saltos de línea reales de Markdown (\\n\\n) para separar cada paso del procedimiento de forma legible.\n\n"
    " Requisitos de CONTENIDO:\n"
    " Genera exactamente 4 elementos en la lista de 'preguntas' y exactamente 3 elementos en la lista de 'ejercicios' con dificultades balanceadas ('fácil', 'medio', 'difícil'). Si el tema es puramente teórico, plantea los ejercicios como casos de estudio, análisis crítico o escenarios de debate conceptual aplicando la misma estructura JSON rígida.\n\n"
    " Apuntes a evaluar: {texto_apuntes}"
)

# =====================================================================
# --- PERSISTENCIA DE DATOS E IMÁGENES ---
# =====================================================================

def guardar_respaldo():
    # Empaquetamos los datos del usuario activo
    paquete_unificado = {
        "datos_materias": st.session_state.datos_materias,
        "fondo_sidebar_b64": st.session_state.fondo_sidebar_b64
    }
    
    # [FASE LOCAL] Guarda en disco local mientras desarrollas en VS Code
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(paquete_unificado, f, ensure_ascii=False, indent=4)
        
    # [FASE COMERCIAL EN LA NUBE]- CLIENTE:
    # Aquí conectarás st.session_state.folder_materias con el LocalStorage
    # o tu base de datos centralizada usando la licencia del usuario.

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

def generar_paquete_zip_respaldo_szr():
    """Compila todas las asignaturas y evidencias en un archivo ZIP estructurado e higiénico sin fugas de memoria."""
    # Datos del membrete/carátula general para nombrar la carpeta raíz
    nombre_alumno = "Estudiante"
    anio_lectivo = datetime.now().strftime("%Y")
    
    # Intentamos extraer datos reales del membrete de la materia activa para personalizar
    for m in st.session_state.datos_materias.values():
        if m.get("caratula", {}).get("usuario"):
            nombre_alumno = m["caratula"]["usuario"].replace(" ", "_")
        if m.get("caratula", {}).get("ciclo"):
            anio_lectivo = m["caratula"]["ciclo"].replace(" ", "").replace("-", "_")
            break
    
    # Desinfectamos el nombre del alumno y año para la carpeta raíz del ZIP
    nombre_alumno = re.sub(r'[\\/*?:"<>|]', "_", nombre_alumno)
    carpeta_raiz = f"PORTAFOLIO_{nombre_alumno}_{anio_lectivo}"
    
    # 🚀 SOLUCIÓN DEFINITIVA BUG 05: Gestor de contexto 'with' para blindar la memoria RAM del servidor
    with io.BytesIO() as buffer_zip:
        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Recorremos cada Área de Estudio de la base de datos
            for m_nombre, m_data in st.session_state.datos_materias.items():
                
                # Reemplaza barras, dos puntos y caracteres prohibidos por guiones bajos
                nombre_carpeta_materia = re.sub(r'[\\/*?:"<>|]', "_", m_nombre.replace(" ", "_"))
                
                curso_seguro = "Periodo Actual"
                if m_data.get("caratula", {}).get("curso"):
                    curso_seguro = m_data["caratula"]["curso"].strip()
                
                # 1. Creamos la plantilla HTML estética de esta materia en específico
                html_materia = templates.obtener_html_materia(m_nombre, curso_seguro, m_data.get("temas", {}))
                
                # 2. Guardamos la foto real decodificada en la carpeta interna del ZIP de la materia
                if m_data.get("temas"):
                    for t_nombre, t_data in m_data["temas"].items():
                        if t_data.get("imagenes"):
                            for f_idx, foto in enumerate(t_data["imagenes"]):
                                # Desinfectamos también el nombre del tema para evitar conflictos de archivos secundarios
                                t_nombre_limpio = re.sub(r'[\\/*?:"<>|]', "_", t_nombre.split(' | ')[0].replace(' ', ''))
                                nombre_archivo_foto = f"img_clase_{nombre_carpeta_materia}_{t_nombre_limpio}_{f_idx}.jpg"
                                try:
                                    foto_bytes = base64.b64decode(foto["b64"])
                                    zip_file.writestr(f"{carpeta_raiz}/{nombre_carpeta_materia}/imagenes/{nombre_archivo_foto}", foto_bytes)
                                except:
                                    pass
                # Guardamos el cuaderno interactivo de la asignatura en su carpeta correspondiente
                zip_file.writestr(f"{carpeta_raiz}/{nombre_carpeta_materia}/{nombre_carpeta_materia}_COMPILADO.html", html_materia)
                
        buffer_zip.seek(0)
        bytes_finales = buffer_zip.getvalue()
        # El bloque finaliza aquí y destruye automáticamente el stream de la memoria RAM
        return bytes_finales

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
    tipo_detectado = "PARCIAL" # Estándar de fábrica de SƨR
    
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

#   📝 CALLBACK DE ACTUALIZACIÓN DE APUNTES SƨR (EVITA PÉRDIDA DE FOCO)
def callback_actualizar_bloque_apunte(materia, tema, indice_bloque, campo_destino, campo_key):
    if campo_key in st.session_state:
        valor_tipeado = st.session_state[campo_key]
        valor_antiguo = st.session_state.datos_materias[materia]["temas"][tema]["bloques"][indice_bloque].get(campo_destino, "")

        # 🔒 COMPUERTA DE SEGURIDAD 1: Validación estructural estricta de la base de datos
        if materia in st.session_state.datos_materias and tema in st.session_state.datos_materias[materia]["temas"]:
            clase_nodo = st.session_state.datos_materias[materia]["temas"][tema]
            bloques_lista = clase_nodo.get("bloques", [])
            
            # 🔒 COMPUERTA DE SEGURIDAD 2: Blindaje contra cambios de índices y eliminaciones inline
            if 0 <= indice_bloque < len(bloques_lista):
                valor_antiguo = bloques_lista[indice_bloque].get(campo_destino, "")
                
                # Detectamos si hubo una modificación real del contenido en la celda
                if valor_tipeado != valor_antiguo:
                    st.session_state.datos_materias[materia]["temas"][tema]["bloques"][indice_bloque][campo_destino] = valor_tipeado
                    
                    # [REQUERIMIENTO 4]: La batería vuelve a pendiente para liberar el botón lateral
                    st.session_state.datos_materias[materia]["temas"][tema]["estado_evaluacion"] = "pendiente"
                    
                    # 🔒 COMPUERTA DE SEGURIDAD 3: Limpieza del caché binario del quiz viejo para forzar regeneración
                    if "quiz_generado_data" in st.session_state:
                        st.session_state.quiz_generado_data = None
                        
                    guardar_respaldo()


#   📌 DECORADOR FRAGMENT: CONTROL ASÍNCRONO DEL RECORDATORIO SƨR
@st.fragment
def renderizar_cabecera_con_recordatorio():
    materia_actual = st.session_state.materia_activa
    materia_data = st.session_state.datos_materias[materia_actual]
    
    lista_clases = list(materia_data["temas"].keys())
    tema_actual = st.session_state.get("clase_seleccionada_actual")
    if not tema_actual or tema_actual not in lista_clases:
        tema_actual = lista_clases[-1] if lista_clases else None
        
    tiene_imagen = bool(materia_data["caratula"].get("imagen"))
    
    # --- RENDERIZADO DE PORTADA NATIVA (ESTRUCTURA CORREGIDA DE DOS GRANDES COLUMNAS) ---
    col_izquierda_perfil, col_derecha_controles = st.columns([5.5, 4.5])
    
    with col_izquierda_perfil:
        col_c2_foto, col_izq_datos = st.columns([3.0, 7.0])
        with col_c2_foto:
            if tiene_imagen:
                st.markdown(f'<div style="text-align: left;"><img src="data:image/jpeg;base64,{materia_data["caratula"]["imagen"]}" style="width: 100%; max-width: 120px; height: auto; aspect-ratio: 6/5; object-fit: cover; border-radius: 10px; border: 1.5px solid #E5C158;"></div>', unsafe_allow_html=True)
            else:
                inicial_materia = materia_actual[0].upper() if materia_actual else "📚"
                # Reemplazado height e inserción flexible para evitar montajes en pantallas chicas
                st.markdown(f'<div style="width: 100%; max-width: 120px; aspect-ratio: 6/5; background: linear-gradient(135deg, #FDFBF7 0%, #EFEBE0 100%); border: 2px double #E5C158; border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: inset 0 0 12px rgba(229, 193, 88, 0.2); font-family: \'Playfair Display\', serif; font-style: italic; font-size: calc(24px + 1.5vw); font-weight: bold; color: #1E293B; text-shadow: 1px 1px 0px #E5C158;">{inicial_materia}</div>', unsafe_allow_html=True)
        
        with col_izq_datos:
            st.markdown(f'<h1 class="titulo-asignatura-szr" style="margin-top: 5px !important;">{materia_actual}</h1>', unsafe_allow_html=True)
            c_data = materia_data.get("caratula", {})
            datos_m_1 = []
            if c_data.get("usuario"): datos_m_1.append(f"👤 {c_data['usuario']}")
            if c_data.get("curso_num"): datos_m_1.append(f"🎓 {c_data['curso_num']}")
            datos_m_2 = []
            if c_data.get("facultad"): datos_m_2.append(f"🏢 {c_data['facultad']}")
            if c_data.get("ciclo"): datos_m_2.append(f"🗓️ {c_data['ciclo']}")
            
            if datos_m_1:
                st.markdown(f'<div class="subtexto-estudiante-szr">{" ༻༺ ".join(datos_m_1)}</div>', unsafe_allow_html=True)
            if datos_m_2:
                st.markdown(f'<div class="subtexto-estudiante-szr" style="margin-top: 2px !important;">{" ༻༺ ".join(datos_m_2)}</div>', unsafe_allow_html=True)            
    
    with col_derecha_controles:
        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        col_sub_b1, col_sub_b2, col_sub_b3 = st.columns([2.0, 2.0, 3.0])
        
        quiz_bloqueo = bool(st.session_state.get("modo_quiz_activo", False))
        
        with col_sub_b1:
            if st.button("⚙️", key=f"trigger_cover_real_{materia_actual}", help="Configurar datos del Usuario", use_container_width=True, disabled=quiz_bloqueo):
                st.session_state.configurando_caratula = not st.session_state.configurando_caratula
                st.session_state.editando_materia = False
                st.rerun()
                
        with col_sub_b2:
            if quiz_bloqueo:
                if st.button("🔙 ", key=f"trigger_quiz_real_{materia_actual}", help="Volver al panel principal de forma segura", use_container_width=True):
                    st.session_state.modo_quiz_activo = False
                    st.session_state.quiz_generado_data = None
                    st.rerun()
            else:
                if st.button("🎯 Quiz", key=f"trigger_quiz_real_{materia_actual}", help="¡Estudia para tus lecciones AQUÍ!", use_container_width=True):
                    st.session_state.modo_quiz_activo = True
                    st.rerun()
                    
        with col_sub_b3:
            label_lectura = "Modo Lectura" if not st.session_state.modo_lectura_activo else "Modo Bloques"
            if st.button(label_lectura, key=f"btn_lectura_{materia_actual}", use_container_width=True, disabled=quiz_bloqueo, help="Comodidad para revisar tus apuntes..."):
                st.session_state.modo_lectura_activo = not st.session_state.modo_lectura_activo
                st.rerun()

        # 📌 AUXS INTERFAZ: Expander integrado por fecha con Alerta Roja Hex Pura
        if tema_actual:
            clase_data_nodo = materia_data["temas"][tema_actual]
            
            # --- MOTOR DE EVALUACIÓN CONJUNTA SƨR (ANTI-VICTORIA PREMATURA) ---
            hoy_actual = datetime.now().date()
            tarea_vencida = False
            if "lista_tareas" in clase_data_nodo:
                total_tareas = len(clase_data_nodo["lista_tareas"])
            else:
                total_tareas = 0
                # Opcional: puedes inicializarla para que no falle después
                clase_data_nodo["lista_tareas"] = [] 
            total_completadas = 0
            alguno_incumplido = False
            alguno_pendiente = False

            # Recorremos el historial completo para calcular el estado real de la clase
            for t in clase_data_nodo["lista_tareas"]:
                try:
                    lim_dt = datetime.strptime(t["fecha_limite"], "%Y-%m-%d").date()
                    if t["completada"]:
                        total_completadas += 1
                    else:
                        if hoy_actual > lim_dt:
                            alguno_incumplido = True
                        else:
                            alguno_pendiente = True
                except: pass

            partes_llave = tema_actual.split(" | ")
            fecha_leccion_pura = partes_llave[1] if len(partes_llave) > 1 else "Hoy"

            # 📊 Tus cadenas de títulos e iconos originales respetados y sincronizados
            if total_tareas == 0:
                titulo_expander = f"⚪ {fecha_leccion_pura} - [Sin tareas registradas]"
                esta_incumplida = False
            elif alguno_incumplido:
                titulo_expander = f"🚨 *{fecha_leccion_pura}* - ¡Alerta de actividad Incompleta!"
                esta_incumplida = True
            elif alguno_pendiente:
                titulo_expander = f"🟢 Pendiente [{fecha_leccion_pura}] -> Tienes actividades en agenda."
                esta_incumplida = False
            elif total_completadas == total_tareas:
                titulo_expander = f"🏅 ¡Felicidades! Actividades ¡Completadas! el {fecha_leccion_pura}"
                esta_incumplida = False

            with st.expander(titulo_expander, expanded=esta_incumplida):
                
                # CORRECCIÓN CRONOLÓGICA (AUXS): Solo hay incumplimiento el DÍA DESPUÉS de vencerse
                hoy_actual = datetime.now().date()
                tarea_vencida = False
                entrega_tardia = False
                if "lista_tareas" not in clase_data_nodo:
                    clase_data_nodo["lista_tareas"] = []
                    
                # Variable de control en sesión para alternar el mini-formulario de añadir
                if "abrir_formulario_tarea" not in st.session_state:
                    st.session_state.abrir_formulario_tarea = False

                # --- FILA DE TÍTULO ERGONÓMICA CON BOTÓN MODULAR ---
                col_titulo_h, col_btn_add_h = st.columns([8.0, 2.0])
                with col_titulo_h:
                    st.markdown("<p style='font-size:13px; color:#475569; margin-top:10px; font-weight:bold;'>📂 Pendientes Registrados:</p>", unsafe_allow_html=True)
                with col_btn_add_h:
                    # Botón sutil al lado de pendientes para alternar la fila de ingreso rápida
                    if st.button("📌", key=f"btn_toggle_add_task_{tema_actual}", use_container_width=True, help="Crear un recordatorio de Actividad"):
                        st.session_state.abrir_formulario_tarea = not st.session_state.abrir_formulario_tarea
                        st.rerun()

                # 1. FILA DE INGRESO DINÁMICA (Aparece solo si pulsa el botón)
                if st.session_state.abrir_formulario_tarea:
                    st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
                    col_add_desc, col_add_cal, col_add_btn = st.columns([5.5, 2.5, 2.0])
                    
                    with col_add_desc:
                        nueva_tarea_tipeada = st.text_input("Nueva tarea urgente:", placeholder="Ej. Entregar informe...", key=f"add_task_txt_{tema_actual}", label_visibility="collapsed")
                    
                    with col_add_cal:
                        fecha_limite_dt = st.date_input("Fecha límite:", value=datetime.now().date(), key=f"add_task_cal_{tema_actual}", label_visibility="collapsed")
                        
                    with col_add_btn:
                        if st.button("✓", key=f"add_task_btn_{tema_actual}", use_container_width=True, type="primary", help="Guardar pendiente"):
                            if nueva_tarea_tipeada.strip():
                                clase_data_nodo["lista_tareas"].append({
                                    "descripcion": nueva_tarea_tipeada.strip(),
                                    "fecha_limite": fecha_limite_dt.strftime("%Y-%m-%d"),
                                    "completada": False
                                })
                                st.session_state.abrir_formulario_tarea = False # Cierra la fila tras guardar
                                guardar_respaldo()
                                st.rerun()

                # 2. RENDERIZADO DEL HISTORIAL DE PENDIENTES CON CONTROL DE DÍA DESPUÉS
                if clase_data_nodo["lista_tareas"]:
                    st.markdown("<hr style='border-top: 1px dashed rgba(0,0,0,0.06); margin: 6px 0 10px 0;'>", unsafe_allow_html=True)
                    
                    for idx, t_item in enumerate(clase_data_nodo["lista_tareas"]):

                        # --- ENLACE CRONOLÓGICO SEGURO SƨR ---
                        tarea_vencida = False
                        try:
                            limite_dt = datetime.strptime(t_item["fecha_limite"], "%Y-%m-%d").date()
                            # 🚀 REGLA ESTRICTA: Solo va tarde si NO está hecha y HOY ya es un día después
                            if hoy_actual > limite_dt and not t_item["completada"]:
                                tarea_vencida = True
                        except: pass

                        # 📊 ASIGNACIÓN QUIRÚRGICA DE ICONOS PREMIUM (PUNTUALIDAD CONTROLADA)
                        if t_item["completada"]:
                            # Compara la fecha límite contra el día de HOY para saber si la marcó tarde
                            try:
                                limite_dt = datetime.strptime(t_item["fecha_limite"], "%Y-%m-%d").date()
                                if hoy_actual > limite_dt:
                                    # 😔 Entregada con retraso (Un día después o más)
                                    icono_estado = "&#x1F614;"
                                    estilo_text_item = "text-decoration: line-through; color: #B45309; opacity: 0.85;"
                                else:
                                    # 🏆 Entregada perfectamente a tiempo (Hoy o antes de vencerse)
                                    icono_estado = "&#x1F3C6;"
                                    estilo_text_item = "text-decoration: line-through; color: #94A3B8; font-size: 12.5px"
                            except:
                                icono_estado = "&#x1F3C6;"
                                estilo_text_item = "text-decoration: line-through; color: #94A3B8; font-style: italic;"
                        
                        elif tarea_vencida:
                            # 🚫 Alerta Roja por incumplimiento estricto
                            icono_estado = "&#x1F6AB;"
                            estilo_text_item = "color: #FF0F0F; font-weight: bold; text-transform: uppercase;"
                        else:
                            # ⏳ Tarea pendiente dentro de la fecha límite (Reloj de arena)
                            icono_estado = "&#x23F3;"
                            estilo_text_item = "color: #1E293B;"

                        # Renderizado simétrico de la fila
                        col_hist_desc, col_hist_date, col_hist_chk = st.columns([6.0, 3.0, 1.0])

                        with col_hist_desc:
                            st.markdown(f"<div style='font-size: 11.5px; margin-top: 4px; {estilo_text_item}'>{icono_estado} {t_item['descripcion']}</div>", unsafe_allow_html=True)

                        with col_hist_date:
                            st.markdown(f"<div style='font-size: 11px; color: #64748B; margin-top: 4px;'>📅 Límite: <strong>{t_item['fecha_limite']}</strong></div>", unsafe_allow_html=True)
                            
                        with col_hist_chk:
                            # 🚀 SOLUCIÓN DEFINITIVA BUG 04: Clave hiper-específica blindada contra colisiones inter-materias
                            chk_key = f"chk_hist_task_{st.session_state.materia_activa}_{tema_actual}_{idx}"
                            check_val = st.checkbox(
                                "Completado", 
                                value=t_item["completada"], 
                                key=chk_key,
                                label_visibility="collapsed" 
                            )                            
                            if check_val != t_item["completada"]:
                                clase_data_nodo["lista_tareas"][idx]["completada"] = check_val
                                guardar_respaldo()
                                st.rerun()

# 🤖 MOTOR GENERAL DE IA CON CONEXIÓN REAL A GOOGLE GEMINI (BLINDADO)
def inyectar_recursos_inteligentes(texto, num_parrafo, col_render, bloque_referencia, tema_actual):
    if not texto.strip() or len(texto) <= 10:
        return
        
    if "ia_sugerencias" not in bloque_referencia:
        bloque_referencia["ia_sugerencias"] = ""
        
    if bloque_referencia["ia_sugerencias"]:
        with col_render:
            st.markdown(
                """
                <div style='background-color: rgba(135, 169, 107, 0.08); padding: 11px 15px; border-radius: 8px; border-left: 4.5px solid #87A96B; margin-top: 0px;'>
                    <span style='color: #2E4A3F; font-weight: bold; font-size: 11.5px; display: block; margin-bottom: 0px;'>
                        🧠 Ampliación de Contexto (SƨR AI)
                    </span>
                """, 
                unsafe_allow_html=True
            )
            st.markdown(bloque_referencia["ia_sugerencias"])
            st.markdown("</div>", unsafe_allow_html=True)
            texto_modificado = texto.strip() != bloque_referencia.get("ia_origen_texto", "").strip()   
            if st.button("🔄 Actualizar", 
                key=f"re_btn_ia_{st.session_state.materia_activa}_{tema_actual}_{num_parrafo}",
                disabled=not texto_modificado,
                help="Se activa si agregas nuevo contenido en este bloque" if not texto_modificado else "Haz clic para actualizar con la nueva info agregada"
            ):
                bloque_referencia["ia_sugerencias"] = ""
                st.rerun()
        return

    with col_render:
        if st.button(f"🧠 Supervisor I.A. Refuerzo - Bloque {num_parrafo:02d}", key=f"btn_ia_gate_{st.session_state.materia_activa}_{tema_actual}_{num_parrafo}", use_container_width=True):
            st.session_state.ejecutando_peticion_ia = True # 🔒 Cierra compuerta al hacer clic
            st.rerun() # Fuerza un redibujado instantáneo para congelar los text_areas

            with st.spinner("Generando recursos premium..."):
                try:
                    api_key_segura = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
                    client = genai.Client(api_key=api_key_segura)                    
                    prompt = (
                        f"Se un tutor académico eficiente y analiza minuciosamente estos apuntes de clase: '{texto}'.\n"
                        f"Genera exactamente 3 recursos de autoaprendizaje complementarios con enlaces dinámicos.\n"
                        f"Devuelve estrictamente el siguiente formato en Markdown, sin textos introductorios, saludos ni notas de relleno:\n\n"
                        f"📺 **Video Recomendado:** Proporciona un enlace de búsqueda directa en YouTube formateado exactamente así: `[Ver videos sobre 'Tema Exacto'](https://youtube.com)`. Menciona un canal educativo recomendado (como 'QuantumFracture', 'JulioProfe', 'Biología desde Cero', etc...) ideal para este concepto.\n\n"
                        f"🛠️ **Simulador o Herramienta:** Nombra una plataforma web interactiva real (como 'PhET Simulations', 'Geogebra', 'WolframAlpha', 'Khan Academy', etc...) útil para practicar y añade su enlace directo de Google formateado así: `[Explorar Herramienta](https://google.com)`.\n"
                        f"📄 **Material de Lectura Científica:** Genera una frase de búsqueda de alta precisión terminada en 'filetype:pdf' para encontrar guías universitarias en Google, y entrégala formateada en un enlace listo de esta manera: `[Descargar PDF Académico](https://google.com)`.\n"
                        f"REGLAS ESTRICTAS:\n"
                        f"- Sé sumamente directo, breve y conciso (máximo dos líneas de descripción por recurso).\n"
                        f"- Asegúrate de reemplazar los espacios por símbolos '+' dentro de la parte 'search?q=' o 'search_query=' de los enlaces de Google/YouTube para que no se rompan las URLs en Streamlit.\n"
                        f"- Si los apuntes están en español, los términos de búsqueda y recomendaciones deben ser en español."
                    )
                    # 🚀 SISTEMA DE REINTENTOS ANTI-SATURACIÓN SƨR
                    response = None
                    ultimo_error_bloque = None

                    for intento in range(3):
                        try:                    
                            response = client.models.generate_content(
                                model='gemini-3.8-flash',
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    temperature=0.1,
                                )
                            )
                            if response:
                                break  # Si responde con éxito, rompemos el bucle
                        
                        except Exception as e_micro_pico:
                            ultimo_error_bloque = e_micro_pico
                            error_msg = str(e_micro_pico).lower()

                            # Captura saturación, límites de cuota o indisponibilidad temporal del servidor de Google
                            if any(x in error_msg for x in ["503", "429", "quota", "overloaded", "unavailable"]):
                                # Backoff Exponencial con Jitter (retraso incremental aleatorio)
                                tiempo_espera_micro = (1.5 ** intento) + random.uniform(0.3, 1.0)
                                time.sleep(tiempo_espera_micro)
                            else:
                                # Si es un error de credenciales o de API Key, se lanza de inmediato
                                raise e_micro_pico

                    # 🔒 COMPUERTA DE CONTENCIÓN: Si el supervisor falla tras 3 intentos, evita el crash en la mesa de trabajo
                    if response is None or not hasattr(response, 'text') or not response.text:
                        detalle_error = str(ultimo_error_bloque if ultimo_error_bloque else 'Timeout')
                        html_explorador_error = f"""
                            <div style='
                               background: linear-gradient(135deg, rgba(251, 191, 36, 0.05) 0%, rgba(217, 119, 6, 0.02) 100%);
                               border: 1.5px dashed rgba(229, 193, 88, 0.4);
                               border-radius: 10px;
                               padding: 12px 16px;
                               margin-top: 10px;
                               margin-bottom: 10px;
                               font-family: \"Inter\", sans-serif;
                            '>
                               <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 6px;'>
                                   <span style='font-size: 15px; animation: pulse 2s infinite;'>🛸</span>
                                   <strong style='color: #B45309; font-size: 13px; font-family: \"Playfair Display\", serif;'>SƨR AI ~ Servidor en Exploración</strong>
                               </div>
                               <p style='margin: 0; font-size: 12px; color: #78350F; line-height: 1.45; font-style: italic;'>
                                   Nuestro robot asistente A.I. está explorando rutas alternas, autopista principal saturada.
                                   Intenta de nuevo en unos segundos.
                               </p>
                                <details style='cursor: pointer; font-size: 11px; color: #9A3412; margin-top: 5px;'>
                                    <summary style='font-weight: bold; focus: outline-none;'>🛠️ Ver bitácora técnica de inspección</summary>
                                    <div style='padding: 6px 10px; background-color: rgba(220, 38, 38, 0.03); border-radius: 4px; border-left: 2px solid #DC2626; margin-top: 4px; font-family: monospace; font-size: 10.5px;'>
                                        Detalles: {detalle_error}
                                    </div>
                                </details>
                            </div>
                        """
                        st.markdown(html_explorador_error, unsafe_allow_html=True)
                        st.stop()
                    
                    # 📐 SANEADO Y SELLADO SEGURO DE RESPUESTA SƨR
                    if response and hasattr(response, 'text') and response.text.strip():
                        bloque_referencia["ia_sugerencias"] = response.text
                        # 🔒 SELLO DE COEXISTENCIA: Almacenamos el texto base para la lógica del botón Actualizar
                        bloque_referencia["ia_origen_texto"] = texto.strip()
                        st.session_state.ejecutando_peticion_ia = False # 🔓 Abre compuerta al terminar con éxito                
                        guardar_respaldo()
                        st.rerun()
                    else:
                        st.error("⚠️ La I.A. responde texto vacío. Resolviendo... Intenta otra vez.")
                    
                except Exception as e:
                    # LÍNEA DE DIAGNÓSTICO ACTIVA: Muestra fallos reales en la consola o app
                    st.error(f"💥 Error real del SDK: {str(e)}")
                    error_msg = str(e).lower()
                    if "quota" in error_msg or "429" in error_msg or "503" in error_msg or "unavailable" in error_msg:
                        st.error("⏳ Los servidores de I.A. están saturados en este momento, espera un par de minutos. Resolviendo...")
                    elif "api_key" in error_msg:
                        st.error("🔑 Error de credenciales: La clave ingresada en el servidor es inválida.")
                    else:
                        st.warning("✨ [SƨR - Servidor en espera... Resolviendo...]")

# --- DEFINICIÓN DE LA PLANTILLA ÚNICA DE PROMPT A.I. SƨR ---
def ejecutar_peticion_ia_bunker(texto_apuntes, prompt=PROMPT_PLANTILLA_QUIZ):
    llave_limpia = str(st.secrets["GEMINI_API_KEY"]).strip().replace('"', '').replace("'", "")
    client = genai.Client(api_key=llave_limpia)

    class PreguntaModel(BaseModel):
        p: str; a: str; b: str; c: str; d: str; r: str; justificacion: str

    class EjercicioModel(BaseModel):
        enunciado: str; dificultad: Literal["fácil", "medio", "difícil"]; solucion: str; error: str

    class ContenedorQuiz(BaseModel):
        tema: str; es_teorica: bool; preguntas: List[PreguntaModel]; ejercicios: List[EjercicioModel]; truco: str

    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ContenedorQuiz,
            temperature=0.1
        )
    )
    return response

# --- MOTOR PARSER PARA LA LIMPIEZA ADAPTATIVA DE CADENAS REALES ---
def procesar_y_limpiar_json_quiz(json_texto):
    res_json = json.loads(json_texto)
    pregs = res_json.get("preguntas", [])
    ejs = res_json.get("ejercicios", [])
    es_teorica_check = res_json.get("es_teorica", False)
    dificultades_fallback = ["fácil", "medio", "difícil"]

    while len(pregs) < 4:
        pregs.append({"p": "Pregunta analítica de refuerzo", "a": "-", "b": "-", "c": "-", "d": "-", "r": "a", "justificacion": "Repaso general."})

    # Saneado dinámico de strings según la clasificación de la IA
    for e_item in ejs:
        if "solucion" in e_item:
            if not es_teorica_check:
                e_item["solucion"] = (str(e_item["solucion"])
                    .replace('perspective$$', '$$').replace('Perspective$$', '$$')
                    .replace('$$\\n', '$$\n\n').replace('\\n$$', '\n\n$$')
                    .replace('\\n$', '\n\n$').replace('$\\n', '$\n\n')
                    .replace('\\n', '\n\n').replace('\n', '\n\n')
                )
            else:
                e_item["solucion"] = str(e_item["solucion"]).replace('\\n', '\n\n').replace('\n', '\n\n')
        if "error" in e_item:
            e_item["error"] = str(e_item["error"]).replace('\\n', '\n\n').replace('\n', '\n\n')

    while len(ejs) < 3:
        idx_falta = len(ejs)
        ejs.append({
            "enunciado": "Reactivo conceptual complementario.",
            "dificultad": dificultades_fallback[idx_falta],
            "solucion": "Análisis desarrollado del bloque de apuntes escolar.",
            "error": "Confirmar fuentes bibliográficas."
        })

    return {
        "tema": res_json.get("tema", "Evaluación Automática SƨR"),
        "es_teorica": es_teorica_check,
        "preguntas": pregs[:4],
        "ejercicios": ejs[:3],
        "truco": res_json.get("truco", "Mantén un mapa mental estructurado.")
    }

# =====================================================================
# --- INICIALIZACIÓN DEL CUADERNO INTELIGENTE ---
# =====================================================================
if "datos_materias" not in st.session_state:
    respaldo = cargar_respaldo()
    if respaldo:
        st.session_state.datos_materias = respaldo["datos_materias"]
        st.session_state.fondo_sidebar_b64 = respaldo["fondo_sidebar_b64"]
    else:
        # Estructura sellada desde el inicio para evitar KeyErrors en ejecuciones limpias
        caratula_defecto = {
            "imagen": None, "usuario": "", "ciclo": "", "curso": "", 
            "curso_num": "", "paralelo_letra": "", "num_parcial": "1ER", 
            "tipo_periodo": "PARCIAL", "semestre_num": "", "facultad": ""
        }
        
        st.session_state.datos_materias = {
            "Area 1": {"temas": {}, "biblioteca": [], "caratula": caratula_defecto.copy()},
            "Area 2": {"temas": {}, "biblioteca": [], "caratula": caratula_defecto.copy()},
            "Area 3": {"temas": {}, "biblioteca": [], "caratula": caratula_defecto.copy()}
        }
        st.session_state.fondo_sidebar_b64 = None

if "materia_activa" not in st.session_state:
    if st.session_state.datos_materias:
        st.session_state.materia_activa = list(st.session_state.datos_materias.keys())[0]
    else:
        st.session_state.materia_activa = "Area 1"


#---- Variables lógicas de control para los formularios desplegables----#
if "editando_materia" not in st.session_state:
    st.session_state.editando_materia = False

if "expander_nueva_mat_abierto" not in st.session_state:
    st.session_state.expander_nueva_mat_abierto = False

if "configurando_caratula" not in st.session_state:
    st.session_state.configurando_caratula = False

# Reparación de bug auto-colapso de las pestañas expandibles
if "rep_bug_exp" not in st.session_state:
    st.session_state.rep_bug_exp = 0

#  INYECCIÓN DE VARIABLES DE GESTIÓN SEMESTRAL SƨR
if "cierre_estado_paso" not in st.session_state:
    st.session_state.cierre_estado_paso = "inicio"

if "respaldo_descargado_exito" not in st.session_state:
    st.session_state.respaldo_descargado_exito = False

if "modo_lectura_activo" not in st.session_state:
    st.session_state.modo_lectura_activo = False

if "quiz_generado_data" not in st.session_state:
    st.session_state.quiz_generado_data = None

if "contador_temas_toast" not in st.session_state:
    st.session_state.contador_temas_toast = 0

# =====================================================================
#   🔒 CORRECCIÓN DEL INTEGRIDAD DE METADATA (CONCORDANCIA SƨR)
# =====================================================================
def callback_agregar_asignatura_nueva():
    nombre_materia_ingresado = st.session_state.get("input_nueva_materia_minimal", "").strip()
    if nombre_materia_ingresado:
        if nombre_materia_ingresado in st.session_state.datos_materias:
            st.sidebar.error(f"⚠️ El área '{nombre_materia_ingresado}' ya existe. Procure ingresarla con otro nombre.")
            return  # 🔒 COMPUERTA DE SEGURIDAD: Corta la ejecución de inmediato para evitar la sobrescritura
        else:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            tema_inicial_defecto = "Introducción"
            llave_introduccion_szr = f"Clase 01 | {fecha_hoy} | {tema_inicial_defecto}"
            
            # 🚀 SINCRONIZACIÓN S.E.D.E: Agregamos la metadata requerida por tus bloques centrales
            st.session_state.datos_materias[nombre_materia_ingresado] = {
                "temas": {
                    llave_introduccion_szr: {
                        "bloques": [{"contenido": "", "observacion": "", "ia_sugerencias": ""}], 
                        "imagenes": [],
                        "lista_tareas": [], # Inicializa la agenda limpia y moderna
                        "meta_num": "01",
                        "meta_fecha": fecha_hoy,
                        "meta_titulo": tema_inicial_defecto,
                        "meta_parcial": "1ER PARCIAL"
                    }
                },
                "caratula": {
                    "imagen": None,
                    "usuario": "",
                    "ciclo": "",
                    "curso": "",
                    "curso_num": "",
                    "paralelo_letra": "",
                    "num_parcial": "1ER",
                    "tipo_periodo": "PARCIAL",
                    "semestre_num": "",
                    "facultad": ""
                },
                "biblioteca": []
            }
            
            # Forzamos el anclaje seguro de navegación para evitar desajustes de llaves previas
            st.session_state.materia_activa = nombre_materia_ingresado
            st.session_state.clase_seleccionada_actual = llave_introduccion_szr
            st.session_state.expander_nueva_mat_abierto = False 
            guardar_respaldo()

def callback_cambiar_materia_activa(nueva_materia):
    st.session_state.materia_activa = nueva_materia
    st.session_state.editando_materia = False
    # No necesita st.rerun(), Streamlit actualiza el estado de forma automática y limpia

# =====================================================================
# 🧠 MOTOR REUTILIZABLE DE EVALUACIÓN ACADÉMICA (SƨR AI CORE UNIFICADO)
# =====================================================================
def ejecutar_generacion_quiz_szr(texto_acumulado_apuntes: str, barra_progreso=None) -> dict:
    """
    Abstrae de forma segura la generación del examen utilizando tu canal de IA existente.
    Maneja reintentos por saturación, actualiza la UI y limpia fugas de LaTeX/Markdown.
    """
    # 🔒 COMPUERTA DE SEGURIDAD PREVENTIVA
    if not texto_acumulado_apuntes.strip():
        raise ValueError("El bloque de apuntes está completamente vacío.")

    response = None
    ultimo_error_capturado = None

    # 🚀 SISTEMA DE REINTENTOS ANTI-SATURACIÓN DE SERVIDOR SƨR
    for intento in range(3):
        try:
            if barra_progreso:
                porcentaje_intento = 15 + (intento * 20)
                barra_progreso.progress(min(porcentaje_intento, 70), text=f"🛰️ Transmitiendo y analizando información... (Intento {intento+1}/3)")
            
            # 🔄 REUTILIZACIÓN DE TU FUNCIÓN ORIGINAL INTACTA
            response = ejecutar_peticion_ia_bunker(texto_acumulado_apuntes, prompt=PROMPT_PLANTILLA_QUIZ)
            
            if response and response.text:
                break  # Rompe el bucle si responde con éxito
        except Exception as e_quiz_pico:
            ultimo_error_capturado = e_quiz_pico
            error_msg = str(e_quiz_pico).lower()
            
            # Captura saturación o límites de cuota (429, 503)
            if any(x in error_msg for x in ["503", "429", "quota", "overloaded", "unavailable"]):
                tiempo_espera_bloqueo = (2 ** intento) + random.uniform(0.5, 1.5)
                time.sleep(tiempo_espera_bloqueo)
            else:
                raise e_quiz_pico  # Lanza errores fatales de inmediato (credenciales, etc.)

    if response is None or not hasattr(response, 'text') or not response.text:
        raise genai.errors.APIError(f"Servidores de Google congestionados. Detalles: {str(ultimo_error_capturado if ultimo_error_capturado else 'Timeout')}")

    if barra_progreso:
        barra_progreso.progress(85, text="✧📜 [SƨR Core]: Estructurando reactivos y aplicando formato...")

    # --- MOTOR PARSER Y SANEADO TIPOGRÁFICO DE RESPUESTA ---
    res_json = json.loads(response.text)                
    pregs = res_json.get("preguntas", [])
    ejs = res_json.get("ejercicios", [])
    es_teorica_check = res_json.get("es_teorica", False)
    dificultades_fallback = ["fácil", "medio", "difícil"]

    # Garantiza la presencia estricta de las 4 preguntas requeridas
    while len(pregs) < 4:
        pregs.append({
            "p": "Pregunta de refuerzo analítico",
            "a": "-", "b": "-", "c": "-", "d": "-", "r": "a",
            "justificacion": "Revise el bloque de contenido de la lección."
        })

    # Limpieza quirúrgica de saltos de línea y bloques LaTeX para evitar roturas visuales
    for e_item in ejs:
        if "solucion" in e_item:
            if not es_teorica_check:
                e_item["solucion"] = (
                    str(e_item["solucion"])
                    .replace('perspective$$', '$$').replace('Perspective$$', '$$')
                    .replace('$$\\n', '$$\n\n').replace('\\n$$', '\n\n$$')
                    .replace('\\n$', '\n\n$').replace('$\\n', '$\n\n')
                    .replace('\\n', '\n\n').replace('\n', '\n\n')
                )
            else:
                e_item["solucion"] = str(e_item["solucion"]).replace('\\n', '\n\n').replace('\n', '\n\n')
        
        if "error" in e_item:
            e_item["error"] = str(e_item["error"]).replace('\\n', '\n\n').replace('\n', '\n\n')

    # Garantiza la presencia estricta de los 3 ejercicios requeridos
    while len(ejs) < 3:
        indice_falta = len(ejs)
        ejs.append({
            "enunciado": "Reactivo analítico complementario conceptual.",
            "dificultad": dificultades_fallback[indice_falta],
            "solucion": "Análisis desarrollado del bloque de apuntes escolar.",
            "error": "Confirmar fuentes bibliográficas oficiales."
        })

    if barra_progreso:
        barra_progreso.progress(100, text="🔋 [SƨR Core]: ¡Evaluación generada con éxito!")
        time.sleep(0.4)
        barra_progreso.empty()

    # Retorna el diccionario listo para indexarse
    return {
        "tema": res_json.get("tema", "Evaluación Automática SƨR"),
        "es_teorica": es_teorica_check,
        "preguntas": pregs[:4],
        "ejercicios": ejs[:3],
        "truco": res_json.get("truco", "Mantén un mapa mental estructurado.")
    }

# --- PANEL LATERAL: BRANDING Y ASIGNATURAS (REPARADO Y BLINDADO) ---
# 📐 LA REPARACIÓN DEFINITIVA: Separamos el logotipo en bloques limpios para evitar rupturas de comillas HTML
st.sidebar.markdown("<h1 style='text-align: center; color: #D4AF37; font-size: 75px; margin: 0; font-family: sans-serif;'>🧠 SƨR</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<h3 style='text-align: center; color: #FFD700; font-size: 15px; margin: -20px 0 0px 0; font-weight: 800; text-align: center;'>Sawata s.ᴇ.ᴅ.ᴇ. Resources</h3>", unsafe_allow_html=True)

st.sidebar.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

st.sidebar.markdown("---")
# --- CONFIGURACIÓN DE DATOS DE LA MATERIA SELECCIONADA ---
materia_data = st.session_state.datos_materias[st.session_state.materia_activa]

# 📐 Creamos dos columnas equilibradas en el panel lateral
col_titulo_areas, col_boton_mas = st.sidebar.columns([8.0, 2.0])

with col_titulo_areas:
    st.markdown(
        """
        <div style='margin-top: -5px;'>
            <h2 style='color: #1B1B1B; font-size: 23px; font-family: "Arial", sans-serif !important; font-weight: 700; letter-spacing: 0.5px; margin-top: -13px;'>📚 Áreas de Estudio</h2>
        </div>
        """, 
        unsafe_allow_html=True
    )

with col_boton_mas:
    # Botón minimalista con símbolo "+" (Unicode Hex) que alterna el estado del mini-expander
    if st.button("🆕", key="btn_toggle_agregar_minimal", use_container_width=True, help="Agregar nueva asignatura"):
        st.session_state.expander_nueva_mat_abierto = not st.session_state.expander_nueva_mat_abierto
        st.rerun()

# 📐 Sub-contenedor desplegable condicional que actúa como expander compacto bajo la fila
if st.session_state.expander_nueva_mat_abierto:
    with st.sidebar.container():
        st.markdown("<p style='font-size: 12px; color: #475569; margin-bottom: 5px; margin-top: -5px;'>✍️ Escribe el nombre de la nueva área de estudio:</p>", unsafe_allow_html=True)
        
        col_in_text, col_in_btn = st.columns([7.5, 2.5])
        with col_in_text:
            st.text_input("Nueva asignatura:", key="input_nueva_materia_minimal", placeholder="Ej. Biología", label_visibility="collapsed")
        with col_in_btn:
            st.button("➕", key="btn_guardar_materia_minimal", use_container_width=True, on_click=callback_agregar_asignatura_nueva)
            
        st.markdown("</div>", unsafe_allow_html=True)

for mat in list(st.session_state.datos_materias.keys()):
    if mat == st.session_state.materia_activa:
        st.sidebar.markdown(
            f"""
            <div style='
                background: linear-gradient(135deg, rgba(229, 193, 88, 0.15) 0%, rgba(229, 193, 88, 0.05) 100%);
                border: 1.5px solid #E5C158;
                border-radius: 8px;
                padding: 8px 14px;
                margin-bottom: 6px;
                font-family: "Inter", sans-serif;
                font-weight: bold;
                font-size: 14px;
                color: #1E293B;
                box-shadow: 0 2px 6px rgba(229, 193, 88, 0.1);
                display: flex;
                align-items: center;
                gap: 8px;
            '>
                <span style='color: #E5C158; font-size: 16px; text-shadow: 0px 0px 4px rgba(229, 193, 88, 0.8), 1px 1px 2px rgba(0, 0, 0, 0.2)'>🌟</span> {mat}
            </div>
            """, 
            unsafe_allow_html=True
        )    
    else:
        st.sidebar.button(
            mat, 
            key=f"btn_nav_{mat}_{st.session_state.rep_bug_exp}", # Vinculado al contador dinámico 
            use_container_width=True,
            on_click=callback_cambiar_materia_activa,
            args=(mat,)
        )

st.sidebar.markdown("---")

# =====================================================================
# 📖 BÚNKER MODULAR: BIBLIOTECA VIRTUAL POR ASIGNATURA
# =====================================================================
if "biblioteca" not in materia_data:
    materia_data["biblioteca"] = []

# Titulo del expander según el estado del Estante
if not materia_data["biblioteca"]:
    titulo_estante = "📭 Biblioteca Digital Vacia - Indexar"
else:
    titulo_estante = f"📭 Biblioteca Digital - {len(materia_data['biblioteca'])} Libro(s)"
with st.sidebar.expander(titulo_estante, key=f"exp_bib_szr{st.session_state.rep_bug_exp}"):
    if not materia_data["biblioteca"]:
        st.markdown(
        """
        <div style='border: 2px dashed #CBD5E1; border-radius: 8px; padding: 15px; text-align: center; background-color: #F8FAFC;'>
            <span style='font-size: 24px;'>📭</span>
            <p style='margin: 5px 0 0 0; font-size: 12px; color: #64748B; font-weight: bold;'>Estante Digital Vacío</p>
            <p style='margin: 2px 0 0 0; font-size: 11px; color: #94A3B8;'>Indexa tus PDFs o Drive arriba.</p>
        </div>
        """, 
        unsafe_allow_html=True
        )
    else:
        st.markdown("<p style='font-size: 10.5px; margin-top:-5px;'>Registra tus PDFs o enlaces de Drive aquí:</p>", unsafe_allow_html=True)

    # Campos del formulario pra indexar
    num_libros_actuales = len(materia_data["biblioteca"])
    nombre_libro = st.text_input("Título:", placeholder="Ej. Álgebra de Baldor", key=f"lib_name_{st.session_state.materia_activa}_{num_libros_actuales}")
    link_libro = st.text_input("Enlace (Drive/URL):", placeholder="https://...", key=f"lib_link_{st.session_state.materia_activa}_{num_libros_actuales}")

    if st.button("🔖 Indexar Libro", use_container_width=True):
        if nombre_libro.strip() and link_libro.strip():
            materia_data["biblioteca"].append({
                "nombre": nombre_libro.strip(),
                "url": link_libro.strip()
            })
            guardar_respaldo()
            st.session_state.rep_bug_exp += 1
            st.rerun()
    if materia_data["biblioteca"]:
        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
        
        # Variable de control para posponer la eliminación segura
        libro_a_eliminar = None
        
        # Clonamos la lista para iterar sobre una base estática y segura
        for idx, libro in enumerate(list(materia_data["biblioteca"])):
            col_lib_link, col_lib_del = st.sidebar.columns([8.3, 1.7])
            
            with col_lib_link:
                st.markdown(f"<span style='font-size: 12.5px;'>📎 Libro - [{libro['nombre']}]({libro['url']})</span>", unsafe_allow_html=True)
            
            with col_lib_del:
                if st.button("🗑️", key=f"del_lib_{st.session_state.materia_activa}_{idx}", use_container_width=True):
                    libro_a_eliminar = idx
        
        # Ejecutamos la mutación fuera del bucle de la interfaz gráfica
        if libro_a_eliminar is not None:
            materia_data["biblioteca"].pop(libro_a_eliminar)
            guardar_respaldo()
            st.session_state.rep_bug_exp += 1
            st.rerun()
st.sidebar.markdown("   ")

# =====================================================================
#   ⚡ [PAQUETE 2 REPARADO]: BOTÓN GUARDAR DEL SIDEBAR INTEGRAL SƨR
# =====================================================================
lista_de_clases_sidebar = list(materia_data.get("temas", {}).keys())
tema_actual_sidebar = st.session_state.get("clase_seleccionada_actual")
if lista_de_clases_sidebar and (tema_actual_sidebar not in lista_de_clases_sidebar):
    tema_actual_sidebar = lista_de_clases_sidebar[-1]

# Variables de control métrico y seguridad originales restablecidas
bateria_baja = True
temas_incompletos = 0
temas_pendientes = 0
temas_guardados = 0
ayuda_contextual = ""
total_caracteres_bunker = 0
estado_evaluacion_actual = "pendiente"

# [REQUERIMIENTO 1]: Buscar dinámicamente el primer tema pendiente en el historial para guiar al usuario
tema_pendiente_por_guardar = None
for llave_t in lista_de_clases_sidebar:
    estado_real = materia_data["temas"][llave_t].get("estado_evaluacion", "pendiente")
    if estado_real == "completado":
        temas_guardados += 1
    else:
        temas_pendientes += 1
        if tema_pendiente_por_guardar is None:
            tema_pendiente_por_guardar = llave_t

# Definición del tema objetivo de procesamiento (prioriza el pendiente detectado)
target_a_guardar = tema_pendiente_por_guardar if tema_pendiente_por_guardar else tema_actual_sidebar

if target_a_guardar and "temas" in materia_data:
    clase_bunker_segura = materia_data["temas"].get(target_a_guardar, {})
    bloques_bunker = clase_bunker_segura.get("bloques", [])
    # Medición rápida de volumen en memoria sin concatenar en RAM
    total_caracteres_bunker = sum(len(b.get("contenido", "")) + len(b.get("observacion", "")) for b in bloques_bunker)
    titulo_leccion_bunker = clase_bunker_segura.get("meta_titulo", "Clase Activa")
    
    if tema_pendiente_por_guardar and total_caracteres_bunker < 150:
        # Caso apuntes breves: Alerta Ámbar restrictiva
        bateria_baja = True
    elif tema_pendiente_por_guardar:
        bateria_baja = False
    else:
        # Portafolio al día: Notificación de éxito permanente
        bateria_baja = True

    with st.sidebar:
            # --- MOTOR DE ALERTAS ERGONÓMICAS Y CITAS ORIGINALES RESTABLECIDO ---
        if temas_guardados >= 2 and temas_pendientes == 0:
            ayuda_contextual = (
                "[🌱]: 'Para un pensamiento de calidad necesitamos datos precisos; sin ellos, la mente solo inventa fantasmas.' ~ Marie Curie\n"
                f"\nProcura guardar la información nueva... '💾' (Historial: {temas_guardados} respaldados)"
            )
        elif temas_pendientes > 0:
            ayuda_contextual = f"⚠️ Tienes {temas_pendientes} temas sin guardar."
        else:
            ayuda_contextual = "🔋 [Loading...]: Presiona 💾 en el panel lateral para procesar y guardar tu información."
        if tema_pendiente_por_guardar:
            if total_caracteres_bunker < 150:
                st.markdown(
                    f"""
                    <div style='background: rgba(217, 119, 6, 0.08); border-left: 4px solid #D97706; border-radius: 6px; padding: 0px; margin-bottom: 10px;'>
                        <span style='color: #B45309; font-size: 9px; font-weight: bold; display: block; text-align: center;'>⚠️ DÉFICIT DE INFORMACIÓN ⚠️</span>
                        <p style='color: #78350F; font-size: 10px; margin: 3px 0 0 0; line-height: 1.3;'>
                            <b>'{titulo_leccion_bunker}'</b> añada más información para tener mejores reactivos (min: 150 caracteres - actual: {total_caracteres_bunker} caracteres).
                        </p>
                    </div>
                    """, unsafe_allow_html=True
                )        
            else:
                st.markdown(
                    f"""
                    <div style='background: rgba(30, 41, 59, 0.05); border-left: 4px solid #1E293B; border-radius: 6px; padding: 10px; margin-bottom: 10px;'>
                        <span style='color: #0F172A; font-size: 9px; font-weight: bold; display: block; text-align: center;'>🔥 TEMA LISTO PARA RESPALDAR 🔥</span>
                        <p style='color: #334155; font-size: 11px; margin: 3px 0 0 0; line-height: 1.3;'>
                            Puedes procesar la información de: <b>'{titulo_leccion_bunker}'</b> ({total_caracteres_bunker} caracteres), buscala en tu historial...
                        </p>
                    </div>
                    """, unsafe_allow_html=True
                )
        else:
            st.markdown(
                """
                <div style='background: rgba(52, 168, 83, 0.06); border-left: 4px solid #34A853; border-radius: 6px; padding: 10px; margin-bottom: 10px;'>
                    <span style='color: #1B5E20; font-size: 9px; font-weight: bold; display: block; text-align: center;'>❄ PORTAFOLIO AL DÍA ❄</span>
                    <p style='color: #2E7D32; font-size: 11px; margin: 3px 0 0 0; line-height: 1.3;'>
                        ¡Gracias!... Todo se encuentra respaldado '🔋'.
                    </p>
                </div>
                """, unsafe_allow_html=True
            )

    col_side_izq, col_side_boton, col_side_der = st.sidebar.columns([4.0, 2.0, 4.0])
    with col_side_boton:
        # Estilos CSS premium aplicados al botón (Mantienen tus propiedades estéticas doradas)
        st.markdown(
            """
            <style>
                div.stButton > button[key="btn_forjar_bunker_szr"] {
                    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important;
                    color: #E5C158 !important;
                    border: 1.5px solid #E5C158 !important;
                    font-family: 'Playfair Display', serif !important;
                    font-size: 13px !important;
                    font-weight: bold !important;
                    font-style: italic !important;
                    letter-spacing: 0.5px !important;
                    border-radius: 50px !important;
                    padding: 8px 16px !important;
                    box-shadow: 0 4px 10px rgba(229, 193, 88, 0.08) !important;
                    transition: all 0.3s ease-in-out !important;
                    width: 100% !important;
                }
            </style>
            """, unsafe_allow_html=True
        )
        # Declaración limpia del gatillo modular
        if st.button("💾", key="btn_forjar_bunker_szr", help=ayuda_contextual, disabled=bateria_baja):
            materia_data["temas"][target_a_guardar]["estado_evaluacion"] = "pendiente"
            guardar_respaldo()
            
            # 2. Fase Inteligente: Si cumple con el mínimo de caracteres, gatilla la IA síncrona en caliente
            if total_caracteres_bunker >= 150:
                texto_bunker_directo = ""
                for b in materia_data["temas"][target_a_guardar].get("bloques", []):
                    texto_bunker_directo += f"\n{b.get('contenido', '')} {b.get('observacion', '')}"
                
                try:
                    st.toast("📡 Conectando con Google AI Studio...", icon="🛰️")
                    # Llamada directa a tu motor unificado centralizado pasando un placeholder silencioso
                    paquete_flash = ejecutar_generacion_quiz_szr(texto_bunker_directo, barra_progreso=None)
                    
                    # Sello de calidad exitoso: Encendemos la batería de inmediato
                    materia_data["temas"][target_a_guardar]["banco_evaluacion"] = paquete_flash
                    materia_data["temas"][target_a_guardar]["estado_evaluacion"] = "completado"
                    st.toast("(✦🔋✦  ¡Información guardada con éxito!", icon="🎆")
                except Exception as e_bunker_ia:
                    # Si falla la red de Google, se guarda el texto pero queda en 🪫 para el Spooler de fondo
                    materia_data["temas"][target_a_guardar]["estado_evaluacion"] = "pendiente"
                    print(f"[DEBUG SƨR] Fallo síncrono al guardar, asignado a cola de fondo: {str(e_bunker_ia)}")
                    st.toast("[🪫]: Loading...  ¡Información guardada con éxito!", icon="⌛")
            else:
                st.toast("⬡🧠⬢  Procesando Información...", icon="🛰️") 
                time.sleep(0.1)
                st.toast("🧠⮫🪫 Guardando Información...", icon="💾")                
            guardar_respaldo()
            st.rerun()
# =====================================================================
#  MAQUINARIA DE ESTADOS VISUALES SƨR (ANTI-ENGANCHE)
# =====================================================================
if tema_actual_sidebar and "temas" in materia_data and tema_actual_sidebar in materia_data["temas"]:
    # Se activa al pulsar el botón
    if estado_evaluacion_actual == "completado" and not bateria_baja:
        st.sidebar.markdown(
            """
            <div style='text-align: center; margin: -5px 0 5px; padding: 6px 0; background-color: rgba(229, 193, 88, 0.1); width: 100%; border-radius: 6px; border: 1px dashed rgba(229, 193, 88, 0.3);'>
                <span style='color: #f1c40f; font-size: 11px; font-weight: 600; text-shadow: 0px 0px 1px #39ff14, 0 0 15px #39ff14;'>✦🔋✦</span>
                <span style='color: #0b6623; font-size: 11px; font-weight: 600; text-shadow: 1px 0px 1px #39ff14, 0 0 15px #39ff14;'>¡Información Guardada!</span>
            </div>
            """, 
            unsafe_allow_html=True
        )

# Función callback para activar de forma segura el permiso de vaciado
def registrar_descarga_exitosa_szr():
    st.session_state.respaldo_descargado_exito = True

# Contenedor Maestro Estático

# 1. El usuario inicia dando por terminado el ciclo escolar
if st.session_state.cierre_estado_paso == "inicio":
    if st.sidebar.button("🏆 Finalizar Ciclo Escolar 🏆", use_container_width=True, type="secondary", key="btn_terminar_ciclo", help="Archivar Información para Resetear Ecosistema"):
        st.session_state.cierre_estado_paso = "opciones"
        st.rerun()

# 2. Se despliega el par de opciones (Archivo de respaldo | Vaciar portafolio)
elif st.session_state.cierre_estado_paso in ["opciones", "confirmacion_escrita"]:
    col_respaldo, col_vaciar = st.sidebar.columns(2)
    
    with col_respaldo:
        # Compilamos el ZIP higiénico en memoria
        datos_zip = generar_paquete_zip_respaldo_szr()
        
        # Botón 1: Descarga del paquete estructurado
        st.download_button(
            label="📦 Archivo/Respaldo",
            data=datos_zip,
            file_name=f"RESPALDO_PORTAFOLIO_SzR_{datetime.now().strftime('%Y_%m_%d')}.zip",
            mime="application/zip",
            use_container_width=True,
            key="btn_descarga_zip_premium",
            help="Genera un archivo comprimido '.ZIP' con todas las materias e imágenes ordenadas en 'HTML' ➔ 🖨️.",
            on_click=registrar_descarga_exitosa_szr
        )
        
    with col_vaciar:
        # Botón 2: Vaciar portafolio con validación ergonómica contra clics accidentales en móvil
        if st.button("⤷🗑️ Portafolio", use_container_width=True, help="Resetea todas las asignaturas y el contenido para el comienzo del próximo periodo escolar. Requiere respaldo previo."):
            # Si presiona por accidente en móvil o pc sin haber descargado el respaldo primero
            if not st.session_state.respaldo_descargado_exito:
                st.sidebar.error("❌ Acción Bloqueada: Por tu seguridad, debes presionar primero el botón 'Archivo de Respaldo' para no perder tus apuntes.")
            else:
                # Si ya tiene el respaldo hecho, pasa al paso de confirmación estricta
                st.session_state.cierre_estado_paso = "confirmacion_escrita"
                st.rerun()

    # 5. Si y solo si descargó y volvió a presionar Vaciar, se pide la confirmación escrita
    if st.session_state.cierre_estado_paso == "confirmacion_escrita":
        st.sidebar.markdown("---")
        st.sidebar.warning("⚠️ Esta acción borrará de forma irreversible toda la plataforma para iniciar un nuevo periodo escolar, presiona primero el botón 'Archivo de Respaldo' para no perder tus apuntes.")
        
        texto_seguridad = st.sidebar.text_input("Escribe 'VACIAR' para reiniciar por completo:", key="input_vaciado_estricto_szr", placeholder="VACIAR")
        
        col_cancelar_act, col_confirmar_act = st.sidebar.columns(2)
        
        with col_cancelar_act:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.cierre_estado_paso = "opciones"
                st.rerun()
                
        with col_confirmar_act:
            if texto_seguridad.strip().upper() == "VACIAR":
                if st.button("🔥 Borrar", use_container_width=True, type="primary"):
                    # Inicialización higiénica y completa de fábrica para blindar las lecturas del hilo principal
                    caratula = {
                    "imagen": None, "usuario": "", "ciclo": "", "curso": "", 
                    "curso_num": "", "paralelo_letra": "", "num_parcial": "1ER", 
                    "tipo_periodo": "PARCIAL", "semestre_num": "", "facultad": ""
                    }
                    st.session_state.datos_materias = {
                        "Area 1": {"temas": {}, "biblioteca": [], "caratula": caratula.copy()},
                        "Area 2": {"temas": {}, "biblioteca": [], "caratula": caratula.copy()},
                        "Area 3": {"temas": {}, "biblioteca": [], "caratula": caratula.copy()}
                    }
                    st.session_state.materia_activa = "Area 1"
                    st.session_state.respaldo_descargado_exito = False
                    st.session_state.cierre_estado_paso = "inicio"

                    # Destruimos la variable fantasma para que no cause KeyErrors al reiniciar
                    st.session_state.clase_seleccionada_actual = None
                    if "quiz_combinado_data" in st.session_state: st.session_state.quiz_combinado_data = None
                    if "quiz_generado_data" in st.session_state: st.session_state.quiz_generado_data = None
                    
                    guardar_respaldo()
                    st.sidebar.success("¡Ecosistema reseteado con éxito! 🎉")
                    st.rerun()
            else:
                st.button("🔥 Confirmar Borrado", use_container_width=True, disabled=True, help="Para continuar escribe la palabra ➔ VACIAR.")
st.sidebar.markdown('<div class="capsula-bloque-szr">', unsafe_allow_html=True)

# =====================================================================
# 🎨 PERSONALIZADOR DE ESCRITORIO DIGITAL (ESTADO NATURAL FORZADO SƨR)
# =====================================================================
if "version_expander_bg" not in st.session_state:
    st.session_state.version_expander_bg = 1

# Cambiamos la key del expander completo para obligarlo a encogerse al refrescar
with st.sidebar.expander("🎨 Fondo de Escritorio", key=f"exp_bg_szr{st.session_state.rep_bug_exp}"):
    foto_sidebar = st.file_uploader("Sube tu textura...", type=["png", "jpg", "jpeg"], key="uploader_bg_sidebar_real", label_visibility="collapsed")
    
    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
    col_bg_aplicar, col_bg_reset = st.columns(2)
    
    with col_bg_aplicar:
        if st.button("⤷💾", use_container_width=True, key="btn_apply_bg_sidebar"):
            if foto_sidebar:
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

                guardar_respaldo()
                st.rerun()

            else:
                st.session_state.expander_bg_abierto = False
                st.rerun()
                
    with col_bg_reset:
        if st.button("⤷🗑️", use_container_width=True, key="btn_reset_bg_sidebar"):
            st.session_state.fondo_sidebar_b64 = None
           
            guardar_respaldo()
            st.rerun()

st.sidebar.markdown('<div class="capsula-bloque-szr">', unsafe_allow_html=True)

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
            /* Resguardo inalterable de fuentes originales de SƨR */
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

# =====================================================================
#   CABECERA MAESTRA GENERALIZADA: TIPOGRAFÍA SERIF PREMIUM "LOVELYN STYLE"
# =====================================================================
if "caratula" not in materia_data or not isinstance(materia_data["caratula"], dict):
    materia_data["caratula"] = {
        "imagen": None, "usuario": "", "ciclo": "", "curso": "", 
        "curso_num": "", "paralelo_letra": "", "semestre_num": "", "facultad": ""
    }

# Renderizado de la Tarjeta de Fondo de la Asignatura con extracción segura
fondo_cabecera = ""
# .get("imagen") evita el KeyError si la propiedad no existe en alguna asignatura reseteada
imagen_b64 = materia_data["caratula"].get("imagen") 

if imagen_b64:
    fondo_cabecera = f"background-image: linear-gradient(rgba(255, 255, 255, 0.25), rgba(255, 255, 255, 0.45)), url('data:image/jpeg;base64,{imagen_b64}');"
else:
    fondo_cabecera = "background-image: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); margin-bottom: 25px;"
# =====================================================================
#   👑 NÚCLEO DE DISEÑO SƨR UNIFICADO (EDICIÓN DORADO ORO FINO GLOBAL)
# =====================================================================
st.markdown(
    """
    <style>
        @import url('https://googleapis.com');

        /* 📐 ERGONOMÍA VERTICAL SƨR: Espacio muerto del techo */
        div[data-testid="stSidebarUserContent"] {
            padding-top: 0rem !important;
        }
        div[data-testid="stSidebarUserContent"] h1 {
            margin-top: 0px !important;
            margin-bottom: -1px !important;
        }
        .block-container {
            padding-top: calc(0.2rem + 0.5vw) !important;
            padding-bottom: calc(0.2rem + 0.5vw) !important;
            padding-left: calc(0.4rem + 1vw) !important;
            padding-right: calc(0.4rem + 1vw) !important;
        }
        /* CORRECCIÓN INTERNA DE TIPOGRAFÍAS FLUIDAS Y REDUCCIÓN DE TAMAÑO SƨR  */
        html, body {
            font-family: 'Inter', sans-serif !important;
            font-size: calc(13px + 0.15vw) !important; /* Base elástica para toda la app */
        }
        /* Aseguramos que el contenedor general no rompa palabras por la mitad */
        [data-testid="stMarkdownContainer"] {
            font-family: 'Inter', sans-serif !important;
            word-break: keep-all !important;
        }
        h1, h2 {
            font-family: 'Playfair Display', serif !important;
            font-weight: 900 !important;
        }

        /* 🔒 TARGET QUIRÚRGICO: Encoge los títulos de Contenido, Observaciones y Galería */
        [data-testid="stMarkdownContainer"] h3 {
            font-family: 'Playfair Display', serif !important;
            font-weight: 900 !important;
            font-size: calc(20px + 0.35vw) !important; /* RESTRABLECIDO: Letra elástica balanceada original */
            white-space: nowrap !important;             /* 🚫 Prohíbe terminantemente los saltos de línea */
            letter-spacing: -0.4px !important;          /* Compacta sutilmente los caracteres */
            margin-bottom: calc(4px + 0.1vw) !important;
            display: inline-block !important;
        }

        /* ✍️ TEXTAREAS */
        div[data-testid="stTextArea"] textarea {
            font-size: calc(10px + 0.15vw) !important; /* RESTABLECIDO: El texto se encoge en pantallas pequeñas */
            line-height: 1.5 !important;
            padding: 0.6em !important;
        }
        .label-seccion-szr {
            font-size: calc(11px + 0.2vw) !important;
            font-weight: bold !important;
            font-family: "Playfair Display", serif !important;
            margin-bottom: 5px !important;
        }
        /* 🌟 AFINAMIENTO DE CAPAS S.E.D.E Y UNIFICACIÓN DORADO ORO FINO */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #F8FAFC !important;
            border: 1.5px solid #E5C158 !important; 
            border-radius: calc(6px + 0.5vw) !important; /* RESTABLECIDO: Curvatura elástica original */
            padding: calc(8px + 0.6vw) calc(10px + 0.6vw) !important; /* RESTABLECIDO: Espaciado interno dinámico */
            margin-bottom: calc(10px + 0.5vw) !important;
            box-shadow: 0 4px 12px rgba(229, 193, 88, 0.03) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 0 !important;
        }

        /* 👑 TÍTULOS Y SUBTEXTOS ELÁSTICOS */
        .titulo-asignatura-szr {
            color: #1E293B !important; 
            margin: 0 !important; 
            font-size: calc(22px + 1.2vw) !important; /* Escalado perfecto en cualquier monitor */
            font-family: 'Playfair Display', serif; 
            font-weight: 900; 
            line-height: 1.2;
        }
        .subtexto-estudiante-szr {
            color: #475569 !important;
            font-size: calc(10.5px + 0.15vw) !important;
            margin-top: 4px !important;
            font-weight: 500;
        }

        /* 📝 CÁPSULAS DE APUNTES: Adaptabilidad elástica horizontal sin deformarse */
        .capsula-bloque-szr {
            background-color: rgba(239, 219, 161, 0.22) !important;
            border: 1.0px solid rgba(229, 193, 88, 0.25) !important;
            border-left: 3.0px solid #E5C158 !important; 
            border-radius: calc(4px + 0.6vw) !important; /* RESTABLECIDO */
            padding: calc(4px + 0.4vw) calc(6px + 0.4vw) !important; /* RESTABLECIDO */
            margin-bottom: calc(10px + 0.5vw) !important;
            box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.04) !important;
            width: 100% !important;
            box-sizing: border-box !important;
        }

        /* 🎨 REJILLA DE BÚSQUEDA VERDE CÉSPED INTELIGENTE */
        div[data-testid="stTextInput"] input {
            background-color: rgba(52, 168, 83, 0.04) !important;
            border: 1px solid rgba(52, 168, 83, 0.15) !important;
            color: #1E293B !important;
            font-weight: 500 !important;
            border-radius: 8px !important;
            font-size: calc(11px + 0.15vw) !important;
            padding: calc(4px + 0.2vw) calc(6px + 0.2vw) !important;
            transition: all 0.25s ease-in-out !important;
        }
        div[data-testid="stTextInput"] input:focus {
            background-color: #FFFFFF !important;
            border: 1px solid #E5C158 !important;
            box-shadow: 0 0 0 3px rgba(229, 193, 88, 0.12) !important;
            outline: none !important;
        }
        /* 📐 BOTONES ERGONÓMICOS */
        div.stButton > button {
            font-size: calc(10px + 0.15vw) !important;
            padding: calc(3px + 0.2vw) calc(6px + 0.4vw) !important;
            border-radius: 40px !important;
            width: 100% !important;
            min-height: 2.2em !important; /* Mantiene una altura ergonómica elástica mínima */
        }

        /* 📸 GALERÍA Y ANEXOS: Blindaje de imágenes con Proporción de Aspecto Fija */
        [data-testid="stImage"] img {
            width: 100% !important;
            height: auto !important;
            aspect-ratio: 16/10 !important; /* Mantiene la proporción dorada sin importar la resolución */
            object-fit: cover !important;
            border-radius: 6px !important;
        }

        /* 📐 COMPONENTES EXPANDIBLES PENDIENTES */
        .stExpander p, .stExpander span, .stExpander label, .stExpander input {
            font-size: calc(10px + 0.1vw) !important;
            font-weight: 500 !important;
        }
        .stExpander summary p {
            font-size: calc(10.5px + 0.1vw) !important;
            font-weight: 600 !important;
        }
        /* Encogemos y alineamos el título de Día, Mes y Año sobre cada caja */
        div[data-testid="stExpander"] label p {
            font-size: 10px !important;
            font-weight: 600 !important;
            margin-bottom: -10px !important;
            color: #475569 !important;
        }
        /* BUG DEL PANEL LATERAL: AIRE PARA EL BOTÓN DE CIERRE NATIVO */
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
            top: 15px !important;
            left: 15px !important;
            z-index: 999999 !important;
        }
        
        /* 📐 DISEÑO ADAPTATIVO ERGONÓMICO PARA TABLETAS Y MÓVILES (SINTAXIS CORREGIDA) */
        @media (max-width: 768px) {
            /* Encoger tipografía serif premium de las asignaturas */
            .titulo-asignatura-szr {
                font-size: calc(18px + 1vw) !important;
            }
            
            .subtexto-estudiante-szr {
                font-size: 11px !important;
            } /* <--- 🔒 ¡LLAVE DE CIERRE INYECTADA AQUÍ PARA EVITAR EL BUG DE ANULACIÓN! */

            /* Encoger las cápsulas y el espaciado vertical de los apuntes */
            .capsula-bloque-szr {
                padding: calc(3px + 0.2vw) calc(5px + 0.2vw) !important;
                margin-bottom: 10px !important;
                border-radius: 8px !important; /* Bordes más sutiles en pantallas táctiles */
            }
            
            /* Reducir botones pequeños del hilo para que no desborden las columnas */
            div.stButton > button {
                font-size: 10px !important;
                padding: 5px 6px !important; /* Mayor espacio físico para la yema del dedo en tablet */
            }
            
            /* Ajustar cajas de texto de búsqueda e inputs generales */
            div[data-testid="stTextInput"] input {
                font-size: 11px !important;
                padding: 4px 6px !important;
            }
            
            /* Fuerza el reordenamiento vertical elástico de las áreas de contenido en móviles */
            [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
                gap: 12px !important;
            }
            /* 🔒 FORZADO RÍGIDO LADO A LADO (EFECTO FOTO SIN APILAMIENTO) */
            [data-testid="stHorizontalBlock"] {
                flex-direction: row !important; /* Obliga a mantener la fila siempre */
                flex-wrap: nowrap !important;   /* Prohíbe mandar las cajas hacia abajo */
                overflow-x: auto !important;    /* Si la pantalla es ultra delgada, crea scroll horizontal */
            }
            
            /* 🎛️ ACTIVACIÓN DE BARRAS DE DESLIZAMIENTO HORIZONTAL EN HISTORIAL SƨR */
            [data-testid="stSelectboxVirtualDropdown"] > div,
            div[data-baseweb="popover"] > div {
                overflow-x: auto !important;   /* ↔️ Activa la barra horizontal automática si el tema es largo */
                overflow-y: auto !important;   /* ↕️ Mantiene el scroll vertical para navegar entre filas */
            }

            [data-testid="stSelectboxVirtualDropdown"] li,
            div[data-baseweb="popover"] li {
            white-space: nowrap !important;       /* 🚫 Prohíbe terminantemente cortar el texto o saltar de línea */
            width: max-content !important;        /* 📐 Fuerza a la fila a estirarse tanto como el nombre más largo */
            min-width: 100% !important;           /* Asegura que cubra todo el ancho visual */
            padding-right: 25px !important;       /* Margen de seguridad al final del texto largo */
            text-overflow: clip !important;       /* Elimina los tres puntos (...) invasivos */
        }

        }
    </style>
    """, 
    unsafe_allow_html=True
)

# =====================================================================
# REFINAMIENTO DE CREDENCIALES: BARRAS VERTICALES "|" Y SIN PARCIAL
# =====================================================================
# Ensamblaje seguro de las píldoras condicionales estilo "Etiqueta Escolar de Alta Gama Verde Eucalipto"
pidolas_html = ""
datos_membrete = []

if materia_data["caratula"].get("usuario"):
    datos_membrete.append(f"👤 {materia_data['caratula']['usuario']}")

# Agrupamos curso y paralelo de forma compacta
curso_val = materia_data["caratula"].get("curso_num", "")
paralelo_val = materia_data["caratula"].get("paralelo_letra", "")
if curso_val or paralelo_val:
    paralelo_str = f" '{paralelo_val}'" if paralelo_val else ""
    datos_membrete.append(f"🎓 {curso_val}{paralelo_str}")

if materia_data["caratula"].get("ciclo"):
    datos_membrete.append(f"🗓️ {materia_data['caratula']['ciclo']}")

if materia_data["caratula"].get("facultad"):
    datos_membrete.append(f"🏢 {materia_data['caratula']['facultad']}")

# Unimos dinámicamente usando el separador rígido "|" solicitado
if datos_membrete:
    separador_rigido = " <span style='color: rgba(255, 255, 255, 0.4); margin: 0 10px; font-weight: normal;'> ~ </span> "
    cinturon_texto = separador_rigido.join(datos_membrete)
    
# =====================================================================
#   👑 CONTROL DE FECHAS, HISTORIAL Y MARQUESINA UNIFICADA SƨR
# =====================================================================

# 1. Inicialización de banderas lógicas básicas de Streamlit
if "editando_titulo_clase_activa" not in st.session_state:
    st.session_state.editando_titulo_clase_activa = False

if "rep_mesa_exp" not in st.session_state:
    st.session_state.rep_mesa_exp = 0

if "clase_seleccionada_actual" not in st.session_state:
    st.session_state.clase_seleccionada_actual = None

# 2. Captura cronológica del sistema para valores por defecto
fecha_sistema_actual = datetime.now()
anio_defecto = fecha_sistema_actual.year
mes_defecto = fecha_sistema_actual.month
dia_defecto = fecha_sistema_actual.day

# 3. Definición estricta de las opciones de los selectores de fecha
opciones_anios = [anio_defecto, anio_defecto - 1, anio_defecto - 2, anio_defecto - 3, anio_defecto - 4]
opciones_meses = [f"{m:02d}" for m in range(1, 13)]
opciones_dias = [f"{d:02d}" for d in range(1, 32)]

lista_de_clases = list(materia_data["temas"].keys())

# 4. Aseguramos lección inicial limpia si la asignatura está vacía de fábrica
if not lista_de_clases:
    fecha_hoy = fecha_sistema_actual.strftime("%Y-%m-%d")
    tema_inicial_defecto = "Escribe el nuevo tema aquí..."
    tema_inicial_llave = f"Clase 01 | {fecha_hoy} | {tema_inicial_defecto}"
    
    materia_data["temas"][tema_inicial_llave] = {
        "bloques": [{"contenido": "", "observacion": "", "ia_sugerencias": ""}], 
        "imagenes": [], "meta_num": "01", "meta_fecha": fecha_hoy, "meta_titulo": tema_inicial_defecto,
        "meta_parcial": materia_data["caratula"].get("semestre_num", "1ER PARCIAL")
    }
    lista_de_clases = [tema_inicial_llave]
    st.session_state.clase_seleccionada_actual = tema_inicial_llave
    guardar_respaldo()

# 5. Mapeamos las clases para el dropdown organizadas por fecha
opciones_dropdown = []
mapeo_dropdown = {}
clases_ordenadas_lista = sorted(lista_de_clases, key=lambda k: materia_data["temas"][k].get("meta_fecha", ""))

for llave_clase in clases_ordenadas_lista:
    c_data = materia_data["temas"][llave_clase]
    etiqueta_visual = f"📅 [{c_data.get('meta_fecha', '')}] ➔ {c_data.get('meta_titulo', '')}"
    opciones_dropdown.append(etiqueta_visual)
    mapeo_dropdown[etiqueta_visual] = llave_clase

if st.session_state.clase_seleccionada_actual not in lista_de_clases:
    st.session_state.clase_seleccionada_actual = clases_ordenadas_lista[-1]

indice_destino_selectbox = clases_ordenadas_lista.index(st.session_state.clase_seleccionada_actual)

# =====================================================================
#   👑 BLOQUE 1: CABECERA NATIVA CON DETALLE DE PORTADA INTEGRADO (S.E.D.E.)
# =====================================================================
tema_actual = st.session_state.clase_seleccionada_actual if st.session_state.clase_seleccionada_actual in lista_de_clases else lista_de_clases[-1]
clase_activa_data = materia_data["temas"][tema_actual]
tiene_imagen = bool(materia_data["caratula"].get("imagen"))

# --- BLOQUE 1: CABECERA NATIVA (CON LETRA CAPITAL RETRO / MODERNA INTEGRADA) ---
with st.container(border=True):
    renderizar_cabecera_con_recordatorio()

# =====================================================================
#   🎯 PARTE 1: EL CASCARÓN DEL SIMULADOR Y RECOLECCIÓN DE APUNTES
# =====================================================================
if st.session_state.get("modo_quiz_activo", False):
    st.markdown("### 🎯 Simulador de Evaluación - SƨR")
    
    # Inicializamos el contador de reintentos automático si no existe
    if "conteo_reintentos_quiz" not in st.session_state:
        st.session_state.conteo_reintentos_quiz = 0
    if "quiz_combinado_data" not in st.session_state:
        st.session_state.quiz_combinado_data = None
    # El gatillo principal a pantalla completa
    if "ejecutando_peticion_ia" not in st.session_state:
        st.session_state.ejecutando_peticion_ia = False

    # 📅 Desplegamos el checklist en dos columnas cronológicas SƨR
    with st.expander("🗳️ Seleccione los temas a evaluar", expanded=True):
        clases_disponibles = list(materia_data.get("temas", {}).keys())
        # Ordenamos estrictamente por fecha de forma cronológica ascendente
        clases_ordenadas_quiz = sorted(clases_disponibles, key=lambda k: materia_data["temas"][k].get("meta_fecha", ""))
        
        st.markdown("<p style='font-size:11px; color:#475569;'>Marque los temas que va a incluir en la generación de su Quiz combinado:</p>", unsafe_allow_html=True)
        
        # 👑 MOTOR DE REJILLA GENERAL ELÁSTICA SƨR (2 COLUMNAS CRONOLÓGICAS)
        st.markdown(
            """
            <style>
                /* Forzamos al contenedor del expander del quiz a crear 2 columnas perfectas con scroll vertical */
                div[data-testid="stExpander"] > div[role="region"] > div {
                    display: grid !important;
                    grid-template-columns: 1fr 1fr !important; /* 📐 Dos columnas simétricas exactas */
                    gap: 0.8em !important;                     /* Aire ergonómico elástico entre cápsulas */
                    max-height: 20em !important;               /* Freno vertical proporcional para no comerse la pantalla */
                    overflow-y: auto !important;                /* ↕️ Scroll vertical interno suave e inmune a bugs */
                    overflow-x: hidden !important;
                    padding: 0.8em !important;
                    background: rgba(229, 193, 88, 0.02) !important;
                    border: 1px dashed rgba(229, 193, 88, 0.25) !important;
                    border-radius: 0.6em !important;
                    width: 100% !important;
                }
                
                /* Ajuste general para que los checkboxes no se corten individualmente */
                div[data-testid="stExpander"] div.element-container {
                    width: 100% !important;
                    margin-bottom: 0px !important;
                }
                
                /* Estilizado premium estilo cápsula de libro para cada renglón completo */
                div[data-testid="stExpander"] label {
                    display: flex !important;
                    align-items: center !important;
                    white-space: normal !important;            /* Permite dos renglones si el título es ultra largo */
                    font-size: 0.85em !important;              /* Texto fluido que escala con la base de la app */
                    background: #FFFFFF !important;
                    padding: 0.6em 0.8em !important;           /* Márgenes internos elásticos */
                    border-radius: 0.5em !important;
                    border: 1px solid #E2E8F0 !important;
                    cursor: pointer !important;
                    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
                    width: 100% !important;
                    box-sizing: border-box !important;
                    transition: all 0.2s ease !important;
                }
                
                /* Efecto sutil al pasar el mouse por encima de la opción del examen */
                div[data-testid="stExpander"] label:hover {
                    border-color: #E5C158 !important;
                    background-color: rgba(229, 193, 88, 0.02) !important;
                }

                /* Ajuste responsivo para celulares muy delgados (Fuerza 1 columna si el espacio es crítico) */
                @media (max-width: 480px) {
                    div[data-testid="stExpander"] > div[role="region"] > div {
                        grid-template-columns: 1fr !important;
                    }
                }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Renderizado continuo en el grid seguro y libre de colisiones en memoria
        clases_seleccionadas = []
        
        # Renderizado continuo en el grid seguro libre de colisiones en memoria
        for c_llave in clases_ordenadas_quiz:
            c_data_q = materia_data["temas"][c_llave]
            estado_bateria = c_data_q.get("estado_evaluacion", "pendiente")
            
            # Sello de energía solicitado (🔋 / 🪫)
            icon_bateria = "🔋" if estado_bateria == "completado" else "🪫"
            
            fecha_q = c_data_q.get('meta_fecha', 'S/F')
            titulo_q = c_data_q.get('meta_titulo', 'Sin Título')
            
            label_capsula = f"{icon_bateria} [{fecha_q}] ➔ {titulo_q}"
            llave_segura_quiz = f"chk_quiz_grid_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}_{c_llave.replace(' ', '_').replace('|', '_')}"
            
            # 🚀 CORRECCIÓN CRÍTICA: Cambiado a value=False para que el usuario elija activamente
            if st.checkbox(label_capsula, value=False, key=llave_segura_quiz):
                clases_seleccionadas.append(c_llave)

    st.markdown("<div style='margin-top: 13px;'></div>", unsafe_allow_html=True)
    total_seleccionados = len(clases_seleccionadas)

    # Contenedores de botones simétricos en paralelo para controlar las acciones
    col_mult_generar, col_acc_barajar = st.columns([5.0, 5.0])

    # ----------------------------------------------------------------=
    # ESCENARIO A: REPASO DE UN SOLO TEMA (MANTIENE TU ALGORITMO E IA ORIGINAL)
    # ----------------------------------------------------------------=
    if total_seleccionados == 1:
        tema_unico_llave = clases_seleccionadas[0]
        nodo_clase_unica = materia_data["temas"][tema_unico_llave]

        with col_mult_generar:
            tiene_banco_valido = isinstance(nodo_clase_unica.get("banco_evaluacion"), dict) and nodo_clase_unica["banco_evaluacion"]
            # Si el tema ya cuenta con su quiz forjado previamente en la agenda, lo cargamos al instante
            if nodo_clase_unica.get("estado_evaluacion") == "completado" and nodo_clase_unica.get("banco_evaluacion"):
                if st.button("🔋➥🧠 Cargar Quiz", use_container_width=True, type="primary"):
                    st.session_state.quiz_generado_data = nodo_clase_unica["banco_evaluacion"]
                    st.rerun()
            else:
                 # 🔒 AUDITORÍA PREVENTIVA DE VOLUMEN DE APUNTES
                texto_acumulado_apuntes = ""
                for b in nodo_clase_unica.get("bloques", []):
                    texto_acumulado_apuntes += f"\n{b.get('contenido', '')} {b.get('observacion', '')}"
                
                # Eliminamos espacios en blanco, saltos de línea y tabulaciones para medir el texto real
                texto_limpio_validacion = re.sub(r'\s+', '', texto_acumulado_apuntes)
                apuntes_vacios = len(texto_limpio_validacion) < 150
                # 🔒 ALERTA ERGONÓMICA COMPUETA DE SEGURIDAD
                if apuntes_vacios:
                    st.markdown(
                        """
                        <div style='
                            border: 1.5px dashed #EF4444; 
                            border-radius: 8px; 
                            padding: 10px 14px; 
                            background-color: rgba(239, 68, 68, 0.04); 
                            margin-bottom: 12px;
                        '>
                            <span style='color: #DC2626; font-size: 12.5px; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 6px;'>
                                🚫 Sin información para procesar... 🚫
                            </span>
                            <p style='margin: 5px 0 4px 7px; font-size: 11.5px; color: #7F1D1D; line-height: 1.4;'>
                                Actualmente disponemos de información muy breve para diseñar reactivos de calidad.
                                Te sugerimos profundizar y enriquecer tus apuntes de contenido o observaciones para desbloquear el simulador.
                            </p>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )

                # Si la batería está vacía, se habilita tu botón original que llama síncronamente a Gemini
                if st.button("📡➦🛰️ Generar Quiz", use_container_width=True, type="primary", disabled=st.session_state.ejecutando_peticion_ia or apuntes_vacios):        
                    st.session_state.ejecutando_peticion_ia = True
                    # Creamos cajas de texto dinámicas que no se borran al recargar el árbol de componentes
                    zona_carga = st.empty()
                    zona_error = st.empty()
                    barra_progreso = st.empty()
                    tiempo_inicial = time.time()
        
                    with zona_carga.container():
                        barra_progreso_ui = st.progress(5, text="[🛰️ SƨR Core]: Abriendo canal seguro a Google A.I. Studio...")
            
                    try:
                        paquete_quiz_szr = ejecutar_generacion_quiz_szr(texto_acumulado_apuntes, barra_progreso)
                        # Sello y guardado permanente en la lección activa para tu base de datos modular
                        materia_data["temas"][tema_unico_llave]["banco_evaluacion"] = paquete_quiz_szr
                        materia_data["temas"][tema_unico_llave]["estado_evaluacion"] = "completado"
                        guardar_respaldo()

                        # --- FIN DEL RECORRIDO: SELLO EXITOSO AL 100% ---
                        barra_progreso.progress(100, text="🔋[SƨR Core]: ¡La Evalucación se generó con éxito!")

                        # Guardamos el objeto completo directo en la sesión
                        st.session_state.quiz_generado_data = paquete_quiz_szr
                        st.session_state.modo_quiz_activo = True
                        st.session_state.ejecutando_peticion_ia = False
                        st.rerun()

                    except Exception as e_error_red:
                        st.session_state.ejecutando_peticion_ia = False
                        st.session_state.quiz_generado_data = None
                        if "barra_progreso" in locals():
                            barra_progreso.empty()
                        zona_carga.empty()
                        with zona_error.container():
                            st.error(f"🚨 Error en la petición: {str(e_error_red)}")
   
    # =====================================================================
    # ESCENARIO B: MODO MULTITEMA / EXAMEN PARCIAL (SORTEO LOCAL SƨR)
    # =====================================================================
    elif total_seleccionados >= 2:
        # Clasificamos de inmediato las clases marcadas según el nivel de su batería
        nodos_temas = materia_data.get("temas", {})
        temas_con_bateria = [t for t in clases_seleccionadas if nodos_temas.get(t, {}).get("estado_evaluacion") == "completado" and isinstance(nodos_temas.get(t, {}).get("banco_evaluacion"), dict) and len(nodos_temas.get(t, {}).get("banco_evaluacion", {}).get("preguntas", [])) == 4]
        
        temas_en_cola_spooler = [t for t in clases_seleccionadas if t not in temas_con_bateria]

        # CRONÓMETRO INVISIBLE SƨR (FORJADO AUTOMÁTICO EN SEGUNDO PLANO)
        if "ultimo_forjado_tiempo" not in st.session_state:
            st.session_state.ultimo_forjado_tiempo = time.time()
            
        if temas_en_cola_spooler:
            tiempo_actual_reloj = time.time()
            segundos_transcurridos = tiempo_actual_reloj - st.session_state.ultimo_forjado_tiempo
            
            # 🚨 CONTROL DE TIEMPO: Se ejecuta silenciosamente cada 120 segundos de fondo
            if segundos_transcurridos >= 100.0:
                # CORRECCIÓN DE INDICE: Extraemos el primer string de tema pendiente de forma segura
                target_recarga = temas_en_cola_spooler[0]
                titulo_target = nodos_temas[target_recarga].get("meta_titulo", "Lección")
                
                try:
                    texto_acumulado_bg = ""
                    for b in nodos_temas[target_recarga].get("bloques", []):
                        texto_acumulado_bg += f"\n{b.get('contenido', '')} {b.get('observacion', '')}"
                    
                    if len(re.sub(r'\s+', '', texto_acumulado_bg)) >= 150:
                        # Invocación limpia delegando en tu función original con formato de prompt reparado
                        response_bg = ejecutar_peticion_ia_bunker(texto_acumulado_bg, prompt=PROMPT_PLANTILLA_QUIZ)
                        
                        if response_bg and response_bg.text:
                            res_json_bg = json.loads(response_bg.text)
                            pregs_bg = res_json_bg.get("preguntas", [])
                            ejs_bg = res_json_bg.get("ejercicios", [])
                            es_teorica_bg = res_json_bg.get("es_teorica", False)
                            dificultades_fallback = ["fácil", "medio", "difícil"]

                             # 🛡️ AUDITORÍA DE CALIDAD SƨR: Forzamos el cumplimiento de la plantilla (4+3)
                            while len(pregs_bg) < 4:
                                pregs_bg.append({"p": "Pregunta de refuerzo analítico", "a": "-", "b": "-", "c": "-", "d": "-", "r": "a", "justificacion": "Repaso"})
                            
                            for e_item in ejs_bg:
                                if "solucion" in e_item:
                                    if not es_teorica_bg:
                                        e_item["solucion"] = (str(e_item["solucion"])
                                            .replace('perspective$$', '$$').replace('Perspective$$', '$$')
                                            .replace('$$\\n', '$$\n\n').replace('\\n$$', '\n\n$$')
                                            .replace('\\n', '\n\n')
                                        )
                                    else:
                                        e_item["solucion"] = str(e_item["solucion"]).replace('\\n', '\n\n')
                                if "error" in e_item:
                                    e_item["error"] = str(e_item["error"]).replace('\\n', '\n\n')

                            while len(ejs_bg) < 3:
                                idx_f = len(ejs_bg)
                                ejs_bg.append({"enunciado": "Reactivo analítico complementario.", "dificultad": dificultades_fallback[idx_f], "solucion": "-", "error": "-"})

                        # Guardamos el paquete en la lección correspondiente
                        nodos_temas[target_recarga]["banco_evaluacion"] = {
                            "tema": res_json_bg.get("tema", titulo_target),
                            "es_teorica": es_teorica_bg,
                            "preguntas": pregs_bg[:4], 
                            "ejercicios": ejs_bg[:3],
                            "truco": res_json_bg.get("truco", "Mapea tus notas de clase.")
                        }
                        nodos_temas[target_recarga]["estado_evaluacion"] = "completado"
                        guardar_respaldo()
                            
                        # Reseteamos el temporizador para la siguiente lección en cola
                        st.session_state.ultimo_forjado_tiempo = time.time()
                        st.toast(f"¡Ya puedes acceder al quiz de: '{titulo_target}'!", icon="🔋")
                        st.rerun()
                            
                except Exception as e_cron:
                    print(f"[DEBUG SƨR Spooler] Error en regeneración: {str(e_cron)}")
                    st.session_state.ultimo_forjado_tiempo = time.time()
        # 🎛️ 3. INTERFAZ GRÁFICA DEL BUFFER DE TRABAJO (COMPENSACIÓN)
        if temas_en_cola_spooler:
            st.warning(f"♾️ **Cola de Generación Activa:** {len(temas_en_cola_spooler)} de los temas seleccionados se están regenerando.\n\nSu examen se mostrará pronto, al terminar tu Quiz no olvides sortear nuevas preguntas regeneradas...")

        # --- ENTRADA DE BOTÓN CARGAR QUIZ (COMPENSACIÓN EXACTA DE 10 PREGUNTAS MIXTAS) ---
        with col_mult_generar:
            bloqueo_simulador = len(temas_con_bateria) == 0
            if st.button("🔋➥🧠 Cargar Quiz", use_container_width=True, type="primary", disabled=bloqueo_simulador, help="Arma tu Quiz de 10 preguntas combinando los temas seleccionados."):
                bolsa_preguntas = []
                bolsa_ejercicios = []
                bolsa_trucos = []
                
                for t_listo in temas_con_bateria:
                    banco = nodos_temas[t_listo].get("banco_evaluacion", {})
                    bolsa_preguntas += banco.get("preguntas", [])
                    bolsa_ejercicios += banco.get("ejercicios", [])
                    if "truco" in banco: 
                        bolsa_trucos.append(banco["truco"])
                
                p_targets = min(5, len(bolsa_preguntas))
                e_targets = min(5, len(bolsa_ejercicios))
                
                # Compensación matemática exacta para que el examen consolidado sume siempre 10 items
                total_actual = p_targets + e_targets
                if total_actual < 10 and (bolsa_preguntas or bolsa_ejercicios):
                    faltantes = 10 - total_actual
                    if len(bolsa_preguntas) > p_targets:
                        p_targets += min(faltantes, len(bolsa_preguntas) - p_targets)
                    elif len(bolsa_ejercicios) > e_targets:
                        e_targets += min(faltantes, len(bolsa_ejercicios) - e_targets)

                if p_targets > 0 or e_targets > 0:
                    st.session_state.quiz_combinado_data = {
                        "tema": "Simulacro Quiz Mixto",
                        "es_teorica": False,
                        "preguntas": random.sample(bolsa_preguntas, p_targets) if bolsa_preguntas else [],
                        "ejercicios": random.sample(bolsa_ejercicios, e_targets) if bolsa_ejercicios else [],
                        "truco": random.choice(bolsa_trucos) if bolsa_trucos else "Agrupa tus notas en bloques visuales."
                    }
                    st.rerun()

        with col_acc_barajar:
            modo_barajar_bloqueado  = len(temas_con_bateria) == 0
            if st.button("🔀︎ Mezclar Quiz", use_container_width=True, disabled=modo_barajar_bloqueado, help="Elige una combinación diferente de preguntas..."):
                bolsa_preguntas_pool = []
                bolsa_ejercicios_pool = []
                bolsa_trucos_pool = []

                for t_listo in temas_con_bateria:
                    banco = nodos_temas[t_listo].get("banco_evaluacion", {})
                    bolsa_preguntas_pool += banco.get("preguntas", [])
                    bolsa_ejercicios_pool += banco.get("ejercicios", [])
                    if "truco" in banco: bolsa_trucos_pool.append(banco["truco"])                
                
                p_targets = min(5, len(bolsa_preguntas_pool))
                e_targets = min(5, len(bolsa_ejercicios_pool))

                st.session_state.quiz_combinado_data = {
                    "tema": "Simulacro Quiz Mixto",
                    "es_teorica": False,
                    "preguntas": random.sample(bolsa_preguntas_pool, p_targets) if bolsa_preguntas_pool else [],
                    "ejercicios": random.sample(bolsa_ejercicios_pool, e_targets) if bolsa_ejercicios_pool else [],
                    "truco": random.choice(bolsa_trucos_pool) if bolsa_trucos_pool else "Agrupa las fórmulas complejas en fichas de repaso para tenerlas a mano mientras resuelves los ejercicios."
                }
                st.toast("¡Combinación de reactivos actualizada!", icon="🎲")
                st.rerun()

    # =====================================================================
    # RENDERIZADO DEL CUESTIONARIO ACTIVO (MONOTEMA O SIMULACRO COMBINADO)
    # =====================================================================
    quiz_activo_render = None
    if total_seleccionados >= 2 and st.session_state.quiz_combinado_data:
        quiz_activo_render = st.session_state.quiz_combinado_data
    elif total_seleccionados == 1 and st.session_state.quiz_generado_data:
        quiz_activo_render = st.session_state.quiz_generado_data
    else:
        # En caso de desajuste de estados o desmarcado masivo, limpiamos buffers de manera segura
        st.session_state.quiz_combinado_data = None
        st.session_state.quiz_generado_data = None

    if quiz_activo_render:
        st.markdown("<hr style='border-top: 1px dashed rgba(0,0,0,0.1); margin: 25px 0;'>", unsafe_allow_html=True)
        st.success("**¡Evaluación estructurada con éxito por SƨR!**")
        quiz = quiz_activo_render
        
        tema = quiz.get("tema", "Simulacro Consolidado")
        es_teorica = quiz.get("es_teorica", False)
        
        tit_seccion_desarrollo = "📝 Comprensión Crítica y Casos de Estudio" if es_teorica else "🧮 Sección Práctica: Desarrollo Algebraico"
        lbl_solucion = "✍️ Respuesta Ideal" if es_teorica else "📝 Resolución Oficial"
        lbl_error = "⚠️ Sesgo Teórico" if es_teorica else "⚠️ Error Común o Tip"
       
        # 📝 PINTA LAS 4 PREGUNTAS EN LA INTERFAZ WEB
        for idx, p in enumerate(quiz.get("preguntas", [])):
            with st.container(border=True):
                st.markdown(f"**Pregunta {idx+1:02d}:** {p.get('p', '-')}")
                opciones = [f"A) {p.get('a','-')}", f"B) {p.get('b','-')}", f"C) {p.get('c','-')}", f"D) {p.get('d','-')}"]
                st.radio("Alternativas:", options=opciones, key=f"radio_szr_{idx}", label_visibility="collapsed")

                # Renderizado con componente nativo para no romper el LaTeX de la justificación
                with st.expander("🔑 Ver Respuesta Correcta y Justificación"):
                    st.success(f"**Opción correcta:** {str(p.get('r', '-')).upper()}")
                    st.markdown(p.get('justificacion', 'No hay justificación registrada.'))

        # 🧮 PINTA LOS 3 EJERCICIOS EN LA INTERFAZ WEB
        if quiz.get("ejercicios"):

            for idx, e in enumerate(quiz.get("ejercicios", [])):
                with st.container(border=True):
                    st.markdown(f"**Reactivo {idx+1:02d} - [{str(e.get('dificultad','medio')).upper()}]**")
                    st.markdown(e.get("enunciado", "-"))

                # Expansor nativo: procesa la solución y tips de forma fluida
                with st.expander("🗜️ Ver Retroalimentación Académica"):
                    st.markdown(f"**{lbl_solucion}:**")

                    st.markdown(str(e.get('solucion', '-')))
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(f"⚠️ **{lbl_error}:**")
                    error_raw = str(e.get('error', "-"))
                    error_limpio = error_raw.replace('\n', '\n\n')
                    st.markdown(error_limpio)

        # 💡 PINTA EL PRO-TIP DE CIERRE
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### 💡Truco de Supervivencia (SƨR Pro-Tip)")
            # 🚀 PARCHE: Cambiado a .get() con texto de respaldo para evitar KeyErrors
            truco_seguro = quiz.get('truco', 'Mantén la calma y repasa los teoremas base de tus apuntes.')
            st.warning(f"🔑 **Secreto de Examen:** {truco_seguro}")
            
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        col_print_final, col_close_final = st.columns([7.0, 3.0])
        
        with col_print_final:
            st.button("🖨️", use_container_width=True, help="Descarga tu examen interactivo.")
            
        with col_close_final:
            if st.button("🔙", use_container_width=True, help="Cerrar Quiz y Volver a Apuntes"):
                st.session_state.modo_quiz_activo = False
                st.session_state.quiz_generado_data = None
                st.session_state.quiz_combinado_data = None
                st.rerun()
            
        st.stop()
if not st.session_state.get("modo_quiz_activo", False):

    # --- VARIABLES DE CONTROL LOGATIVO PARA EL EXPENDER COMPACTO MULTIUSO ---
    if "modo_edicion_historial" not in st.session_state:
        st.session_state.modo_edicion_historial = False

    lista_de_clases = list(materia_data["temas"].keys())
    fechas_y_titulos_existentes = [
        (materia_data["temas"][k].get("meta_fecha", "").strip(), materia_data["temas"][k].get("meta_titulo", "").strip().upper()) 
        for k in lista_de_clases if k != tema_actual
    ]

    fecha_nueva_str = datetime.now().strftime("%Y-%m-%d")
    titulo_ingresado_clean = ""
    input_invalido = True

    with st.container(border=True):
        # 📐 DISEÑO SIMÉTRICO DIRECTO SƨR EN 1 SOLA FILA PARA COMPACTAR EL ESPACIO
        col_fecha_nueva, col_titulo_nuevo, col_btn_agg, col_dropdown_historial, col_btn_multiuso = st.columns(
            [0.8, 3.5, 0.8, 4.1, 0.8]
        )

        # ------------------------------------------------=================
        # COLUMNA 1: | Fecha | (Calendario expandible nativo e independiente)
        # ------------------------------------------------=================
        with col_fecha_nueva:
            fecha_nueva_clase = st.date_input(
                "Fecha Clase:", 
                value=datetime.now().date(), 
                key=f"cal_nueva_szr_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}",
                label_visibility="collapsed"
            )
            fecha_nueva_str = fecha_nueva_clase.strftime("%Y-%m-%d")

        # ------------------------------------------------=================
        # COLUMNA 2: | Tema o título | (Entrada de texto para la nueva clase)
        # ------------------------------------------------=================
        with col_titulo_nuevo:
            input_nuevo_tema = st.text_input(
                "Nuevo Tema:",
                placeholder="Escribe el nuevo tema aquí...",
                key=f"input_nuevo_tema_szr_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}",
                label_visibility="collapsed"
            )
            # Rescatamos tu lógica de validación de duplicados o campos vacíos
            titulo_ingresado_clean = input_nuevo_tema.strip()
            
            # El botón AGG se bloquea si se mantiene el texto por defecto o está vacío
            input_invalido = not titulo_ingresado_clean or titulo_ingresado_clean == "Escribe el nuevo tema aquí..."
        # ------------------------------------------------=================
        # COLUMNA 3: | agg | (Botón de guardado para la nueva lección)
        # ------------------------------------------------=================
        with col_btn_agg:
            # Tu regla: Permanece estrictamente bloqueado hasta que ingrese un título válido
            if st.button("✢", key=f"btn_agg_clase_szr_{st.session_state.materia_activa}", use_container_width=True, disabled=input_invalido, help="Registrar nuevo tema/título en esta Área."):
                
                # El escaneo ocurre ÚNICAMENTE al hacer clic, liberando la memoria de la app
                ya_existe_generico_en_esta_fecha = any(
                    materia_data["temas"][k].get("meta_fecha", "").strip() == fecha_nueva_str.strip() and 
                    materia_data["temas"][k].get("meta_titulo", "").strip().upper() == titulo_ingresado_clean.upper()
                    for k in lista_de_clases
                )
                
                if ya_existe_generico_en_esta_fecha:
                    # Activamos la alerta traslúcida caligráfica en pantalla si hay colisión de nombres
                    st.session_state.error_duplicado_visible = True
                    st.rerun()
                else:
                    st.session_state.error_duplicado_visible = False

                # [REQUERIMIENTO 2]: Lanzar aviso Toast cada 2 temas agregados a la libreta
                st.session_state.contador_temas_toast += 1

                if st.session_state.contador_temas_toast % 2 == 0:
                    st.toast("Tienes lecciones pendientes a guardar. Recuerda presionar '💾' para resguardar tus apuntes...", icon="⚠️")
                else:
                    st.toast("¡Archivado!.", icon="🔥")

                # Detectamos si la única clase existente es el cascarón de fábrica para renombrarla de inmediato
                es_clase_inicial_basura = len(lista_de_clases) == 1 and materia_data["temas"][tema_actual].get("meta_titulo", "").strip() == "Escribe el nuevo tema aquí..."

                if es_clase_inicial_basura:
                    # Extraemos el nodo original intacto para no dañar sus bloques ni observaciones anteriores
                    nodo_original = materia_data["temas"].pop(tema_actual)
                    
                    # Actualizamos la metadata interna de la clase manteniendo el ID '01'
                    nodo_original["meta_fecha"] = fecha_nueva_str
                    nodo_original["meta_titulo"] = titulo_ingresado_clean
                    nodo_original["meta_parcial"] = materia_data["caratula"].get("semestre_num", "1ER PARCIAL")
                    nodo_original["estado_evaluacion"] = "pendiente"
                    
                    # Reconstruimos la clave oficial de barras e inyectamos el nodo mutado
                    nueva_llave_auto = f"Clase 01 | {fecha_nueva_str} | {titulo_ingresado_clean}"
                    materia_data["temas"][nueva_llave_auto] = nodo_original
                    
                    st.session_state.clase_seleccionada_actual = nueva_llave_auto
                
                else:
                    # Recuperamos tu lógica de autoincremento matemático
                    numeros_existentes = [int(materia_data["temas"][k]["meta_num"]) for k in lista_de_clases if materia_data["temas"][k].get("meta_num", "").isdigit()]
                    num_auto = f"{max(numeros_existentes) + 1:02d}" if numeros_existentes else "01"
                    
                    # Armamos la estructura de la llave oficial inalterable de SƨR
                    nuevo_membrete = f"Clase {num_auto} | {fecha_nueva_str} | {titulo_ingresado_clean}"
                    
                    # Inicializamos la hoja de apuntes respetando la metadata de tus bloques
                    materia_data["temas"][nuevo_membrete] = {
                        "bloques": [{"contenido": "", "observacion": "", "ia_sugerencias": ""}], 
                        "imagenes": [], 
                        "meta_num": num_auto, 
                        "meta_fecha": fecha_nueva_str, 
                        "meta_titulo": titulo_ingresado_clean,
                        "meta_parcial": materia_data["caratula"].get("semestre_num", "1ER PARCIAL"),
                        "estado_evaluacion": "pendiente",
                        "banco_evaluacion": {"preguntas": [], "ejercicios": [], "truco": ""}
                    
                    }
                    
                    st.session_state.clase_seleccionada_actual = nuevo_membrete
            # 🔒 LIMPIEZA DE ESTRUCTURAS: Evita parpadeos o fallas de retención de índices en Streamlit
                key_radio_historial = f"rad_historial_scroll_bateria_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}"
                if key_radio_historial in st.session_state:
                    del st.session_state[key_radio_historial]
                
                key_selectbox_historial = f"sb_historial_main_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}"
                if key_selectbox_historial in st.session_state:
                    del st.session_state[key_selectbox_historial]

                
                st.session_state.rep_mesa_exp += 1
                guardar_respaldo()
                st.rerun()
        # ------------------------------------------------=================
        # COLUMNA 4: | historialclases | (Expander Deslizante de Alta Definición SƨR)
        # ------------------------------------------------=================
        with col_dropdown_historial:
            # 1. Creamos la lista elástica inyectando la batería real de la base de datos
            opciones_radio_bateria = []
            mapeo_radio_bateria = {}
            
            for llave_clase in clases_ordenadas_lista:
                c_nodo = materia_data["temas"][llave_clase]
                fecha_q = c_nodo.get('meta_fecha', '')
                titulo_q = c_nodo.get('meta_titulo', 'Sin Título')
                estado_b = c_nodo.get("estado_evaluacion", "pendiente")
                
                # Asignamos el sello de energía de la base de datos
                icon_bateria = "🔋" if c_nodo.get("estado_evaluacion", "pendiente") == "completado" else "🪫"
                                
                # Nombre 100% completo, intocable y definido de extremo a extremo
                etiqueta_completa = f"{icon_bateria} [{fecha_q}] ➔ {titulo_q}"
                
                opciones_radio_bateria.append(etiqueta_completa)
                mapeo_radio_bateria[etiqueta_completa] = llave_clase

            # Buscamos el índice seguro para que la pestaña activa aparezca marcada por defecto
            if st.session_state.clase_seleccionada_actual in clases_ordenadas_lista:
                idx_actual = clases_ordenadas_lista.index(st.session_state.clase_seleccionada_actual)
                indice_radio_seguro = min(idx_actual, len(opciones_radio_bateria) - 1)
            else:
                indice_radio_seguro = 0

            # 2. Envolvemos la maquinaría dentro de un expander ultracompacto para salvar espacio
            with st.expander("📂 Historial de temas agregados...", expanded=False):
                
                # 3. Inyectamos el CSS rígido que acuesta los botones y activa el deslizamiento horizontal
                st.markdown(
                    """
                    <style>
                        /* Obliga a las opciones a ponerse de lado y activar el desplazamiento de arrastre */
                        div.stRadio > div[role="radiogroup"] {
                            display: flex !important;
                            flex-direction: row !important;
                            overflow-x: auto !important;
                            overflow-y: hidden !important;
                            white-space: nowrap !important;
                            width: 100% !important;
                            padding: 10px 5px !important;
                            background: rgba(229, 193, 88, 0.03) !important;
                            border: 1px dashed rgba(229, 193, 88, 0.3) !important;
                            border-radius: 8px !important;
                            gap: 10px !important;
                        }
                        /* Estilizado premium estilo cápsula para cada lección completa */
                        div.stRadio label {
                            white-space: nowrap !important;
                            font-size: 11px !important;
                            background: #FFFFFF !important;
                            padding: 5px 12px !important;
                            border-radius: 15px !important;
                            border: 1px solid #E2E8F0 !important;
                            cursor: pointer !important;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
                        }
                        /* Ocultamos los botones circulares de selección para mantener estética limpia */
                        div.stRadio input[type="radio"] {
                            display: none !important;
                        }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                # Renderizamos la botonera deslizable con las baterías incluidas
                clase_seleccionada_etiqueta = st.radio(
                    "Deslizar:",
                    options=opciones_radio_bateria,
                    index=indice_radio_seguro,
                    key=f"rad_historial_scroll_bateria_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}",
                    label_visibility="collapsed"
                )

                # Si el estudiante arrastra, elige y hace clic en una clase, saltamos de inmediato
                if clase_seleccionada_etiqueta and clase_seleccionada_etiqueta in mapeo_radio_bateria:
                    nuevo_tema_elegido = mapeo_radio_bateria[clase_seleccionada_etiqueta]
                    if nuevo_tema_elegido != st.session_state.clase_seleccionada_actual:
                        st.session_state.clase_seleccionada_actual = nuevo_tema_elegido
                        st.rerun()
                    
        # ------------------------------------------------=================
        # COLUMNA 5: | editar / guardar | (El gatillo multiuso de control)
        # ------------------------------------------------=================
        with col_btn_multiuso:
            # Cambia dinámicamente de etiqueta según el estado activo del expander inferior
            label_multiuso = "💾" if st.session_state.modo_edicion_historial else "✏️"
            
            # El botón solo se desbloquea si el historial tiene lecciones válidas cargadas
            historial_vacio = not opciones_dropdown or not tema_actual or "Escribe el nuevo tema aquí..." in tema_actual
            
            if st.button(label_multiuso, key=f"btn_multi_edit_szr_{st.session_state.materia_activa}", use_container_width=True, disabled=historial_vacio):
                if st.session_state.modo_edicion_historial:
                    # Al presionar 'Guardar', activamos un interruptor lógico ficticio
                    st.session_state.ejecutar_guardado_edicion = True
                else:
                    # Al presionar 'Editar', desplegamos el panel oculto ergonómico
                    st.session_state.modo_edicion_historial = True
                st.rerun()
        # ------------------------------------------------=================
        # DESPLIEGUE DEL PANEL INFERIOR ERGONÓMICO DE EDICIÓN (BAJO LA FILA)
        # ------------------------------------------------=================
        if st.session_state.modo_edicion_historial and not historial_vacio:
            st.markdown("<hr style='border-top: 1px dashed rgba(229, 193, 88, 0.25); margin: 10px 0;'>", unsafe_allow_html=True)
            st.markdown("<p style='font-size: 11px; color: #C26146; font-weight: bold; margin-bottom: 2px;'>✏️ Modificando los datos de la lección seleccionada en el Historial:</p>", unsafe_allow_html=True)

            nueva_fecha_editada_str = datetime.now().strftime("%Y-%m-%d")
            titulo_editado_clean = ""
            # Recuperamos los datos del nodo de la clase que el usuario eligió en el selectbox
            clase_a_modificar_data = materia_data["temas"][tema_actual]

            col_edit_cal, col_edit_txt, col_edit_del = st.columns([3.0, 7.0, 1.5])

            with col_edit_cal:
                # 1. Calendario expandible para alterar la fecha de la clase antigua
                fecha_actual_dt = datetime.strptime(clase_a_modificar_data["meta_fecha"], "%Y-%m-%d").date()
                nueva_fecha_editada = st.date_input("Modificar Fecha:", value=fecha_actual_dt, key=f"edit_cal_node_{tema_actual}")
                nueva_fecha_editada_str = nueva_fecha_editada.strftime("%Y-%m-%d")
                
            with col_edit_txt:
                # 2. Caja de texto para renombrar el título o tema de la clase antigua
                nuevo_titulo_editado = st.text_input("Modificar Tema/Título:", value=clase_a_modificar_data["meta_titulo"], key=f"edit_txt_node_{tema_actual}")
                titulo_editado_clean = nuevo_titulo_editado.strip()

            with col_edit_del:
                st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
                if len(lista_de_clases) > 1:
                    # Inicializamos la bandera de confirmación específica para esta fila si no existe
                    if "confirmando_borrado_inline" not in st.session_state:
                        st.session_state.confirmando_borrado_inline = False

                    if not st.session_state.confirmando_borrado_inline:
                        # Estado 1: Botón de alerta natural
                        if st.button("⮑🗑️", key=f"btn_del_clase_inline_{tema_actual}", use_container_width=True, type="secondary", help="Eliminar esta lección completa."):
                            st.session_state.confirmando_borrado_inline = True
                            st.rerun()
                    else:
                        # Estado 2: Despliegue simétrico del Visto (Confirmar) y la X (Cancelar)
                        col_conf_visto, col_conf_cancelar = st.columns(2)
                        with col_conf_visto:
                            if st.button("✔", key=f"btn_inline_ok_del_{tema_actual}", use_container_width=True, type="primary", help="Sí, borrar permanentemente."):
                                materia_data["temas"].pop(tema_actual)
                                guardar_respaldo()
                                st.session_state.clase_seleccionada_actual = list(materia_data["temas"].keys())[-1]
                                st.session_state.confirmando_borrado_inline = False
                                st.session_state.modo_edicion_historial = False
                                st.rerun()
                        with col_conf_cancelar:
                            if st.button("❌", key=f"btn_inline_no_del_{tema_actual}", use_container_width=True, help="Cancelar y proteger lección."):
                                st.session_state.confirmando_borrado_inline = False
                                st.rerun()
                else:
                    st.button("⮑🗑️", use_container_width=True, disabled=True, help="No puedes eliminar la única lección del portafolio.")

            # --- MOTOR DE PROCESAMIENTO Y SELLADO DE CAMBIOS (ACCIONADO POR EL BOTÓN MULTIUSO) ---
            if st.session_state.get("ejecutar_guardado_edicion", False):
                st.session_state.ejecutar_guardado_edicion = False # Apagamos el gatillo lógico
                
                if not titulo_editado_clean:
                    titulo_editado_clean = "Escribe el nuevo tema aquí..."

                # El escaneo ocurre EN CALIENTE únicamente al confirmar la edición
                fechas_y_titulos_existentes = [
                    (materia_data["temas"][k].get("meta_fecha", "").strip(), materia_data["temas"][k].get("meta_titulo", "").strip().upper()) 
                    for k in lista_de_clases if k != tema_actual
                ]
                
                # Rescatamos tu lógica exacta de prevención de coexistencia/duplicados inter-clases
                chequeo_duplicado_edicion = (nueva_fecha_editada_str, titulo_editado_clean.upper()) in fechas_y_titulos_existentes
                
                if chequeo_duplicado_edicion:
                    st.session_state.error_duplicado_visible = True
                    st.session_state.modo_edicion_historial = True # Mantiene abierto el panel para corregir
                    st.rerun()
                else:
                    st.session_state.error_duplicado_visible = False
                    
                    # Sincronizamos los valores dentro del diccionario de la base de datos
                    clase_a_modificar_data["meta_fecha"] = nueva_fecha_editada_str
                    clase_a_modificar_data["meta_titulo"] = titulo_editado_clean
                    clase_a_modificar_data["estado_evaluacion"] = "pendiente"
                    
                    # Reconstruimos la llave de barras oficial sin alterar los bloques de apuntes
                    num_back = clase_a_modificar_data.get("meta_num", "01")
                    nueva_llave_auto = f"Clase {num_back} | {nueva_fecha_editada_str} | {titulo_editado_clean}"
                    
                    # Cambiamos la clave en el diccionario de la materia extrayendo el nodo completo
                    materia_data["temas"][nueva_llave_auto] = materia_data["temas"].pop(tema_actual)
                    
                    # Forzamos la actualización inmediata de la navegación ANTES del rerun
                    st.session_state.clase_seleccionada_actual = nueva_llave_auto
        
                    # 🚀 SOLUCIÓN DEFINITIVA BUG 09: Destrucción del búfer obsoleto del radio widget
                    # Limpiamos los buffers del widget para que st.radio recalcule correctamente su índice objetivo
                    key_radio_historial = f"rad_historial_scroll_bateria_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}"
                    if key_radio_historial in st.session_state:
                        del st.session_state[key_radio_historial]

                    # Sincronización estricta de la llave complementaria solicitada
                    key_antigua_selectbox = f"sb_historial_main_{st.session_state.materia_activa}_{st.session_state.rep_mesa_exp}"
                    if key_antigua_selectbox in st.session_state:
                        del st.session_state[key_antigua_selectbox]
                        
                    guardar_respaldo()         
                    # Anclamos la navegación a la nueva llave, cerramos el expander y refrescamos
                    st.session_state.modo_edicion_historial = False
                    st.rerun()

# =====================================================================
#   AQUÍ COMIENZAN TUS FORMULARIOS DESPLEGABLES (AFUERA DE LA MARQUESINA)
# =====================================================================

# Formulario desplegable discreto para Renombrar Asignatura (Mantenido intacto al 100%)
if st.session_state.editando_materia:
    st.markdown("<br>", unsafe_allow_html=True)
    nuevo_nombre_mat = st.text_input("✏️ Modificar nombre de la asignatura:", value=st.session_state.materia_activa, key="input_rename_centro")
    
    col_btn_ren_corto, col_btn_ren_aire = st.columns([4.0, 18.0])
    with col_btn_ren_corto:
        if st.button("Confirmar Cambio", key="btn_confirm_rename_centro", use_container_width=True):
            if nuevo_nombre_mat.strip() and nuevo_nombre_mat != st.session_state.materia_activa:
                st.session_state.datos_materias[nuevo_nombre_mat] = st.session_state.datos_materias.pop(st.session_state.materia_activa)
                st.session_state.materia_activa = nuevo_nombre_mat
                st.session_state.editando_materia = False
                st.session_state.configurando_caratula = False 
                guardar_respaldo()
                st.rerun()
            else:
                st.session_state.editando_materia = False
                st.rerun()
else:
    pass

# =====================================================================
# 📝 FORMULARIO DE MEMBRETE UNIFICADO (CON RENOMBRADO INTEGRADO - INTERFAZ ORIGINAL)
# =====================================================================
fecha_clase_input = f"{st.session_state.get('sel_fecha_anio_szr', datetime.now().year)}-{st.session_state.get('sel_fecha_mes_szr', f'{datetime.now().month:02d}')}-{st.session_state.get('sel_fecha_dia_szr', f'{datetime.now().day:02d}')}"
if st.session_state.configurando_caratula and not st.session_state.get("modo_quiz_activo", False):
    st.markdown("##### 📝 Configurar Membrete o Carátula")
    
    # 🌟 INTEGRACIÓN: Tu campo mejorado para renombrar la asignatura al inicio del formulario
    nuevo_nombre_mat = st.text_input("✏️ Modificar nombre de la asignatura:", value=st.session_state.materia_activa, key="input_rename_centro")

    col_sub_estudiante, col_sub_facultad = st.columns([6.7, 3.3])
    with col_sub_estudiante:
        estudiante_tmp = st.text_input("👤 Nombre del Estudiante o Autor:", value=materia_data["caratula"].get("usuario", ""), key="car_u_centro")
    with col_sub_facultad:
        facultad_tmp = st.text_input("🏢 Facultad - Carrera o Institución:", value=materia_data["caratula"].get("facultad", ""), key="car_fac", placeholder="Ej. Facultad de Ingeniería") 
    
    col_sub_curso, sep_2, col_sub_paralelo = st.columns([3.3, 3.4, 3.3])
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
 
    # 🌟 RESTAURACIÓN S.E.D.E: Fila unificada para subir el Banner y controlar el membrete en paralelo
    st.markdown("<hr style='border-top: 1px solid rgba(0,0,0,0.05); margin: 15px 0;'>", unsafe_allow_html=True)
    
    col_media_save, col_media_reset, col_media_foto, col_media_del_img = st.columns([2.0, 2.0, 4.0, 2.0])
      
    with col_media_foto:
        # El cargador se queda libre y en silencio
        foto_portada = st.file_uploader("🖼️ Sube una foto de cabecera:", type=["png", "jpg", "jpeg"], key="car_f_centro")
            
    with col_media_save:        
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        # VALIDACIÓN PREVIA DE COLISIÓN DE NOMBRES
        nombre_antiguo = st.session_state.materia_activa
        nombre_nuevo_clean = nuevo_nombre_mat.strip()
        
        # Comprobamos si el usuario intenta cambiar el nombre por uno que ya pertenece a OTRA materia
        nombre_en_conflicto = (nombre_nuevo_clean != nombre_antiguo) and (nombre_nuevo_clean in st.session_state.datos_materias)
        
        if nombre_en_conflicto:
            st.error(f"🚫Ya existe 🚫\n'{nombre_nuevo_clean}'.")
            # El botón se renderiza deshabilitado para impedir la ejecución del hilo de guardado
            st.button("💾", use_container_width=True, disabled=True, key="btn_guardar_membrete_disabled")
        else:
            if st.button("💾", use_container_width=True, help="Confirmar y Guardar Ajustes", key="btn_guardar_membrete_real", type="primary"):
                
                # Procesamos la foto con medida fija al presionar guardar
                if foto_portada:
                    img_portada = Image.open(foto_portada)
                    img_portada = img_portada.resize((100, int((100 / float(img_portada.width)) * float(img_portada.height))), Image.Resampling.LANCZOS)
                    if img_portada.mode in ("RGBA", "P"):
                        img_portada = img_portada.convert("RGB")
                    
                    buffer_comprimido = io.BytesIO()
                    img_portada.save(buffer_comprimido, format="JPEG", quality=75)
                    materia_data["caratula"]["imagen"] = base64.b64encode(buffer_comprimido.getvalue()).decode("utf-8")

                # Asignaciones de texto intactas
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
                
                if nombre_nuevo_clean and nombre_nuevo_clean != nombre_antiguo:
                    # 1. Recuperamos la lección que estaba visualizando el usuario antes del cambio
                    clase_activa_guardada = st.session_state.get("clase_seleccionada_actual")             
                    # 2. Renombramos la materia en el diccionario maestro
                    st.session_state.datos_materias[nombre_nuevo_clean] = st.session_state.datos_materias.pop(nombre_antiguo)
                    st.session_state.materia_activa = nombre_nuevo_clean
                    # 3. Forzamos a la sesión a recordar la lección bajo el contexto de la nueva materia
                    st.session_state.clase_seleccionada_actual = clase_activa_guardada
                    
                    # Evita persistencia de preguntas viejas en la nueva materia
                    st.session_state.quiz_combinado_data = None
                    st.session_state.quiz_generado_data = None
                
                st.session_state.configurando_caratula = False
                guardar_respaldo()
                st.rerun()

    with col_media_del_img:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        # 📸 BOTÓN EXCLUSIVO PARA QUITAR LA IMAGEN
        estado_deshabilitado = not bool(materia_data["caratula"].get("imagen"))
        if st.button("🖼️➔🗑️", use_container_width=True, help="Eliminar la foto de cabecera", key="btn_del_only_photo_szr", disabled=estado_deshabilitado):
            materia_data["caratula"]["imagen"] = None
            st.session_state.configurando_caratula = False
            guardar_respaldo()
            st.rerun()

    with col_media_reset:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        # ESTE SIGUE CORRESPONDIENDO AL RESETEO TOTAL DE LA CARÁTULA
        if st.button("♻️", use_container_width=True, help="Restablecer toda la información del usuario", key="btn_reset_caratula_real"):
            materia_data["caratula"] = {"imagen": None, "usuario": "", "ciclo": "", "curso": "", "curso_num": "", "paralelo_letra": "", "semestre_num": "", "facultad": ""}
            st.session_state.configurando_caratula = False
            guardar_respaldo()
            st.rerun()
else:
    pass


# Extraemos el nodo de datos activo de la lección seleccionada
clase_activa_data = materia_data["temas"][tema_actual]
titulo_limpio_actual = clase_activa_data["meta_titulo"].strip()

# Renderizado de la alerta traslúcida y caligráfica con los tonos suavizados solicitados
if st.session_state.get("error_duplicado_visible", False):
    st.markdown(
        f"""
        <div style='
            border: 1.5px dashed rgba(224, 86, 86, 0.35); 
            border-radius: 10px; 
            padding: 14px 20px; 
            background-color: rgba(245, 137, 137, 0.06); 
            margin-top: 15px; 
            margin-bottom: 5px; 
            backdrop-filter: blur(5px); 
            font-family: "Comic Sans MS", "Chalkboard SE", "Quicksand", sans-serif;
        '>
            <span style='color: #A63333; font-size: 14px; font-weight: bold; display: flex; align-items: center; gap: 9px;'>
                ⚠️ Coexistencia en Agenda
            </span>
            <p style='margin: 6px 0 0 0; font-size: 13px; color: #5C2E2E; line-height: 1.5;'>
                El Tema o Titulo ingresado ya se encuentra registrado para esta fecha. Modifica el Tema o Titulo en el cuadro de texto para poder guardar los cambios de forma segura, si es la continuación de tema o titulo anterior añade un distintivo.
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

# =====================================================================
# 📌 DECORADOR FRAGMENT: CONTROL ASÍNCRONO DE LA MESA DE TRABAJO SƨR
# =====================================================================
@st.fragment
def renderizar_mesa_trabajo_szr(tema_actual, materia_data):
    # Asegurar la carga de elementos a la lección activa de forma segura
    clase_data = materia_data["temas"][tema_actual]
    bloques_actuales = clase_data["bloques"]
    titulo_actual_raw = clase_data.get("meta_titulo", "").strip()
    if "imagenes" not in clase_data:
        clase_data["imagenes"] = []
    # Si la clase actual mantiene el nombre de fábrica, mostramos el mensaje guía en lugar de las cajas
    if titulo_actual_raw == "Escribe el nuevo tema aquí...":
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style='
                background: linear-gradient(135deg, rgba(229, 193, 88, 0.04) 0%, rgba(229, 193, 88, 0.01) 100%);
                border: 2px double #E5C158;
                border-radius: 12px;
                padding: 40px 20px;
                text-align: center;
                box-shadow: inset 0 0 20px rgba(229, 193, 88, 0.02);
            '>
                <span style='font-size: 35px; display: block; margin-bottom: 10px;'>✒️</span>
                <h2 style='font-family: "Playfair Display", serif; color: #1E293B; font-size: 18px; margin-bottom: 8px;'>Área de Apuntes</h2>
                <p style='color: #64748B; font-size: 13px; max-width: 450px; margin: 0 auto 0 auto; line-height: 1.4;'>
                    Ingresa el nombre del tema en la caja superior y presiona el botón <b>✢</b> para activar tu cuaderno inteligente.
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        return # ⛔ CORTA LA EJECUCIÓN: Impide de forma absoluta pintar las cajas de apuntes abajo
    
    # NIVEL SUPERIOR: Entrada de Datos (Mitad y Mitad de la pantalla)
    col_contenido, col_observacion = st.columns([7.0, 3.0])
            
    with col_contenido:
        st.markdown("<h3 style='color: #C26146; margin-bottom: 10px; font-family: \"Playfair Display\", serif;'>📝 Contenido</h3>", unsafe_allow_html=True)

    with col_observacion:
        st.markdown("<h3 style='color: #D3B5A6; margin-bottom: 10px; font-family: \"Playfair Display\", serif;'>💡Observaciones</h3>", unsafe_allow_html=True)
    st.markdown('<div class="capsula-bloque-szr">', unsafe_allow_html=True)
   
    # --- RENDERIZADO DINÁMICO DE FILAS EN CÁPSULAS INDIVIDUALES ---
    for i in range(len(bloques_actuales)):
        bloque = bloques_actuales[i]
        
        # Modo Lectura Activo: Se eliminan text areas y botones; se muestra tipografía limpia de libro
        if st.session_state.modo_lectura_activo:
            col_lectura_cont, col_lectura_obs = st.columns([7.0, 3.0])
            with col_lectura_cont:
                if bloque["contenido"].strip():
                    st.markdown(f"<div style='font-size:15px; line-height:1.6; color:#1E293B; padding:5px 0;'>{bloque['contenido']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='font-style:italic; color:#94A3B8; font-size:13px;'>Bloque de contenido vacío.</p>", unsafe_allow_html=True)
            with col_lectura_obs:
                if bloque["observacion"].strip():
                    st.markdown(f"<div style='font-size:13.5px; font-style:italic; color:#64748B; background:#F8FAFC; padding:8px; border-radius:6px; border-left:3px solid #D3B5A6;'>{bloque['observacion']}</div>", unsafe_allow_html=True)
            
            # Si hay sugerencias de IA guardadas, se muestran impresas de manera estética
            if bloque.get("ia_sugerencias"):
                st.markdown(
                    f"""
                    <div style='background-color: rgba(135, 169, 107, 0.04); padding: 10px 15px; border-radius: 6px; border-left: 3px solid #87A96B; margin-top: 5px; margin-bottom: 15px; font-size: 13px;'>
                        <strong>🧠 Análisis de Refuerzo Guardado:</strong><br>{bloque["ia_sugerencias"].replace('\n', '<br>')}
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            # Modo Edición Activo: Interfaz normal acoplada con Callbacks antideslizamiento de foco
            col_contenido, col_observacion = st.columns([7.0, 3.0])
            
            key_textarea_cont = f"cont_szr_{st.session_state.materia_activa}_{tema_actual}_{i}"
            key_textarea_obs = f"obs_szr_{st.session_state.materia_activa}_{tema_actual}_{i}"
            # Determinamos si el editor debe congelarse en base a la transmisión activa
            bloqueo_edicion_activo = st.session_state.get("ejecutando_peticion_ia", False)
            
            with col_contenido:
                st.text_area("",
                    value=bloque["contenido"], 
                    key=key_textarea_cont, 
                    height=120, 
                    placeholder="Anota tus apuntes aquí...",
                    label_visibility="collapsed",
                    disabled=bloqueo_edicion_activo, # 🔒 Compuerta de seguridad S.E.D.E
                    on_change=callback_actualizar_bloque_apunte,
                    args=(st.session_state.materia_activa, tema_actual, i, "contenido", key_textarea_cont)
                )
                
            with col_observacion:
                st.text_area( "",
                    value=bloque["observacion"], 
                    key=key_textarea_obs, 
                    height=120, 
                    placeholder="Palabras clave, ideas importantes o comentarios...",
                    label_visibility="collapsed",
                    disabled=bloqueo_edicion_activo, # 🔒 Compuerta de seguridad S.E.D.E
                    on_change=callback_actualizar_bloque_apunte,
                    args=(st.session_state.materia_activa, tema_actual, i, "observacion", key_textarea_obs)
                )
            
            # --- FILA DE ACCIONES HORIZONTAL (EDICIÓN) ---
            col_inf_ia, col_inf_pizarra, col_inf_quitar = st.columns([4.5, 2.5, 3.0])
            
            with col_inf_ia:
                print(bloque["contenido"])
                inyectar_recursos_inteligentes(bloque["contenido"], i+1, col_inf_ia, bloque, tema_actual)
                
            with col_inf_pizarra:
                llave_pizarra = f"btn_pizarra_gate_{st.session_state.materia_activa}_{tema_actual}_{i}"
                if st.button("🖥️ ☙❧ Pizarra", key=llave_pizarra, use_container_width=True, help="Abrir lienzo flotante para lápiz óptico"):
                    # Activamos el interruptor en la sesión global
                    st.session_state[f"pizarra_activa_global_{i}"] = True
                    st.rerun()
                
            with col_inf_quitar:
                if len(bloques_actuales) > 1 and i > 0:
                    if st.button(f"⤷🗑️", key=f"btn_del_block_{st.session_state.materia_activa}_{tema_actual}_{i}", use_container_width=True, help="Eliminar nuevo bloque"):
                        bloques_actuales.pop(i)
                        guardar_respaldo()
                        st.rerun()
#            prompt_pizarra = (
#                "Analiza la imagen adjunta que contiene anotaciones a mano alzada de un estudiante. "
#                "La imagen está dividida visualmente o contiene ideas de clase y comentarios.\n\n"
#                "Tu objetivo es devolver estrictamente un objeto JSON con dos llaves, sin textos de relleno:\n"
#                "{\n"
#                "  'contenido': 'Transcribe y desarrolla de forma clara, estructurada y ordenada en párrafos limpios el tema principal dibujado o escrito.',\n"
#                "  'observaciones': 'Extrae las palabras clave, conceptos críticos, fórmulas aisladas o anotaciones al margen de forma resumida.'\n"
#                "}"
#            )
    # =====================================================================
    # 🔍 BARRA DE BÚSQUEDA GLOBAL Y BOTÓN AGREGAR (MUESTRAN UNA SOLA VEZ)
    # =====================================================================
    st.markdown('<div class="capsula-bloque-szr">', unsafe_allow_html=True)
 
    col_global_sep, col_global_btn, col_global_sep, col_global_search = st.columns([1, 2, 1, 6.0])
    
    # Botón reactivo para seguir expandiendo el cuaderno (Fuera del FOR, dentro del IF)
    with col_global_btn:
        if st.button("✜ Bloque ⮭", use_container_width=True, help="Añade un bloque para nuevo contenido para diversificar la información..."):
            bloques_actuales.append({"contenido": "", "observacion": "", "ia_sugerencias": ""})
            guardar_respaldo()
            st.rerun()
    with col_global_search:
        # Creamos una sub-rejilla interna de 3 componentes en una sola fila
        # 2.0 para el texto, 6.0 para la caja, 2.0 para el botón
        col_g_txt, col_g_input, col_g_btn = st.columns([1.8, 6.4, 1.8])

        with col_g_txt:
            # Pintamos cada letra de forma independiente en HTML
            html_letras_web = (
                "<div style='margin-top: 7px; font-family: sans-serif; font-weight: 950; font-size: 16px; white-space: nowrap; letter-spacing: 0.5px; text-shadow: 0px 1px 2px rgba(0,0,0,0.05);'>"
                "<span style='color: #4285F4;'>🌐W</span>"     # Globo y W en Azul Eléctrico
                "<span style='color: #EA4335;'>E</span>"       # E en Rojo Vibrante
                "<span style='color: #FBBC05;'>B</span>"       # B en Amarillo Destello
                "</div>"
            )
            st.markdown(html_letras_web, unsafe_allow_html=True)
                
        with col_g_input:
            # Clave global e independiente blindada contra fallos de bucles
            key_input_duda = f"d_input_google_global_{st.session_state.materia_activa}_{st.session_state.rep_bug_exp}"
            duda_estudiante = st.text_input("Ingrese su búsqueda aquí:", placeholder="🔎 Buscar...", key=key_input_duda, label_visibility="collapsed")

        with col_g_btn:
            # Si el estudiante escribió algo -> Generamos su link seguro
            if duda_estudiante and duda_estudiante.strip():
                query_segura = urllib.parse.quote_plus(duda_estudiante.strip())
                url_final_google = f"https://google.com/search?q={query_segura}"
                
                st.link_button(
                    label=f"💡",
                    url=url_final_google,
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.button("💡", use_container_width=True, disabled=True, key=f"btn_g_dis_global_{st.session_state.materia_activa}")

    # =====================================================================
    # 🖨️ OPCIÓN 1: DOBLE MOTOR DE EXPORTACIÓN IMPRIMIBLE REAL SƨR
    # =====================================================================    
    # Creamos dos columnas elegantes para colocar los botones en paralelo
    col_print_clase, col_print_cuaderno = st.columns(2)

    fecha_actual = tema_actual.split(" | ")[1] if len(tema_actual.split(" | ")) > 1 else datetime.now().strftime("%Y-%m-%d")
    periodo_activo_caratula = materia_data["caratula"].get("ciclo", "Periodo Actual")

    # --- 📐 INICIALIZACIÓN DEL BOTÓN 1: CLASE ACTUAL ---
    html_clase_unica = templates.obtener_html_clase_unica(
        materia_activa=st.session_state.materia_activa,
        fecha_actual=fecha_actual, 
        tema_actual=tema_actual,
        bloques_actuales=bloques_actuales,
        imagenes_clase=clase_data.get("imagenes", []))
    nombre_descarga_clase = f"{tema_actual.replace(' | ', '_').replace(' ', '_')}_Imprimir.html"

    with col_print_clase:
        st.download_button(
            label="🖨️ Imprimible Tema/Titulo Actual",
            data=html_clase_unica,
            file_name=nombre_descarga_clase,
            mime="text/html",
            use_container_width=True
        )

    # --- 📐 INICIALIZACIÓN DEL BOTÓN 2: CUADERNO COMPLETO ---
    
    html_todo_el_cuaderno = templates.obtener_html_cuaderno_completo(st.session_state.materia_activa, periodo_activo_caratula, materia_data.get("temas", {}))
    nombre_descarga_cuaderno = f"ASIGNATURA_{st.session_state.materia_activa.upper()}.html"

    with col_print_cuaderno:
        st.download_button(
            label="🖨️ Imprimible Área Completa",
            data=html_todo_el_cuaderno,
            file_name=nombre_descarga_cuaderno,
            mime="text/html",
            use_container_width=True
        )
        
    st.markdown('<div class="capsula-bloque-szr">', unsafe_allow_html=True)
    # =====================================================================
    # 📸 TERCER BLOQUE: GALERÍA INTELIGENTE OPTIMIZADA (BLINDAJE DE CONTADOR Y PLACEHOLDER)
    # =====================================================================
    with st.container(border=True):
        
        # 📐 REJILLA S.E.D.E: 4.5 para título | 3.5 para el uploader silencioso | 2.0 para el gatillo de cámara
        col_galeria_upload, col_galeria_btn, col_galeria_txt = st.columns([5.0, 1.5, 3.5])
        
        with col_galeria_txt:
            st.markdown("<h3 style='color: #0F172A; margin-top: 10px; margin-bottom: 0px; font-family: \"Playfair Display\", serif;'>📸 Galería/Anexos</h3>", unsafe_allow_html=True)
        
        with col_galeria_upload:
            # Llave uploader dinámica blindada contra atascos de búfer
            llave_uploader_dinamica = f"uploader_{st.session_state.materia_activa}_{tema_actual}_{st.session_state.rep_bug_exp}"
            archivo_cargado = st.file_uploader("Subir Visual", type=["png", "jpg", "jpeg"], key=llave_uploader_dinamica, label_visibility="collapsed")

        with col_galeria_btn:
            st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
            if st.button("¡Agg!", use_container_width=True, type="primary", help="Procesar e inyectar la imagen cargada en tu búnker de evidencias"):
                if archivo_cargado:
                    img_clase = Image.open(archivo_cargado)
                    
                    # 🚀 BALANCE COMERCIAL DEFINITIVO (BUG 10 REFINADO): Alta Definición Académica 
                    # Escalamos a 1280px (HD) para resguardar la nitidez de fórmulas y textos pequeños al descargar
                    if img_clase.width > 1280:
                        ancho_t = 1280
                        alto_t = int((ancho_t / float(img_clase.width)) * float(img_clase.height))
                        img_clase = img_clase.resize((ancho_t, alto_t), Image.Resampling.LANCZOS)
                    
                    if img_clase.mode in ("RGBA", "P"):
                        img_clase = img_clase.convert("RGB")
                        
                    buffer_img = io.BytesIO()
                    # Calidad al 75% con optimización activa: perfecta legibilidad en impresiones sin saturar la RAM
                    img_clase.save(buffer_img, format="JPEG", quality=75, optimize=True)
                    imagen_base64 = base64.b64encode(buffer_img.getvalue()).decode("utf-8")

                    fecha_foto = datetime.now().strftime("%Y-%m-%d")
                    hora_foto = datetime.now().strftime("%H:%M:%S")
                    
                    foto_ya_existe = any(f["b64"] == imagen_base64 for f in clase_data["imagenes"])
                    if not foto_ya_existe:
                        clase_data["imagenes"].append({
                            "b64": imagen_base64,
                            "fecha": fecha_foto,
                            "hora": hora_foto,
                            "pie": "" 
                        })
                        
                        # Gatillo de limpieza por refresco de llave
                        st.session_state.rep_bug_exp += 1
                        guardar_respaldo()
                        st.rerun()

        # --- REJILLA AUTOMÁTICA DE IMÁGENES ---
        if clase_data["imagenes"]:
            st.markdown("<hr style='border-top: 1px solid rgba(0,0,0,0.03); margin: 15px 0 10px 0;'>", unsafe_allow_html=True)
            columnas_fotos = st.columns(4) 

            # Inicializamos un buffer de renderizado rápido en la sesión si no existe
            if "cache_binario_fotos" not in st.session_state:
                st.session_state.cache_binario_fotos = {}

            for idx, foto_obj in enumerate(clase_data["imagenes"]):
                with columnas_fotos[idx % 4]: 
                   # Evitamos decodificar el Base64 repetidamente en cada rerun
                    foto_b64_key = foto_obj["b64"][:50] + str(idx) # Llave única corta
                    if foto_b64_key not in st.session_state.cache_binario_fotos:
                        st.session_state.cache_binario_fotos[foto_b64_key] = base64.b64decode(foto_obj["b64"])
                    
                    # Pintamos la foto leyendo el baxazinario directo de RAM, reduciendo el lag al 0%
                    st.image(st.session_state.cache_binario_fotos[foto_b64_key], use_container_width=True)
                    
                    f_fija = foto_obj.get("fecha", datetime.now().strftime("%Y-%m-%d"))
                    h_fija = foto_obj.get("hora", datetime.now().strftime("%H:%M:%S"))
                    st.markdown(f"<span style='font-size: 11px; color: #94A3B8; display: block; margin-bottom: 4px;'>🔒 Registro: {f_fija} | {h_fija}</span>", unsafe_allow_html=True)
                                   
                    # Dejamos value con el dato real del JSON y movemos la guía al placeholder nativo
                    nuevo_comentario = st.text_input(
                        "✏️ Nota:", 
                        value=foto_obj["pie"], 
                        placeholder="✍️ Añadir nota o descripción...", # Texto fantasma guía ergonómico
                        key=f"live_note_edit_{st.session_state.materia_activa}_{tema_actual}_{idx}",
                        label_visibility="collapsed"
                    )
                    
                    if nuevo_comentario != foto_obj["pie"]:
                        clase_data["imagenes"][idx]["pie"] = nuevo_comentario
                        guardar_respaldo()

                    # Controles de tarjeta simétricos
                    col_card_download, col_card_delete = st.columns(2)
                    
                    with col_card_download:
                        foto_bytes_recuperados = base64.b64decode(foto_obj["b64"])
                        st.download_button(
                            label="📥",
                            data=foto_bytes_recuperados,
                            file_name=f"EVIDENCIA_{f_fija}_{idx}.jpg",
                            mime="image/jpeg",
                            use_container_width=True,
                            help="Descargar fotografía",
                            key=f"dl_btn_card_{st.session_state.materia_activa}_{tema_actual}_{idx}"
                        )
                        
                    with col_card_delete:
                        if st.button("🗑️", key=f"del_img_{idx}", use_container_width=True, help="Eliminar Imagen"):
                            # 1. Extraemos de forma quirúrgica la casilla de la foto sobre la cual hizo clic el alumno
                            clase_data["imagenes"].pop(idx)
                            # 2. Vaciamos por completo el búfer temporal de la memoria RAM.
                            # Esto garantiza que al reordenarse las fotos sobrevivientes en sus nuevos índices,
                            # no arrastren ni hereden residuos de miniaturas o bytes cruzados de la foto muerta.
                            st.session_state.cache_binario_fotos = {} 
                            # 3. Incrementamos los contadores de control de refresco del uploader
                            st.session_state.rep_bug_exp += 1 
                            # 4. Sellamos los cambios en el disco duro local y reiniciamos la UI en caliente
                            guardar_respaldo()

# --- DISPARADOR DE LA MESA DE TRABAJO (ENUNCIAR LA FUNCIÓN FRAGMENTADA) ---
if tema_actual and not st.session_state.get("modo_quiz_activo", False):
    renderizar_mesa_trabajo_szr(
        tema_actual=tema_actual, 
        materia_data=materia_data
    )

# =====================================================================
# 🚀 NÚCLEO DE DISPARO RAÍZ DE PIZARRA FLOTANTE SƨR (AFUERA DEL FRAGMENT)
# =====================================================================
if tema_actual and "datos_materias" in st.session_state and not st.session_state.get("modo_quiz_activo", False):
    bloques_raiz = materia_data["temas"][tema_actual]["bloques"]
    for idx_b, b_nodo in enumerate(bloques_raiz):
        if st.session_state.get(f"pizarra_activa_global_{idx_b}", False):
            pizarra.abrir_pizarra_flotante_szr(
                materia=st.session_state.materia_activa,
                tema=tema_actual,
                indice_bloque=idx_b,
                bloque_ref=b_nodo,
                funcion_guardar=guardar_respaldo
            )


# Prueba temporal de diagnóstico SƨR
if "GEMINI_API_KEY" in st.secrets:
    st.sidebar.success("🔑 ¡Llave detectada en Secrets!")
else:
    st.sidebar.error("❌ Archivo de secretos invisible")
