
from mcp_layer.server import handle_request


def call_tool(tool_name: str, payload: dict):
    """
    Client interface used by agents
    """

    response = handle_request(tool_name, payload)

    if response.get("status") == "error":
        raise Exception(response["message"])
    
    return response["data"]