from mcp_layer.tools.mongo_mcp_tools import get_candidates, store_resume


TOOL_REGISTRY = {
    "store_resume": store_resume,
    "get_candidates": get_candidates
}

def handle_request(tool_name: str, payload: dict):
    """
    Central MCP handler
    """

    if tool_name not in TOOL_REGISTRY:
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' not found"
        }
    
    try:
        result = TOOL_REGISTRY[tool_name](payload)
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }