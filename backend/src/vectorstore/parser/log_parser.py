from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedLogEntry:
    """
    Structured view of a parsed log line, including the originating file and pattern.
    """

    pattern: str
    source: Path
    line_number: int
    fields: Dict[str, Any]
    raw: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "source": str(self.source),
            "line_number": self.line_number,
            "fields": self.fields,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class _CompiledPattern:
    name: str
    description: str
    is_json: bool
    line_regex: Optional[Pattern[str]]
    group_map: Dict[str, int]
    start_regex: Optional[Pattern[str]]
    continue_regex: Optional[Pattern[str]]


class LogParser:
    """
    Parse log files located in the data directory using regex/JSON patterns declared
    in vectorstore/config/log_patterns.json.
    """

    def __init__(
        self,
        patterns_path: Optional[Path | str] = None,
        data_dir: Optional[Path | str] = None,
    ) -> None:
        self.patterns_path = (
            Path(patterns_path)
            if patterns_path
            else Path(__file__).resolve().parent.parent / "config" / "log_patterns.json"
        )
        backend_root = Path(__file__).resolve().parents[3]
        default_data_dir = backend_root / "data" / "raw" / "synthetic"
        self.data_dir = Path(data_dir) if data_dir else default_data_dir
        self._patterns: List[_CompiledPattern] = self._load_patterns(self.patterns_path)

    def parse_directory(self, data_dir: Optional[Path | str] = None) -> Iterator[ParsedLogEntry]:
        """
        Walk a directory (defaults to backend/data/raw/synthetic) and yield parsed log entries for
        any *.log files discovered. Files are processed one line at a time to limit
        memory usage.
        """

        root = Path(data_dir) if data_dir else self.data_dir
        if not root.exists():
            raise FileNotFoundError(f"Log directory does not exist: {root}")

        for file_path in sorted(root.rglob("*.log")):
            logger.debug("Parsing log file: %s", file_path)
            yield from self.parse_file(file_path)

    def parse_file(
        self,
        file_path: Path | str,
        pattern_hint: Optional[str] = None,
    ) -> Iterator[ParsedLogEntry]:
        """
        Stream-parse a single log file, yielding ParsedLogEntry objects.
        A pattern hint can be supplied to try that pattern before others.
        """

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {path}")

        patterns = self._ordered_patterns(pattern_hint)
        buffered_line: Optional[str] = None
        line_number = 0

        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            while True:
                raw_line = buffered_line if buffered_line is not None else handle.readline()
                buffered_line = None
                if raw_line == "":
                    break

                line_number += 1
                line = raw_line.rstrip("\n")
                entry_line_number = line_number
                matched = self._match_line(line, patterns)
                if not matched:
                    logger.debug("No pattern matched line %s in %s", line_number, path)
                    continue

                pattern, fields = matched
                raw_block = line
                if pattern.continue_regex:
                    should_expand = True
                    if pattern.start_regex:
                        should_expand = bool(pattern.start_regex.search(line))
                    if should_expand:
                        raw_block, fields, consumed, buffered_line = self._consume_continuations(
                            handle, pattern, raw_block, fields
                        )
                        line_number += consumed

                yield ParsedLogEntry(
                    pattern=pattern.name,
                    source=path,
                    line_number=entry_line_number,
                    fields=fields,
                    raw=raw_block,
                )

    def _load_patterns(self, patterns_path: Path) -> List[_CompiledPattern]:
        with patterns_path.open("r", encoding="utf-8") as handle:
            pattern_data = json.load(handle)

        compiled: List[_CompiledPattern] = []
        for name, config in pattern_data.items():
            compiled.append(
                _CompiledPattern(
                    name=name,
                    description=config.get("description", ""),
                    is_json=bool(config.get("json", False)),
                    line_regex=self._maybe_compile(config.get("line_pattern")),
                    group_map={k: int(v) for k, v in (config.get("groups") or {}).items()},
                    start_regex=self._maybe_compile((config.get("multiline") or {}).get("start_pattern")),
                    continue_regex=self._maybe_compile((config.get("multiline") or {}).get("continue_pattern")),
                )
            )
        return compiled

    def _maybe_compile(self, pattern: Optional[str]) -> Optional[Pattern[str]]:
        return re.compile(pattern) if pattern else None

    def _ordered_patterns(self, hint: Optional[str]) -> List[_CompiledPattern]:
        if not hint:
            return self._patterns
        preferred = [p for p in self._patterns if p.name == hint]
        remainder = [p for p in self._patterns if p.name != hint]
        return preferred + remainder

    def _match_line(
        self,
        line: str,
        patterns: List[_CompiledPattern],
    ) -> Optional[tuple[_CompiledPattern, Dict[str, Any]]]:
        for pattern in patterns:
            parsed = self._try_parse(pattern, line)
            if parsed is not None:
                return pattern, parsed
        return None

    def _try_parse(self, pattern: _CompiledPattern, line: str) -> Optional[Dict[str, Any]]:
        if pattern.is_json:
            try:
                parsed_json = json.loads(line)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed_json, dict):
                return parsed_json
            return {"value": parsed_json}

        if not pattern.line_regex:
            return None

        match = pattern.line_regex.match(line)
        if not match:
            return None

        fields: Dict[str, Any] = {}
        for key, index in pattern.group_map.items():
            try:
                fields[key] = match.group(index)
            except IndexError:
                logger.debug("Pattern %s missing group %s", pattern.name, index)

        if "message" not in fields and match.group(0):
            fields["message"] = match.group(0)

        return fields

    def _consume_continuations(
        self,
        handle: Any,
        pattern: _CompiledPattern,
        initial_raw: str,
        initial_fields: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any], int, Optional[str]]:
        """
        Gather continuation lines that belong to the current log entry.
        Returns the concatenated raw string, the updated fields, and
        the count of additional lines consumed along with a buffered
        non-continuation line (if encountered).
        """

        extra_lines: List[str] = []
        consumed = 0
        buffered: Optional[str] = None

        for next_line in handle:
            if next_line == "":
                break
            candidate = next_line.rstrip("\n")
            if pattern.continue_regex and pattern.continue_regex.match(candidate):
                extra_lines.append(candidate)
                consumed += 1
                continue

            buffered = next_line
            break

        if extra_lines:
            joined = "\n".join(extra_lines)
            if "message" in initial_fields:
                initial_fields["message"] = f"{initial_fields['message']}\n{joined}"
            initial_raw = f"{initial_raw}\n{joined}"

        return initial_raw, initial_fields, consumed, buffered


__all__ = ["LogParser", "ParsedLogEntry", "main"]


def main() -> None:
    """
    Lightweight CLI to sanity-check log parsing against the configured data directory.
    """

    parser = argparse.ArgumentParser(description="Parse logs using configured patterns.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Directory to search for *.log files (defaults to backend/data/raw).",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="Override path to log_patterns.json.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Parse a single file instead of scanning the directory.",
    )
    parser.add_argument(
        "--pattern-hint",
        type=str,
        default=None,
        help="Try this pattern name first when parsing.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum entries to print (default: 10).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (default: INFO).",
    )

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    log_parser = LogParser(patterns_path=args.patterns, data_dir=args.data_dir)

    entries: Iterator[ParsedLogEntry]
    if args.file:
        entries = log_parser.parse_file(Path(args.file), pattern_hint=args.pattern_hint)
    else:
        entries = log_parser.parse_directory(data_dir=args.data_dir)

    printed = 0
    for entry in entries:
        print(json.dumps(entry.as_dict()))
        printed += 1
        if args.limit and printed >= args.limit:
            break

    logger.info("Printed %s parsed entries", printed)


if __name__ == "__main__":
    main()
