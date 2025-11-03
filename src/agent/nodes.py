import logging
import sys
import json
import re
import asyncio
from typing import List, Dict, Any
from pydantic import TypeAdapter
from llama_index.core import PromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from fastmcp import Client as McpClient  # This is the correct high-level client
from fastmcp.client.transports import StdioTransport
from src.brain.engine import get_query_engine, Settings
from src.agent.state import OrionState, Hypothesis, HypothesisList

log = logging.getLogger(__name__)

def expand_hypotheses(state: OrionState) -> OrionState:
    """
    The first node in the graph. It uses the "Brain" (RAG) to
    generate initial hypotheses for the "Tree of Thoughts."
    """
    log.info(f"--- 🧠 EXPANDING on Alert: '{state.initial_alert}' ---")
    
    query_engine = get_query_engine()
    rag_context_str = str(query_engine.query(state.initial_alert))
    log.info(f"Got RAG context: {rag_context_str[:150]}...")

    # --- 2. Generate Hypotheses (LLM) ---
    
    # We ask for a JSON *list* since that's what the LLM is giving us.
    system_prompt_str = f"""
    You are a 'Tree of Thoughts' agent designed to find the root cause of a system alert.
    You must generate a list of 2-3 distinct hypotheses to investigate.
    For each hypothesis, list the specific tool calls required to test it.
    
    **IMPORTANT QUERY RULES:**
    1.  **Loki queries** (for `query_loki`) MUST be valid LogQL: `{{job="<service_name>"}} |= "<log_message_to_find>"`
    2.  **Prometheus queries** (for `query_prometheus`) MUST be valid PromQL.
    3.  The service name for our app is `fake_app`.
    4.  Functions like `rate()`, `increase()`, and `sum_over_time()` MUST use a range vector (e.g., `[1m]` or `[5m]`).
    
    **Your response MUST be *only* a valid JSON list of `Hypothesis` objects.**
    
    Here is the JSON schema for a *single Hypothesis* you *must* follow:
    {Hypothesis.model_json_schema()}
    """
    
    user_prompt_str = f"""
    Here is the user's alert:
    "{state.initial_alert}"
    
    Here is the context I found in the knowledge base:
    "{rag_context_str}"
    
    Please generate the JSON list of `Hypothesis` objects based on this information.
    """
    
    prompt_messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt_str),
        ChatMessage(role=MessageRole.USER, content=user_prompt_str)
    ]
    
    raw_json_str = "" # Initialize
    json_to_parse = "" # Initialize
    try:
        # 1. Call the LLM
        log.info("Calling LLM to generate hypotheses (manual JSON)...")
        response = Settings.llm.chat(prompt_messages)
        
        # 2. Get the raw text
        raw_json_str = response.message.content
        log.info(f"Raw LLM output: {raw_json_str}")

        # 3. Find all JSON blocks
        json_blocks = re.findall(r"```json\n(.*?)\n```", raw_json_str, re.DOTALL)
        
        if not json_blocks:
            log.info("No markdown blocks found. Assuming raw JSON output.")
            json_to_parse = raw_json_str.strip()
        else:
            log.info(f"Found {len(json_blocks)} JSON blocks. Parsing the last one.")
            json_to_parse = json_blocks[-1].strip()
            
        # 4. --- THIS IS THE FIX ---
        # We use a TypeAdapter to parse a LIST of Hypothesis objects
        # This will also use the aliases we defined in state.py
        adapter = TypeAdapter(List[Hypothesis])
        parsed_list = adapter.validate_json(json_to_parse)
        
        state.hypotheses = parsed_list
        log.info(f"Generated {len(state.hypotheses)} new hypotheses.")
        
    except Exception as e:
        log.error(f"Failed to generate and parse structured hypotheses: {e}")
        if json_to_parse:
            log.error(f"JSON that failed parsing: {json_to_parse}")
        elif raw_json_str:
            log.error(f"Raw LLM output that failed: {raw_json_str}")
        state.hypotheses = []

    return state

async def run_tool(tool_call: "ToolCall") -> str:
    """
    A helper function to connect to a specific MCP server and run a tool.
    This is what connects the agent to the "Hands".
    """
    command_to_run = []
    tool_args = {}

    if tool_call.tool_name == "query_prometheus":
        command_to_run = ["uv", "run", "mcp_servers/mcp_prometheus.py"]
        # Prometheus server's tool function expects an arg named 'query'
        tool_args = {"query": tool_call.tool_input} 
    elif tool_call.tool_name == "query_loki":
        command_to_run = ["uv", "run", "mcp_servers/mcp_loki.py"]
        # Loki server's tool function expects an arg named 'log_query'
        tool_args = {"log_query": tool_call.tool_input}
    else:
        return f"Error: Unknown tool '{tool_call.tool_name}'"

    try:
        log.info(f"Running command: {' '.join(command_to_run)}")
        # 1. Create the StdioTransport configuration
        # This tells the client *how* to start the server
        transport = StdioTransport(
            command=command_to_run[0], # "uv"
            args=command_to_run[1:],   # ["run", "mcp_servers/mcp_loki.py"]
        )
        
        # 2. Connect to the MCP server process using the transport
        async with McpClient(transport) as client:
            log.info(f"Calling tool: {tool_call.tool_name} with input: {tool_call.tool_input}")
            
            # 3. Run the tool and get the result
            result = await client.call_tool(
                tool_call.tool_name,
                tool_args 
            )
            
            # 4. Extract the simple string from the result
            return str(result.data) 
            
    except Exception as e:
        log.error(f"Failed to run tool {tool_call.tool_name}: {e}")
        return f"Error: {e}"


