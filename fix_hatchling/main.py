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

def positive_int(value):
    """Helper function to validate positive integer for argparse."""
    try:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
        return ivalue
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not an integer")

def repo_format(value):
    """Helper function to validate 'owner/repo' format for argparse."""
    if '/' not in value or len(value.split('/')) != 2:
        raise argparse.ArgumentTypeError(f"Repository '{value}' is not in 'owner/repo' format.")
    return value

# --- Nixpkgs Scanning Logic ---
def find_hatchling_files(search_dir):
    try:
        cmd = ["rg", "-l", "--ignore-case", "hatchling", search_dir]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line for line in proc.stdout.strip().split('\n') if line]
    except FileNotFoundError:
        tqdm.write("Error: 'rg' (ripgrep) is not installed or not in PATH.", file=sys.stderr)
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
        for block_match in block_pattern.finditer(content):
            block_content = block_match.group(1)
            owner_match = owner_pattern.search(block_content)
            repo_match = repo_pattern.search(block_content)
            if owner_match and repo_match:
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                relative_path = os.path.relpath(file_path, start=project_root)
                found_repos.append({"path": relative_path, "owner": owner_match.group(1), "repo": repo_match.group(1)})
        return found_repos
    except Exception as e:
        tqdm.write(f"Could not process file {file_path}: {e}", file=sys.stderr)
        return []

def run_scan():
    """Scans nixpkgs for hatchling packages and populates the database."""
    print("--- Starting Nixpkgs Scan ---")
    script_dir = os.path.dirname(__file__)
    nixpkgs_path = os.path.abspath(os.path.join(script_dir, "../../nixpkgs"))

    if not os.path.isdir(nixpkgs_path):
        print(f"Error: Nixpkgs directory not found at {nixpkgs_path}")
        return

    hatchling_files = find_hatchling_files(nixpkgs_path)
    if not hatchling_files:
        print("No files referencing 'hatchling' were found.")
        return

    print(f"Found {len(hatchling_files)} files. Extracting repository info...")
    
    all_packages = [info for file_path in tqdm(hatchling_files, desc="Scanning files") for info in extract_repo_info(file_path)]

    unique_packages = [dict(t) for t in {tuple(d.items()) for d in all_packages}]
    
    db = TinyDB(DB_PATH)
    Package = Query()
    inserted_count = 0
    print(f"Processing {len(unique_packages)} unique packages into the database...")
    for pkg in tqdm(unique_packages, desc="Updating database"):
        if not db.contains((Package.owner == pkg['owner']) & (Package.repo == pkg['repo'])):
            db.insert({'path': pkg['path'], 'owner': pkg['owner'], 'repo': pkg['repo'], 'searched_github': False, 'found_on_github': False})
            inserted_count += 1
            
    print(f"Scan complete. Inserted {inserted_count} new packages into {DB_PATH}.")

# --- GitHub Searching Logic ---

def search_github(query, token):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/search/code?q={query}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            tqdm.write(f"-> Got 403 on search. Waiting 10s and retrying...", file=sys.stderr)
            time.sleep(10)
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                tqdm.write("  -> Retry successful.")
                return response.json()
            except requests.exceptions.RequestException as retry_e:
                tqdm.write(f"  -> Retry failed: {retry_e}", file=sys.stderr)
    except requests.exceptions.RequestException as e:
        tqdm.write(f"Request error for {url}: {e}", file=sys.stderr)
    return None

def run_search(limit=None, repo_str=None):
    """Searches GitHub for packages based on database entries or a specific repo string."""
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    github_token = os.getenv("GITHUB_TOKEN")

    if not github_token or github_token == "your_github_token_here":
        print("Error: GITHUB_TOKEN not found in the root .env file.")
        return
        
    db = TinyDB(DB_PATH)
    Package = Query()

    if repo_str:
        owner, repo = repo_str.split('/', 1)
        print(f"--- Starting GitHub Search for specific repository: {owner}/{repo} ---")
        query = f'hatchling==1.27.0+filename:pyproject.toml+repo:{owner}/{repo}'
        result = search_github(query, github_token)
        found = result and result.get("total_count", 0) > 0
        
        if found:
            print(f"-> Match FOUND for {owner}/{repo}")
        else:
            print(f"-> No match found for {owner}/{repo}")
        
        db.update({'searched_github': True, 'found_on_github': found}, (Package.owner == owner) & (Package.repo == repo))
        print("Search complete. Database record updated (if it existed).")

    else:
        print("--- Starting GitHub Search for unsearched packages ---")
        unsearched = db.search(Package.searched_github == False)
        if not unsearched:
            print("No unsearched packages found.")
            return
            
        packages_to_search = unsearched[:limit] if limit else unsearched
        print(f"Found {len(unsearched)} unsearched packages. Starting search for {len(packages_to_search)} of them.")
        
        for package in tqdm(packages_to_search, desc="Searching GitHub"):
            owner, repo = package.get("owner"), package.get("repo")
            if not owner or not repo:
                db.update({'searched_github': True}, doc_ids=[package.doc_id])
                continue
            
            query = f'hatchling==1.27.0+filename:pyproject.toml+repo:{owner}/{repo}'
            result = search_github(query, github_token)
            
            found = result and result.get("total_count", 0) > 0
            db.update({'searched_github': True, 'found_on_github': found}, doc_ids=[package.doc_id])
            
            time.sleep(6.5)
        print("GitHub search complete.")

# --- Reporting Logic ---
def run_report():
    print("--- Generating Report ---")
    db = TinyDB(DB_PATH)
    matches = db.search(Query().found_on_github == True)
    
    if not matches:
        print("No packages with GitHub matches found in the database.")
        return
        
    print(f"Found {len(matches)} Nix packages with corresponding GitHub matches for 'hatchling==1.27.0':")
    for match in matches:
        print(f"  - Nixpkgs Path: {match['path']}")
        print(f"    Repository:   {match['owner']}/{match['repo']}\n")

# --- Main CLI Logic ---
def main():
    parser = argparse.ArgumentParser(description="A CLI tool to find hatchling versions in Nixpkgs and verify on GitHub.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Scan nixpkgs and populate the database with new entries.")
    
    search_parser = subparsers.add_parser("search", help="Search GitHub for packages.")
    search_group = search_parser.add_mutually_exclusive_group()
    search_group.add_argument("-l", "--limit", type=positive_int, help="Limit the number of unsearched repositories to process.")
    search_group.add_argument("--repo", type=repo_format, help="Search a specific repository in 'owner/repo' format.")

    subparsers.add_parser("report", help="Report which nixpkgs files have a GitHub match.")
    subparsers.add_parser("all", help="Run scan, search (all), and report in order.")

    args = parser.parse_args()

    if args.command == "scan":
        run_scan()
    elif args.command == "search":
        run_search(limit=args.limit, repo_str=args.repo)
    elif args.command == "report":
        run_report()
    elif args.command == "all":
        print("Running all steps: scan, search (all), then report.")
        run_scan()
        run_search()
        run_report()

if __name__ == "__main__":
    main()
