import argparse
import json
import os
import re
import subprocess
import sys
import time
import requests
from dotenv import load_dotenv
from tinydb import TinyDB, Query
from tqdm import tqdm

DB_PATH = 'db.json'

# --- Argparse Helper Functions ---
def positive_int(value):
    try:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
        return ivalue
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not an integer")

def repo_format(value):
    if '/' not in value or len(value.split('/')) != 2:
        raise argparse.ArgumentTypeError(f"Repository '{value}' is not in 'owner/repo' format.")
    return value

# --- Nixpkgs Scanning Logic ---
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

def extract_repo_info(file_path):
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
                project_root = os.path.abspath(os.path.dirname(__file__))
                relative_path = os.path.relpath(file_path, start=project_root)
                found_repos.append({"path": relative_path, "owner": owner.group(1), "repo": repo.group(1)})
        return found_repos
    except Exception as e:
        tqdm.write(f"Could not process file {file_path}: {e}", file=sys.stderr)
        return []

def run_scan(package_name):
    print(f"--- Starting Nixpkgs Scan for '{package_name}' ---")
    nixpkgs_path = os.path.abspath("../nixpkgs")

    if not os.path.isdir(nixpkgs_path):
        print(f"Error: Nixpkgs directory not found at {nixpkgs_path}")
        return

    files = find_package_files(nixpkgs_path, package_name)
    if not files:
        print(f"No files referencing '{package_name}' were found.")
        return

    print(f"Found {len(files)} files. Extracting repository info...")
    all_packages = [info for path in tqdm(files, desc="Scanning files") for info in extract_repo_info(path)]
    unique_packages = [dict(t) for t in {tuple(d.items()) for d in all_packages}]
    
    db = TinyDB(DB_PATH)
    Package = Query()
    count = 0
    print(f"Upserting {len(unique_packages)} unique packages...")
    for pkg in tqdm(unique_packages, desc="Updating database"):
        pkg_data = {**pkg, 'package': package_name, 'searched_github': False, 'found_on_github': False}
        db.upsert(pkg_data, (Package.owner == pkg['owner']) & (Package.repo == pkg['repo']))
        count += 1
            
    print(f"Scan complete. Upserted {count} packages for '{package_name}'.")

# --- GitHub Searching Logic ---
def search_github_all_repos(query, token):
    """Performs a paginated search across all of GitHub."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/search/code?q={query}&per_page=100"
    all_items = []
    
    with tqdm(desc="Fetching GitHub pages") as pbar:
        while url:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                items = data.get("items", [])
                all_items.extend(items)
                
                url = response.links.get('next', {}).get('url')
                pbar.update(1)
                if url:
                    time.sleep(6) # Adhere to rate limit
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


def run_search(package_name, version=None):
    load_dotenv()
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token or github_token == "your_github_token_here":
        print("Error: GITHUB_TOKEN not found.")
        return
        
    db = TinyDB(DB_PATH)
    Package = Query()
    
    search_term = f"{package_name}=={version}" if version else package_name
    print(f"--- Starting GitHub-wide search for '{search_term}' in pyproject.toml ---")

    query = f'"{search_term}"+filename:pyproject.toml'
    github_results = search_github_all_repos(query, github_token)
    
    if not github_results:
        print("No results found on GitHub.")
        return
        
    # Create a set of owner/repo strings for efficient lookup
    found_repos = {item['repository']['full_name'] for item in github_results}
    print(f"\nFound {len(found_repos)} unique repositories on GitHub with matches.")

    # Now, update the local database
    print("Updating local database...")
    all_local_packages = db.search(Package.package == package_name)
    
    for package in tqdm(all_local_packages, desc="Updating local DB"):
        repo_full_name = f"{package['owner']}/{package['repo']}"
        found = repo_full_name in found_repos
        db.update({'searched_github': True, 'found_on_github': found}, doc_ids=[package.doc_id])
        
    print("Search and database update complete.")

# --- Reporting Logic ---
def run_report(package_name):
    # (The report function remains the same)
    print(f"--- Generating Report for '{package_name}' ---")
    db = TinyDB(DB_PATH)
    matches = db.search((Query().found_on_github == True) & (Query().package == package_name))
    if not matches:
        print("No packages with GitHub matches found in the database for this package.")
        return
    print(f"Found {len(matches)} Nix packages with corresponding GitHub matches:")
    for match in matches:
        print(f"  - Nixpkgs Path: {match['path']}")
        print(f"    Repository:   {match['owner']}/{match['repo']}\n")

# --- Main CLI Logic ---
def main():
    parser = argparse.ArgumentParser(description="Find package versions in Nixpkgs and verify on GitHub.")
    parser.add_argument("package", help="The name of the package to process (e.g., 'hatchling').")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan nixpkgs and populate the database, resetting search status for found packages.")
    
    search_parser = subparsers.add_parser("search", help="Search all of GitHub for the package and update local DB.")
    search_parser.add_argument("--version", help="The specific version to search for (e.g., '1.27.0'). Optional.")

    subparsers.add_parser("report", help="Report which nixpkgs files have a GitHub match for the package.")
    
    all_parser = subparsers.add_parser("all", help="Run scan, search, and report in order for the package.")
    all_parser.add_argument("--version", help="The version to use for the 'search' step. Optional.")

    args = parser.parse_args()

    if args.command == "scan":
        run_scan(args.package)
    elif args.command == "search":
        run_search(args.package, version=args.version)
    elif args.command == "report":
        run_report(args.package)
    elif args.command == "all":
        version_str = f" with version '{args.version}'" if args.version else ""
        print(f"Running all steps for package '{args.package}'{version_str}...")
        run_scan(args.package)
        run_search(args.package, version=args.version)
        run_report(args.package)

if __name__ == "__main__":
    main()
