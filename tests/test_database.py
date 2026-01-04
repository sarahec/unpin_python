import pytest
from unpin_python.database import Database

@pytest.fixture
def mem_db():
    """Fixture to create a fresh in-memory database for each test."""
    db = Database(':memory:')
    yield db
    db.close()

def test_create_tables(mem_db):
    """Test if tables are created successfully."""
    # Check if tables exist by trying to select from them
    try:
        mem_db.cursor.execute("SELECT * FROM scans")
        mem_db.cursor.execute("SELECT * FROM repositories")
        mem_db.cursor.execute("SELECT * FROM search_runs")
        mem_db.cursor.execute("SELECT * FROM search_matches")
    except Exception as e:
        pytest.fail(f"Table creation check failed: {e}")

def test_upsert_and_get_scan(mem_db):
    """Test inserting and retrieving scan results."""
    package_name = "test-pkg"
    repos = [{"path": "pkgs/a/a.nix", "owner": "test", "repo": "one"}]
    
    mem_db.upsert_scan_result(package_name, repos)
    
    scan_result = mem_db.get_scan_repositories(package_name)
    assert len(scan_result) == 1
    assert scan_result[0]['owner'] == "test"

    # Test upsert (should replace)
    new_repos = [{"path": "pkgs/b/b.nix", "owner": "test", "repo": "two"}]
    mem_db.upsert_scan_result(package_name, new_repos)
    scan_result = mem_db.get_scan_repositories(package_name)
    assert len(scan_result) == 1
    assert scan_result[0]['owner'] == "test"
    assert scan_result[0]['repo'] == "two"

def test_insert_and_get_search(mem_db):
    """Test inserting and retrieving search results."""
    pkg = "test-pkg"
    search_str = "test-pkg==1.0"
    found_repos = {"user/repo1", "user/repo2"}

    # First, need a scan result to exist
    mem_db.upsert_scan_result(pkg, [
        {"path": "pkgs/a/a.nix", "owner": "user", "repo": "repo1"},
        {"path": "pkgs/b/b.nix", "owner": "user", "repo": "repo2"},
        {"path": "pkgs/c/c.nix", "owner": "user", "repo": "repo3"}, # This one won't be in the search
    ])

    search_id = mem_db.insert_search_result(pkg, search_str, found_repos)
    assert search_id > 0
    
    report_data = mem_db.get_latest_search_report(pkg, search_str)
    assert report_data is not None
    assert len(report_data) == 2
    
    # Check that only the matching repos are returned
    packages = {item['package'] for item in report_data}
    assert packages == {pkg}