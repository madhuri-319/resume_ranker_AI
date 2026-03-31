# Agent 03 — Candidate Search Agent

## Role
Accepts a natural language search query from an Admin and finds matching candidates
from the MongoDB `resumes` collection. Translates human intent into structured database
queries using an LLM to extract filters, then executes the query and returns matches.

---

## Triggered By
- **User Role**: Admin (Recruiter)
- **UI Action**: Admin enters a natural language prompt and clicks "Search"
- **Route Value**: `state["route"] = "search"`

---

## Inputs (from GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `search_query` | `str` | Natural language query from admin (e.g. "Java developer with 4 years experience") |

---

## Outputs (written to GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `matched_candidates` | `list[dict]` | List of candidate documents from MongoDB matching the query |
| `error` | `str` | Error message if search fails |

---

## Step-by-Step Logic

### Step 1 — Validate Input
```
- Check that search_query is non-empty string
- Check length > 3 characters
- If fails → set state["error"] = "Search query is empty", return early
```

### Step 2 — Parse Query Intent via LLM
```
Tool: llm_tools.py → call_llm(prompt)
Prompt Template: prompts.py → SEARCH_PARSE_PROMPT

Purpose:
  Convert the admin's natural language query into structured filter criteria
  that can be used to build a MongoDB query.

Input: state["search_query"]

Example Input:
  "Java developer with 4 years experience and Spring Boot knowledge"

Expected LLM JSON output:
{
  "required_skills": ["Java", "Spring Boot"],
  "preferred_skills": [],
  "min_experience_years": 4,
  "max_experience_years": null,
  "education_keywords": [],
  "role_keywords": ["developer", "engineer"],
  "certification_keywords": [],
  "free_text_keywords": ["Java", "Spring Boot", "developer"]
}

Parsing:
  - Strip JSON code fences
  - json.loads() to parse
  - If parsing fails → fall back to simple text search (Step 3b)
  - Store as local variable query_filters
```

### Step 3 — Build MongoDB Query

#### 3a. Structured Filter Query (when LLM parse succeeds)
```python
Build a MongoDB query dict combining multiple conditions with $and:

mongo_query = {"$and": []}

# Skills filter (at least one required skill must be in resume skills array)
if query_filters["required_skills"]:
    skills_regex = [re.compile(s, re.IGNORECASE) for s in query_filters["required_skills"]]
    mongo_query["$and"].append({
        "skills": {"$in": skills_regex}
    })

# Experience filter
if query_filters["min_experience_years"]:
    exp_filter = {"experience_years": {"$gte": query_filters["min_experience_years"]}}
    if query_filters.get("max_experience_years"):
        exp_filter["experience_years"]["$lte"] = query_filters["max_experience_years"]
    mongo_query["$and"].append(exp_filter)

# Free text search across raw_text (full-text index on MongoDB)
if query_filters["free_text_keywords"]:
    mongo_query["$and"].append({
        "$text": {"$search": " ".join(query_filters["free_text_keywords"])}
    })

# If no $and conditions were added, remove the key (match all)
if not mongo_query["$and"]:
    mongo_query = {}
```

#### 3b. Fallback: Simple Text Search (when LLM parse fails)
```python
# Uses MongoDB full-text index on raw_text field
mongo_query = {
    "$text": {"$search": state["search_query"]}
}
```

#### 3c. MongoDB Full-Text Index (Setup Note)
```
# Run once during database setup:
db.resumes.create_index([
    ("raw_text", "text"),
    ("skills", "text"),
    ("work_history.role", "text")
])
```

### Step 4 — Execute MongoDB Query
```
Tool: mongo_tools.py → search_candidates(query, limit)

- Execute query against "resumes" collection
- Projection: return all fields EXCEPT raw_text (too large for list view)
  projection = {"raw_text": 0}
- Sort: by ats_score descending (best matches first), then by uploaded_at descending
  sort = [("ats_score", -1), ("uploaded_at", -1)]
- Limit results to 50 (configurable via config.py)
- Convert ObjectId to string for each result

If query returns 0 results:
  - Try a relaxed fallback: drop experience filter, keep skills only
  - If still 0 → return empty list (not an error; handled in UI)

Store results in state["matched_candidates"]
```

### Step 5 — Post-Process Results
```
For each candidate in matched_candidates:
  - Ensure all ObjectId fields are converted to strings
  - Add a "match_score" field: int 0–100 based on how many filters matched
    (used for display ranking in UI and Excel report)
  - Format "uploaded_at" as human-readable date string: "Jan 15, 2024"

This post-processing makes results safe to serialize and display directly.
```

### Step 6 — Return State
```
- state["matched_candidates"] = list of cleaned candidate dicts
- If list is empty: this is NOT an error — UI handles the empty state message
- Return state
```

---

## Code Skeleton

