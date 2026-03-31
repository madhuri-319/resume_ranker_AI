# Agent 02 — ATS Scorer Agent

## Role
Evaluates a parsed resume against a provided job description and returns a standardised
ATS score (0–100), a per-category breakdown, and actionable improvement suggestions.
This agent enables both employee self-assessment and recruiter screening consistency.

---

## Triggered By
- **User Role**: Employee
- **UI Action**: User provides a job description and clicks "Get ATS Score"
- **Route Value**: `state["route"] = "score"`
- **Prerequisite**: Resume must already be parsed (Agent 1 must have run, or `parsed_resume` pre-loaded from MongoDB)

---

## Inputs (from GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `parsed_resume` | `dict` | Structured resume data from Agent 1 or loaded from MongoDB |
| `job_description` | `str` | Raw JD text entered by employee in the Streamlit UI |

---

## Outputs (written to GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `ats_score` | `int` | Overall score from 0 to 100 |
| `ats_breakdown` | `dict` | Per-category scores (skills, experience, education, keywords) |
| `ats_feedback` | `list[str]` | Ordered list of improvement suggestions |
| `error` | `str` | Error message if scoring fails |

---

## Scoring Model

The ATS score is computed across **4 weighted categories**:

| Category | Weight | What is Measured |
|----------|--------|-----------------|
| **Skills Match** | 40% | Overlap between resume skills and JD required skills |
| **Experience Level** | 25% | Years of experience vs JD requirement |
| **Education** | 15% | Degree level and relevance to JD |
| **Keyword Coverage** | 20% | Presence of key JD terms in resume text |

**Final Score = Σ (category_score × weight)**

---

## Step-by-Step Logic

### Step 1 — Validate Inputs
```
- Check that parsed_resume is not empty dict
- Check that job_description is non-empty string (> 20 characters)
- If either fails → set state["error"], return early
```

### Step 2 — Extract JD Requirements via LLM
```
Tool: llm_tools.py → call_llm(prompt)
Prompt Template: prompts.py → JD_PARSE_PROMPT

Purpose: Convert raw JD text into structured requirements for comparison

Input: state["job_description"]

Expected LLM JSON output:
{
  "required_skills": ["Python", "Django", "REST APIs"],
  "preferred_skills": ["Docker", "Kubernetes"],
  "min_experience_years": 3,
  "education_requirement": "Bachelor's in Computer Science or related",
  "key_keywords": ["microservices", "agile", "CI/CD", "cloud"]
}

- Strip JSON code fences, parse with json.loads()
- Store as local variable jd_requirements
- If parsing fails → fall back to keyword-only scoring (see Step 4 fallback)
```

### Step 3 — Compute Per-Category Scores

#### 3a. Skills Match Score (0–100)
```
required_skills = jd_requirements["required_skills"]
preferred_skills = jd_requirements.get("preferred_skills", [])
resume_skills = [s.lower() for s in parsed_resume.get("skills", [])]

# Normalize to lowercase for comparison
required_lower = [s.lower() for s in required_skills]
preferred_lower = [s.lower() for s in preferred_skills]

matched_required = [s for s in required_lower if s in resume_skills]
matched_preferred = [s for s in preferred_lower if s in resume_skills]

# Required skills are worth more
required_score = len(matched_required) / max(len(required_lower), 1)
preferred_score = len(matched_preferred) / max(len(preferred_lower), 1)

skills_score = int((required_score * 0.8 + preferred_score * 0.2) * 100)
```

#### 3b. Experience Score (0–100)
```
resume_years = parsed_resume.get("experience_years", 0)
required_years = jd_requirements.get("min_experience_years", 0)

if required_years == 0:
    experience_score = 100  # No requirement = full marks
elif resume_years >= required_years:
    experience_score = 100
elif resume_years >= required_years * 0.75:
    experience_score = 75   # Close but under
elif resume_years >= required_years * 0.5:
    experience_score = 50
else:
    experience_score = 25
```

