from collections import defaultdict
from .database import Database

def run_report(package_name, canonical_search_string, db_path):
    """Generates a grouped and sorted report in the format: path<TAB>package1, package2..."""
    print(f"--- Generating Report for '{package_name}' (search: '{canonical_search_string}') ---")
    
    db = Database(db_path)
    matches = db.get_latest_search_report(package_name, canonical_search_string)
    db.close()
    
    if not matches:
        print("No matching packages found in the database for this search.")
        return

    # Group packages by their Nixpkgs file path
    grouped_results = defaultdict(list)
    for match in matches:
        grouped_results[match['path']].append(match['package'])
        
    print(f"\nFound {len(matches)} total package matches across {len(grouped_results)} Nixpkgs files:")
    
    # Sort by Nixpkgs file path and print in the specified format
    for path, packages in sorted(grouped_results.items()):
        # Sort the package names alphabetically for consistent output
        sorted_packages = sorted(packages)
        # Join them with a comma
        joined_packages = ", ".join(sorted_packages)
        # Print in the desired format
        print(f"{path}\t{joined_packages}")