```python
# agents/candidate_search_agent.py

from state.graph_state import GraphState
from tools.llm_tools import call_llm
from tools.mongo_tools import search_candidates
from utils.prompts import SEARCH_PARSE_PROMPT
import json, re

def candidate_search_agent(state: GraphState) -> GraphState:
    """
    Agent 3: Translates admin NLP query into MongoDB search, returns matched candidates.
    """
    search_query = state.get("search_query", "").strip()

    # Step 1: Validate
    if len(search_query) <= 3:
        state["error"] = "Search query is too short."
        return state

    # Step 2: Parse query intent
    query_filters = None
    try:
        parse_prompt = SEARCH_PARSE_PROMPT.format(search_query=search_query)
        raw = call_llm(parse_prompt)
        query_filters = json.loads(raw.strip().replace("```json","").replace("```",""))
    except Exception as e:
        print(f"[CandidateSearchAgent] LLM parse failed: {e}, using fallback")

    # Step 3: Build MongoDB query
    if query_filters:
        mongo_query = _build_structured_query(query_filters)
    else:
        mongo_query = {"$text": {"$search": search_query}}

    # Step 4: Execute
    try:
        results = search_candidates(mongo_query, limit=50)
    except Exception as e:
        state["error"] = f"Search failed: {str(e)}"
        return state

    # Step 5: Post-process
    state["matched_candidates"] = _post_process(results, query_filters)
    return state


def _build_structured_query(filters: dict) -> dict:
    conditions = []

    if filters.get("required_skills"):
        regexes = [re.compile(s, re.IGNORECASE) for s in filters["required_skills"]]
        conditions.append({"skills": {"$in": regexes}})

    if filters.get("min_experience_years"):
        exp = {"experience_years": {"$gte": filters["min_experience_years"]}}
        if filters.get("max_experience_years"):
            exp["experience_years"]["$lte"] = filters["max_experience_years"]
        conditions.append(exp)

    if filters.get("free_text_keywords"):
        conditions.append({"$text": {"$search": " ".join(filters["free_text_keywords"])}})

    return {"$and": conditions} if conditions else {}


def _post_process(candidates: list, filters: dict) -> list:
    results = []
    for c in candidates:
        c["_id"] = str(c["_id"])
        if "uploaded_at" in c:
            c["uploaded_at"] = c["uploaded_at"].strftime("%b %d, %Y")
        results.append(c)
    return results
```

---

## Prompt Template

```python
SEARCH_PARSE_PROMPT = """
You are an expert HR recruiter assistant. Parse the recruiter's search query
and extract structured search filters. Return ONLY a JSON object.

Search Query: "{search_query}"

Extract:
- required_skills: list of technical skills explicitly mentioned
- preferred_skills: list of nice-to-have skills (may be empty)
- min_experience_years: integer (null if not specified)
- max_experience_years: integer (null if not specified)
- education_keywords: list of education-related terms (e.g. "B.Tech", "MBA")
- role_keywords: list of job role terms (e.g. "developer", "analyst", "manager")
- certification_keywords: list of certifications mentioned
- free_text_keywords: 3-5 most important search terms for full-text search

JSON Output:
"""
```

---

## Query Examples

| Admin Input | Parsed Filters | MongoDB Conditions |
|---|---|---|
| "Java developer with 4 years experience" | skills: [Java], min_exp: 4 | skills in [Java], experience_years >= 4 |
| "ML engineer with Python and TensorFlow" | skills: [Python, TensorFlow], role: [engineer] | skills in both |
| "Senior React developer AWS certified" | skills: [React, AWS], certs: [AWS] | skills + certifications match |
| "Data analyst with SQL" | skills: [SQL], role: [analyst] | skills + text search |

---

## MongoDB Tools

```python
# tools/mongo_tools.py

def search_candidates(query: dict, limit: int = 50) -> list:
    collection = get_collection()
    projection = {"raw_text": 0}  # Exclude large text field
    sort = [("ats_score", -1), ("uploaded_at", -1)]
    cursor = collection.find(query, projection).sort(sort).limit(limit)
    return list(cursor)
```

---

## Error Scenarios & Handling

| Scenario | Behavior |
|----------|----------|
| Empty search query | Set error, return early |
| LLM parse fails | Fall back to raw text search |
| MongoDB text index not set up | Falls back to regex scan (slower, still works) |
| No candidates found | Return empty list, UI shows "No matches" message |
| MongoDB connection error | Set `state["error"]`, return state |

---

## Testing Checklist

- [ ] Search for a skill present in seeded test data (expect matches)
- [ ] Search for a non-existent skill (expect empty list, no error)
- [ ] Search with experience filter (e.g. "5+ years") → verify experience_years filter applied
- [ ] Test LLM parse failure by mocking → verify fallback text search runs
- [ ] Verify `_id` fields are strings (not ObjectId) in results
- [ ] Verify `uploaded_at` is formatted as human-readable string
- [ ] Test limit: seed 60+ candidates, verify max 50 returned
