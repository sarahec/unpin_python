import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
from tqdm import tqdm

from database import Database

DB_PATH = 'db.scratch.json'

def parse_specifier(spec_str):
    match = re.search(r'(==|!=|>=|<=|>|<)', spec_str)
    if match:
        op = match.group(1)
        package_name = spec_str[:match.start()].strip()
        version_part = spec_str[match.end():].strip()
        search_string_with_spaces = f"{package_name} {op} {version_part}"
        canonical_search_string = f"{package_name}{op}{version_part}"
        return package_name, search_string_with_spaces, canonical_search_string
    else:
        package_name = spec_str.strip()
        search_string_with_spaces = f"{package_name} == "
        canonical_search_string = f"{package_name}=="
        return package_name, search_string_with_spaces, canonical_search_string

def find_package_files(search_dir, package_name):
    try:
        cmd = ["rg", "-l", "--ignore-case", package_name, search_dir]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line for line in proc.stdout.strip().split('\n') if line]
    except FileNotFoundError:
        tqdm.write("Error: 'rg' (ripgrep) is not installed.", file=sys.stderr)
        return []
    except subprocess.CalledProcessError as e:
        tqdm.write(f"Error during file search: {e.stderr}", file=sys.stderr)
        return []

def extract_repo_info(file_path, nixpkgs_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        block_pattern = re.compile(r'fetchFromGitHub\s*{\s*([\s\S]*?)\s*};', re.DOTALL)
        owner_pattern = re.compile(r'owner\s*=\s*"([^"]+)"')
        repo_pattern = re.compile(r'repo\s*=\s*"([^"]+)"')
        
        found_repos = []
        for match in block_pattern.finditer(content):
            owner = owner_pattern.search(match.group(1))
            repo = repo_pattern.search(match.group(1))
            if owner and repo:
                relative_path = os.path.relpath(file_path, start=nixpkgs_path)
                found_repos.append({"path": relative_path, "owner": owner.group(1), "repo": repo.group(1)})
        return found_repos
    except Exception as e:
        tqdm.write(f"Could not process file {file_path}: {e}", file=sys.stderr)
        return []

def run_scan(package_name, nixpkgs_path):
    if not nixpkgs_path:
        print("--- Skipping Nixpkgs Scan: --nixpkgs-path not provided --")
        return
        
    print(f"--- Starting Nixpkgs Scan for '{package_name}' in {nixpkgs_path} ---")
    if not os.path.isdir(nixpkgs_path):
        print(f"Error: Nixpkgs directory not found at {nixpkgs_path}")
        return

    files = find_package_files(nixpkgs_path, package_name)
    if not files:
        print(f"No files referencing '{package_name}' were found in {nixpkgs_path}.")
        return

    print(f"Found {len(files)} files. Extracting repository info...")
    all_repos = [info for path in tqdm(files, desc="Scanning files") for info in extract_repo_info(path, nixpkgs_path)]
    unique_repos = [dict(t) for t in {tuple(d.items()) for d in all_repos}]
    
    db = Database(DB_PATH)
    upserted_count = db.upsert_scan_result(package_name, unique_repos)
    db.close()
    
    print(f"Scan complete. Upserted {upserted_count} unique repositories for '{package_name}'.")

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
                if url: time.sleep(6)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    tqdm.write("-> Rate limit hit. Waiting 60s...", file=sys.stderr)
                    time.sleep(60)
                else:
                    tqdm.write(f"HTTP error: {e}", file=sys.stderr)
                    break
            except requests.exceptions.RequestException as e:
                tqdm.write(f"Request error: {e}", file=sys.stderr)
                break
    return all_items

def run_search(package_name, search_string_with_spaces, canonical_search_string):
    load_dotenv()
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token or github_token == "your_github_token_here":
        print("Error: GITHUB_TOKEN not found.")
        return
        
    db = Database(DB_PATH)
    scan_result = db.get_scan_result(package_name)
    if not scan_result or not scan_result.get('repositories'):
        print(f"No scan data found for '{package_name}'. A scan must be run at least once.")
        db.close()
        return

    print(f"--- Starting GitHub-wide search for '{canonical_search_string}' (and variants) ---")
    
    query1 = f'"{canonical_search_string}"+filename:pyproject.toml'
    results1 = search_github_all_repos(query1, github_token)
    
    all_github_results_map = {item['repository']['full_name']: item for item in results1}

    if search_string_with_spaces != canonical_search_string:
        query2 = f'"{search_string_with_spaces}"+filename:pyproject.toml'
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

def run_report(package_name, canonical_search_string):
    print(f"--- Generating Report for '{package_name}' (search: '{canonical_search_string}') ---")
    db = Database(DB_PATH)
    latest_search = db.get_latest_search_report(package_name, canonical_search_string)
    db.close()
    
    if not latest_search:
        print("No searches have been run for this package/version specifier.")
        return

    matches = latest_search['results']
    search_string = latest_search['search_string']

    if not matches:
        print(f"The latest search for '{search_string}' found no matching packages in Nixpkgs.")
        return
        
    print(f"Found {len(matches)} Nix packages with corresponding GitHub matches:")
    for match in matches:
        print(f"  - Nixpkgs Path: {match['path']}")
        print(f"    Repository:   {match['owner']}/{match['repo']}\n")

def main():
    parser = argparse.ArgumentParser(description="A tool to correlate Nixpkgs packages with GitHub search results.")
    parser.add_argument("-n", "--nixpkgs-path", default=os.path.abspath("../nixpkgs"), help="Path to your local nixpkgs clone. Default: ../nixpkgs")
    parser.add_argument("command", choices=['scan', 'search', 'report', 'all'], help="The command to execute.")
    parser.add_argument("specifier", help="The package and optional version to process (e.g., 'hatchling', 'hatchling==1.27.0').")

    args = parser.parse_args()
    
    package_name, search_string_with_spaces, canonical_search_string = parse_specifier(args.specifier)

    if args.command == "scan":
        run_scan(package_name, args.nixpkgs_path)
    elif args.command == "search":
        run_search(package_name, search_string_with_spaces, canonical_search_string)
    elif args.command == "report":
        run_report(package_name, canonical_search_string)
    elif args.command == "all":
        print(f"Running all steps for specifier '{args.specifier}'...")
        if args.nixpkgs_path and os.path.isdir(args.nixpkgs_path):
            run_scan(package_name, args.nixpkgs_path)
        else:
            print("--- Skipping Nixpkgs Scan: --nixpkgs-path not provided or invalid ---")

        run_search(package_name, search_string_with_spaces, canonical_search_string)
        run_report(package_name, canonical_search_string)

if __name__ == "__main__":
    main()
