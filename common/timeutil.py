from datetime import datetime, timezone


def canon_ts(value) -> str:
    """Floor a timestamp to the UTC hour and return an offset-aware ISO string.

    OpenAQ uses a trailing Z. Open-Meteo omits seconds. Both become the same key,
    so an upsert cannot store the same hour twice under two spellings.
    """
    if isinstance(value, datetime):
        d = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        d = datetime.fromisoformat(text)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    d = d.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return d.isoformat()
