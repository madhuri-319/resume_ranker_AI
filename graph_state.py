from typing import TypedDict, Optional

class GraphState(TypedDict, total=False):
    # Routing
    route: str                        # "upload" | "score" | "search"
    user_role: str                    # "employee" | "admin"

    # Resume Parser Agent
    raw_pdf_path: str
    raw_text: str
    parsed_resume: dict
    mongo_doc_id: str

    # ATS Scorer Agent
    job_description: str
    ats_score: int
    ats_feedback: list
    ats_breakdown: dict

    # Candidate Search Agent
    search_query: str
    matched_candidates: list

    # Report Generator Agent
    excel_file_path: str

    # Error handling
    error: str
