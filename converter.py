import os
import io
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import docx
import pandas as pd
import tempfile

def convert_to_pdf(source_path, file_extension):
    """
    Convierte archivos (docx, xlsx, png, jpg) a un PDF temporal.
    Retorna la ruta del PDF generado.
    """
    file_extension = file_extension.lower().replace('.', '')
    
    if file_extension in ['pdf']:
        return source_path # No hacer nada si ya es PDF
        
    output_pdf_path = source_path + ".converted.pdf"
    
    try:
        if file_extension in ['png', 'jpg', 'jpeg']:
            _image_to_pdf(source_path, output_pdf_path)
            
        elif file_extension in ['docx', 'doc']:
            _docx_to_pdf(source_path, output_pdf_path)
            
        elif file_extension in ['xlsx', 'xls']:
            _excel_to_pdf(source_path, output_pdf_path)
            
        else:
            return None # Formato no soportado
            
        return output_pdf_path
        
    except Exception as e:
        print(f"Error en conversión: {e}")
        return None

def _image_to_pdf(image_path, output_path):
    """Convierte una imagen en una página PDF."""
    img = Image.open(image_path)
    c = canvas.Canvas(output_path)
    
    # Ajustar tamaño de página al de la imagen o usar carta
    img_width, img_height = img.size
    c.setPageSize((img_width, img_height))
    
    c.drawImage(image_path, 0, 0, width=img_width, height=img_height)
    c.save()

def _docx_to_pdf(docx_path, output_path):
    """Extrae texto de Word y crea un PDF simple."""
    doc = docx.Document(docx_path)
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    text_object = c.beginText(40, height - 40)
    text_object.setFont("Helvetica", 10)
    
    for para in doc.paragraphs:
        # Manejo básico de saltos de página si el texto es muy largo
        if text_object.getY() < 40:
            c.drawText(text_object)
            c.showPage()
            text_object = c.beginText(40, height - 40)
            text_object.setFont("Helvetica", 10)
            
        # Limpiar texto de caracteres no compatibles
        clean_text = para.text.encode('latin-1', 'replace').decode('latin-1')
        text_object.textLine(clean_text)
        
    c.drawText(text_object)
    c.save()

def _excel_to_pdf(excel_path, output_path):
    """Convierte hojas de Excel a PDF (texto plano de tablas)."""
    dfs = pd.read_excel(excel_path, sheet_name=None) # Leer todas las hojas
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    text_object = c.beginText(40, height - 40)
    text_object.setFont("Courier", 8) # Fuente monoespaciada para tablas
    
    for sheet_name, df in dfs.items():
        text_object.textLine(f"--- Hoja: {sheet_name} ---")
        
        # Convertir dataframe a string
        table_str = df.to_string()
        
        for line in table_str.split('\n'):
            if text_object.getY() < 40:
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(40, height - 40)
                text_object.setFont("Courier", 8)
            
            clean_line = line.encode('latin-1', 'replace').decode('latin-1')
            text_object.textLine(clean_line)
            
        text_object.textLine("") # Espacio entre hojas
        
    c.drawText(text_object)
    c.save()
