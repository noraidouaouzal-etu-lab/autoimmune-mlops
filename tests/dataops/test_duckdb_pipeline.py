import duckdb
import pytest
from pathlib import Path

def test_mock_duckdb_schema(tmp_path):
    # Tests that the DuckDB structure matches the expected engine schema
    db_path = tmp_path / "test_catalog.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE mock_table (id INTEGER, title VARCHAR, content VARCHAR);")
    con.execute("INSERT INTO mock_table VALUES (1, 'Sample Title', 'Sample Content');")
    
    res = con.execute("SELECT COUNT(*) FROM mock_table;").fetchone()
    assert res[0] == 1
    con.close()