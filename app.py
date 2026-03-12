import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import re
import json
import sys
import os
import phoenix as px
from opentelemetry import trace
from datetime import datetime

# tracing.py will handle the tracing setup
tracer = trace.get_tracer(__name__)

st.set_page_config(
    page_title="Streamlit",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── SIDEBAR CONFIGURATION ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='text-align: center; font-weight: 400; font-size: 26px; margin-top: 10px; margin-bottom: 30px;'>Solutions Scope</h2>",
        unsafe_allow_html=True,
    )

    # Start Phoenix tracing and get URL (BEFORE other imports)
    from tracing import start_tracing
    phoenix_url = start_tracing()

    # Placeholders matching screenshot exactly
    sidebar_app = st.selectbox("Application", ["Select Application", "LLMatScale.ai"], key="sb_app")
    st.selectbox("Application", ["Select LLM model", "Groq"], key="sb_model")
    st.selectbox("Specifications 3", ["Streamlit Cloud Used"], key="sb_spec")

    # Adding spacing
    st.markdown("<div style='height: 30px;justify-content: center;'></div>", unsafe_allow_html=True)
    clear_btn = st.button("Clear/Reset", key="clear_btn")

    st.markdown(
        """
        <div style='text-align: center; margin-top: 4rem;'>
            <p style='font-size: 16px; font-weight: 600; margin-bottom: 20px;'>Build & Deployed on</p>
            <div style='display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-top: 15px;'>
                <div style='width: 30px; height: 70px; border-radius: 8px; display: flex; align-items: center; justify-content: center;'>
                    <img src='https://i.im.ge/2026/03/04/eYH8HT.image.png' width='30' style='object-fit: contain;'>
                </div>
                <div style='width: 30px; height: 70px; border-radius: 8px; display: flex; align-items: center; justify-content: center;'>
                    <img src='https://i.im.ge/2026/03/04/eYHgy0.oie-png.png' width='30' style='object-fit: contain;'>
                </div>
                <div style='width: 30px; height: 70px; border-radius: 8px; display: flex; align-items: center; justify-content: center;'>
                    <img src='https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/1280px-Amazon_Web_Services_Logo.svg.png' width='30' style='object-fit: contain;'>
                </div>
                <div style='width: 30px; height: 70px; border-radius: 8px; display: flex; align-items: center; justify-content: center;'>
                    <img src='https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Microsoft_Azure.svg/1200px-Microsoft_Azure.svg.png' width='30' style='object-fit: contain;'>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if clear_btn:
        st.session_state.history = []
        st.session_state.current_evaluation = None
        st.rerun()

from utils import (
    load_css,
    extract_text,
    calculate_performance,
    create_excel_download,
    create_pdf_download,
    apply_color_coding,
)
from ai_wrapper import get_groq_client, evaluate_performance, re_evaluate_with_trace, chat_with_data
from evaluator import evaluate_response

def robust_json_repair(text):
    """
    High-resilience JSON extraction and repair.
    Handles: conversational junk, unescaped newlines, trailing commas, and partial objects.
    """
    import json as json_lib
    import re
    
    # 1. Targeted Extraction
    match = re.search(r'<json>\s*(.*?)\s*</json>', text, re.DOTALL | re.IGNORECASE)
    candidate = match.group(1).strip() if match else ""
    
    if not candidate:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            candidate = text[start:end+1]
    
    if not candidate:
        return None
        
    # 2. Clean-up phase
    cleaned = candidate
    
    # Remove trailing commas before closing braces/brackets
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    
    # Fix common AI "internal quote" issue: "Key": "Value "quoted" value"
    lines = cleaned.splitlines()
    for i in range(len(lines)):
        line = lines[i].strip()
        if line and not re.search(r'^".*?":\s*', line):
            pass

    try:
        return json_lib.loads(cleaned)
    except json_lib.JSONDecodeError:
        try:
            # Try to escape any remaining raw newlines inside the string
            escaped = re.sub(r'\n(?![ \t]*[{}])', r'\\n', cleaned)
            return json_lib.loads(escaped)
        except:
            # Attempt auto-closing
            test_str = cleaned
            for _ in range(5):
                test_str += "}"
                try:
                    return json_lib.loads(test_str)
                except:
                    continue
            return None

def generate_fallback_summary(evaluation_list):
    """Auto-generates an Executive Summary if the AI failed to provide one."""
    if not evaluation_list:
        return {}
    
    # Calculate average rating
    ratings = []
    for item in evaluation_list:
        try:
            val = re.findall(r"\d+\.?\d*", str(item.get("Rating", 0)))
            if val: ratings.append(float(val[0]))
        except: pass
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    # Identify low scores (< 7)
    low_scores = []
    for i in evaluation_list:
        try:
            val = re.findall(r"\d+\.?\d*", str(i.get("Rating", 0)))
            if val and float(val[0]) < 7:
                low_scores.append(i)
        except: pass
    
    summary = {
        "Overall Performance": f"The audit indicates an average operational rating of {avg_rating:.1f}/10.",
        "Key Improvement Findings": " • " + " \n • ".join([f"{i.get('Criterion')}: {i.get('How To Improve')}" for i in low_scores]) if low_scores else "Performance is consistently high across all criteria. No critical improvement areas identified.",
        "Note": "This summary was auto-generated from the Audit Matrix to ensure transparency."
    }
    return summary

def render_review_box(content):
    """Parses and renders the 'Review of Changes' box as a clean, aligned list."""
    if not content:
        return
    
    # Split by common list markers and re-format
    # This handles both 1. 2. and • items
    items = re.split(r'(\d+\.|\u2022|\*|-)', content)
    
    html_list = ""
    current_marker = ""
    
    for part in items:
        part = part.strip()
        if not part: continue
        
        if re.match(r'^(\d+\.|\u2022|\*|-)$', part):
            current_marker = part
        else:
            if current_marker:
                html_list += f"<li><span class='marker'>{current_marker}</span> <span class='text'>{part}</span></li>"
            else:
                # If no marker yet, just add as a plain paragraph or the first item
                html_list += f"<p>{part}</p>"
    
    st.markdown(f"""
    <div class="review-box">
        <div class="review-title">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
            Review of Changes
        </div>
        <ul class="review-list">
            {html_list}
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Custom CSS matching the target exactly
st.markdown(
    """
<style>
    /* Global Font */
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700;800&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Source Sans Pro', sans-serif;
    }

    /* Hide standard header */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Main Background - pure white 'Paper' aesthetic */
    .stApp {
        background: #ffffff !important;
        color: #1e293b !important; /* Deep Charcoal */
    }

    /* Center container restriction to match visual flow */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 5rem !important;
        max-width: 960px !important;
    }

    /* Sidebar Background & Text colors */
    [data-testid="stSidebar"] {
        background-color: #3b82f6 !important; /* Material Blue */
        border-right: none !important;
    }

    /* Sidebar Text overriding */
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* Hide specific selectbox labels completely */
    .stSelectbox label {
        display: none !important;
    }

    /* Sidebar Selectbox Customization */
    [data-testid="stSidebar"] div[data-baseweb="select"] {
        cursor: pointer;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #f4f6f8 !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 4px;
        min-height: 48px;
    }
    /* Set selectbox text to dark gray inside the sidebar select container */
    [data-testid="stSidebar"] div[data-baseweb="select"] span {
        color: #333333 !important;
        font-size: 15px !important;
        font-weight: 400 !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] svg {
        fill: #333 !important;
        color: #333 !important;
    }
    /* Fix the specific text node Streamlit generates so it isn't white */
    .stSelectbox div[data-baseweb="select"] * {
        color: #333333 !important;
    }

    /* Global Override for sidebar text exceptions */
    [data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #333333 !important;
    }

    /* Sidebar Green Clear/Reset Button */
    [data-testid="stSidebar"] .stButton {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        margin: 0 auto !important;
    }

    [data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(135deg, #34A853 0%, #2c9347 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 10px 32px !important;
        box-shadow: 0 4px 12px rgba(52, 168, 83, 0.3);
        transition: all 0.3s ease-in-out !important;
        font-size: 14px !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: linear-gradient(135deg, #2c9347 0%, #1a7a3a 100%) !important;
        transform: translateY(-3px) !important;
        box-shadow: 0 6px 16px rgba(52, 168, 83, 0.4) !important;
    }
    [data-testid="stSidebar"] .stButton > button:active {
        transform: translateY(-1px) !important;
    }

    /* Main Area Selectbox customization */
    div[data-baseweb="select"] > div {
        background-color: #f9fafb !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        min-height: 48px;
    }
    div[data-baseweb="select"] span {
        color: #111827 !important;
        font-size: 15px !important;
    }
    div[data-baseweb="select"] svg {
        fill: #000 !important;
    }

    /* Text Area & Input - Mild & Clean */
    .stTextArea textarea, .stTextInput input {
        background-color: #f9fafb !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
    }
    
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }

    /* Horizontal rule styling */
    hr {
        border: 0;
        border-top: 1px solid #e2e8f0;
        margin: 1.5rem 0 3.5rem 0 !important;
    }

    /* ═══════════════════════════════════════════════
       PREMIUM FILE UPLOADER — Animated Drop Zone
    ═══════════════════════════════════════════════ */

    /* Keyframes */
    @keyframes dashedSpin {
        0%   { stroke-dashoffset: 0; }
        100% { stroke-dashoffset: 60; }
    }
    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.0),  0 4px 24px rgba(59,130,246,0.06); }
        50%       { box-shadow: 0 0 0 6px rgba(59,130,246,0.08), 0 8px 32px rgba(59,130,246,0.16); }
    }
    @keyframes floatIcon {
        0%, 100% { transform: translateY(0px) scale(1);    }
        50%       { transform: translateY(-8px) scale(1.05); }
    }
    @keyframes browseShine {
        0%   { left: -100%; }
        55%  { left: 220%; }
        100% { left: 220%; }
    }
    @keyframes fadeSlideIn {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* Drop Zone Container */
    [data-testid="stFileUploadDropzone"] {
        position: relative !important;
        background: #f9fafb !important; /* Mild light grey */
        border: 2px dashed #c8d3e0 !important;
        border-radius: 14px !important;
        padding: 3rem 2.5rem !important;
        text-align: center !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
    }

    /* Subtle radial overlay (decorative, very faint) */
    [data-testid="stFileUploadDropzone"]::before {
        content: '' !important;
        position: absolute !important;
        inset: 0 !important;
        background: none !important;
        pointer-events: none !important;
    }

    /* Hover State */
    [data-testid="stFileUploadDropzone"]:hover {
        background: #f7f9fc !important;
        border-color: #3b82f6 !important;
        border-style: solid !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(59,130,246,0.12) !important;
    }

    /* Active / Drag-over */
    [data-testid="stFileUploadDropzone"]:active,
    [data-testid="stFileUploadDropzone"][data-dragging="true"] {
        background: #eef4ff !important;
        border-color: #2563eb !important;
        box-shadow: 0 8px 24px rgba(37,99,235,0.15) !important;
    }

    /* Upload SVG Icon */
    [data-testid="stFileUploadDropzone"] svg {
        fill: #4b5563 !important;
        color: #4b5563 !important;
        filter: none !important;
    }

    /* Drag & drop main label — milder charcoal */
    [data-testid="stFileUploadDropzone"] p {
        color: #374151 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        font-family: 'Inter', sans-serif !important;
        letter-spacing: 0.1px !important;
        margin-top: 10px !important;
    }

    /* Hint text (file size limit etc.) — dark grey, readable */
    [data-testid="stFileUploadDropzone"] span:not(button span):not(button *) {
        color: #374151 !important;
        font-size: 12.5px !important;
        font-weight: 500 !important;
    }

    /* ── Browse Files Button ── */
    [data-testid="stFileUploadDropzone"] button {
        background: #3b82f6 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 28px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        font-family: 'Inter', sans-serif !important;
        letter-spacing: 0.3px !important;
        box-shadow: 0 2px 8px rgba(59,130,246,0.30) !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        margin-top: 10px !important;
    }

    /* Button text — force white at all times */
    [data-testid="stFileUploadDropzone"] button span,
    [data-testid="stFileUploadDropzone"] button * {
        color: #ffffff !important;
        font-weight: 600 !important;
    }

    /* Button hover */
    [data-testid="stFileUploadDropzone"] button:hover {
        background: #2563eb !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(59,130,246,0.40) !important;
    }

    /* Button press */
    [data-testid="stFileUploadDropzone"] button:active {
        transform: translateY(0px) !important;
        box-shadow: 0 2px 6px rgba(59,130,246,0.25) !important;
    }

    /* Uploaded file info chips */
    [data-testid="stFileUploaderFileName"],
    [data-testid="stFileUploaderFileSize"],
    .stFileUploaderFileData,
    [data-testid="stUploadedFileName"],
    .uploadedFileName,
    .uploadedFileSize {
        color: #111827 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }


    /* Loading Spinner Text Color */
    .stSpinner > div > div {
        color: #111827 !important; /* Black/Dark Gray text for visibility on white background */
        font-weight: 600 !important;
    }

    /* Typography Overrides */
    .title-text {
        text-align: center;
        font-size: 34px;
        font-weight: 800;
        color: #000000;
        margin-bottom: 2px;
        letter-spacing: -0.5px;
    }

    .section-left-title {
        font-size: 28px;
        font-weight: 800;
        color: #000000;
        line-height: 1.3;
        margin-top: 15px;
    }

    .mouse-icon-container {
        text-align: left;
        padding-left: 20px;
        margin-top: 10px;
    }

    /* Upload labels styling hack -> overriding streamlit label */
    .stFileUploader label {
        display: block !important;
        color: #333333 !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        margin-bottom: 5px !important;
    }

    /* Reusing some logic styles */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 22px 18px;
        text-align: center;
        height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        border-color: #3b82f6;
    }
    .metric-card .label { font-size: 0.72rem; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 8px; }
    .metric-card .value { font-size: 2.2rem; font-weight: 900; line-height: 1; color: #111827; }
    .metric-card .value.good { color: #10b981; }
    .metric-card .value.warn { color: #f59e0b; }
    .metric-card .value.bad { color: #ef4444; }

    /* Result section headers */
    .sec-head {
        font-size: 1.25rem;
        font-weight: 800;
        color: #111827;
        margin: 2.5rem 0 1rem 0;
        border-bottom: 2px solid #e5e7eb;
        padding-bottom: 0.5rem;
    }

    /* Logic Table headers fix */
    div[data-testid="stDataFrame"] {
        background: #ffffff !important;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.08);
        overflow: hidden;
        border: 1px solid #d1d5db !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Prevent empty space in table container */
    [data-testid="stDataFrame"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Enhanced Table Styling */
    [data-testid="stDataFrame"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        background: #ffffff !important;
        border-spacing: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    [data-testid="stDataFrame"] thead {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    }

    [data-testid="stDataFrame"] th {
        background: inherit !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        padding: 14px 12px !important;
        border: 1px solid #1d4ed8 !important;
        text-align: left !important;
        font-size: 13px !important;
        letter-spacing: 0.3px !important;
    }

    [data-testid="stDataFrame"] td {
        padding: 12px !important;
        border: 1px solid #d1d5db !important;
        color: #111827 !important;
        background: #ffffff !important;
        font-size: 13px !important;
    }

    [data-testid="stDataFrame"] tbody {
        margin: 0 !important;
        padding: 0 !important;
    }

    [data-testid="stDataFrame"] tbody tr {
        background: #ffffff !important;
        transition: background-color 0.2s ease;
        border-bottom: 1px solid #d1d5db !important;
    }

    [data-testid="stDataFrame"] tbody tr:hover {
        background: #f3f4f6 !important;
    }

    [data-testid="stDataFrame"] tbody tr:nth-child(odd) {
        background: #fafafa !important;
    }

    [data-testid="stDataFrame"] tbody tr:nth-child(odd):hover {
        background: #f0f0f0 !important;
    }

    /* Remove scrollbar padding */
    [data-testid="stDataFrame"] .stTable {
        padding: 0 !important;
    }

    /* Clean, Animated Execute Button */
    @keyframes subtlePulse {
        0% { box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2); }
        50% { box-shadow: 0 4px 25px rgba(59, 130, 246, 0.4); }
        100% { box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2); }
    }

    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important;
        font-family: 'Inter', 'Roboto', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 16px 32px !important;
        font-size: 16px !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        animation: subtlePulse 3s infinite;
        position: relative;
        overflow: hidden;
    }

    .stButton > button::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 50%;
        height: 100%;
        background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0) 100%);
        transform: skewX(-25deg);
        transition: all 0.7s ease;
    }

    .stButton > button:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 25px rgba(59, 130, 246, 0.5) !important;
    }

    .stButton > button:hover::after {
        left: 200%;
    }

    .stButton > button:active {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
    }

    /* ── Download Buttons ── */
    @keyframes downloadShine {
        0%   { left: -100%; }
        60%  { left: 200%; }
        100% { left: 200%; }
    }

    [data-testid="stDownloadButton"] > button {
        position: relative !important;
        overflow: hidden !important;
        color: #ffffff !important;
        font-family: 'Inter', 'Source Sans Pro', sans-serif !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        letter-spacing: 0.4px !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 28px !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: transform 0.25s ease, box-shadow 0.25s ease !important;
    }

    /* Excel button — green gradient */
    [data-testid="stDownloadButton"]:nth-of-type(1) > button {
        background: linear-gradient(135deg, #059669 0%, #10b981 50%, #34d399 100%) !important;
        box-shadow: 0 4px 18px rgba(16, 185, 129, 0.35) !important;
    }

    /* PDF button — indigo/purple gradient */
    [data-testid="stDownloadButton"]:nth-of-type(2) > button {
        background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #8b5cf6 100%) !important;
        box-shadow: 0 4px 18px rgba(109, 40, 217, 0.35) !important;
    }

    /* Shine sweep on both */
    [data-testid="stDownloadButton"] > button::after {
        content: '';
        position: absolute !important;
        top: 0 !important;
        left: -100% !important;
        width: 55% !important;
        height: 100% !important;
        background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.28) 50%, rgba(255,255,255,0) 100%) !important;
        transform: skewX(-20deg) !important;
        animation: downloadShine 2.8s infinite !important;
    }

    /* Hover lift + stronger glow */
    [data-testid="stDownloadButton"]:nth-of-type(1) > button:hover {
        transform: translateY(-4px) scale(1.02) !important;
        box-shadow: 0 10px 28px rgba(16, 185, 129, 0.55) !important;
    }
    [data-testid="stDownloadButton"]:nth-of-type(2) > button:hover {
        transform: translateY(-4px) scale(1.02) !important;
        box-shadow: 0 10px 28px rgba(109, 40, 217, 0.55) !important;
    }

    /* Active press */
    [data-testid="stDownloadButton"] > button:active {
        transform: translateY(-1px) scale(0.99) !important;
    }
    /* Review of Changes Box */
    .review-box {
        background: #f0f7ff;
        border-left: 4px solid #3b82f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
    }
    .review-title {
        color: #1d4ed8;
        font-weight: 800;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
    }
    .review-title svg {
        width: 18px;
        height: 18px;
        margin-right: 8px;
        fill: #3b82f6;
    }
    .review-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    .review-list li {
        display: flex;
        margin-bottom: 10px;
        font-size: 0.95rem;
        color: #334155;
        line-height: 1.5;
    }
    .review-list li .marker {
        color: #3b82f6;
        font-weight: 700;
        margin-right: 12px;
        flex-shrink: 0;
        min-width: 20px;
    }
    .review-list li .text {
        flex-grow: 1;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ─── MAIN CONTENT ─────────────────────────────────────────────────────────────

# ─── MAIN CONTENT ─────────────────────────────────────────────────────────────

# --- Top Logo (Circular Hero Logo) ---
st.markdown(
    """
<div style="display: flex; justify-content: center; align-items: center; margin-bottom: 5px; margin-top: -50px;">
    <img src="https://i.im.ge/2026/03/04/eYH8HT.image.png" width="180">
</div>
""",
    unsafe_allow_html=True,
)

# --- Main Title ---
st.markdown("<div class='title-text' style='margin-bottom: 25px;'>Agentic AI Learning Program – Foundational Learning</div>", unsafe_allow_html=True)
st.markdown("<hr style='margin-bottom: 30px;'>", unsafe_allow_html=True)

# --- Row 1: Select Application ---
c1, c2 = st.columns([1.0, 1.0])
with c1:
    st.markdown("<div class='section-left-title' style='margin-top: 0;'>Select Application</div>", unsafe_allow_html=True)
with c2:
    if sidebar_app == "Select Application":
        st.markdown("<div style='margin-top: 15px; font-size: 16px; color: #666; font-weight: 600;'>Please select the application in the left sidebar.</div>", unsafe_allow_html=True)
        selected_app = "None"
    else:
        selected_app = st.selectbox("app_selector_main", ["Select an application","Personal Narrative"], key="app_selector_main")

st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)

# --- Initialize File Variables ---
narrative_file = None
rubric_file = None
personal_narrative_file = None

# --- Conditional Upload Sections Based on Application ---
if selected_app == "Select an application" or selected_app == "None":
    # Show empty space when no application selected
    st.markdown("<div style='height: 300px;'></div>", unsafe_allow_html=True)

elif selected_app == "Personal Narrative":
    # --- Row 2: Upload Personal Narrative ---
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("<div class='section-left-title'>Upload Personal<br>Narrative (PDF)</div>", unsafe_allow_html=True)
    with c2:
        personal_narrative_file = st.file_uploader("Upload Personal Narrative", type=["pdf", "docx", "txt"], key="personal_narrative")

    st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)

    # --- Row 3: Upload Rubric ---
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("<div class='section-left-title'>Upload the<br>Rubric (PDF)</div>", unsafe_allow_html=True)
    with c2:
        rubric_file = st.file_uploader("Upload Rubric", type=["pdf", "docx", "txt"], key="personal_rubric")

    st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)

    # --- Row 4: Reference Answer (Gold Answer) ---
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("<div class='section-left-title'>Provide Reference<br>Answer (Gold)</div>", unsafe_allow_html=True)
    with c2:
        reference_answer = st.text_area("Reference Answer", height=150, key="reference_answer_input", help="The gold standard answer to compare against for semantic similarity.")

st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

# ─── APP LOGIC (EVALUATION EXECUTION) ─────────────────────────────────────────
analyze_btn = st.button("🚀 Execute Operational Audit", use_container_width=True)

if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_evaluation' not in st.session_state:
    st.session_state.current_evaluation = None
if 'editable_data' not in st.session_state:
    st.session_state.editable_data = None
if 'refinement_mode' not in st.session_state:
    st.session_state.refinement_mode = False
if 'edited_trace' not in st.session_state:
    st.session_state.edited_trace = ""
if 'edited_narrative' not in st.session_state:
    st.session_state.edited_narrative = ""
# Store rubric & narrative text for trace-guided re-evaluation
if 'rubric_text_stored' not in st.session_state:
    st.session_state.rubric_text_stored = ""
if 'narrative_text_stored' not in st.session_state:
    st.session_state.narrative_text_stored = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
# Original (unmodified) trace — used to detect if user actually changed it
if 'original_trace' not in st.session_state:
    st.session_state.original_trace = ""
if 'semantic_score' not in st.session_state:
    st.session_state.semantic_score = 0.0
if 'intent_score' not in st.session_state:
    st.session_state.intent_score = 0.0
if 'rubric_result' not in st.session_state:
    st.session_state.rubric_result = "N/A"
if 'last_response_raw' not in st.session_state:
    st.session_state.last_response_raw = ""
if 'edited_review' not in st.session_state:
    st.session_state.edited_review = ""
if 'improved_review' not in st.session_state:
    st.session_state.improved_review = ""

if analyze_btn:
    if selected_app == "Select an application" or selected_app == "None":
        st.error("⚠️ Please select an application from the dropdown first.")
    elif not rubric_file or (selected_app == "CUCP Re-Evaluations" and not narrative_file) or (selected_app == "Personal Narrative" and not personal_narrative_file):
        st.error("⚠️  Please upload both the Rubric and Narrative documents.")
    else:
        client = get_groq_client()
        if not client:
            st.error("🔑  Groq API Key missing. Set the `GROQ_API_KEY` environment variable.")
        else:
            with st.spinner("🤖  AI Auditor analysing operational data…"):
                with tracer.start_as_current_span("extract_rubric_text") as span:
                    span.set_attribute("description", "PDF parsing")
                    rubric_text = extract_text(rubric_file)

                if selected_app == "CUCP Re-Evaluations":
                    with tracer.start_as_current_span("extract_narrative_text") as span:
                        span.set_attribute("description", "Narrative extraction")
                        narrative_text = extract_text(narrative_file)
                else:  # Personal Narrative
                    with tracer.start_as_current_span("extract_narrative_text") as span:
                        span.set_attribute("description", "Narrative extraction")
                        narrative_text = extract_text(personal_narrative_file)

                # Store for trace-guided re-evaluation later
                st.session_state.rubric_text_stored  = rubric_text
                st.session_state.narrative_text_stored = narrative_text

                with tracer.start_as_current_span("groq_llm_evaluation") as span:
                    span.set_attribute("description", "LLM evaluation")
                    result_text = evaluate_performance(
                        client=client,
                        rubric_text=rubric_text,
                        narrative_text=narrative_text,
                        gold_reference_text=st.session_state.get("reference_answer_input", ""),
                        model="llama-3.1-8b-instant",
                        temperature=0.1,
                    )

                if result_text:
                    st.session_state.current_evaluation = result_text
                    
                    # Robust Parsing: Try to find tags even if there's extra text or poor formatting
                    # Robust Parsing: Try to find tags even if there's extra text or poor formatting
                    trace_match = re.search(r'<trace>(.*?)</trace>', result_text, re.DOTALL | re.IGNORECASE)
                    trace_text = trace_match.group(1).strip() if trace_match else "Processing thoughts..."
                    st.session_state.edited_trace  = trace_text
                    st.session_state.original_trace = trace_text
                    
                    st.session_state.editable_data = robust_json_repair(result_text)
                    if not st.session_state.editable_data:
                         # Critical Fallback: Try to extract as much of the JSON as possible if the whole object is broken
                         st.session_state.editable_data = {}
                         
                         eval_match = re.search(r'"Evaluation":\s*(\[.*?\])', result_text, re.DOTALL)
                         if eval_match:
                             try:
                                 st.session_state.editable_data["Evaluation"] = json.loads(eval_match.group(1))
                             except:
                                 pass
                                 
                         # Try multiple variations for Executive Summary
                         exec_match = re.search(r'"Executive\s*Summary":\s*(\{.*?\})', result_text, re.DOTALL | re.IGNORECASE)
                         if not exec_match:
                             exec_match = re.search(r'"Summary":\s*(\{.*?\})', result_text, re.DOTALL | re.IGNORECASE)
                             
                         if exec_match:
                             try:
                                 st.session_state.editable_data["Executive Summary"] = json.loads(exec_match.group(1))
                             except:
                                 pass
                         
                         if not st.session_state.editable_data:
                             st.session_state.editable_data = None

                    if not st.session_state.editable_data:
                         st.error("❌ High Sensitivity Parsing Error: The AI used illegal characters in the audit matrix. I am attempting an auto-fix, please click 'Refine' if the table is empty.")

                    main_text = re.sub(r'<trace>.*?</trace>', '', result_text, flags=re.DOTALL | re.IGNORECASE)
                    main_text = re.sub(r'<json>.*?</json>', '', main_text, flags=re.DOTALL | re.IGNORECASE).strip()
                    st.session_state.edited_narrative = main_text
                    st.session_state.last_response_raw = main_text
                    
                    # Initial evaluation has no "review" section
                    st.session_state.edited_review = ""

                    # Semantic Evaluation
                    score_sem, score_intent, rubric_status, fb_sem = evaluate_response(
                        user_prompt=narrative_text,
                        response=main_text,
                        reference=st.session_state.get("reference_answer_input", "")
                    )
                    st.session_state.semantic_score = score_sem
                    st.session_state.intent_score = score_intent
                    st.session_state.rubric_result = rubric_status

                    # Store in history
                    st.session_state.history.append(
                        {
                            "timestamp": time.time(),
                            "score": round(score_sem * 100, 1),
                            "data": result_text,
                        }
                    )

                    # Log to CSV
                    rec = {
                        "timestamp": datetime.now().isoformat(),
                        "prompt": narrative_text[:1000], # truncated for log
                        "response": main_text[:1000],
                        "reference": st.session_state.get("reference_answer_input", "")[:1000],
                        "semantic_score": score_sem,
                        "intent_score": score_intent,
                        "rubric_result": rubric_status,
                        "feedback": fb_sem
                    }
                    df_log = pd.DataFrame([rec])
                    log_file = "evaluation_log.csv"
                    df_log.to_csv(log_file, mode="a", header=not os.path.exists(log_file), index=False)

                    st.success("✅  Narrative Architect Complete!")

if st.session_state.current_evaluation:
    # Use session state for all rendering to ensure edits are reflected
    data = st.session_state.editable_data
    if not isinstance(data, dict):
        # Fallback parsing if state is empty
        json_match = re.search(r'<json>(.*?)</json>', st.session_state.current_evaluation, re.DOTALL)
        try:
            data = json.loads(json_match.group(1).strip()) if json_match else {}
        except:
            data = {}
    
    # Ensure data is a dictionary for the rest of the logic
    data = dict(data) if data else {}
    
    trace_content = st.session_state.edited_trace
    main_text = st.session_state.edited_narrative
    
    # ─── A. TRACING PHASE ───
    if st.session_state.refinement_mode:
        st.markdown("<div class='sec-head'>⚙️ Refine Trace (Internal Reasoning)</div>", unsafe_allow_html=True)
        if st.session_state.edited_review:
            st.info(f"**Previous Change Review:** {st.session_state.edited_review}")
        st.session_state.edited_trace = st.text_area("Edit Trace Content", value=st.session_state.edited_trace, height=200, label_visibility="collapsed")
    else:
        # Show review if exists
        render_review_box(st.session_state.edited_review)
            
        formatted_trace = trace_content.replace("\n", "<br>")
        st.markdown(f"""
        <style>
            .trace-details {{
                margin-bottom: 2rem; 
                border-left: 4px solid #3b82f6;
            }}
            .trace-details summary {{
                list-style: none;
                cursor: pointer;
                outline: none;
                margin-top: 15px; 
                padding: 8px 20px; 
                border-radius: 6px; 
                border: 1px solid #3b82f6; 
                background: transparent; 
                color: #3b82f6; 
                font-weight: 600; 
                transition: all 0.3s ease;
                display: inline-block;
            }}
            .trace-details summary:hover {{
                background: rgba(59, 130, 246, 0.05);
                transform: translateY(-1px);
            }}
            .trace-details summary::-webkit-details-marker {{
                display: none;
            }}
            .trace-content {{
                color: #64748b; 
                font-style: italic; 
                line-height: 1.6; 
                margin-top: 15px; 
                border-top: 1px solid #e2e8f0; 
                padding-top: 15px;
            }}
        </style>
        <div class="glass-card trace-details">
            <h4 style="margin-top:0; color:#3b82f6; display:flex; align-items:center;">
                <svg style="width:20px;height:20px;margin-right:8px;fill:#3b82f6;" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
                Tracing Phase (Internal Reasoning)
            </h4>
            <details>
                <summary>View Trace</summary>
                <div class="trace-content">
                    {formatted_trace}
                </div>
            </details>
        </div>
        """, unsafe_allow_html=True)

    # ─── B. METRICS DASHBOARD (Restored) ───
    if data:
        score, band, risk, supervision, badge_html = calculate_performance(data)
        
        # Performance indicator logic
        sc = "good" if score >= 75 else "warn" if score >= 50 else "bad"
        
        # Risk level logic (0-10, lower is better)
        evals = data.get("Evaluation", [])
        avg_risk = sum(float(re.findall(r"\d+", str(i.get("Risk Level", 5)))[0]) if re.findall(r"\d+", str(i.get("Risk Level", 5))) else 5 for i in evals) / len(evals) if evals else 5
        rc = "good" if avg_risk <= 3 else "warn" if avg_risk <= 7 else "bad"
        
        # Reuse score for simplified indicators
        mc = "good" if score >= 80 else "bad"

        st.markdown("<div class='sec-head'>📊  Performance Overview</div>", unsafe_allow_html=True)
        metrics_cols = st.columns(5, gap="small")
        
        # Determine status colors
        sem_cls = "good" if st.session_state.rubric_result == "PASS" else "bad"
        int_cls = "good" if st.session_state.intent_score >= 0.60 else "warn" if st.session_state.intent_score >= 0.40 else "bad"
        
        metrics = [
            (metrics_cols[0], "Performance Score", f"{score}%", sc, badge_html),
            (metrics_cols[1], "Compliance Risk", risk, rc, ""),
            (metrics_cols[2], "Semantic Similarity", f"{st.session_state.semantic_score:.2f}", sem_cls, ""),
            (metrics_cols[3], "Rubric Status", st.session_state.rubric_result, sem_cls, ""),
            (metrics_cols[4], "Intent Match", f"{st.session_state.intent_score:.2f}", int_cls, ""),
        ]
        for col, label, value, cls, extra in metrics:
            with col:
                extra_html = f"<div style='margin-top:8px;'>{extra}</div>" if extra else ""
                st.markdown(f"""<div class='metric-card'><div class='label'>{label}</div><div class='value {cls}' style='font-size: 1.6rem;'>{value}</div>{extra_html}</div>""", unsafe_allow_html=True)

        st.markdown("<div class='sec-head'>🗂  Operational Audit Matrix</div>", unsafe_allow_html=True)
        if "Evaluation" in data:
            eval_list = data.get("Evaluation", [])
            
            # ── Clean up Python list-string formatting globally before rendering ──
            # e.g. "['Provide documented evidence...', 'item2']" → "Provide documented evidence... • item2"
            import ast
            for row in eval_list:
                for k, v in row.items():
                    if isinstance(v, list):
                        row[k] = " • ".join(str(item).strip(" '\"") for item in v if str(item).strip(" '\""))
                    elif isinstance(v, str):
                        stripped = v.strip()
                        if stripped.startswith("[") and stripped.endswith("]"):
                            try:
                                parsed = ast.literal_eval(stripped)
                                if isinstance(parsed, list):
                                    row[k] = " • ".join(str(item).strip(" '\"") for item in parsed if str(item).strip(" '\""))
                            except Exception:
                                row[k] = stripped[1:-1].strip().strip("'\"")
                        # Also strip stray leading/trailing quotes/brackets
                        if isinstance(row[k], str):
                            row[k] = row[k].strip("'\"[]")
                            
            if st.session_state.editable_data is not None:
                st.session_state.editable_data["Evaluation"] = eval_list
                
            df = pd.DataFrame(eval_list)

            if st.session_state.refinement_mode:
                # EDITABLE MODE
                # Use a callback to immediately capture edits into session state
                # BEFORE the Save button triggers a rerun (which would lose them).
                def _capture_edits():
                    """Called by data_editor on_change — persists the delta immediately."""
                    delta = st.session_state.get("data_editor_main", {})
                    if not delta or st.session_state.editable_data is None:
                        return
                    rows = list(st.session_state.editable_data.get("Evaluation", []))
                    # Apply edited_rows changes
                    for row_idx_str, changes in delta.get("edited_rows", {}).items():
                        row_idx = int(row_idx_str)
                        if row_idx < len(rows):
                            rows[row_idx].update(changes)
                    # Apply added_rows
                    for new_row in delta.get("added_rows", []):
                        rows.append(new_row)
                    # Apply deleted_rows (in reverse so indices stay valid)
                    for del_idx in sorted(delta.get("deleted_rows", []), reverse=True):
                        if del_idx < len(rows):
                            rows.pop(del_idx)
                    st.session_state.editable_data["Evaluation"] = rows

                try:
                    st.data_editor(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        key="data_editor_main",
                        on_change=_capture_edits,
                        column_config={
                            "Rating": st.column_config.NumberColumn("Rating", min_value=0, max_value=10, step=0.1, format="%.1f"),
                            "Evidence Score": st.column_config.NumberColumn("Evidence Score", min_value=0, max_value=10, step=0.1, format="%.1f"),
                            "Risk Level": st.column_config.NumberColumn("Risk Level", min_value=0, max_value=10, step=0.1, format="%.1f"),
                            "Priority": st.column_config.NumberColumn("Priority", min_value=0, max_value=10, step=0.1, format="%.1f"),
                        }
                    )
                except Exception as e:
                    st.error(f"Editor error: {e}")
            else:
                # ─── STATIC MODE: Split Minimalist Tables ───
                def render_minimal_table(dataframe, columns, title):
                    st.markdown(f"<div style='margin: 25px 0 15px 0; color: #1e293b; font-size: 1.1rem; font-weight: 600; border-left: 4px solid #94a3b8; padding-left: 12px;'>{title}</div>", unsafe_allow_html=True)
                    
                    subset_df = dataframe[columns]
                    
                    html_table = f"""
                    <div style="width:100%; overflow-x:auto; border:1px solid #e2e8f0; border-radius:8px; margin-bottom:1.5rem;">
                    <table style="width:100%; border-collapse:collapse; background:#ffffff; font-family:'Inter',sans-serif; font-size:13px; color: #334155;">
                    <thead>
                    <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                    """
                    for col in columns:
                        html_table += f'<th style="text-align:left; padding:12px 15px; font-weight:600; color:#475569; border-right: 1px solid #f1f5f9;">{col}</th>'
                    html_table += "</tr></thead><tbody>"
                    
                    for idx, row in subset_df.iterrows():
                        html_table += '<tr style="border-bottom: 1px solid #f1f5f9;">'
                        for col in columns:
                            val = row[col]
                            html_table += f'<td style="padding:12px 15px; text-align:left; border-right: 1px solid #f1f5f9; line-height: 1.5; vertical-align: top;">{val}</td>'
                        html_table += "</tr>"
                    
                    html_table += "</tbody></table></div>"
                    st.markdown(html_table, unsafe_allow_html=True)

                # Define Groups
                perf_cols = ["Criterion", "Rating", "Evidence Found", "Evidence Score", "Risk Level", "Operational Impact"]
                strat_cols = ["Criterion", "Root Cause", "Corrective Action", "How To Improve", "Measurable KPI Target", "Priority"]
                
                # Check which columns actually exist in the AI output
                available_cols = list(df.columns)
                perf_cols = [c for c in perf_cols if c in available_cols]
                strat_cols = [c for c in strat_cols if c in available_cols]

                render_minimal_table(df, perf_cols, "I. Performance Assessment & Readiness")
                render_minimal_table(df, strat_cols, "II. Operational Improvement Strategy")


        st.markdown("<div class='sec-head'>📡  Criteria Radar — Compliance Coverage</div>", unsafe_allow_html=True)
        evals = data.get("Evaluation", [])
        if evals:
            def _parse_num(val, default=0):
                try:
                    return float(re.findall(r"[-+]?\d*\.\d+|\d+", str(val))[0]) if re.findall(r"[-+]?\d*\.\d+|\d+", str(val)) else default
                except: return default

            criteria = [i.get("Criterion", "?") for i in evals]
            status_r = [_parse_num(i.get("Rating", 0)) / 10.0 for i in evals]
            evi_r = [_parse_num(i.get("Evidence Score", 0)) / 10.0 for i in evals]
            risk_r = [(10 - _parse_num(i.get("Risk Level", 10))) / 10.0 for i in evals]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=[*status_r, status_r[0]], 
                theta=[*criteria, criteria[0]], 
                fill="toself", 
                fillcolor="rgba(16, 185, 129, 0.25)", 
                line={"color": "#10b981", "width": 3}, 
                name="Operational Rating"
            ))
            fig.add_trace(go.Scatterpolar(
                r=[*evi_r, evi_r[0]], 
                theta=[*criteria, criteria[0]], 
                fill="toself", 
                fillcolor="rgba(59, 130, 246, 0.2)", 
                line={"color": "#3b82f6", "width": 2.2, "dash": "dot"}, 
                name="Evidence Score"
            ))
            fig.add_trace(go.Scatterpolar(
                r=[*risk_r, risk_r[0]], 
                theta=[*criteria, criteria[0]], 
                fill="toself", 
                fillcolor="rgba(239, 68, 68, 0.15)", 
                line={"color": "#ef4444", "width": 1.5, "dash": "dash"}, 
                name="Risk Clearance (Inverted)"
            ))
            fig.update_layout(
                polar={
                    "bgcolor": "rgba(255,255,255,0.8)", 
                    "radialaxis": {
                        "visible": True, 
                        "range": [0, 1.05], 
                        "tickvals": [0, 0.25, 0.5, 0.75, 1.0], 
                        "ticktext": ["0%", "25%", "50%", "75%", "100%"],
                        "tickfont": {"color": "black"}
                    },
                    "angularaxis": {
                        "tickfont": {"color": "black", "size": 12, "weight": "bold"}
                    }
                }, 
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)", 
                height=450, 
                margin={"l": 80, "r": 80, "t": 40, "b": 40}
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='sec-head'>📋  Executive Operational Summary</div>", unsafe_allow_html=True)
        
        # Determine the correct key for extraction
        summary_obj = data.get("Executive Summary") or data.get("Summary")
        
        # Fallback: Auto-generate if missing
        if not summary_obj and data.get("Evaluation"):
            summary_obj = generate_fallback_summary(data.get("Evaluation"))
            
        if summary_obj:
            st.markdown("<div style='background: #ffffff; padding: 25px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.06);'>", unsafe_allow_html=True)
            for k, v in summary_obj.items():
                if not v: continue
                
                # Split by various markers but keep it high-quality
                bullets = [b.strip() for b in re.split(r'•|(?<=\n)-\s*|(?<=\n)\*\s*', str(v)) if b.strip()]
                
                if len(bullets) > 1:
                    v_html = "".join([f"<div style='margin-left: 20px; text-indent: -18px; margin-bottom: 10px; font-weight: 500; color: #475569;'>• {b}</div>" for b in bullets])
                else:
                    v_html = f"<div style='font-weight: 500; color: #475569;'>{v}</div>"
                    
                st.markdown(f"""
                <div style='margin-bottom: 24px; border-bottom: 1px solid #f1f5f9; padding-bottom: 15px;'>
                    <div style='font-size: 0.72rem; font-weight: 800; color: #2563eb; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; display: flex; align-items: center;'>
                        <span style="width: 8px; height: 8px; background: #2563eb; border-radius: 50%; margin-right: 10px;"></span>
                        {k}
                    </div>
                    <div style='font-size: 0.98rem; line-height: 1.7;'>
                        {v_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("The AI did not generate an explicit Executive Summary section. Please check the Operational Audit Matrix for detailed findings.")

    # ─── D. HUMAN-IN-THE-LOOP (Buttons) ───
    st.markdown("<h3 style='color:#1f2937; margin-bottom: 20px;'>🔄 Human-in-the-Loop Approval</h3>", unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")
    with col1:
        if st.session_state.refinement_mode:
            if st.button("💾 Save & Update View", use_container_width=True):
                user_trace      = st.session_state.edited_trace.strip()
                original_trace  = st.session_state.original_trace.strip()
                rubric_stored    = st.session_state.get("rubric_text_stored", "")
                narrative_stored = st.session_state.get("narrative_text_stored", "")

                # Only call LLM if the user actually CHANGED the trace text.
                # If they just edited table cells, skip LLM and keep the
                # manual edits already captured by _capture_edits callback.
                trace_was_changed = (user_trace != original_trace) and user_trace

                if trace_was_changed and rubric_stored and narrative_stored:
                    client = get_groq_client()
                    if client:
                        with st.spinner("🤖  Re-evaluating based on your trace instructions…"):
                            with tracer.start_as_current_span("llm_re_evaluation") as span:
                                span.set_attribute("description", "HIFL re-evaluation")
                                result_text = re_evaluate_with_trace(
                                    client=client,
                                    rubric_text=rubric_stored,
                                    narrative_text=narrative_stored,
                                    user_trace_instructions=user_trace,
                                    model="llama-3.1-8b-instant",
                                    temperature=0.5,
                                )
                        if result_text:
                            st.session_state.current_evaluation = result_text
                            trace_match = re.search(r'<trace>(.*?)</trace>', result_text, re.DOTALL)
                            new_trace = trace_match.group(1).strip() if trace_match else user_trace
                            st.session_state.edited_trace   = new_trace
                            st.session_state.original_trace = new_trace  # reset baseline
                            json_match = re.search(r'<json>(.*?)</json>', result_text, re.DOTALL)
                            if json_match:
                                try:
                                    st.session_state.editable_data = json.loads(json_match.group(1).strip())
                                except:
                                    pass
                            st.session_state.edited_narrative = main_text
                            
                            review_match = re.search(r'<review>(.*?)</review>', result_text, re.DOTALL)
                            st.session_state.edited_review = review_match.group(1).strip() if review_match else ""
                            
                            st.success("✅  Re-evaluation complete based on your trace instructions!")
                    else:
                        st.error("🔑  Groq API Key missing.")
                else:
                    # Trace unchanged — manual table edits are already saved
                    # by the _capture_edits callback. Nothing extra needed.
                    st.success("✅  Your manual edits have been saved!")

                st.session_state.refinement_mode = False
                st.rerun()
        else:
            if st.button("✅ Confirm & Save to Timeline", use_container_width=True):
                # Save the current state (including any manual edits) to history
                import json as _json
                snapshot = _json.dumps(st.session_state.editable_data) if st.session_state.editable_data else ""
                st.session_state.history.append({
                    "timestamp": time.time(),
                    "score": 100,
                    "data": snapshot,
                    "manual": True,
                })
                st.session_state.confirmed = True
                st.success("✅  Changes confirmed and saved to timeline!")
    with col2:
        if st.session_state.refinement_mode:
            if st.button("❌ Cancel Refinement", use_container_width=True):
                st.session_state.refinement_mode = False
                st.rerun()
        else:
            if st.button("✍️ Refine & Edit Trace", use_container_width=True):
                st.session_state.refinement_mode = True
                st.rerun()

    # ─── Human Feedback Loop (RLHF) ───
    st.markdown("<h3 style='color:#1f2937; margin-top: 30px; margin-bottom: 20px;'>💬 Human Feedback (for improvement)</h3>", unsafe_allow_html=True)
    user_feedback = st.text_area("Provide feedback on the above response:", height=100, key="human_feedback_text_input")
    if st.button("🔄 Regenerate with Feedback", use_container_width=True):
        if "last_response_raw" not in st.session_state or not st.session_state.last_response_raw:
            st.error("⚠️ Please generate a response first.")
        else:
            improved_prompt = (
                f"Improve the previous answer using this feedback:\n\n"
                f"Feedback: {user_feedback}\n\n"
                f"Previous Response: {st.session_state['last_response_raw']}\n\n"
                f"Please provide the updated evaluation with a <review> section explaining your changes."
            )
            with st.spinner("🤖 AI Auditor regenerating improved response..."):
                with tracer.start_as_current_span("llm_regeneration_with_feedback") as span:
                    span.set_attribute("description", "Regeneration with human feedback")
                    client = get_groq_client()
                    
                    # Use REFINE_SYSTEM_PROMPT for better change tracking
                    from ai_wrapper import REFINE_SYSTEM_PROMPT
                    chat = client.chat.completions.create(
                        model="llama-3.1-8b-instant", 
                        messages=[
                            {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                            {"role": "user", "content": improved_prompt}
                        ],
                        max_tokens=2048,
                        temperature=0.7
                    )
                    improved_resp_raw = chat.choices[0].message.content
                    
                    # Parse review
                    rev_match = re.search(r'<review>(.*?)</review>', improved_resp_raw, re.DOTALL)
                    st.session_state.improved_review = rev_match.group(1).strip() if rev_match else ""
                    
                    # Strip tags for display (Handle missing closing tags gracefully with |$)
                    clean_resp = re.sub(r'<trace>.*?(</trace>|$)', '', improved_resp_raw, flags=re.DOTALL)
                    clean_resp = re.sub(r'<review>.*?(</review>|$)', '', clean_resp, flags=re.DOTALL)
                    clean_resp = re.sub(r'<json>.*?(</json>|$)', '', clean_resp, flags=re.DOTALL)
                    
                    # Final cleanup of any standalone tags or AI noise
                    clean_resp = re.sub(r'</?(trace|review|json)>', '', clean_resp, flags=re.IGNORECASE)
                    clean_resp = clean_resp.strip()
                    
                    st.session_state.improved_response = clean_resp if clean_resp else "The AI provided an incomplete response. Please try refining your feedback or checking the Audit Matrix below."
                    st.session_state.last_improved_raw = improved_resp_raw
                    
            st.subheader("Improved Response Preview")
            render_review_box(st.session_state.improved_review)
            st.info(st.session_state.improved_response)

            # --- NEW: Accept & Apply Button ---
            if st.button("✅ Accept & Apply Changes", use_container_width=True):
                raw = st.session_state.get("last_improved_raw", "")
                if raw:
                    # 1. Update JSON Data
                    json_match = re.search(r'<json>(.*?)</json>', raw, re.DOTALL)
                    if json_match:
                        try:
                            # Use the global robust_json_repair
                            parsed = robust_json_repair(raw)
                            if parsed:
                                st.session_state.editable_data = parsed
                        except Exception as e:
                            st.error(f"Failed to update table data: {e}")
                    
                    # 2. Update Narrative & Evaluation Source
                    st.session_state.edited_narrative = st.session_state.improved_response
                    st.session_state.current_evaluation = raw # Sync the source string
                    
                    # 3. Update Trace & Review
                    trace_match = re.search(r'<trace>(.*?)</trace>', raw, re.DOTALL)
                    if trace_match:
                        st.session_state.edited_trace = trace_match.group(1).strip()
                    
                    st.session_state.edited_review = st.session_state.improved_review
                    
                    # 4. Clear Preview and Rerun
                    st.session_state.improved_response = None
                    st.session_state.improved_review = None
                    st.success("✨ Audit updated with your feedback!")
                    st.rerun()

            # Log improvement attempt
            rec_fb = {
                "timestamp": datetime.now().isoformat(),
                "prompt": improved_prompt[:1000],
                "response": st.session_state.improved_response[:1000],
                "feedback": user_feedback
            }
            df_fb = pd.DataFrame([rec_fb])
            fb_log_file = "feedback_log.csv"
            df_fb.to_csv(fb_log_file, mode="a", header=not os.path.exists(fb_log_file), index=False)
            st.success("✅ Improved response generated and logged!")

    # ─── C. NARRATIVE DRAFT (Contextual Visibility) ───
    if st.session_state.refinement_mode:
        st.markdown("<div class='sec-head'>🖋️ Narrative Architect Draft (Refining)</div>", unsafe_allow_html=True)
        st.session_state.edited_narrative = st.text_area("Edit Narrative Draft", value=st.session_state.edited_narrative, height=400, label_visibility="collapsed")
    elif getattr(st.session_state, 'confirmed', False):
        st.markdown("<div class='sec-head'>🖋️ Final Narrative Draft</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="glass-card" style="padding: 2rem; border-left: 4px solid #3b82f6; font-family: 'Inter', sans-serif; color: #1e293b; line-height: 1.7; font-size: 1.1rem;">
            {st.session_state.edited_narrative}
        </div>
        """, unsafe_allow_html=True)
    # Draft is hidden in 'Normal' mode before confirmation to match "before make it non vivble"

    # ─── D.5 ARIZE PHOENIX TRACES (NATIVE) ───
    st.markdown("<div class='sec-head'>🔍 LLM Traces (via Phoenix)</div>", unsafe_allow_html=True)
    with st.expander("View Phoenix Dashboard and Traces", expanded=False):
        if phoenix_url:
            st.markdown(f"**Dashboard URL:** [{phoenix_url}]({phoenix_url})")
            # Embed the dashboard in an iframe
            st.components.v1.iframe(phoenix_url, height=800, scrolling=True)
        else:
            st.warning("Phoenix Dashboard is not available.")
        
        try:
            import time
            time.sleep(1) 
            phoenix_client = px.Client()
            spans_df = phoenix_client.get_spans_dataframe()
            if spans_df is not None and not spans_df.empty:
                st.dataframe(spans_df, use_container_width=True)
        except Exception as e:
            pass

    # ─── E. EXPORT ───
    if data:
        st.markdown("<div class='sec-head'>💾  Export Intelligence</div>", unsafe_allow_html=True)
        st.markdown("""
        <p style="color:#111827; font-size:15px; font-weight:500; margin-bottom:16px;">
            Download the full audit report in your preferred format.
        </p>
        """, unsafe_allow_html=True)
        export_df = pd.DataFrame(data.get("Evaluation", []))
        feedback_val = st.session_state.get("human_feedback_text_input", "")
        excel_data = create_excel_download(export_df, json_data=data, human_feedback=feedback_val)
        pdf_data = create_pdf_download(data, human_feedback=feedback_val)
        dl1, dl2 = st.columns([1, 1], gap="medium")
        with dl1:
            st.download_button("📥 Export as Excel", data=excel_data, file_name="audit_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with dl2:
            st.download_button("📄 Export as PDF", data=pdf_data, file_name="audit_report.pdf", mime="application/pdf", use_container_width=True)


    # ─── E. FLOATING CHAT ASSISTANT (Native popover) ───
    # Inject CSS to position the st.popover floating at the bottom right
    st.markdown("""
        <style>
        /* ═══════════════════════════════════════
           FLOATING CHAT ICON — Premium Animated
        ═══════════════════════════════════════ */

        /* ── Keyframe Animations ── */
        @keyframes chatPulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.5), 0 4px 20px rgba(59,130,246,0.35); }
            50%       { box-shadow: 0 0 0 14px rgba(59,130,246,0), 0 4px 20px rgba(59,130,246,0.35); }
        }
        @keyframes chatBounceIn {
            0%   { transform: scale(0) translateY(60px); opacity: 0; }
            60%  { transform: scale(1.15) translateY(-6px); opacity: 1; }
            80%  { transform: scale(0.95) translateY(2px); }
            100% { transform: scale(1) translateY(0); }
        }
        @keyframes chatIconFloat {
            0%, 100% { transform: translateY(0); }
            50%      { transform: translateY(-5px); }
        }
        @keyframes chatGradientSpin {
            0%   { filter: hue-rotate(0deg); }
            100% { filter: hue-rotate(30deg); }
        }

        /* ── Fixed container — bottom right ── */
        /* Target both the popover AND its Streamlit parent wrapper */
        div:has(> div[data-testid="stPopover"]),
        div[data-testid="stPopover"] {
            position: fixed !important;
            bottom: 28px !important;
            right: 28px !important;
            left: auto !important;
            z-index: 99999 !important;
            width: auto !important;
            animation: chatBounceIn 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
        /* Ensure the parent element container doesn't block it */
        .stElementContainer:has(div[data-testid="stPopover"]) {
            position: fixed !important;
            bottom: 28px !important;
            right: 28px !important;
            left: auto !important;
            z-index: 99999 !important;
            width: auto !important;
        }

        /* ── Circular button — gradient, glow, float ── */
        div[data-testid="stPopover"] > button,
        div[data-testid="stPopover"] > div > button {
            border-radius: 50% !important;
            width: 68px !important;
            height: 68px !important;
            min-width: 68px !important;
            min-height: 68px !important;
            padding: 0 !important;
            background: linear-gradient(135deg, #3b82f6 0%, #6366f1 50%, #8b5cf6 100%) !important;
            color: white !important;
            border: none !important;
            font-size: 30px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            cursor: pointer !important;
            animation: chatPulse 2.5s ease-in-out infinite, chatIconFloat 3s ease-in-out infinite, chatGradientSpin 4s linear infinite !important;
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease !important;
            box-shadow: 0 6px 24px rgba(59,130,246,0.45) !important;
        }

        /* ── Button hover — lift + intense glow ── */
        div[data-testid="stPopover"] > button:hover,
        div[data-testid="stPopover"] > div > button:hover {
            transform: scale(1.12) translateY(-4px) !important;
            box-shadow: 0 10px 35px rgba(99,102,241,0.6), 0 0 0 6px rgba(139,92,246,0.2) !important;
            animation: chatGradientSpin 2s linear infinite !important;
        }

        /* ── Button text (the emoji) ── */
        div[data-testid="stPopover"] > button p,
        div[data-testid="stPopover"] > div > button p {
            font-size: 28px !important;
            line-height: 1 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* ── Chat popover window — glassmorphism ── */
        div[data-testid="stPopoverBody"] {
            width: 400px !important;
            max-width: 92vw !important;
            max-height: 520px !important;
            border-radius: 18px !important;
            border: 1px solid rgba(255,255,255,0.3) !important;
            background: rgba(255,255,255,0.97) !important;
            backdrop-filter: blur(16px) !important;
            -webkit-backdrop-filter: blur(16px) !important;
            box-shadow: 0 20px 60px rgba(0,0,0,0.12), 0 0 0 1px rgba(59,130,246,0.08) !important;
            padding: 1rem !important;
            right: 0px !important;
            left: auto !important;
            margin-bottom: 78px !important;
            animation: chatBounceIn 0.4s ease forwards !important;
        }

        </style>
    """, unsafe_allow_html=True)

    with st.popover("💬"):
        st.markdown("<h4 style='color:#1f2937; margin-bottom: 5px; text-align: center;'>Namma LLM.ai Chat</h4>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 0.8rem; color: #64748b; text-align: center; margin-bottom: 10px;'>Ask questions about this evaluation.</p>", unsafe_allow_html=True)
        
        chat_container = st.container(height=350)
        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Input for chat
        if prompt := st.chat_input("Ask about the evaluation..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with chat_container.chat_message("user"):
                st.markdown(prompt)
                
            with chat_container.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    client = get_groq_client()
                    if client and st.session_state.rubric_text_stored and st.session_state.narrative_text_stored:
                        with tracer.start_as_current_span("chat_llm_query") as span:
                            span.set_attribute("description", "chatbot query")
                            response = chat_with_data(
                                client=client,
                                rubric_text=st.session_state.rubric_text_stored,
                                narrative_text=st.session_state.narrative_text_stored,
                                evaluation_data=st.session_state.get("editable_data"),
                                user_message=prompt,
                                chat_history=st.session_state.chat_history[:-1]
                            )
                    elif not client:
                        response = "⚠️ API Key missing. Please set GROQ_API_KEY."
                    else:
                        response = "⚠️ Please upload and analyze documents first before chatting."
                    
                    st.markdown(response)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})