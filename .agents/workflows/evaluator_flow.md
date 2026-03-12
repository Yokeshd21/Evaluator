---
description: Evaluator AI Auditor Step-by-Step Workflow
---

Evaluator AI Auditor: System Architecture & Workflow
The Evaluator AI Auditor is an end-to-end operational auditing framework that leverages Natural Language Processing (NLP) and Large Language Models (LLMs) to evaluate employee behavioral narratives against standardized benchmarks.

1. Data Ingestion & Configuration
The process begins with the ingestion of three core data components:

Narrative Upload: A PDF document containing the behavioral "memory" or activity log of an employee.

Rubric Configuration: A CSV file defining the specific audit criteria (e.g., Task Execution, Process Adherence, Communication).

Reference (Gold) Answer: A benchmark narrative provided by the user that represents an ideal "Passing" performance.

2. Pre-Processing Phase
Before analysis, the raw data undergoes automated refinement:

Text Extraction: The system utilizes pdfplumber to parse and extract text from the uploaded PDF.

Normalization: Text is cleaned by converting to lowercase, removing redundant whitespace, and stripping markdown formatting to ensure data consistency.

3. Semantic Similarity Mapping
To determine initial alignment, the system performs a vector-based comparison:

Vector Embedding: Both the User Narrative and the Gold Answer are converted into high-dimensional vectors using the all-mpnet-base-v2 model.

Cosine Similarity Calculation: The system measures the mathematical "distance" between the two vectors.

Threshold Validation: A benchmark of 0.75 is applied:

PASS (≥ 0.75): The narrative demonstrates high semantic alignment with the gold standard.

FAIL (< 0.75): The narrative deviates significantly from expected behavior.

4. AI Audit Execution (LLM Layer)
The core analysis is handled by an enterprise-grade LLM:

Inference Engine: Data is passed to Llama 3.1-8B (via Groq) with a specialized "Enterprise Auditor" system prompt.

Trace Analysis: The AI performs a granular "Trace" to map specific evidence found in the narrative to the rubric criteria.

Structured Output: The AI generates a JSON object containing scores, root causes, identified risks, and suggested corrective actions across seven distinct categories.

5. Visualization & UI Rendering
Results are transformed into actionable insights via a Streamlit-based dashboard:

Metrics Dashboard: Displays high-level KPIs including Total Score, Risk Level, and Rubric Status.

Operational Matrix: A sortable, interactive table for deep-diving into specific findings.

Radar Chart: A Plotly-based visualization illustrating "Compliance Coverage" across all categories.

Executive Summary: An auto-generated synthesis of the audit’s overall health and critical takeaways.

6. Human-in-the-Loop (HIFL) Refinement
The system allows for human oversight to ensure accuracy:

Feedback Loop: Users can flag specific scores or provide contextual nuances (e.g., "This score is too low due to X").

Iterative Regeneration: The AI re-evaluates the narrative using the user’s feedback as a new constraint.

State Persistence: Once confirmed, the updated results are saved to the session state for reporting.

7. Intelligence Export
Finalized audits are available in two formats:

Excel: A multi-sheet workbook containing the full Audit Matrix, Summary, and Feedback logs.

PDF: A formatted, presentation-ready report including all visualizations and executive findings..