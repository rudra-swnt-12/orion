import json
import requests
from mcp.server.fastmcp import FastMCP
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

LOKI_URL = "http://localhost:3100"

mcp = FastMCP(name="loki_server")
log.info("Starting Loki MCP Server...")
log.info(f"Connecting to Loki at {LOKI_URL}")

@mcp.tool()
def query_loki(log_query: str) -> str:
    log.info(f"Received LogQL query: {log_query}")
    api_endpoint = f"{LOKI_URL}/loki/api/v1/query_range"
    params = {
        'query': log_query,
        # We'll just query the last 5 minutes to keep it fast
        'limit': 50 
    }
    try:
        # --- 3. The Tool's Logic ---
        response = requests.get(api_endpoint, params=params)
        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
        result_data = response.json()
        if not result_data.get('data', {}).get('result'):
            log.warning("Query returned no data.")
            return "Query successful, but returned no log data."
        
        # Convert the Python dict result into a JSON string
        result_str = json.dumps(result_data['data']['result'], indent=2)
        log.info(f"Query successful. Returning result (length: {len(result_str)})")
        return result_str

    except Exception as e:
        log.error(f"Error while running query '{log_query}': {e}")
        return f"Error: Could not execute query. {e}"

if __name__ == "__main__":
    mcp.run()