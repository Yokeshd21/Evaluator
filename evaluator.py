import re
from sentence_transformers import SentenceTransformer, util

# Load a more robust pretrained embedder (768-dim)
# all-mpnet-base-v2 provides better semantic depth than all-MiniLM-L6-v2
embedder = SentenceTransformer("all-mpnet-base-v2")

def normalize_text(text: str) -> str:
    """
    Normalizes text to improve similarity matching:
    - Lowercases
    - Strips markdown (basic)
    - Removes extra whitespace/newlines
    """
    if not text:
        return ""
    # Remove markdown bold/italic/code markers
    text = re.sub(r'[*_`#]', '', text)
    # Convert to lowercase
    text = text.lower()
    # Replace multiple spaces/newlines with a single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def evaluate_response(user_prompt: str, response: str, reference: str):
    """
    Compute semantic similarity and intent matching scores with normalization.
    Returns (semantic_score, intent_score, rubric_status, feedback).
    """
    # Normalize inputs
    norm_resp = normalize_text(response)
    norm_ref  = normalize_text(reference)
    norm_prompt = normalize_text(user_prompt)

    # Embed normalized text
    emb_resp = embedder.encode(norm_resp, convert_to_tensor=True)
    emb_ref  = embedder.encode(norm_ref, convert_to_tensor=True)
    semantic_score = util.cos_sim(emb_resp, emb_ref).item()
    
    # Embed user prompt and response for intent matching
    emb_prompt = embedder.encode(norm_prompt, convert_to_tensor=True)
    intent_score = util.cos_sim(emb_prompt, emb_resp).item()
    
    # Pass/Fail mapping back to rubric (Threshold = 0.75)
    rubric_status = "PASS" if semantic_score >= 0.75 else "FAIL"
    
    # Refined feedback based on semantic alignment
    if semantic_score > 0.85:
        feedback = "Excellent: High semantic alignment."
    elif semantic_score >= 0.75:
        feedback = "Pass: Strong alignment with core concepts."
    elif semantic_score > 0.50:
        feedback = "Partial: Captures some concepts but misses key details."
    else:
        feedback = "Low: Insufficient match with rubric intent."

    return semantic_score, intent_score, rubric_status, feedback
