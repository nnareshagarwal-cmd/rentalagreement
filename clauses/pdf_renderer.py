"""
clauses/pdf_renderer.py — PDF Generation Engine for AgreementAI
===============================================================
Generates high-fidelity PDF documents for rental and leave-license agreements.
Uses Microsoft Word COM (win32com) for 100% exact DOCX layout fidelity,
with xhtml2pdf fallback when Word COM is not active.
"""

import os
import logging
import tempfile

logger = logging.getLogger("AgreementAI_PDF")

def generate_pdf(data, output_path=None):
    """
    Generate PDF for agreement data and save to output_path.
    """
    from .agreement_renderer import generate_docx

    if not output_path:
        raise ValueError("output_path is required for PDF generation")

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 1. Try win32com Word.Application PDF conversion (100% Word layout fidelity)
    tmp_docx_path = None
    try:
        tmp_fd, tmp_docx_path = tempfile.mkstemp(suffix='.docx')
        os.close(tmp_fd)

        generate_docx(data, output_path=tmp_docx_path)

        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        word = None
        doc = None
        try:
            word = win32com.client.Dispatch('Word.Application')
            word.Visible = False
            word.DisplayAlerts = 0  # wdAlertsNone - suppress any modal prompts
            doc = word.Documents.Open(os.path.abspath(tmp_docx_path), ReadOnly=True)
            doc.SaveAs(os.path.abspath(output_path), FileFormat=17)  # 17 = wdFormatPDF
        finally:
            if doc is not None:
                try:
                    doc.Close(SaveChanges=0)
                except Exception:
                    pass
            if word is not None:
                try:
                    word.Quit()
                except Exception:
                    pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception as e:
        logger.warning(f"win32com Word PDF conversion fallback: {e}")
    finally:
        if tmp_docx_path and os.path.exists(tmp_docx_path):
            try:
                os.remove(tmp_docx_path)
            except OSError:
                pass

    # 2. Fallback: xhtml2pdf HTML conversion
    try:
        from .html_renderer import generate_preview_html
        from xhtml2pdf import pisa

        html_content = generate_preview_html(data)
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4;
                    margin: 15mm 20mm 20mm 20mm;
                }}
                body {{
                    font-family: 'Times-Roman', 'Times New Roman', serif;
                    font-size: 11pt;
                    line-height: 1.5;
                    color: #000000;
                }}
                h2 {{
                    text-align: center;
                    font-size: 14pt;
                    text-decoration: underline;
                    margin-bottom: 20px;
                }}
                .clause-block {{
                    margin-bottom: 12px;
                    text-align: justify;
                }}
                .clause-text {{
                    margin: 0;
                }}
                b, strong {{
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        with open(output_path, 'wb') as pdf_file:
            pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file)
            if pisa_status.err:
                logger.warning(f"xhtml2pdf reported warnings/errors: {pisa_status.err}")

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception as e:
        logger.error(f"xhtml2pdf fallback failed: {e}")
        raise RuntimeError(f"Could not generate PDF document: {e}") from e

    return output_path
