
from mcp_layer.client import call_tool


print("\nTesting get_candidates...")

query_response = call_tool("get_candidates", {
    "filters": {
        "technical_skills.Programming Languages": "kotlin"
    }
})

print("Query Response:", query_response)