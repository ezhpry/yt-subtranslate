import sys


def log_info(stage: str, message: str) -> None:
    print(f"[{stage.upper()}] {message}", file=sys.stderr)


def log_warn(stage: str, message: str) -> None:
    print(f"[{stage.upper()}] WARNING: {message}", file=sys.stderr)


def log_error(stage: str, message: str) -> None:
    print(f"[{stage.upper()}] ERROR: {message}", file=sys.stderr)
