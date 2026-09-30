# Project Documentation

New to this project? Start here.

## Recommended reading order

1. [What happens when I ask the assistant a question?](BACKEND_OVERVIEW.md) - beginner-friendly backend guide.
2. [SQL Agent: from a question to a database answer](SQL_AGENT.md).
3. [ETL Agent: from an external API to saved files](ETL_AGENT.md).
4. [Company Policy: find the evidence before answering](POLICY_AGENT.md).
5. [Setup and running](SETUP.md).
6. [ETL Files and Company Policy API reference](API_REFERENCE.md).

Start with the backend overview, then follow the SQL, ETL, and Company Policy examples. See the setup guide and API reference for operational details.

## Optional reading

- [Historical V1 interface reference](V1_INTERFACE.md) - earlier contracts and acceptance evidence, not current setup instructions.
- [Python learning guides](learning/README.md) - beginner concepts using historical project examples.
- [Historical frontend proposal](history/FRONTEND_APPLICATION_OVERVIEW.md).
- [Architecture before cleanup](history/ARCHITECTURE_BEFORE_CLEANUP.md).
- [Company Policy audit](history/POLICY_AUDIT.md) - dated validation evidence, not a fresh test run.

Historical references are retained for their design context and dated validation evidence. Use the guides above and current source for present behavior.

## Architecture diagrams

- [Router: SQL, ETL, and Policy](../artifacts/graphs/data_agent_graph.png)
- [SQL graph](../artifacts/graphs/sql_analyst_graph.png)
- [ETL graph](../artifacts/graphs/etl_analyst_graph.png)

Diagrams remain in `artifacts/graphs/`, the output directory used by [the graph-generation script](../scripts/generate_graphs.py). Policy is a router node backed by services, not a separate LangGraph graph.
