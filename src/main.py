import sys
import argparse
import logging
from src.agent.graph import create_orion_graph

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)


def run_orion_cli():
    """
    The main entry point for the Project Orion command-line tool.
    """
    parser = argparse.ArgumentParser(
        description="Project Orion: An AI Root-Cause Analyst."
    )
    parser.add_argument(
        "alert",
        type=str,
        help="The initial alert message to investigate (e.g., 'FATAL: Database connection limit reached!')",
    )
    args = parser.parse_args()

    log.info("Compiling Project Orion agent...")
    orion_agent = create_orion_graph()

    initial_input = {"initial_alert": args.alert}
    log.info(f"Received alert. Running investigation for: '{args.alert}'")

    # .invoke() runs the full graph and returns the final state
    final_state = orion_agent.invoke(initial_input)

    print("\n" + "=" * 50)
    print(" 🚀 PROJECT ORION: FINAL CONCLUSION 🚀")
    print("=" * 50)
    print(final_state.get("final_conclusion", "Error: No conclusion was reached."))


if __name__ == "__main__":
    run_orion_cli()
