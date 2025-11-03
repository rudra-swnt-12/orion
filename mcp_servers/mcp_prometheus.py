import json
from mcp.server.fastmcp import FastMCP
from prometheus_api_client import PrometheusConnect
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

PROMETHEUS_URL = "http://localhost:9090"

mcp = FastMCP(name="prometheus_server")
log.info("Starting Prometheus MCP Server")
log.info(f"Attempting to connect to Prometheus at {PROMETHEUS_URL}")


@mcp.tool()
def query_prometheus(query: str) -> str:
    log.info(f"Received query: {query}")
    try:
        # Connect to the Prometheus service (running in Docker)
        prom_client = PrometheusConnect(url=PROMETHEUS_URL, disable_ssl=True)
        result = prom_client.custom_query(query=query)
        if not result:
            log.warning("Query returned no data.")
            return "Query successful, but returned no data."

        # Convert the Python list/dict result into a string
        # so the LLM can easily read it.
        result_str = json.dumps(result, indent=2)
        log.info(f"Query successful. Returning result (length: {len(result_str)})")
        return result_str

    except Exception as e:
        log.error(f"Error while running query '{query}': {e}")
        # Return the error message to the LLM so it knows it failed
        return f"Error: Could not execute query. {e}"


if __name__ == "__main__":
    mcp.run()
