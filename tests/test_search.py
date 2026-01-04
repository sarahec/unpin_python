import pytest
from search import run_search
from unittest.mock import MagicMock, patch

# Mock response from GitHub API
MOCK_GITHUB_API_RESPONSE = {
    "total_count": 1,
    "incomplete_results": False,
    "items": [
        {
            "repository": {
                "full_name": "test-owner/test-repo"
            }
        }
    ]
}

@patch('search.search_github_all_repos')
@patch('search.Database')
@patch('search.load_dotenv') # Don't need to load .env in tests
def test_run_search(mock_dotenv, MockDatabase, mock_search_github):
    """Test the main run_search function using mocks."""
    # Setup mocks
    mock_db_instance = MockDatabase.return_value
    mock_db_instance.get_scan_repositories.return_value = [
        {"path": "pkgs/a/a.nix", "owner": "test-owner", "repo": "test-repo"},
        {"path": "pkgs/b/b.nix", "owner": "another-owner", "repo": "another-repo"}
    ]
    mock_search_github.return_value = MOCK_GITHUB_API_RESPONSE['items']

    run_search("test-pkg", "test-pkg==1.0", "test-pkg==1.0", ":memory:")
    
    # Assertions
    mock_db_instance.get_scan_repositories.assert_called_once_with("test-pkg")
    mock_search_github.assert_called_once()
    mock_db_instance.insert_search_result.assert_called_once()
    
    # Check that the data passed to insert_search_result is correct
    call_args = mock_db_instance.insert_search_result.call_args[0]
    assert call_args[0] == "test-pkg" # package_name
    assert call_args[1] == "test-pkg==1.0" # canonical_search_string
    # The set of found repos on GH
    assert call_args[2] == {"test-owner/test-repo"}
    
    mock_db_instance.close.assert_called_once()