async def evaluate_hypotheses_async(state: OrionState) -> OrionState:
    """
    The second node in the graph. It runs all tool calls for all
    hypotheses in parallel to test them.
    """
    log.info(f"--- 🛠️ EVALUATING {len(state.hypotheses)} Hypotheses ---")
    
    tasks_to_run = []
    
    # Collect all tool calls from all hypotheses
    for hypothesis in state.hypotheses:
        for tool_call in hypothesis.tools_to_call:
            tasks_to_run.append(run_tool(tool_call))
    
    # Run all tool calls in parallel using asyncio.gather
    log.info(f"Running {len(tasks_to_run)} tool calls in parallel...")
    results = await asyncio.gather(*tasks_to_run)
    log.info("All tool calls completed.")

    # Now, assign the results back to the correct hypotheses
    result_index = 0
    for hypothesis in state.hypotheses:
        result_texts = []
        for _ in hypothesis.tools_to_call:
            result_texts.append(results[result_index])
            result_index += 1
        
        # Join all tool results for a single hypothesis into one string
        hypothesis.evaluation_result = "\n---\n".join(result_texts)
        # log.debug(f"Hypothesis '{hypothesis.hypothesis}' result: {hypothesis.evaluation_result}")

    return state

# A synchronous wrapper for our async function
def evaluate_hypotheses(state: OrionState) -> OrionState:
    return asyncio.run(evaluate_hypotheses_async(state))

def synthesize_conclusion(state: OrionState) -> OrionState:
    """
    The final node. It looks at all the evaluated hypotheses
    and generates a single, human-readable conclusion.
    """
    log.info(f"--- 🔬 SYNTHESIZING Conclusion ---")

    # Create a summary of all the findings
    report_parts = [f"Initial Alert: {state.initial_alert}\n"]
    for i, h in enumerate(state.hypotheses):
        report_parts.append(f"--- Hypothesis {i+1}: {h.hypothesis} ---")
        report_parts.append("Tool Call Results:")
        report_parts.append(str(h.evaluation_result))
        report_parts.append("---------------------------------")
    
    full_report = "\n".join(report_parts)

    system_prompt_str = """
    You are a 'Senior Site Reliability Engineer (SRE)' for Project Orion.
    Your job is to analyze a report of hypotheses and their tool call results,
    determine the most likely root cause, and provide a single, clear conclusion.

    - **Analyze** the evidence from the tool results.
    - **Discard** hypotheses that are disproven (e.g., "Query returned no data" or errors).
    - **Identify** the hypothesis that is supported by the data.
    - **Conclude** with a final, human-readable summary that states the root cause
    and (if possible) the recommended fix from the knowledge base.
    """
    
    user_prompt_str = f"""
    Here is the full investigation report:
    
    {full_report}
    
    Please provide your final conclusion.
    """

    prompt_messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt_str),
        ChatMessage(role=MessageRole.USER, content=user_prompt_str)
    ]

    try:
        log.info("Calling LLM to synthesize final conclusion...")
        response = Settings.llm.chat(prompt_messages)
        final_conclusion = response.message.content
        
        state.final_conclusion = final_conclusion
        log.info("Conclusion generated.")
        
    except Exception as e:
        log.error(f"Failed to synthesize conclusion: {e}")
        state.final_conclusion = "Error: Failed to generate a final conclusion."

    return state

if __name__ == "__main__":
    
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    log.info("--- Testing FULL Pipeline: EXPAND -> EVALUATE -> SYNTHESIZE ---")
    log.info("Please ensure the SRE sandbox is running: docker-compose up -d")
    
    # 1. Create a starting state
    test_alert = "FATAL: Database connection limit reached!"
    start_state = OrionState(initial_alert=test_alert)
    
    # 2. Run the EXPAND node
    expanded_state = expand_hypotheses(start_state)
    
    print("\n--- Result from EXPAND ---")
    if not expanded_state.hypotheses:
        log.error("EXPAND node returned no hypotheses. Exiting.")
        sys.exit(1)
        
    for i, h in enumerate(expanded_state.hypotheses):
        print(f"  Hypothesis {i+1}: {h.hypothesis}")
        
    # 3. Run the EVALUATE node
    evaluated_state = evaluate_hypotheses(expanded_state)
    
    print("\n--- Result from EVALUATE ---")
    for h in evaluated_state.hypotheses:
        print(f"\n  Hypothesis: {h.hypothesis}")
        print("    --- Tool Results ---")
        print(h.evaluation_result)
        print("    --------------------")
        
    # 4. Run the SYNTHESIZE node
    final_state = synthesize_conclusion(evaluated_state)
    
    # 5. Print the final answer!
    print("\n" + "="*50)
    print(" 🚀 PROJECT ORION: FINAL CONCLUSION 🚀")
    print("="*50)
    print(final_state.final_conclusion)