#### 3c. Education Score (0–100)
```
Use LLM sub-prompt to evaluate:
  "Does this education background: {parsed_resume['education']}
   meet this requirement: {jd_requirements['education_requirement']}?
   Rate 0, 50, 75, or 100. Return only the integer."

Parse the integer from response.
If LLM fails → default to 75
```

#### 3d. Keyword Coverage Score (0–100)
```
key_keywords = jd_requirements.get("key_keywords", [])
resume_full_text = state.get("raw_text", "").lower()
# Also check structured fields
resume_searchable = resume_full_text + " ".join(
    parsed_resume.get("skills", []) +
    [w["role"] for w in parsed_resume.get("work_history", [])]
).lower()

matched_keywords = [kw for kw in key_keywords if kw.lower() in resume_searchable]
keyword_score = int(len(matched_keywords) / max(len(key_keywords), 1) * 100)
```

### Step 4 — Compute Weighted Final Score
```
weights = {
    "skills": 0.40,
    "experience": 0.25,
    "education": 0.15,
    "keywords": 0.20
}

breakdown = {
    "skills": skills_score,
    "experience": experience_score,
    "education": education_score,
    "keywords": keyword_score
}

final_score = sum(breakdown[k] * weights[k] for k in weights)
state["ats_score"] = round(final_score)
state["ats_breakdown"] = breakdown
```

### Step 5 — Generate Improvement Feedback via LLM
```
Prompt Template: prompts.py → ATS_FEEDBACK_PROMPT

Build context for the prompt:
  - Score breakdown
  - Missing required skills
  - Missing keywords
  - Experience gap (if any)

Expected LLM output: JSON list of strings
[
  "Add these missing required skills to your resume: Docker, Kubernetes",
  "Your resume lacks 1 year of experience compared to the JD minimum of 4 years",
  "Include these keywords from the JD: microservices, CI/CD, agile",
  "Expand your education section to clarify your Computer Science background",
  "Consider adding a project section demonstrating REST API development"
]

- Parse the list with json.loads()
- Store in state["ats_feedback"]
```

### Step 6 — Optionally Update MongoDB
```
If state["mongo_doc_id"] is present:
  - Update the existing resume document with:
    { "$set": { "ats_score": state["ats_score"] } }
  
This allows the admin to later search/sort by ATS score
```

### Step 7 — Return State
```
Return updated GraphState with all scoring fields populated
```

---

## Code Skeleton

```python
# agents/ats_scorer_agent.py

from state.graph_state import GraphState
from tools.llm_tools import call_llm
from tools.mongo_tools import update_ats_score
from utils.prompts import JD_PARSE_PROMPT, ATS_FEEDBACK_PROMPT
import json

def ats_scorer_agent(state: GraphState) -> GraphState:
    """
    Agent 2: Scores resume against JD and returns structured feedback.
    """
    parsed_resume = state.get("parsed_resume", {})
    job_description = state.get("job_description", "")

    # Step 1: Validate
    if not parsed_resume:
        state["error"] = "No parsed resume found. Please upload a resume first."
        return state
    if len(job_description.strip()) < 20:
        state["error"] = "Job description is too short to score against."
        return state

    # Step 2: Extract JD requirements
    try:
        jd_prompt = JD_PARSE_PROMPT.format(job_description=job_description)
        jd_raw = call_llm(jd_prompt)
        jd_requirements = json.loads(jd_raw.strip().replace("```json","").replace("```",""))
    except Exception as e:
        print(f"[ATSScorerAgent] JD parse failed: {e}, using keyword fallback")
        jd_requirements = {"required_skills": [], "min_experience_years": 0,
                           "key_keywords": [], "education_requirement": ""}

    # Step 3: Score each category
    skills_score    = _score_skills(parsed_resume, jd_requirements)
    experience_score = _score_experience(parsed_resume, jd_requirements)
    education_score = _score_education(parsed_resume, jd_requirements)
    keyword_score   = _score_keywords(state, jd_requirements)

    # Step 4: Weighted total
    breakdown = {
        "skills": skills_score,
        "experience": experience_score,
        "education": education_score,
        "keywords": keyword_score
    }
    weights = {"skills": 0.40, "experience": 0.25, "education": 0.15, "keywords": 0.20}
    state["ats_score"] = round(sum(breakdown[k] * weights[k] for k in weights))
    state["ats_breakdown"] = breakdown

    # Step 5: Feedback
    try:
        feedback_prompt = ATS_FEEDBACK_PROMPT.format(
            breakdown=json.dumps(breakdown),
            resume=json.dumps(parsed_resume),
            jd_requirements=json.dumps(jd_requirements),
            final_score=state["ats_score"]
        )
        feedback_raw = call_llm(feedback_prompt)
        state["ats_feedback"] = json.loads(feedback_raw.strip().replace("```json","").replace("```",""))
    except Exception as e:
        state["ats_feedback"] = ["Could not generate detailed feedback. Please review the score breakdown."]

    # Step 6: Update MongoDB
    if state.get("mongo_doc_id"):
        try:
            update_ats_score(state["mongo_doc_id"], state["ats_score"])
        except Exception:
            pass  # Non-fatal

    return state
```

