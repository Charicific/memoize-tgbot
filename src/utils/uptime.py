import time

# Record the exact start time of the process
BOT_START_TIME = time.time()


def get_uptime_string() -> str:
    """
    Returns a human-readable uptime duration string, e.g., '4d 12h 30m 5s'.
    """
    seconds = int(time.time() - BOT_START_TIME)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    # Always show seconds if it's the only metric, or if under a minute
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)
