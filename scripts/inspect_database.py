"""Explicitly write the schema snapshot formerly generated during imports."""
from pathlib import Path

from data_agent.config import database_config, load_environment
from data_agent.services.database import DatabaseService


def main() -> None:
    load_environment()
    result = DatabaseService(database_config()).schema_detail("public")
    Path("test_schema_detail.txt").write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
