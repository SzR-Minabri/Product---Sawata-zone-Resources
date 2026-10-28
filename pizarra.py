import streamlit as st
import time
import io
from PIL import Image
from google import genai
from google.genai import types  
from pydantic import BaseModel, Field  
import json
import base64
from datetime import datetime
import os

# 1. Esquema estricto para obligar a Gemini a estructurar y jerarquizar la información
class PizarraSchema(BaseModel):
    jerarquia: str = Field(description="Clasificación estructural exacta determinada por el título manuscrito: 'Título Principal', 'Subtítulo' o 'Cuerpo General'.")
    contenido: str = Field(description="Transcribe y desarrolla en párrafos limpios el tema principal. Cualquier expresión matemática, límite, función o derivada DEBE estar en LaTeX rodeada por $ (ej: $f(x)=x^2$).")
    observaciones: str = Field(description="Conceptos críticos, tips del alfiler o anotaciones al margen de forma súper resumida.")

@st.dialog("🖥️ Pizarra de Trazos Activa SƨR", width="large")
def abrir_pizarra_flotante_szr(materia, tema, indice_bloque, bloque_ref, funcion_guardar):
    from streamlit_drawable_canvas import st_canvas
    
    # 🔒 MEMORIA INMUNE SƨR: Resguarda la estructura de trazos del lienzo
    llave_memoria_trazos = f"trazos_canvas_{materia}_{tema}_{indice_bloque}"
    if llave_memoria_trazos not in st.session_state:
        st.session_state[llave_memoria_trazos] = None

    # Estilos Premium minimalistas solicitados: Sin iconos abrumadores
    st.markdown(
        """
        <style>
            .cabecera-pizarra-szr {
                background: linear-gradient(135deg, rgba(239, 219, 161, 0.12) 0%, rgba(229, 193, 88, 0.04) 100%);
                border: 1px solid rgba(229, 193, 88, 0.25);
                border-left: 4px solid #E5C158;
                border-radius: 6px;
                padding: 8px 12px;
                margin-bottom: 12px;
            }
            .titulo-pizarra-szr {
                color: #1E293B !important;
                font-family: "Playfair Display", serif !important;
                font-size: 15px !important;
                font-weight: 700 !important;
                margin: 0 !important;
            }
        </style>
        <div class="cabecera-pizarra-szr">
            <h4 class="titulo-pizarra-szr">Lienzo Académico S.E.D.E. Core</h4>
        </div>
        """, 
        unsafe_allow_html=True
    )

    # 🛠️ BARRA DE HERRAMIENTAS ULTRA-COMPACTA Y ERGONÓMICA
    col_piz_tool, col_piz_color, col_piz_size, col_piz_clip = st.columns([3.5, 2.0, 2.5, 2.0])
    
    with col_piz_tool:
        modo_herramienta = st.selectbox("Herramienta:", ("freedraw", "point", "transform"), key=f"float_mode_{indice_bloque}", label_visibility="collapsed")
    with col_piz_color:
        color_defecto = "#B45309" if modo_herramienta == "point" else "#1E293B"
        color_trazo = st.color_picker("Color:", color_defecto, key=f"float_color_{indice_bloque}", label_visibility="collapsed")
    with col_piz_size:
        grosor_defecto = 10 if modo_herramienta == "point" else 3
        grosor_lapiz = st.slider("Grosor:", 1, 20, grosor_defecto, key=f"float_size_{indice_bloque}", label_visibility="collapsed")
    with col_piz_clip:
        # El switch tipo alfiler/clip que solicitaste para forzar la desviación a observaciones
        forzar_observacion = st.toggle("📌 Alfiler", key=f"piz_clip_toggle_{indice_bloque}", help="Desvía todo el análisis de este trazo al estante de Observaciones.")

    # ✏️ LIENZO DE RENDERIZADO EN VIVO (Textura limpia marfil académica)
    canvas_resultado = st_canvas(
        initial_drawing=st.session_state[llave_memoria_trazos],
        fill_color="rgba(180, 83, 9, 0.25)" if modo_herramienta == "point" else "rgba(255, 255, 255, 0)", 
        stroke_width=grosor_lapiz,
        stroke_color=color_trazo,
        background_color="#FAF9F5",
        update_streamlit=False, 
        height=340, 
        drawing_mode=modo_herramienta,
        key=f"widget_canvas_{materia}_{tema}_{indice_bloque}",
        display_toolbar=False # Oculta la barra nativa abrumadora para dar nitidez absoluta
    )
    st.markdown("<hr style='border-top: 1px dashed rgba(0,0,0,0.05); margin: 10px 0 8px 0;'>", unsafe_allow_html=True)
    col_float_save, col_float_close = st.columns(2)
    
    with col_float_save:
        if st.button("🪄 Finalizar e Indexar Trazo", use_container_width=True, type="primary"):
            if canvas_resultado.image_data is not None:
                with st.spinner("🧠 Procesando trazo y guardando en Anexos..."):
                    try:
                        # 1. Transformación HD del lienzo y codificación Base64
                        img_raw = Image.fromarray(canvas_resultado.image_data.astype('uint8'), 'RGBA')
                        img_rgb = img_raw.convert("RGB")
                        
                        buffer_img = io.BytesIO()
                        img_rgb.save(buffer_img, format="JPEG", quality=85)
                        imagen_base64 = base64.b64encode(buffer_img.getvalue()).decode("utf-8")
                        
                        fecha_foto = datetime.now().strftime("%Y-%m-%d")
                        hora_foto = datetime.now().strftime("%H:%M:%S")
                        
                        # 2. Inyección automática en el estante de Anexos/Galería (Tu Requerimiento Base)
                        st.session_state.datos_materias[materia]["temas"][tema]["imagenes"].append({
                            "b64": imagen_base64,
                            "fecha": fecha_foto,
                            "hora": hora_foto,
                            "pie": "Evidencia - Pizarra digital indexada" 
                        })

                        # 3. Transcripción Multimodal Inteligente estructurada con Gemini 2.5
                        api_key_segura = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
                        client = genai.Client(api_key=api_key_segura)

                        prompt_pizarra = (
                            "Analiza minuciosamente esta pizarra táctil de clase. Identifica las letras manuscritas, esquemas o fórmulas.\n"
                            "Cumple estrictamente con el esquema JSON provisto. Si detectas expresiones matemáticas o leyes físicas, escríbelas en LaTeX rodeadas por un signo de dólar ($)."
                        )

                        # Relectura limpia para el payload de la API
                        buffer_img.seek(0)
                        img_pil_lista = Image.open(buffer_api := buffer_img)

                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[img_pil_lista, prompt_pizarra],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=PizarraSchema,
                                temperature=0.1
                            )
                        )

                        if response and response.text:
                            res_json = json.loads(response.text.strip())
                            
                            jerarquia_detectada = res_json.get("jerarquia", "Cuerpo General")
                            texto_contenido = res_json.get("contenido", "")
                            texto_observacion = res_json.get("observaciones", "")
                            
                            # 4. Enrutamiento ergonómico según la posición del Alfiler/Clip
                            if forzar_observacion:
                                # Va directo y limpio al estante derecho
                                bloque_ref["observacion"] = f"{bloque_ref['observacion']}\n\n{texto_contenido}\n{texto_observacion}".strip()
                            else:
                                # Aplica formato estructurado al contenido según la detección jerárquica de Gemini
                                if jerarquia_detectada == "Título Principal":
                                    bloque_ref["contenido"] = f"### {texto_contenido}\n\n{bloque_ref['contenido']}".strip()
                                elif jerarquia_detectada == "Subtítulo":
                                    bloque_ref["contenido"] = f"#### {texto_contenido}\n\n{bloque_ref['contenido']}".strip()
                                else:
                                    bloque_ref["contenido"] = f"{bloque_ref['contenido']}\n\n{texto_contenido}".strip()
                                
                                # Las notas secundarias van de fondo a la derecha
                                if texto_observacion:
                                    bloque_ref["observacion"] = f"{bloque_ref['observacion']}\n\n{texto_observacion}".strip()

                            # 5. Sello de reinicio para que la batería de Quizzes detecte el nuevo material
                            st.session_state.datos_materias[materia]["temas"][tema]["estado_evaluacion"] = "pendiente"
                            
                            # Persistencia y Cierre Limpio
                            if canvas_resultado.json_data is not None:
                                st.session_state[llave_memoria_trazos] = canvas_resultado.json_data
                                
                            funcion_guardar()
                            st.session_state[f"pizarra_activa_global_{indice_bloque}"] = False
                            st.toast("¡Trazo analizado e inyectado a los subproductos!", icon="🪄")
                            time.sleep(0.5)
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"💥 Error al procesar visión artificial: {str(e)}")
            else:
                st.error("⚠️ El lienzo se encuentra vacío.")
                
    with col_float_close:
        if st.button("🚪 Guardar Trazo y Pausar", use_container_width=True):
            if canvas_resultado.json_data is not None:
                st.session_state[llave_memoria_trazos] = canvas_resultado.json_data
                st.session_state[f"pizarra_activa_global_{indice_bloque}"] = False
                st.rerun()