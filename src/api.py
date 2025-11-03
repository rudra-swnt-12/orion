import logging
from fastapi import FastAPI
from pydantic import BaseModel
import sys
from src.agent.graph import create_orion_graph

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(
    title="Project Orion API",
    description="An AI Root-Cause Analyst",
)

# Compile the agent on startup
orion_agent = create_orion_graph()


class DiagnoseRequest(BaseModel):
    alert: str


class DiagnoseResponse(BaseModel):
    conclusion: str


@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose_alert(request: DiagnoseRequest):
    """
    Run the full Orion agent pipeline on an incoming alert.
    """
    log.info(f"Received API request for alert: {request.alert}")
    initial_input = {"initial_alert": request.alert}

    # Run the full agent
    final_state = orion_agent.invoke(initial_input)

    conclusion = final_state.get("final_conclusion", "Error: No conclusion found.")
    return DiagnoseResponse(conclusion=conclusion)


@app.get("/")
def read_root():
    return {"status": "Project Orion API is running"}
