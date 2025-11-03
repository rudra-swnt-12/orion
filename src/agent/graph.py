import logging
import sys
from langgraph.graph import StateGraph, END
from src.agent.state import OrionState
from src.agent.nodes import (
    expand_hypotheses,
    evaluate_hypotheses,
    synthesize_conclusion,
)

# Set up logging
log = logging.getLogger(__name__)

def create_orion_graph() -> StateGraph:
    """
    Builds the complete LangGraph agent for Project Orion.
    """
    
    # 1. Initialize the StateGraph with our OrionState
    workflow = StateGraph(OrionState)

    # 2. Add the three nodes we built
    log.info("Adding nodes to graph...")
    workflow.add_node("expand", expand_hypotheses)
    workflow.add_node("evaluate", evaluate_hypotheses)
    workflow.add_node("synthesize", synthesize_conclusion)

    # 3. Define the edges (the flow of the graph)
    log.info("Defining graph edges...")
    
    # After expanding, always evaluate
    workflow.add_edge("expand", "evaluate")
    
    # After evaluating, always synthesize
    workflow.add_edge("evaluate", "synthesize")
    
    # The synthesize node is the final step
    workflow.add_edge("synthesize", END)

    # 4. Set the entry point
    workflow.set_entry_point("expand")

    log.info("Graph definition complete.")
    return workflow.compile()

# --- Standalone Test Block ---
if __name__ == "__main__":
    
    # Configure logging for the test
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    log.info("--- Testing Compiled Orion Graph ---")
    
    # 1. Compile the graph
    orion_agent = create_orion_graph()

    # 2. Define the input alert
    # We pass the alert in the format defined by our OrionState
    test_alert = "FATAL: Database connection limit reached!"
    initial_input = OrionState(initial_alert=test_alert)

    log.info(f"Running agent with input: '{test_alert}'")

    # 3. Run the agent by "streaming" its state
    # This lets us see the output of each step as it happens
    for step in orion_agent.stream(initial_input):
        step_name, state = list(step.items())[0]
        print("\n" + "="*30)
        log.info(f"Finished Step: {step_name.upper()}")
        print("="*30)
        
        if step_name == "expand":
            log.info("Generated Hypotheses:")
            for i, h in enumerate(state['hypotheses']):
                print(f"  {i+1}: {h.hypothesis}")
        
        if step_name == "evaluate":
            log.info("Tool Evaluation Complete. Results added to state.")
        
        if step_name == "synthesize":
            print("\n" + "="*50)
            print(" 🚀 PROJECT ORION: FINAL CONCLUSION 🚀")
            print("="*50)
            print(state['final_conclusion'])