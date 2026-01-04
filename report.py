import os
import sys
from collections import defaultdict
from database import Database

def run_report(package_name, canonical_search_string, db_path):
    """Generates a grouped and sorted report from the latest search results."""
    print(f"--- Generating Report for '{package_name}' (search: '{canonical_search_string}') ---")
    
    db = Database(db_path)
    latest_search = db.get_latest_search_report(package_name, canonical_search_string)
    db.close()
    
    if not latest_search:
        print("No searches have been run for this package/version specifier.")
        return

    matches = latest_search.get('results', [])
    search_string = latest_search.get('search_string', canonical_search_string)

    if not matches:
        print(f"The latest search for '{search_string}' found no matching packages in Nixpkgs.")
        return
        
    # Group repositories by their Nixpkgs file path
    grouped_results = defaultdict(list)
    for match in matches:
        repo_full_name = f"{match['owner']}/{match['repo']}"
        grouped_results[match['path']].append(repo_full_name)
        
    print(f"Found {len(matches)} total repository matches across {len(grouped_results)} Nixpkgs files for '{search_string}':\n")
    
    # Sort the report by file path and format as requested
    for path, repos in sorted(grouped_results.items()):
        # Ensure repos are sorted before joining
        sorted_repos = sorted(repos)
        joined_repos = ", ".join(sorted_repos)
        print(f"{path}\tMatches: {joined_repos}")