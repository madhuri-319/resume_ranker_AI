# 00 — System Overview

## Purpose

This document explains the full architecture of the ATS Multi-Agent System —
how agents connect, how state flows, and how each user role maps to a LangGraph path.

---

## Problem Being Solved

| Pain Point | Solution |
|---|---|
| Manual resume screening is slow | Resume Parser Agent automates structured extraction |
| Inconsistent scoring across recruiters | ATS Scorer Agent applies standardized LLM-based criteria |
| No candidate self-assessment tool | Employee-facing ATS score with improvement suggestions |
| Hard to search across stored resumes | Candidate Search Agent enables NLP natural-language queries |
| Exporting results is manual | Report Generator Agent produces ready-to-download Excel |

---

## User Roles

### Employee
An individual job-seeker or internal employee who:
- Uploads their resume PDF via the Streamlit UI
- Optionally requests an ATS score against a job description

### Admin (Recruiter)
An internal recruiter or HR admin who:
- Types a natural language search query (e.g. "Java developer 4 years")
- Receives a list of matching candidate profiles
- Downloads an Excel file with candidate info and resume paths

---

## LangGraph State (Shared Across All Agents)

All agents read from and write to a single `GraphState` TypedDict:

```python
class GraphState(TypedDict):
    # Routing
    route: str                        # "upload" | "score" | "search"
    user_role: str                    # "employee" | "admin"

    # Resume Parser
    raw_pdf_path: str                 # Uploaded file path
    raw_text: str                     # Extracted plain text from PDF
    parsed_resume: dict               # Structured resume fields (name, skills, etc.)
    mongo_doc_id: str                 # MongoDB _id after storage

    # ATS Scorer
    job_description: str              # JD provided by employee for scoring
    ats_score: int                    # Score 0-100
    ats_feedback: list[str]           # Bullet list of improvement suggestions
    ats_breakdown: dict               # Per-category scores

    # Candidate Search
    search_query: str                 # Admin's natural language prompt
    matched_candidates: list[dict]    # List of candidate docs from MongoDB

    # Report Generator
    excel_file_path: str              # Final output file path
    error: str                        # Any error messages
```

---

## LangGraph Graph Design

```
[START]
   │
   ▼
[router_node]  ◄── decides route from GraphState.route
   │
   ├── "upload" ──────► [resume_parser_agent]
   │                            │
   │                           [END]
   │
   ├── "score" ───────► [ats_scorer_agent]
   │                            │
   │                           [END]
   │
   └── "search" ──────► [candidate_search_agent]
                                │
                        [report_generator_agent]
                                │
                               [END]
```

### Why this structure?
- The three routes are **mutually exclusive** per request — no need to run all agents every time
- The `search → report` chain always runs together — search results must feed into the Excel report
- Each agent receives only the state fields it needs (reads selectively, writes selectively)

---

## Agent Responsibilities Summary

### Agent 1 — Resume Parser Agent
- **Input**: `raw_pdf_path`
- **Output**: `raw_text`, `parsed_resume`, `mongo_doc_id`
- **Key Actions**: Extract PDF text → LLM-parse into structured fields → Save to MongoDB

### Agent 2 — ATS Scorer Agent
- **Input**: `parsed_resume`, `job_description`
- **Output**: `ats_score`, `ats_feedback`, `ats_breakdown`
- **Key Actions**: Build scoring prompt → LLM evaluation → Parse structured response

### Agent 3 — Candidate Search Agent
- **Input**: `search_query`
- **Output**: `matched_candidates`
- **Key Actions**: Parse query intent → MongoDB query (text search + filters) → Return matching docs

### Agent 4 — Report Generator Agent
- **Input**: `matched_candidates`
- **Output**: `excel_file_path`
- **Key Actions**: Format candidate data → Generate styled Excel file → Return download path

---

## MongoDB Schema

### Collection: `resumes`

```json
{
  "_id": "ObjectId",
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["Python", "Java", "SQL"],
  "experience_years": 4,
  "education": [
    { "degree": "B.Tech", "field": "Computer Science", "institution": "NIT", "year": 2020 }
  ],
  "work_history": [
    { "company": "TCS", "role": "Software Engineer", "duration": "2 years", "technologies": ["Java", "Spring"] }
  ],
  "certifications": ["AWS Certified", "Oracle Java"],
  "resume_file_path": "/uploads/john_doe_resume.pdf",
  "raw_text": "Full extracted text...",
  "uploaded_at": "2024-01-15T10:30:00Z",
  "ats_score": 78
}
```

---

## Streamlit UI Flow

```
┌─────────────────────────────────────────────┐
│              Role Selection                  │
│         [Employee]     [Admin]               │
└─────────────────────────────────────────────┘

Employee View:                  Admin View:
┌──────────────────┐           ┌──────────────────────────┐
│ Upload Resume    │           │ Search Candidates        │
│ [File Upload]    │           │ [Text Input Prompt]      │
│                  │           │                          │
│ [Optional]       │           │ [Search Button]          │
│ Paste JD         │           │                          │
│                  │           │ Results Table            │
│ [Get ATS Score]  │           │                          │
│                  │           │ [Download Excel Button]  │
│ Score: 78/100    │           └──────────────────────────┘
│ Feedback list    │
└──────────────────┘
```

---

## Error Handling Strategy

Each agent should:
1. Wrap its main logic in `try/except`
2. Write any exception message to `state["error"]`
3. Return the modified state regardless
4. The Streamlit UI checks `state["error"]` and displays it to the user

---

## Environment Variables Required

```env
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/ats_db
OPENAI_API_KEY=sk-...
UPLOAD_DIR=./uploads
EXPORT_DIR=./exports
LLM_MODEL=gpt-4o
```
