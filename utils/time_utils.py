def ms_to_srt_timestamp(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1_000
    ms %= 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def srt_timestamp_to_ms(timestamp: str) -> int:
    """Convert SRT timestamp HH:MM:SS,mmm to milliseconds."""
    h, m, rest = timestamp.split(":")
    s, ms_str = rest.split(",")
    return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms_str)
