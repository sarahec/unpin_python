import pytest
import os
from unpin_python.scan import run_scan, extract_repo_info
from unittest.mock import MagicMock, patch

# A mock of a nix file content
MOCK_NIX_FILE_CONTENT = """
{ lib, fetchFromGitHub, python3Packages }:

python3Packages.buildPythonApplication rec {
  pname = "some-package";
  version = "1.0";

  src = fetchFromGitHub {
    owner = "test-owner";
    repo = "test-repo";
    rev = "v${version}";
    hash = "sha256-...";
  };

  buildInputs = [ python3Packages.hatchling ];
}
"""

def test_extract_repo_info(tmp_path):
    """Test extracting repository info from a mock nix file."""
    nix_file = tmp_path / "default.nix"
    nix_file.write_text(MOCK_NIX_FILE_CONTENT)
    
    nixpkgs_root = str(tmp_path)
    result = extract_repo_info(str(nix_file), nixpkgs_root)
    
    assert len(result) == 1
    assert result[0]['owner'] == 'test-owner'
    assert result[0]['repo'] == 'test-repo'
    assert result[0]['path'] == 'default.nix'

@patch('unpin_python.scan.find_package_files')
@patch('unpin_python.scan.extract_repo_info')
@patch('unpin_python.scan.Database')
def test_run_scan(MockDatabase, mock_extract_repo, mock_find_files, tmp_path):
    """Test the main run_scan function using mocks."""
    # Setup mocks
    mock_db_instance = MockDatabase.return_value
    mock_find_files.return_value = ["/fake/nixpkgs/pkgs/a/a.nix"]
    mock_extract_repo.return_value = [{"path": "pkgs/a/a.nix", "owner": "test", "repo": "one"}]

    nixpkgs_path = str(tmp_path)
    os.makedirs(nixpkgs_path, exist_ok=True) # Ensure the directory exists

    run_scan("test-pkg", nixpkgs_path, ":memory:")

    # Assertions
    mock_find_files.assert_called_once_with(nixpkgs_path, "test-pkg")
    mock_extract_repo.assert_called_once_with("/fake/nixpkgs/pkgs/a/a.nix", nixpkgs_path)
    mock_db_instance.upsert_scan_result.assert_called_once()
    # Check that the data passed to upsert is correct
    call_args = mock_db_instance.upsert_scan_result.call_args[0]
    assert call_args[0] == "test-pkg"
    assert call_args[1] == [{"path": "pkgs/a/a.nix", "owner": "test", "repo": "one"}]
    mock_db_instance.close.assert_called_once()
