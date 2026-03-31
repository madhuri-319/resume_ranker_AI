# Agent 04 — Report Generator Agent

## Role
Takes the list of matched candidates from Agent 3 and produces a styled, downloadable
Excel (.xlsx) file. This is the final step in the Admin search flow, giving recruiters
a professional, ready-to-share report with candidate data and resume paths.

---

## Triggered By
- **Always runs after Agent 3** (Candidate Search Agent)
- **Route**: `search → candidate_search_agent → report_generator_agent → END`
- **Condition**: Runs regardless of whether matched_candidates is empty (generates empty report with headers)

---

## Inputs (from GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `matched_candidates` | `list[dict]` | List of candidate documents from MongoDB (post-processed) |
| `search_query` | `str` | Original admin query — used in the report header/filename |

---

## Outputs (written to GraphState)

| Field | Type | Description |
|-------|------|-------------|
| `excel_file_path` | `str` | Absolute path to the generated `.xlsx` file |
| `error` | `str` | Error message if file generation fails |

---

## Excel Report Structure

### Sheet: "Candidates"

| Column | Source Field | Notes |
|--------|-------------|-------|
| # | row index | 1-based row number |
| Candidate Name | `candidate_name` | |
| Email | `email` | Hyperlink formatted |
| Phone | `phone` | |
| Skills | `skills` | Join list as comma-separated string |
| Experience (Years) | `experience_years` | Integer |
| Education | `education` | "Degree, Institution (Year)" per entry, newline separated |
| ATS Score | `ats_score` | Colored cell: green ≥70, yellow 50–69, red <50 |
| Current Role | `work_history[0].role` | Most recent role |
| Current Company | `work_history[0].company` | Most recent company |
| Certifications | `certifications` | Comma-separated |
| Resume Path | `resume_file_path` | Relative path to PDF |
| Uploaded On | `uploaded_at` | Formatted date string |

### Sheet: "Search Summary"
```
Search Query    : Java developer with 4 years experience
Generated On    : March 30, 2024 at 14:22
Total Matches   : 12
Exported By     : ATS System
```

---

## Step-by-Step Logic

### Step 1 — Validate Inputs
```
- Check that matched_candidates is a list (may be empty — not an error)
- Check that search_query is non-empty
- Ensure the export directory exists (create if not)
  export_dir = os.environ.get("EXPORT_DIR", "./exports")
  os.makedirs(export_dir, exist_ok=True)
```

### Step 2 — Generate Output Filename
```python
from datetime import datetime
import re

# Sanitize query for filename
safe_query = re.sub(r"[^a-zA-Z0-9_]", "_", search_query)[:40]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"candidates_{safe_query}_{timestamp}.xlsx"
output_path = os.path.join(export_dir, filename)
```

### Step 3 — Create Excel Workbook
```
Tool: excel_tools.py → generate_candidates_excel(candidates, search_query, output_path)

Library: openpyxl

Workbook setup:
  wb = Workbook()
  ws_candidates = wb.active
  ws_candidates.title = "Candidates"
  ws_summary = wb.create_sheet("Search Summary")
```

### Step 4 — Style the Header Row
```python
# Header row styling
header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
header_font = Font(bold=True, color="FFFFFF", size=11)
header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

HEADERS = [
    "#", "Candidate Name", "Email", "Phone", "Skills",
    "Experience (Years)", "Education", "ATS Score",
    "Current Role", "Current Company", "Certifications",
    "Resume Path", "Uploaded On"
]

for col_idx, header in enumerate(HEADERS, 1):
    cell = ws_candidates.cell(row=1, column=col_idx, value=header)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = header_alignment

# Freeze header row
ws_candidates.freeze_panes = "A2"
```

### Step 5 — Write Candidate Rows
```python
for row_idx, candidate in enumerate(matched_candidates, start=2):
    
    # Helper to safely get field
    def get(field, default="N/A"):
        val = candidate.get(field, default)
        return val if val is not None else default
    
    # Format education
    education_lines = []
    for edu in candidate.get("education", []):
        line = f"{edu.get('degree','')} in {edu.get('field','')} — {edu.get('institution','')} ({edu.get('year','')})"
        education_lines.append(line)
    education_str = "\n".join(education_lines) or "N/A"

    # Most recent work
    work = candidate.get("work_history", [{}])
    recent_role = work[0].get("role", "N/A") if work else "N/A"
    recent_company = work[0].get("company", "N/A") if work else "N/A"

    row_data = [
        row_idx - 1,                                      # #
        get("candidate_name"),                            # Name
        get("email"),                                     # Email
        get("phone"),                                     # Phone
        ", ".join(candidate.get("skills", [])) or "N/A", # Skills
        get("experience_years", 0),                       # Experience
        education_str,                                    # Education
        get("ats_score", ""),                             # ATS Score
        recent_role,                                      # Current Role
        recent_company,                                   # Current Company
        ", ".join(candidate.get("certifications", [])) or "N/A",  # Certs
        get("resume_file_path"),                          # Resume Path
        get("uploaded_at"),                               # Uploaded On
    ]

    for col_idx, value in enumerate(row_data, 1):
        cell = ws_candidates.cell(row=row_idx, column=col_idx, value=value)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        
        # Alternate row background
        if row_idx % 2 == 0:
            cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    
    # ATS Score color coding (column 8)
    score_cell = ws_candidates.cell(row=row_idx, column=8)
    score = candidate.get("ats_score", 0) or 0
    if score >= 70:
        score_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        score_cell.font = Font(color="276221", bold=True)
    elif score >= 50:
        score_cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
        score_cell.font = Font(color="9C6500", bold=True)
    elif score > 0:
        score_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        score_cell.font = Font(color="9C0006", bold=True)
```

