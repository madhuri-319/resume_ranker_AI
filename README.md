# ATS Multi-Agent System — LangGraph + Streamlit

## Overview

An AI-powered Applicant Tracking System (ATS) that automates resume parsing, scoring,
candidate storage, and intelligent search using a multi-agent LangGraph workflow.

---

## Project Structure

```
ats-langgraph/
│
├── main.py                        # LangGraph graph builder & entry point
├── streamlit_app.py               # Streamlit UI (Employee & Admin roles)
├── config.py                      # Environment variables, MongoDB URI, model config
├── requirements.txt
│
├── state/
│   └── graph_state.py             # Shared TypedDict state across all agents
│
├── agents/
│   ├── resume_parser_agent.py     # Agent 1: Parses and stores resumes
│   ├── ats_scorer_agent.py        # Agent 2: Scores resume against ATS criteria
│   ├── candidate_search_agent.py  # Agent 3: NLP-based candidate search
│   └── report_generator_agent.py  # Agent 4: Generates Excel export for admin
│
├── tools/
│   ├── pdf_extractor.py           # PyMuPDF / pdfplumber text extraction
│   ├── mongo_tools.py             # MongoDB CRUD operations
│   ├── excel_tools.py             # openpyxl Excel file generation
│   └── llm_tools.py               # LLM call wrappers (OpenAI / Anthropic)
│
├── utils/
│   ├── prompts.py                 # All LLM prompt templates
│   └── validators.py             # Input/output validators
│
└── docs/
    └── agents/
        ├── 00_SYSTEM_OVERVIEW.md
        ├── 01_resume_parser_agent.md
        ├── 02_ats_scorer_agent.md
        ├── 03_candidate_search_agent.md
        └── 04_report_generator_agent.md
```

---

## Agent Overview

| # | Agent | Role | Triggered By |
|---|-------|------|--------------|
| 1 | **Resume Parser Agent** | Extracts structured data from PDF and stores to MongoDB | Employee uploads resume |
| 2 | **ATS Scorer Agent** | Scores resume against job criteria, returns feedback | Employee requests ATS score |
| 3 | **Candidate Search Agent** | NLP search over MongoDB candidates | Admin enters search prompt |
| 4 | **Report Generator Agent** | Creates Excel file with matched candidates | After search completes |

---

## Graph Flow

```
[START]
   │
   ├──(route: "upload")──► [Resume Parser Agent] ──► [END]
   │
   ├──(route: "score")───► [ATS Scorer Agent] ──────► [END]
   │
   └──(route: "search")──► [Candidate Search Agent] ──► [Report Generator Agent] ──► [END]
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph |
| UI | Streamlit |
| LLM | OpenAI GPT-4o / Claude 3.5 |
| Database | MongoDB Atlas |
| PDF Parsing | pdfplumber + PyMuPDF |
| Excel Export | openpyxl |
| Embeddings (optional) | OpenAI text-embedding-3-small |

---

## Setup

```bash
pip install -r requirements.txt

# Set environment variables
export MONGODB_URI="mongodb+srv://..."
export OPENAI_API_KEY="sk-..."

# Run the app
streamlit run streamlit_app.py
```
