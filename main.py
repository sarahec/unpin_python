import argparse
import os
import re

from scan import run_scan
from search import run_search
from report import run_report
from reset import run_reset

DB_PATH = 'db.sqlite'

def parse_specifier(spec_str):
    match = re.search(r'(==|!=|>=|<=|>|<)', spec_str)
    if match:
        op = match.group(1)
        parts = re.split(f'({re.escape(op)})', spec_str, 1)
        if len(parts) >= 3:
            package_name = parts[0].strip()
            version_part = parts[2].strip()
            search_string_with_spaces = f"{package_name} {op} {version_part}"
            canonical_search_string = f"{package_name}{op}{version_part}"
            return package_name, search_string_with_spaces, canonical_search_string
    # Fallback for no operator or malformed specifier
    package_name = spec_str.strip()
    search_string_with_spaces = f"{package_name} == "
    canonical_search_string = f"{package_name}=="
    return package_name, search_string_with_spaces, canonical_search_string

def main():
    parser = argparse.ArgumentParser(description="A tool to correlate Nixpkgs packages with GitHub search results.")
    parser.add_argument("-n", "--nixpkgs-path", default=os.path.abspath("../nixpkgs"), help="Path to your local nixpkgs clone.")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="The command to execute.")

    # --- Parser for commands that need specifiers ---
    specifier_commands = ['scan', 'search', 'report', 'all']
    for cmd in specifier_commands:
        cmd_parser = subparsers.add_parser(cmd, help=f"{cmd.capitalize()} the database for given package specifiers.")
        cmd_parser.add_argument("specifiers", nargs='+', help="One or more package specifiers (e.g., 'hatchling', 'gcovr==7.2').")

    # --- Parser for the reset command ---
    reset_parser = subparsers.add_parser("reset", help="Delete data from the database.")
    reset_parser.add_argument("packages", nargs='+', help="One or more package names to reset, or '*' to reset the entire database.")

    args = parser.parse_args()
    
    if args.command == "reset":
        run_reset(args.packages, DB_PATH)
        return

    # --- Logic for commands with specifiers ---
    for specifier in args.specifiers:
        package_name, search_string_with_spaces, canonical_search_string = parse_specifier(specifier)
        
        if args.command == "scan":
            run_scan(package_name, args.nixpkgs_path, DB_PATH)
        elif args.command == "search":
            run_search(package_name, search_string_with_spaces, canonical_search_string, DB_PATH)
        elif args.command == "report":
            run_report(package_name, canonical_search_string, DB_PATH)
        elif args.command == "all":
            print(f"--- Running all steps for specifier '{specifier}' ---")
            if args.nixpkgs_path and os.path.isdir(args.nixpkgs_path):
                run_scan(package_name, args.nixpkgs_path, DB_PATH)
            else:
                print(f"--- Skipping Nixpkgs Scan for '{package_name}': --nixpkgs-path not provided or invalid ---")
            run_search(package_name, search_string_with_spaces, canonical_search_string, DB_PATH)
            run_report(package_name, canonical_search_string, DB_PATH)

if __name__ == "__main__":
    main()