### Step 6 — Set Column Widths
```python
COLUMN_WIDTHS = {
    "A": 5,   # #
    "B": 22,  # Name
    "C": 28,  # Email
    "D": 16,  # Phone
    "E": 40,  # Skills
    "F": 12,  # Experience
    "G": 45,  # Education
    "H": 12,  # ATS Score
    "I": 25,  # Role
    "J": 25,  # Company
    "K": 30,  # Certifications
    "L": 40,  # Resume Path
    "M": 15,  # Uploaded On
}

for col_letter, width in COLUMN_WIDTHS.items():
    ws_candidates.column_dimensions[col_letter].width = width

# Set row height for header
ws_candidates.row_dimensions[1].height = 30
```

### Step 7 — Write Search Summary Sheet
```python
summary_data = [
    ("Search Query", search_query),
    ("Generated On", datetime.now().strftime("%B %d, %Y at %H:%M")),
    ("Total Matches", len(matched_candidates)),
    ("Exported By", "ATS Multi-Agent System"),
]

for row_idx, (label, value) in enumerate(summary_data, start=2):
    ws_summary.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
    ws_summary.cell(row=row_idx, column=2, value=value)

ws_summary.column_dimensions["A"].width = 20
ws_summary.column_dimensions["B"].width = 50
```

### Step 8 — Save and Return
```python
wb.save(output_path)
state["excel_file_path"] = output_path
```

---

## Code Skeleton

```python
# agents/report_generator_agent.py

from state.graph_state import GraphState
from tools.excel_tools import generate_candidates_excel
import os, re
from datetime import datetime

def report_generator_agent(state: GraphState) -> GraphState:
    """
    Agent 4: Generates styled Excel report of matched candidates for admin download.
    """
    matched_candidates = state.get("matched_candidates", [])
    search_query = state.get("search_query", "search")

    # Step 1: Ensure export dir
    export_dir = os.environ.get("EXPORT_DIR", "./exports")
    os.makedirs(export_dir, exist_ok=True)

    # Step 2: Generate filename
    safe_query = re.sub(r"[^a-zA-Z0-9_]", "_", search_query)[:40]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"candidates_{safe_query}_{timestamp}.xlsx"
    output_path = os.path.join(export_dir, filename)

    # Step 3-8: Generate Excel
    try:
        generate_candidates_excel(matched_candidates, search_query, output_path)
        state["excel_file_path"] = output_path
    except Exception as e:
        state["error"] = f"Excel generation failed: {str(e)}"

    return state
```

---

## Streamlit Download Integration

```python
# In streamlit_app.py — after graph execution

if state.get("excel_file_path"):
    with open(state["excel_file_path"], "rb") as f:
        st.download_button(
            label=f"📥 Download Results ({len(state['matched_candidates'])} candidates)",
            data=f.read(),
            file_name=os.path.basename(state["excel_file_path"]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
```

---

## Error Scenarios & Handling

| Scenario | Behavior |
|----------|----------|
| `matched_candidates` is empty | Generate Excel with headers only, no rows |
| Export directory missing | Create it automatically with `os.makedirs` |
| Disk write permission error | Set `state["error"]`, return state |
| Corrupt candidate data (missing fields) | Use `"N/A"` as default for all missing fields |
| Very large result set (50 candidates) | openpyxl handles this; no chunking needed |

---

## Testing Checklist

- [ ] Generate report with 0 candidates (expect file with headers only)
- [ ] Generate report with 10 candidates (verify all rows populated)
- [ ] Verify ATS score color coding: green/yellow/red
- [ ] Verify "Search Summary" sheet populated correctly
- [ ] Verify column widths and frozen header row
- [ ] Verify filename includes sanitized query and timestamp
- [ ] Test with candidate missing optional fields (education, certifications)
- [ ] Verify Streamlit download button returns valid .xlsx file
