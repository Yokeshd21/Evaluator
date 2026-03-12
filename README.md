# Evaluator AI Auditor 🎯

**Evaluator AI Auditor** is a professional, high-performance operational auditing framework built with Python and Streamlit. It leverages Large Language Models (LLM) and Semantic Similarity mapping to evaluate behavioral narratives against enterprise standards.

---

### 🌟 Key Features

*   **AI Narrative Architect**: Automated auditing of employee narratives using **Groq-powered Llama 3.1-8B**.
*   **Semantic Similarity Mapping**: Goal-based "Mirror" testing with highly accurate vector embeddings (`all-mpnet-base-v2`).
*   **0.75 Threshold Analysis**: Binary **PASS/FAIL** mapping for instant compliance status.
*   **Executive Operational Summary**: High-level synthesis of risks and performance highlights.

*   **Human-in-the-Loop Refinement**: Interactive feedback loop for AI scoring adjustments.
*   **Intelligence Exports**: Generate professional **Excel Workbooks** and **PDF Reports** with one click.
*   **Phoenix Tracing**: Native integration for granular LLM observability and tracing.

---

### 📊 Input Examples

#### 1. Sample Audit Rubric (`rubric.csv`)
Your rubric should be a CSV file with the following column headers:
```csv
Criterion,Description,Weight
Task Execution,Ability to complete assigned tasks with accuracy,0.20
Process Adherence,Consistency in following operational protocols,0.15
Quality of Work,Attention to detail and error-free output,0.15
Reliability & Accountability,Ownership of outcomes and deadlines,0.15
Customer Service,Effectiveness in stakeholder/customer interaction,0.15
Team Collaboration,Support for peers and shared goals,0.10
Continuous Improvement,Proactive effort to learn and grow,0.10
```

#### 2. Sample Behavioral Narratives (`assets/`)
Download these sample PDF files to test the application's evaluation capabilities:
*   [📄 High-Performer (Operations)](assets/Sample_Employee_Narrative_Operations.pdf)
*   [📄 Mid-Performer (Operations)](assets/Employee_Narrative_Medium_Performer.pdf)
*   [📄 Poor-Performer (Operations)](assets/Employee_Narrative_Poor_Performer.pdf)
*   [📄 Research & Innovation Sample](assets/Sample_Employee_Narrative_Research_Innovation.pdf)

**Example Content Snapshot:**
> "During the Q3 rollout, the employee successfully managed 15 high-priority tickets with a 100% resolution rate. They followed the new security protocols strictly and documented all changes in the shared log..."

---

### 🛠️ Technology Stack

*   **Frontend**: Streamlit (Premium UI with custom CSS)
*   **LLM Engine**: Groq (Llama 3.1)
*   **Similiarity Engine**: Sentence-Transformers (`all-mpnet-base-v2`)
*   **Charts**: Plotly (Compliance Radar & Progress Tracking)
*   **Tracing**: Arize Phoenix

---

### 🚀 Getting Started

#### 1. Clone the Repository
```bash
git clone https://github.com/your-username/evaluator.git
cd evaluator
```

#### 2. Set Up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure API Keys
Create a `.env` file in the root directory:
```text
GROQ_API_KEY=your_api_key_here
```

#### 5. Run the Application
```bash
streamlit run app.py
```

---

### 📂 Project Structure

*   `app.py`: Main Streamlit application and UI logic.
*   `ai_wrapper.py`: Integration with Groq LLM and system prompting.
*   `evaluator.py`: Logic for semantic similarity and intent scoring.
*   `utils.py`: Utility functions for PDF/Excel/PDF processing.
*   `tracing.py`: Arize Phoenix instrumentation and setup.
*   `.gitignore`: Pre-configured to ignore local logs and byte-code.

---

### 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Built with ❤️ for Operational Excellence.**
