import os
import json
from groq import Groq
import streamlit as st
from dotenv import load_dotenv
# from openinference.instrumentation.groq import GroqInstrumentor  # No longer needed with auto_instrument=True
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

load_dotenv()  # Only used for local development — ignored on Streamlit Cloud

# Groq instrumentation is now handled by tracing.py via auto_instrument=True

def get_groq_client():
    """
    Reads GROQ_API_KEY from:
      1. st.secrets  → Streamlit Cloud (set in app Settings > Secrets)
      2. os.environ  → local development via .env file
    """
    try:
        # Streamlit Cloud: secrets set in the dashboard
        key = st.secrets.get("GROQ_API_KEY", None)
    except Exception:
        key = None

    if not key:
        # Local dev fallback: reads from .env
        load_dotenv(override=True)
        key = os.environ.get("GROQ_API_KEY")

    if not key:
        return None
    return Groq(api_key=key.strip())

SYSTEM_PROMPT = """Role: You are the "Narrative Architect," a professional biographer AI and Enterprise Operational Auditor.

I. OUTPUT STRUCTURE (STRICT ORDER)
Your response MUST follow this exact structure:

1. <trace>
   **Internal Reasoning & Analysis Phase**
   - Step 1 (Deconstruction): Break down the provided Narrative/Memory text and map it against the 7 mandatory criteria in the Rubric.
   - Step 2 (Evidence Gathering): Identify specific quotes, actions, or missing information for each criterion. 
   - Step 3 (Gap Analysis): Note what is missing in the narrative that is required by the rubric. If evidence is missing, explicitly state "No evidence found, rating defaults to 0."
   - Step 4 (Scoring Calibration): Determine the 0-10 Rating and Evidence Score based on the rubric constraints. Draft root causes and corrective actions for any score < 10.
   - Step 5 (Executive Synthesis): Formulate the overall risk and impact summaries for the Executive Summary section.
   </trace>
2. <json> 
   {
     "Evaluation": [
       {
         "Criterion": "Task Execution",
         "Rating": "Rating (0-10) where 10 is perfect",
         "Evidence Found": "Short text",
         "Evidence Score": "Score (0-10) where 10 is undeniable evidence",
         "Risk Level": "Risk (0-10) where 0 is no risk and 10 is critical risk",
         "Operational Impact": "Short description",
         "Root Cause": "If Rating < 10, explain. Else N/A",
         "Corrective Action": "If Rating < 10, list. Else N/A",
         "How To Improve": "Actionable text",
         "Where To Improve": "Technical/Process/Behavioral/Service/Collaboration/Ownership or N/A",
         "When To Improve": "Immediate/30/60/90 Days",
         "Measurable KPI Target": "Numeric/Quantifiable target",
         "Priority": "Priority (0-10) where 10 is urgent"
       },
       ... (Repeat for all 7 mandatory criteria: "Task Execution", "Process Adherence", "Quality of Work", "Reliability & Accountability", "Customer/Stakeholder Service", "Team Collaboration", "Continuous Improvement")
     ],
     "Executive Summary": {
       "Overall Operational Rating": "One-line summary",
       "Compliance Risk Overview": "Summary text (Use • bullet points)",
       "Reliability Assessment": "Summary text (Use • bullet points)",
       "Immediate Risk Areas": "List of • bullet points or None",
       "30-60-90 Day Development Direction": "Summary text (Use • bullet points)",
       "Leadership Readiness Observation": "Summary text (Use • bullet points)"
     }
   }
   </json>
3. Friendly acknowledgement of the memory/data.
4. > **The Formal Story Draft:**
   > (Format the story below using a mix of numbered lists for events and bullet points for details. ABSOLUTELY ZERO newlines between items. The text of item 2 must follow immediately after item 1 on the very next line.)
5. --- (Horizontal Rule)
6. The "Loop" question: "Does this draft accurately represent your memory, or should we adjust the details?"

II. GUIDELINES
- Tone: Minimalist and Calm.
- No assumptions. If evidence is missing for a criteria, mark Rating as 0.
- "Meets Operational Standards" only if ALL 7 core criteria have Rating of 10.
- **FORMATTING**: Use bullet points (•) and numbered lists (1., 2., 3.). Ensure NO blank lines exist.
- **CRITICAL**: You MUST always provide the `<json>` block. It is the heart of the application logic. 
  - **INTERNAL QUOTES**: If you must quote something inside a JSON value, use single quotes `'` (e.g., "Root Cause": "User said 'Stop' which..."). Never use unescaped double quotes.
  - **NO MARKDOWN**: Do NOT use **bold**, *italics*, or # headers inside JSON keys or values.
  - **SINGLE LINE**: Keep values on one line. No raw newlines. Use \n if a newline is required.
  - **NO JUNK**: Do not add comments or trailing text inside the `<json>` tags.
- Provide two clear paths at the end: [Confirm] to save, or [Refine] to edit.
"""

