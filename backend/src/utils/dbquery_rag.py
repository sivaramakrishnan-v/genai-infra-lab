import json
import sys
from pathlib import Path
from typing import Iterable
import re

SCRIPT_DIR = Path(__file__).resolve().parent
TABLES_FILE = SCRIPT_DIR / "pg_tables.txt"


def _setup_sys_path() -> None:
    if str(SCRIPT_DIR) in sys.path:
        sys.path.remove(str(SCRIPT_DIR))
    src_root = SCRIPT_DIR.parent
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


_setup_sys_path()

from dotenv import find_dotenv, load_dotenv
from langchain.chains.sql_database.query import create_sql_query_chain
from langchain_openai import ChatOpenAI

try:
    from langchain_community.utilities import SQLDatabase
except ImportError:
    from langchain.sql_database import SQLDatabase

from utils.config import load_database_config, load_openai_settings


def load_tables(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def build_connection_string(config: dict) -> str:
    return (
        "postgresql+psycopg://"
        f"{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )


def create_db(connection_string: str, tables: Iterable[str]) -> SQLDatabase:
    return SQLDatabase.from_uri(
        connection_string,
        include_tables=list(tables),
        sample_rows_in_table_info=2,
    )


def create_chain() -> tuple[SQLDatabase, ChatOpenAI, object]:
    load_dotenv(find_dotenv())
    api_key, model_name = load_openai_settings()

    db_config = load_database_config()
    connection_string = build_connection_string(db_config)
    print("database config loaded....")

    tables = load_tables(TABLES_FILE)
    db = create_db(connection_string, tables)

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0,
    )

    chain = create_sql_query_chain(llm, db)
    return db, llm, chain


def sanitize_sql(sql_text: str) -> str:
    cleaned = sql_text.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = "".join(part for idx, part in enumerate(parts) if idx % 2 == 1).strip()

    # Strip common model labels like "Query:", "SQLQuery:", "SQL:" (case-insensitive).
    cleaned = re.sub(r"^\s*(sql\s*query|sqlquery|sql|query)\s*:\s*", "", cleaned, flags=re.I)
    # Strip a leading standalone "sql" line.
    cleaned = re.sub(r"^\s*sql\s*$", "", cleaned, flags=re.I | re.M).strip()
    return cleaned


def summarize_result(llm: ChatOpenAI, question: str, result: object) -> str:
    result_text = json.dumps(result, default=str)
    prompt = (
        "You are a data assistant. Use only the provided query result to answer the "
        "user's question in clear, concise language.\n\n"
        f"Question: {question}\n"
        f"Query Result: {result_text}"
    )
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def prompt_loop(db: SQLDatabase, llm: ChatOpenAI, chain: object) -> None:
    while True:
        print("\n\nAsk Your Question")
        try:
            question = input()
        except EOFError:
            print("\nexiting!!!")
            return

        if question == "bye":
            print("\nexiting!!!")
            return

        sql_query = chain.invoke({"question": question})
        sql_query = sanitize_sql(str(sql_query))
        answer = db.run(sql_query)
        response_text = summarize_result(llm, question, answer)
        print("\n ### BOT RESPONSE ###")
        print("\n....." + response_text)

        if sql_query:
            print("\n ### BOT GENERATED QUERY ###")
            print("\n....." + str(sql_query))


def main() -> None:
    db, llm, chain = create_chain()
    prompt_loop(db, llm, chain)


if __name__ == "__main__":
    main()
