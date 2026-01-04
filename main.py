import argparse
import os
import re

from scan import run_scan
from search import run_search
from report import run_report

# Changed DB_PATH to use .sqlite extension
DB_PATH = 'db.sqlite'

def parse_specifier(spec_str):
    match = re.search(r'(==|!=|>=|<=|>|<)', spec_str)
    
    if match:
        op = match.group(1)
        # Split by the operator, handle potential empty strings if operator is at start/end
        parts = re.split(f'({re.escape(op)})', spec_str, 1)
        
        # Ensure there are at least 3 parts: [before_op, op, after_op]
        if len(parts) >= 3:
            package_name = parts[0].strip()
            version_part = parts[2].strip()
            
            search_string_with_spaces = f"{package_name} {op} {version_part}"
            canonical_search_string = f"{package_name}{op}{version_part}"
            return package_name, search_string_with_spaces, canonical_search_string
        else:
            package_name = spec_str.strip()
            return package_name, package_name, package_name
    else:
        package_name = spec_str.strip()
        search_string_with_spaces = f"{package_name} == "
        canonical_search_string = f"{package_name}=="
        return package_name, search_string_with_spaces, canonical_search_string

def main():
    parser = argparse.ArgumentParser(description="A tool to correlate Nixpkgs packages with GitHub search results.")
    parser.add_argument("-n", "--nixpkgs-path", default=os.path.abspath("../nixpkgs"), help="Path to your local nixpkgs clone. Default: ../nixpkgs")
    parser.add_argument("command", choices=['scan', 'search', 'report', 'all'], help="The command to execute.")
    parser.add_argument("specifier", help="The package and optional version to process (e.g., 'hatchling', 'hatchling==1.27.0').")

    args = parser.parse_args()
    
    package_name, search_string_with_spaces, canonical_search_string = parse_specifier(args.specifier)

    if args.command == "scan":
        run_scan(package_name, args.nixpkgs_path, DB_PATH)
    elif args.command == "search":
        run_search(package_name, search_string_with_spaces, canonical_search_string, DB_PATH)
    elif args.command == "report":
        run_report(package_name, canonical_search_string, DB_PATH)
    elif args.command == "all":
        print(f"Running all steps for specifier '{args.specifier}'...")
        if args.nixpkgs_path and os.path.isdir(args.nixpkgs_path):
            run_scan(package_name, args.nixpkgs_path, DB_PATH)
        else:
            print("--- Skipping Nixpkgs Scan: --nixpkgs-path not provided or invalid ---")

        run_search(package_name, search_string_with_spaces, canonical_search_string, DB_PATH)
        run_report(package_name, canonical_search_string, DB_PATH)

if __name__ == "__main__":
    main()