---

## Prompt Templates

```python
JD_PARSE_PROMPT = """
You are an expert HR analyst. Parse the job description below and return ONLY a JSON object.

Extract:
- required_skills: list of explicitly required technical skills
- preferred_skills: list of nice-to-have/preferred skills
- min_experience_years: integer (0 if not specified)
- education_requirement: string describing degree/field requirement
- key_keywords: list of important domain/industry terms from the JD

Job Description:
\"\"\"
{job_description}
\"\"\"

JSON Output:
"""

ATS_FEEDBACK_PROMPT = """
You are an expert career coach. Based on the ATS scoring below, generate a list of
specific, actionable improvement suggestions for the candidate.

Resume Data: {resume}
JD Requirements: {jd_requirements}
Score Breakdown: {breakdown}
Final Score: {final_score}/100

Return ONLY a JSON array of 4-6 improvement suggestions as strings.
Each suggestion should be specific, actionable, and reference concrete missing items.
Order from highest-impact to lowest-impact.

JSON Array Output:
"""
```

---

## Output Examples

### Score Breakdown
```json
{
  "skills": 75,
  "experience": 100,
  "education": 75,
  "keywords": 60
}
```

### ATS Feedback
```json
[
  "Add missing required skills to your resume: Docker, Kubernetes, CI/CD pipelines",
  "Include these high-priority JD keywords: microservices, REST API, agile methodology",
  "Your experience level meets the JD requirement — highlight specific achievements per role",
  "Clarify your education section to explicitly mention Computer Science or related field",
  "Consider adding a 'Projects' section showcasing cloud or containerization experience"
]
```

---

## Error Scenarios & Handling

| Scenario | Behavior |
|----------|----------|
| `parsed_resume` is empty | Set error, return early |
| JD is too short | Set error, return early |
| JD parse LLM fails | Use empty defaults, continue with partial scoring |
| Education LLM sub-call fails | Default education score to 75 |
| Feedback LLM fails | Set generic fallback feedback message |
| MongoDB update fails | Log silently, continue (non-fatal) |

---

## Testing Checklist

- [ ] Score a strong matching resume → expect 80–100
- [ ] Score a weak/unrelated resume → expect < 40
- [ ] Test with missing `experience_years` in parsed_resume
- [ ] Test with empty job description (expect error)
- [ ] Test with JD that has no skills listed (expect graceful fallback)
- [ ] Verify all 4 category scores appear in breakdown
- [ ] Verify feedback list has 4–6 items
- [ ] Verify MongoDB document `ats_score` field is updated
