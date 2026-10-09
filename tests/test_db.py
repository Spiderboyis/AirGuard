from common.db import pg_filter, select, upsert


def test_pg_filter_quotes_reserved_characters():
    assert pg_filter("eq.geo:hauz khas") == 'eq."geo:hauz khas"'
    assert pg_filter("gt.0") == "gt.0"


def test_upsert_keeps_the_last_duplicate_and_roundtrips_json():
    upsert("route_cache", [
        {"key": "geo:hauz khas", "response": [1, 2]},
        {"key": "geo:hauz khas", "response": [28.5, 77.2]},
    ], "key")
    rows = select("route_cache", select="key,response", key="eq.geo:hauz khas")
    assert rows == [{"key": "geo:hauz khas", "response": [28.5, 77.2]}]
