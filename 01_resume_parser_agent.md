# Agent 01 — Resume Parser Agent

## Role
Extracts structured information from an uploaded resume PDF and persists it to MongoDB.
This is the foundational agent — all other agents depend on the data it creates.

---

## Triggered By
- **User Role**: Employee
- **UI Action**: User uploads a `.pdf` resume file
- **Route Value**: `state["route"] = "upload"`

---

## Inputs (from GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `raw_pdf_path` | `str` | Absolute path to the uploaded PDF file on disk |

---

## Outputs (written to GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `raw_text` | `str` | Full plain text extracted from the PDF |
| `parsed_resume` | `dict` | Structured candidate data (name, skills, experience, etc.) |
| `mongo_doc_id` | `str` | MongoDB `_id` string of the inserted document |
| `error` | `str` | Error message if any step fails (empty string on success) |

---

## Step-by-Step Logic

### Step 1 — Validate Input File
```
- Check that raw_pdf_path exists on disk
- Check file extension is .pdf
- Check file size is > 0 bytes and < 10MB
- If any check fails → write error to state["error"] and return early
```

### Step 2 — Extract Raw Text from PDF
```
Tool: pdf_extractor.py → extract_text_from_pdf(path)

- Use pdfplumber as primary extractor
  - Open PDF
  - Iterate all pages
  - Concatenate page.extract_text() for each page
  - Strip excess whitespace and normalize line breaks

- Fallback to PyMuPDF (fitz) if pdfplumber returns empty text
  - Open with fitz.open(path)
  - Iterate pages with page.get_text("text")

- If both return empty text:
  - Set state["error"] = "Could not extract text from PDF. It may be a scanned image."
  - Return early (do not proceed to LLM)

- Store result in state["raw_text"]
```

### Step 3 — LLM Structured Extraction
```
Tool: llm_tools.py → call_llm(prompt, model)
Prompt Template: prompts.py → RESUME_PARSE_PROMPT

Build the prompt:
  - System: "You are a resume parser. Extract structured information in JSON format only."
  - User: f"Parse this resume:\n\n{state['raw_text']}"

Expected LLM JSON output schema:
{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["skill1", "skill2"],
  "experience_years": int,
  "education": [
    {
      "degree": "string",
      "field": "string",
      "institution": "string",
      "year": int
    }
  ],
  "work_history": [
    {
      "company": "string",
      "role": "string",
      "duration": "string",
      "technologies": ["tech1", "tech2"]
    }
  ],
  "certifications": ["cert1", "cert2"],
  "summary": "string"
}

Parsing the LLM response:
  - Strip markdown code fences if present (```json ... ```)
  - Parse with json.loads()
  - If JSON parsing fails → log warning, store raw_text only, set parsed_resume = {}
  - If parsing succeeds → store in state["parsed_resume"]
```

### Step 4 — Save to MongoDB
```
Tool: mongo_tools.py → insert_resume(document)

Build the final MongoDB document:
{
  ...state["parsed_resume"],               # All LLM-extracted fields
  "raw_text": state["raw_text"],           # Full text for search
  "resume_file_path": state["raw_pdf_path"],
  "uploaded_at": datetime.utcnow(),
  "ats_score": None                        # Filled later by ATS Scorer Agent
}

- Insert to collection: "resumes"
- Capture inserted_id and convert to string
- Store in state["mongo_doc_id"]

If insert fails:
  - Set state["error"] = f"Database error: {str(e)}"
  - Return state without crashing
```

### Step 5 — Return State
```
- Return the full updated GraphState
- On success: raw_text, parsed_resume, and mongo_doc_id are all populated
- On failure: error field is non-empty, other fields may be partial
```

---

## Code Skeleton

