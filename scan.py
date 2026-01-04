import os
import re
import subprocess
import sys
from tqdm import tqdm
from database import Database

def find_package_files(search_dir, package_name):
    try:
        cmd = ["rg", "-l", "--ignore-case", package_name, search_dir]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line for line in proc.stdout.strip().split('\n') if line]
    except FileNotFoundError:
        tqdm.write("Error: 'rg' (ripgrep) is not installed.", file=sys.stderr)
        return []
    except subprocess.CalledProcessError as e:
        tqdm.write(f"Error during file search for '{package_name}': {e.stderr}", file=sys.stderr)
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

def run_scan(package_name, nixpkgs_path, db_path):
    if not nixpkgs_path:
        print("--- Skipping Nixpkgs Scan: --nixpkgs-path not provided ---")
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
    
    db = Database(db_path)
    upserted_count = db.upsert_scan_result(package_name, unique_repos)
    db.close()
    
    print(f"Scan complete. Upserted {upserted_count} unique repositories for '{package_name}'.")