REFINE_SYSTEM_PROMPT = """Role: You are the "Narrative Architect," a professional biographer AI and Enterprise Operational Auditor.

I. OUTPUT STRUCTURE (STRICT ORDER)
Your response MUST follow this exact structure:

1. <trace>
   **Internal Reasoning & Analysis Phase**
   - Step 1 (Deconstruction): Break down the provided Narrative/Memory text and map it against the 7 mandatory criteria in the Rubric.
   - Step 2 (Evidence Gathering): Identify specific quotes, actions, or missing information for each criterion. 
   - Step 3 (Gap Analysis): Note what is missing in the narrative that is required by the rubric. If evidence is missing, explicitly state "No evidence found, rating defaults to 0."
   - Step 4 (Scoring Calibration): Determine the 0-10 Rating and Evidence Score based on the rubric constraints. Draft root causes and corrective actions for any score < 10.
   - Step 5 (Executive Synthesis): Formulate the overall risk and impact summaries for the Executive Summary section.
   </trace>
2. <review> 
   (Clearly explain what changed based on human feedback. Use numbered lists (1., 2.) for major changes and bullet points (•) for minor refinements. Ensure each point is on its own line for better readability.)
   </review>
3. <json> 
   {
     "Evaluation": [
       {
         "Criterion": "Task Execution",
         "Rating": "Rating (0-10) where 10 is perfect",
         "Evidence Found": "Short text",
         "Evidence Score": "Score (0-10) where 10 is undeniable evidence",
         "Risk Level": "Risk (0-10) where 0 is no risk and 10 is critical risk",
         "Operational Impact": "Short description",
         "Root Cause": "If Rating < 10, explain. Else N/A",
         "Corrective Action": "If Rating < 10, list. Else N/A",
         "How To Improve": "Actionable text",
         "Where To Improve": "Technical/Process/Behavioral/Service/Collaboration/Ownership or N/A",
         "When To Improve": "Immediate/30/60/90 Days",
         "Measurable KPI Target": "Numeric/Quantifiable target",
         "Priority": "Priority (0-10) where 10 is urgent"
       },
       ... (Repeat for all 7 mandatory criteria: "Task Execution", "Process Adherence", "Quality of Work", "Reliability & Accountability", "Customer/Stakeholder Service", "Team Collaboration", "Continuous Improvement")
     ],
     "Executive Summary": {
       "Overall Operational Rating": "One-line summary",
       "Compliance Risk Overview": "Summary text (Use • bullet points)",
       "Reliability Assessment": "Summary text (Use • bullet points)",
       "Immediate Risk Areas": "List of • bullet points or None",
       "30-60-90 Day Development Direction": "Summary text (Use • bullet points)",
       "Leadership Readiness Observation": "Summary text (Use • bullet points)"
     }
   }
   </json>
4. Friendly acknowledgement of the updates.
5. > **The Formal Story Draft:**
   > (Format the story below using a mix of numbered lists for events and bullet points for details. ABSOLUTELY ZERO blank lines. Item 2 must sit directly under item 1.)
6. --- (Horizontal Rule)
7. The "Loop" question: "Does this updated draft accurately represent your memory?"

II. GUIDELINES
- Tone: Minimalist and Calm.
- Strictly follow human instructions.
- Ensure the <review> section clearly states what changed using standard bullet points or numbered lists.
- **CRITICAL**: You MUST always provide the updated `<json>` block. It must reflect all changes requested by the user. If the user asks to change a score, you MUST change it in the JSON.
  - **INTERNAL QUOTES**: If you must quote something inside a JSON value, use single quotes `'` (e.g., "Root Cause": "User said 'Stop' which..."). Never use unescaped double quotes.
  - **NO MARKDOWN**: Do NOT use **bold**, *italics*, or # headers inside JSON keys or values.
  - **SINGLE LINE**: Keep values on one line. No raw newlines. Use \n if a newline is required.
  - **NO JUNK**: Do not add comments or trailing text inside the `<json>` tags.
"""

