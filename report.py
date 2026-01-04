from database import Database

def run_report(package_name, canonical_search_string, db_path):
    """Generates a grouped and sorted report from the latest search results."""
    print(f"--- Generating Report for '{package_name}' (search: '{canonical_search_string}') ---")
    
    db = Database(db_path)
    matches = db.get_latest_search_report(package_name, canonical_search_string)
    db.close()
    
    if not matches:
        print("No matching packages found in the database for this search.")
        return
        
    print(f"Found {len(matches)} Nix packages with corresponding GitHub matches:")
    for match in sorted(matches, key=lambda x: x['path']):
        print(f"  - Nixpkgs Path: {match['path']}")
        print(f"    Repository:   {match['owner']}/{match['repo']}\n")
