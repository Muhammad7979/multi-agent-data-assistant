"""Application composition and the shared command entry point."""
from langchain_core.messages import HumanMessage

from data_agent.agents.router import build_data_agent
from data_agent.config import load_environment

EXAMPLE_REQUEST = "I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder"
# EXAMPLE_REQUEST = "How many users are registered?"


def run_request(question: str, *, agent=None) -> dict:
    """Run a request and preserve the existing full graph-state response.

    Call load_environment() once at your host application's startup. A future
    HTTP layer can call this function or reuse an explicitly built graph.
    """
    if agent is None:
        agent = build_data_agent()
    return agent.invoke({
        "messages": [HumanMessage(content=question)],
        "route_response": "",
    })


def main() -> None:
    """Run the existing example through the installed application command."""
    load_environment()
    print(run_request(EXAMPLE_REQUEST))


if __name__ == "__main__":
    main()
