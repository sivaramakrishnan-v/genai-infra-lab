import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
if str(_script_dir) in sys.path:
    sys.path.remove(str(_script_dir))
_src_root = _script_dir.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dotenv import load_dotenv, find_dotenv

from langchain_openai import ChatOpenAI
from langchain.chains.sql_database.query import create_sql_query_chain
try:
    from langchain_community.utilities import SQLDatabase
except ImportError:
    from langchain.sql_database import SQLDatabase

from utils.config import load_database_config, load_openai_settings

load_dotenv(find_dotenv())
api_key, model_name = load_openai_settings()

#print(api_key)

# logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)
# logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

db_config = load_database_config()
connection_string = (
    "postgresql+psycopg://"
    f"{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

print("database config loaded....")

tables_path = Path(__file__).resolve().parent / "pg_tables.txt"
tables = [
    line.strip()
    for line in tables_path.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]

db = SQLDatabase.from_uri(
    connection_string,
    include_tables=tables,
    sample_rows_in_table_info=2,
)

llm = ChatOpenAI(
    model=model_name,
    api_key=api_key,
    temperature=0,
)

db_chain = create_sql_query_chain(llm, db)


def extract_sql_query(intermediate_steps):
    for step in intermediate_steps:
        if isinstance(step, str) and "SQLQuery:" in step:
            return step.split("SQLQuery:", 1)[1].strip()
    return None


def sanitize_sql(sql_text: str) -> str:
    cleaned = sql_text.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = "".join(part for idx, part in enumerate(parts) if idx % 2 == 1).strip()
    if cleaned.lower().startswith("sql"):
        cleaned = cleaned[3:].strip()
    if cleaned.lower().startswith("sqlquery:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned


while True:
    print("\n\nAsk Your Question")
    question = input()
    # print("\nquestion..." + question)
    if question == "bye":
        print("\nexiting!!!")
        exit()

    # if question == "websearch":
    #     response = searchGoogle()
    #     print(response)

    sql_query = db_chain.invoke({"question": question})
    sql_query = sanitize_sql(str(sql_query))
    answer = db.run(sql_query)
    print("\n ### BOT RESPONSE ###")
    print("\n....." + str(answer))

    if sql_query:
        print("\n ### BOT GENERATED QUERY ###")
        print("\n....." + str(sql_query))
