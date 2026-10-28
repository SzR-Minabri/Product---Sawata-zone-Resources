import base64

def obtener_html_materia(m_nombre, curso_seguro, temas_data):
    """Generar HTML para el respaldo ZIP de una materia completa"""
    html= f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{m_nombre} - Respaldo Portafolio del curso: {curso_seguro}</title>
        <style>
            body {{ font-family: 'Arial', sans-serif; padding: 40px; color: #0F172A; line-height: 1.6; background-color: #F8FAFC; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #FFFFFF; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .header {{ border-bottom: 3px solid #4A6B5D; padding-bottom: 15px; margin-bottom: 30px; }}
            .header h1 {{ color: #4A6B5D; margin: 0; font-size: 32px; }}
            .clase-seccion {{ margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px dashed #E2E8F0; }}
            .clase-title {{ color: #1E3A8A; font-size: 20px; font-weight: bold; margin-bottom: 15px; }}
            .bloque {{ border-left: 4px solid #D4AF37; padding-left: 15px; margin-bottom: 20px; }}
            .obs {{ font-size: 13px; color: #475569; font-style: italic; background: #F1F5F9; padding: 10px; border-radius: 6px; margin-top: 5px; }}
            .ia-box {{ font-size: 13px; color: #2E4A3F; margin-top: 10px; background-color: rgba(135, 169, 107, 0.08); padding: 12px 15px; border-radius: 6px; border-left: 4px solid #87A96B; }}
            .galeria {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 15px; }}
            .img-item {{ border: 1px solid #E2E8F0; padding: 8px; border-radius: 6px; text-align: center; background: #FAFAFA; }}
            .img-item img {{ max-width: 100%; height: auto; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📚 ÁREA DE ESTUDIO: {m_nombre}</h1>
                <p>Ecosistema de Aprendizaje Automatizado SƨR</p>
            </div>
    """
    # Si la materia no tiene clases registradas
    if not temas_data:
        html += "<p style='color: #94A3B8; font-style: italic;'>No se registraron lecciones en este periodo.</p>"
    else:
        # Recorremos cada clase de la materia
        for t_nombre, t_data in temas_data.items():
            html += f'<div class="clase-seccion"><div class="clase-title">📅 {t_nombre}</div>'
            # Añadimos los bloques de apuntes y observaciones
            for idx, blq in enumerate(t_data.get("bloques", [])):
                html += f"""
                <div class="bloque">
                    <strong>📌 PÁRRAFO {idx+1:02d}:</strong>
                    <p style="margin: 5px 0;">{blq.get('contenido', '')}</p>
                    <div class="obs"><strong>💡 Observación:</strong> {blq.get('observacion', '')}</div>
                """
                if blq.get("ia_sugerencias"):
                    ia_clean = blq["ia_sugerencias"].replace("\n", "<br>")
                    html += f'<div class="ia-box"><strong>🧠 Sugerencias Exploración Inteligente - SƨR:</strong><br>{ia_clean}</div>'
                html += "</div>"        
            # Añadimos las imágenes de esta clase con referencias locales relativas dentro del ZIP
            if t_data.get("imagenes"):
                html += "<div class='galeria'>"
                for f_idx, foto in enumerate(t_data["imagenes"]):
                    nombre_archivo_foto = f"img_clase_{t_nombre.split(' | ')[0].replace(' ', '')}_{f_idx}.jpg"
                    html += f"""
                    <div class="img-item">
                        <img src="data:image/jpeg;base64,{foto.get('b64')}" style="width: 100%; height: auto; border-radius: 6px; object-fit: cover;">
                        <div style="font-size: 11px; margin-top: 5px; color: #64748B;">{foto.get('pie', 'Anexo')}</div>
                    </div>
                    """
                html += "</div>"
            html += "</div>"        
    html += "</div></body></html>"
    return html


def obtener_html_clase_unica(materia_activa, fecha_actual, tema_actual, bloques_actuales, imagenes_clase):
    """Generar HTML de una sola sección de área de estudio"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>SƨR {fecha_actual} ~  {tema_actual}</title>
        <style>
            body {{ font-family: 'Arial', sans-serif; padding: 40px; color: #0F172A; line-height: 1.6; }}
            .header {{ border-bottom: 3px solid #1E3A8A; padding-bottom: 15px; margin-bottom: 30px; }}
            .header h1 {{ color: #1E3A8A; margin: 0 0 10px 0; font-size: 26px; }}
            .header h3 {{ color: #475569; margin: 0; font-size: 15px; font-weight: normal; }}
            .bloque {{ border-left: 4px solid #1E3A8A; padding-left: 20px; margin-bottom: 25px; page-break-inside: avoid; }}
            .bloque h4 {{ color: #1E3A8A; margin: 0 0 5px 0; font-size: 15px; text-transform: uppercase; }}
            .texto {{ font-size: 14px; color: #0F172A; margin: 0 0 8px 0; }}
            .obs {{ font-size: 13px; color: #475569; font-style: italic; margin: 0 0 8px 0; background-color: #F8FAFC; padding: 8px; border-radius: 4px; }}
            .ia-box {{ font-size: 13px; color: #2E4A3F; margin-top: 10px; background-color: rgba(135, 169, 107, 0.08); padding: 12px 15px; border-radius: 6px; border-left: 4px solid #87A96B; }}
            /* Modificación AUXS: Forzar salto de página estricto para separar anexos */
            .seccion-anexos {{ page-break-before: always !important; margin-top: 50px; border-top: 3px double #1E3A8A; padding-top: 30px; }}
            .grid-print-fotos {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 25px; }}
            .print-foto-item {{ border: 1px solid #CBD5E1; padding: 12px; border-radius: 8px; text-align: center; page-break-inside: avoid; background: #FFF; }}
            .print-foto-item img {{ max-width: 100%; max-height: 280px; object-fit: contain; border-radius: 4px; }}
            @media print {{ body {{ padding: 20px; }} .btn-print {{ display: none; }} }}
            .btn-print {{ background-color: #1E3A8A; color: white; border: none; padding: 12px 25px; font-weight: bold; border-radius: 8px; cursor: pointer; font-size: 15px; margin-bottom: 20px; width: 100%; }}
        </style>
    </head>
    <body>
        <button class="btn-print" onclick="window.print()">🖨️ Imprimible de esta sección - PDF</button>
        <div class="header">
            <h1>📚 ÁREA: {materia_activa}</h1>
            <h3>📅 {tema_actual}</h3>
        </div>
    """
    # Bucle operativo del Botón 1 (Con soporte para sugerencias de IA)
    for idx, blq in enumerate(bloques_actuales):
        html += f"""
        <div class="bloque">
            <h4>📌 PÁRRAFO {idx+1:02d}</h4>
            <p class="texto"><strong>Contenido:</strong> {blq.get('contenido', '')}</p>
            <p class="obs"><strong>Observaciones:</strong> {blq.get('observacion', '')}</p>
        """
        if blq.get("ia_sugerencias"):
            ia_formateada = blq["ia_sugerencias"].replace("\n", "<br>")
            html += f'<div class="ia-box"><strong>🧠 Recursos de Análisis SƨR:</strong><br>{ia_formateada}</div>'
        html += "</div>"
    
    if imagenes_clase:
        html += "<div class='seccion-anexos'><h2>🎞️ GALERÍA DE ANEXOS VISUALES</h2><div class='grid-print-fotos'>"
        for foto_obj in imagenes_clase:
            html += f"""
            <div class='print-foto-item'>
                <img src='data:image/jpeg;base64,{foto_obj["b64"]}'>
                <div style='font-size: 11px; color: #64748B; margin-top: 5px;'>{foto_obj.get("fecha", "")} | {foto_obj.get("hora", "")}</div>
                <div style='font-size: 12px; font-weight: bold;'>{foto_obj["pie"]}</div>
            </div>
            """
        html += "</div></div>"
    html += "</body></html>"
    return html


def obtener_html_cuaderno_completo(materia_activa, periodo_activo, temas_data):
    """Generar HTML de un área especifica con su respectivo indice de imágenes."""
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>SƨR - 🗂️ Área - {materia_activa.upper()}({periodo_activo})</title>
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
            .ia-box {{ font-size: 13px; color: #2E4A3F; margin-top: 10px; background-color: rgba(135, 169, 107, 0.08); padding: 12px 15px; border-radius: 6px; border-left: 4px solid #87A96B; }}
            
            /* SOLUCIÓN AL BUG: Estilos de la galería global agregados */
            .seccion-anexos-global {{ page-break-before: always !important; margin-top: 50px; border-top: 3px double #1E3A8A; padding-top: 30px; }}
            .grid-print-fotos {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 25px; margin-top: 20px; }}
            .print-foto-item {{ border: 1px solid #CBD5E1; padding: 12px; border-radius: 8px; text-align: center; page-break-inside: avoid; background: #FFF; }}
            .print-foto-item img {{ max-width: 100%; max-height: 280px; object-fit: contain; border-radius: 4px; }}
            
            @media print {{ body {{ padding: 20px; }} .btn-print {{ display: none; }} .clase-seccion:first-of-type {{ page-break-before: avoid; }} }}
            .btn-print {{ background-color: #059669; color: white; border: none; padding: 12px 25px; font-weight: bold; border-radius: 8px; cursor: pointer; font-size: 15px; margin-bottom: 20px; width: 100%; }}
        </style>
    </head>
    <body>
        <button class="btn-print" onclick="window.print()">🖨️ Imprimible de todas las clases del Área: {materia_activa.upper()} - PDF</button>
        <div class="main-title">
            <h1>🗂️ LIBRETA DE ÁREA</h1>
            <h2>{materia_activa.upper()}</h2>
            <p>Ecosistema de Aprendizaje Automatizado SƨR</p>
        </div>
    """
    todas_las_imagenes = []

    for t_nombre, t_data in temas_data.items():
        html += f'<div class="clase-seccion"><div class="clase-header"><h2>📅 {t_nombre}</h2></div>'

        for idx, blq in enumerate(t_data.get("bloques", [])):
            html += f"""
            <div class="bloque">
                <h4>📌 PÁRRAFO {idx+1:02d}</h4>
                <p class="texto"><strong>Contenido:</strong> {blq.get('contenido', '')}</p>
                <p class="obs"><strong>Observaciones:</strong> {blq.get('observacion', '')}</p>
            """
            if blq.get("ia_sugerencias"):
                ia_formateada = blq["ia_sugerencias"].replace("\n", "<br>")
                html += f'<div class="ia-box"><strong>🧠 Recursos de Análisis SƨR:</strong><br>{ia_formateada}</div>'
            html += "</div>"
        html += "</div>" # Corrección: Cierre de contenedor por clase
        
        if t_data.get("imagenes"):
            for foto in t_data["imagenes"]:
                todas_las_imagenes.append({"clase": t_nombre, "foto": foto})

    if todas_las_imagenes:
        html += "<div class='seccion-anexos-global'><h1>🎞️ GALERÍA DE ANEXOS VISUALES</h1><div class='grid-print-fotos'>"
        for item in todas_las_imagenes:
            html += f"""
            <div class='print-foto-item'>
                <img src='data:image/jpeg;base64,{item["foto"]["b64"]}'>
                <div style='font-size: 11px; color: #64748B; margin-top: 5px;'>📑 {item["clase"]} | 🗓️ {item["foto"].get("fecha","")}</div>
                <div style='font-size: 12px; font-weight: bold;'>📝 Nota: {item["foto"].get("pie", "")}</div>
            </div>
            """
        html += "</div></div>"
    html += "</body></html>"
    return html
