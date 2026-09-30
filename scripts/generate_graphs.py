"""Explicit graph rendering; never invoked by application startup."""
from pathlib import Path

from data_agent.agents.etl import build_etl_graph
from data_agent.agents.router import build_data_agent
from data_agent.agents.sql import build_sql_graph
from data_agent.config import default_data_root, load_environment


def main() -> None:
    load_environment()
    root = default_data_root()
    sql_graph = build_sql_graph()
    etl_graph = build_etl_graph(data_root=root)
    router = build_data_agent(sql_graph=sql_graph, etl_graph=etl_graph, data_root=root)
    output = root / "artifacts" / "graphs"
    output.mkdir(parents=True, exist_ok=True)
    for name, graph in (
        ("data_agent", router), ("sql_analyst", sql_graph), ("etl_analyst", etl_graph),
    ):
        (output / f"{name}_graph.png").write_bytes(graph.get_graph().draw_mermaid_png())


if __name__ == "__main__":
    main()