```python
# agents/resume_parser_agent.py

from state.graph_state import GraphState
from tools.pdf_extractor import extract_text_from_pdf
from tools.llm_tools import call_llm
from tools.mongo_tools import insert_resume
from utils.prompts import RESUME_PARSE_PROMPT
import json
import os

def resume_parser_agent(state: GraphState) -> GraphState:
    """
    Agent 1: Parses resume PDF and stores structured data in MongoDB.
    """
    pdf_path = state.get("raw_pdf_path", "")

    # Step 1: Validate
    if not pdf_path or not os.path.exists(pdf_path):
        state["error"] = f"File not found: {pdf_path}"
        return state

    # Step 2: Extract text
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text.strip():
        state["error"] = "PDF text extraction failed. File may be image-based."
        return state
    state["raw_text"] = raw_text

    # Step 3: LLM parse
    try:
        prompt = RESUME_PARSE_PROMPT.format(resume_text=raw_text)
        llm_response = call_llm(prompt)
        clean = llm_response.strip().replace("```json", "").replace("```", "")
        state["parsed_resume"] = json.loads(clean)
    except Exception as e:
        state["parsed_resume"] = {}
        # Non-fatal: still proceed to store raw text
        print(f"[ResumeParserAgent] LLM parse warning: {e}")

    # Step 4: Store in MongoDB
    try:
        doc_id = insert_resume(state)
        state["mongo_doc_id"] = str(doc_id)
    except Exception as e:
        state["error"] = f"MongoDB insert failed: {str(e)}"

    return state
```

---

## Prompt Template

```
# utils/prompts.py

RESUME_PARSE_PROMPT = """
You are an expert resume parser.

Extract all relevant information from the resume text below and return ONLY a valid JSON object.
Do not include any explanation, markdown, or code fences — only raw JSON.

Expected fields:
- candidate_name (string)
- email (string)
- phone (string)
- skills (list of strings)
- experience_years (integer, total years of work experience)
- education (list of objects with: degree, field, institution, year)
- work_history (list of objects with: company, role, duration, technologies)
- certifications (list of strings)
- summary (1-2 sentence professional summary)

Resume Text:
\"\"\"
{resume_text}
\"\"\"

JSON Output:
"""
```

---

## Tools Used

### `pdf_extractor.py`
```python
import pdfplumber
import fitz  # PyMuPDF

def extract_text_from_pdf(path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        pass

    if not text.strip():
        # Fallback to PyMuPDF
        try:
            doc = fitz.open(path)
            for page in doc:
                text += page.get_text("text") + "\n"
        except Exception:
            pass

    return text.strip()
```

### `mongo_tools.py → insert_resume`
```python
from pymongo import MongoClient
from datetime import datetime
import os

def get_collection():
    client = MongoClient(os.environ["MONGODB_URI"])
    db = client["ats_db"]
    return db["resumes"]

def insert_resume(state: dict) -> str:
    collection = get_collection()
    doc = {
        **state.get("parsed_resume", {}),
        "raw_text": state.get("raw_text", ""),
        "resume_file_path": state.get("raw_pdf_path", ""),
        "uploaded_at": datetime.utcnow(),
        "ats_score": None
    }
    result = collection.insert_one(doc)
    return result.inserted_id
```

---

## Error Scenarios & Handling

| Scenario | Behavior |
|----------|----------|
| File path is empty or missing | Set `state["error"]`, return early |
| PDF is scanned/image-only | Set `state["error"]`, return early |
| LLM returns invalid JSON | Log warning, set `parsed_resume = {}`, continue to MongoDB step |
| MongoDB connection fails | Set `state["error"]`, return state |
| PDF has mixed text + images | Extract text portions, silently skip image pages |

---

## Testing Checklist

- [ ] Upload a standard text-based PDF resume
- [ ] Upload a scanned image PDF (expect graceful error)
- [ ] Upload a multi-page resume (verify all pages extracted)
- [ ] Simulate MongoDB failure (expect error in state)
- [ ] Verify MongoDB document contains all expected fields
- [ ] Verify `mongo_doc_id` is returned and valid ObjectId string