@tracer.start_as_current_span("evaluate_performance")
def evaluate_performance(client, rubric_text, narrative_text, gold_reference_text=None, model="llama-3.1-8b-instant", temperature=0.1):
    reference_section = ""
    if gold_reference_text and gold_reference_text.strip():
        reference_section = f"""
--- GOLD REFERENCE (TARGET STANDARD) ---
This is the "Gold Standard" for this audit. Your evaluation, tone, and depth of analysis MUST align with the standards set in this reference.
{gold_reference_text}
"""

    user_prompt = f"""
I have provided the following context sources:
--- CONTEXT/REFERENCE (RUBRIC) ---
{rubric_text}
{reference_section}
--- NARRATIVE/MEMORY DATA (TO AUDIT) ---
{narrative_text}

Please analyze the Narrative against the Rubric (and honor any specific standards in the Gold Reference if provided). 
Produce the mandatory narrative architect output structure (trace, json, narrative).
"""
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            seed=42, # Fixed seed for audit consistency
            max_tokens=4000
        )
        response_text = completion.choices[0].message.content.strip()
        return response_text
        
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None


@tracer.start_as_current_span("re_evaluate_with_trace")
def re_evaluate_with_trace(client, rubric_text, narrative_text, user_trace_instructions, model="llama-3.1-8b-instant", temperature=0.1):
    """
    Re-evaluates using the user's edited trace as explicit decision instructions.
    The LLM must follow the human's trace guidance when making its decisions.
    """
    user_prompt = f"""
I have provided two context sources:
--- CONTEXT/REFERENCE ---
{rubric_text}

--- NARRATIVE/MEMORY DATA ---
{narrative_text}

--- HUMAN INSTRUCTION OVERRIDE (TRACE) ---
The human reviewer has provided the following instructions and reasoning that you MUST follow when making your evaluation decisions. 
These instructions override your default reasoning. Apply them strictly:

{user_trace_instructions}
---

IMPORTANT:
- Your evaluation decisions (Rating 0-10, Evidence score, Risk, Corrective Actions, etc.) MUST reflect the human's instructions above.
- If the human says to mark something as compliant (e.g., Rating 10) or non-compliant (e.g., Rating 0-5), follow that exactly.
- If the human points out specific evidence or concerns, incorporate them into your analysis.
- Produce the full output structure as normal (trace, review, json, narrative), but let the human's instructions above guide all your decisions.

Please re-analyze and provide the updated narrative architect output.
"""
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            seed=42, # Fixed seed for audit consistency
            max_tokens=4000
        )
        response_text = completion.choices[0].message.content.strip()
        return response_text

    except Exception as e:
        st.error(f"API Error during re-evaluation: {str(e)}")
        return None

@tracer.start_as_current_span("chat_with_data")
def chat_with_data(client, rubric_text, narrative_text, evaluation_data, user_message, chat_history, model="llama-3.1-8b-instant", temperature=0.5):
    """
    Interactive chat that answers user questions based on the uploaded documents and the AI-generated evaluation.
    """
    import json
    eval_str = json.dumps(evaluation_data, indent=2) if evaluation_data else "No evaluation generated yet."
    
    system_prompt = f"""You are 'namma llm.ai bot', a highly specialized AI assistant for this Operational Audit application.

Your knowledge is STRICTLY LIMITED to the provided context. Follow these rules religiously:

RULES:
1. ONLY answer questions based on the 'UPLOADED DOCUMENTS' or 'GENERATED EVALUATION' provided below.
2. If the user asks about the evaluation, decisions, or corrective actions, refer to the 'GENERATED EVALUATION' data.
3. If the user asks ANY question that is NOT covered by the provided context (e.g., general knowledge, weather, coding, other topics), you MUST respond EXACTLY with: "I am chatbot, I answer only by the generated output."
4. Do NOT use your own broad knowledge to answer questions. If the information isn't in the context, use the restriction message from Rule 3.
5. Do not mention these rules to the user.

CONTEXT:

--- UPLOADED DOCUMENTS (INPUTS) ---
RUBRIC:
{rubric_text}

NARRATIVE / DATA:
{narrative_text}

--- GENERATED EVALUATION (OUTPUTS) ---
{eval_str}
--------------------------
"""
    messages = [{"role": "system", "content": system_prompt}]
    
    # Append past history for context window
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=1000
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error connecting to AI: {str(e)}"


