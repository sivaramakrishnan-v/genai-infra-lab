# vectorstore/db/queries.py
import logging

logger = logging.getLogger(__name__)


INSERT_LOG_MASTER = """
INSERT INTO log_master (
    source_name, source_type, service_name, environment,
    log_format, line_count, byte_size, parse_status,
    parse_error, parsed_at, created_at
)
VALUES (
    %(source_name)s, %(source_type)s, %(service_name)s, %(environment)s,
    %(log_format)s, %(line_count)s, %(byte_size)s, %(parse_status)s,
    %(parse_error)s, %(parsed_at)s, %(created_at)s
)
RETURNING id;
"""


INSERT_LOG_EVENT = """
INSERT INTO log_event (
    master_id, ts, service_name, level, trace_id, span_id,
    message, raw_line, metadata, logger_name, thread_name,
    exception_type, exception_msg, stack_trace, created_at
)
VALUES (
    %(master_id)s, %(ts)s, %(service_name)s, %(level)s, %(trace_id)s,
    %(span_id)s, %(message)s, %(raw_line)s, %(metadata)s,
    %(logger_name)s, %(thread_name)s,
    %(exception_type)s, %(exception_msg)s, %(stack_trace)s,
    %(created_at)s
);
"""


def main() -> None:
    """
    Smoke test to log the available SQL templates for quick inspection.
    """

    logging.basicConfig(level=logging.INFO)
    logger.info("INSERT_LOG_MASTER SQL:\n%s", INSERT_LOG_MASTER.strip())
    logger.info("INSERT_LOG_EVENT SQL:\n%s", INSERT_LOG_EVENT.strip())
    logger.info("SQL templates loaded successfully.")


if __name__ == "__main__":
    main()
