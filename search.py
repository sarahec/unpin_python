import os
import re
import sys
import time
import requests
from dotenv import load_dotenv
from tqdm import tqdm
from database import Database

def search_github_all_repos(query, token):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/search/code?q={query}&per_page=100"
    all_items = []
    
    with tqdm(desc="Fetching GitHub pages", leave=False) as pbar:
        while url:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                all_items.extend(data.get("items", []))
                url = response.links.get('next', {}).get('url')
                pbar.update(1)
                if url: time.sleep(6) # Adhere to rate limit: 10 requests/minute
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    tqdm.write(f"-> Rate limit hit. Waiting 60s for {url}...", file=sys.stderr)
                    time.sleep(60) # Wait 1 minute if rate limit is hit
                else:
                    tqdm.write(f"HTTP error for {url}: {e}", file=sys.stderr)
                    break
            except requests.exceptions.RequestException as e:
                tqdm.write(f"Request error for {url}: {e}", file=sys.stderr)
                break
    return all_items

def run_search(package_name, search_string_with_spaces, canonical_search_string, db_path):
    load_dotenv()
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token or github_token == "your_github_token_here":
        print("Error: GITHUB_TOKEN not found.")
        return
        
    db = Database(db_path)
    scan_result = db.get_scan_result(package_name)
    if not scan_result or not scan_result.get('repositories'):
        print(f"No scan data found for '{package_name}'. A scan must be run at least once.")
        db.close()
        return

    print(f"--- Starting GitHub-wide search for '{canonical_search_string}' (and variants) ---")
    
    query1 = f'"{canonical_search_string}"+filename:pyproject.toml'
    print(f"Searching for: {canonical_search_string}")
    results1 = search_github_all_repos(query1, github_token)
    
    all_github_results_map = {item['repository']['full_name']: item for item in results1}

    if search_string_with_spaces != canonical_search_string:
        query2 = f'"{search_string_with_spaces}"+filename:pyproject.toml'
        print(f"Searching for: {search_string_with_spaces}")
        results2 = search_github_all_repos(query2, github_token)
        all_github_results_map.update({item['repository']['full_name']: item for item in results2})
    
    found_repos_on_github = set(all_github_results_map.keys())
    
    if not found_repos_on_github:
        print("No results found on GitHub for either query variant.")
        db.insert_search_result(package_name, canonical_search_string, [])
        db.close()
        return
        
    print(f"\nFound {len(found_repos_on_github)} unique repositories on GitHub with matches.")

    local_repos = scan_result['repositories']
    matches = [repo_info for repo_info in local_repos if f"{repo_info['owner']}/{repo_info['repo']}" in found_repos_on_github]
    
    stored_count = db.insert_search_result(package_name, canonical_search_string, matches)
    db.close()
    
    print(f"Search complete. Stored {stored_count} matches in the database for '{canonical_search_string}'.")