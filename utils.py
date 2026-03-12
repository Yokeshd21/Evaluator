import base64
import streamlit as st
import PyPDF2
import docx
import pandas as pd
import io
import re
from fpdf import FPDF

def load_css(file_name):
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Failed to load CSS: {e}")

def extract_text(file):
    """Extracts text from PDF, DOCX, or TXT files."""
    if file is None:
        return ""
    
    file_type = file.name.split('.')[-1].lower()
    text = ""
    
    try:
        if file_type == 'txt':
            text = file.getvalue().decode('utf-8')
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif file_type == 'docx':
            doc = docx.Document(file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            st.error(f"Unsupported file type: {file_type}")
    except Exception as e:
        st.error(f"Error reading file {file.name}: {e}")
        
    return text

def calculate_performance(json_data):
    """
    Calculates the performance score and bands based on JSON AI output with 0-10 ratings.
    """
    if "Evaluation" not in json_data:
         return 0, "Error", "High", "High", ""

    evaluations = json_data["Evaluation"]
    if not evaluations:
        return 0, "No Data", "N/A", "N/A", ""
    
    def extract_num(val, default=0):
        try:
            if isinstance(val, (int, float)): return float(val)
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val))
            return float(nums[0]) if nums else float(default)
        except:
            return float(default)

    total_weighted_score = 0
    count = len(evaluations)

    for item in evaluations:
        rating = extract_num(item.get("Rating"), 0)
        evidence = extract_num(item.get("Evidence Score"), 0)
        risk_level = extract_num(item.get("Risk Level"), 10) # 10 is max risk
        
        # item_score (0-10 scale): 50% Rating, 30% Evidence, 20% Risk (inverted)
        item_score = (rating * 0.5) + (evidence * 0.3) + ((10 - risk_level) * 0.2)
        total_weighted_score += item_score
        
    score = (total_weighted_score / count) * 10.0 if count > 0 else 0.0
    score = round(min(max(score, 0), 100), 1)

    # Secondary risk assessment for the band label
    total_risk = sum(extract_num(i.get("Risk Level"), 5) for i in evaluations)
    avg_risk_val = total_risk / count if count > 0 else 5
    
    if score >= 90:
        band = "Operationally Excellent"
        badge_class = "badge-excellent"
        risk = "Low"
        supervision = "Minimal"
    elif score >= 75:
        band = "Operationally Strong"
        badge_class = "badge-strong"
        risk = "Low-Medium"
        supervision = "Standard"
    elif score >= 50:
        band = "Operationally Moderate"
        badge_class = "badge-moderate"
        risk = "Medium-High"
        supervision = "Close"
    else:
        band = "Operational Risk"
        badge_class = "badge-risk"
        risk = "Critical"
        supervision = "Direct"

    badge_html = f'<div class="badge {badge_class}">{band}</div>'
    
    return score, band, risk, supervision, badge_html

def create_excel_download(df, json_data=None, human_feedback=""):
    """Converts evaluation results, executive summary, and feedback to a multi-sheet Excel file."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: Audit Report (The Matrix)
        df.to_excel(writer, index=False, sheet_name='Audit Report')
        workbook = writer.book
        worksheet = writer.sheets['Audit Report']
        
        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top',
            'fg_color': '#00122e', 'font_color': 'white', 'border': 1
        })
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 20)
            
        # Sheet 2: Executive Summary
        if json_data and "Executive Summary" in json_data:
            summary_data = []
            for k, v in json_data["Executive Summary"].items():
                summary_data.append({"Section": k, "Content": str(v)})
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, index=False, sheet_name='Executive Summary')
            
            summary_ws = writer.sheets['Executive Summary']
            for col_num, value in enumerate(summary_df.columns.values):
                summary_ws.write(0, col_num, value, header_format)
                summary_ws.set_column(col_num, col_num, 40)

        # Sheet 3: Human Feedback
        if human_feedback:
            fb_df = pd.DataFrame([{"Human Feedback Provided": human_feedback}])
            fb_df.to_excel(writer, index=False, sheet_name='Human Feedback')
            fb_ws = writer.sheets['Human Feedback']
            fb_ws.set_column(0, 0, 80)
            fb_ws.write(0, 0, "Human Feedback Provided", header_format)

    return output.getvalue()

def apply_color_coding(val):
    """Pandas styler wrapper to color code cells based on 0-10 scale or categorical flags"""
    try:
        # Try numeric first
        num_val = float(val)
        if num_val >= 8:
            color = '#10b981'
            bg = '#ecfdf5'
        elif num_val >= 4:
            color = '#d97706'
            bg = '#fffbeb'
        else:
            color = '#dc2626'
            bg = '#fef2f2'
        return f'color: {color}; font-weight: 600; background-color: {bg};'
    except:
        val_str = str(val).strip().upper()
        if val_str in ["YES", "LOW", "STRONG"]:
            color = '#10b981'
            bg = '#ecfdf5'
        elif val_str in ["NO", "HIGH", "NONE", "WEAK", "CRITICAL"]:
            color = '#dc2626'
            bg = '#fef2f2'
        elif val_str in ["MEDIUM", "MODERATE"]:
            color = '#d97706'
            bg = '#fffbeb'
        else:
            color = '#111827'
            bg = '#ffffff'
        return f'color: {color}; font-weight: 600; background-color: {bg};'

def create_pdf_download(json_data, human_feedback=""):
    """Creates a PDF report from the evaluation JSON data including human feedback."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Operational Audit Report", ln=True, align='C')
    pdf.ln(10)
    
    if "Executive Summary" in json_data:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Executive Summary", ln=True)
        pdf.set_font("Arial", size=11)
        for k, v in json_data["Executive Summary"].items():
            # Handle unicode gracefully
            text = f"{k}: {v}".encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 8, txt=text)
        pdf.ln(5)
        
    if "Evaluation" in json_data:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Audit Details", ln=True)
        pdf.set_font("Arial", size=10)
        for item in json_data["Evaluation"]:
            crit = str(item.get("Criterion", ""))
            rating = str(item.get("Rating", "0"))
            pdf.set_font("Arial", 'B', 10)
            tit_text = f"Criterion: {crit} - Rating: {rating}/10".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 8, txt=tit_text, ln=True)
            pdf.set_font("Arial", size=10)
            for k, v in item.items():
                if k not in ["Criterion", "Rating"]:
                    t_text = f"  {k}: {v}".encode('latin-1', 'replace').decode('latin-1')
                    pdf.multi_cell(0, 6, txt=t_text)
            pdf.ln(3)

    if human_feedback:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Human Feedback & Refinements", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, txt=human_feedback.encode('latin-1', 'replace').decode('latin-1'))

    return pdf.output(dest='S').encode('latin-1')
