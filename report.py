from database import Database

def run_report(package_name, canonical_search_string, db_path):
    """Generates a report from the latest search for a given package and search string."""
    print(f"--- Generating Report for '{package_name}' (search: '{canonical_search_string}') ---")
    db = Database(db_path)
    latest_search = db.get_latest_search_report(package_name, canonical_search_string)
    db.close()
    
    if not latest_search:
        print("No searches have been run for this package/version specifier.")
        return

    matches = latest_search['results']
    
    if not matches:
        print(f"The latest search found no matching packages in Nixpkgs.")
        return
        
    print(f"Found {len(matches)} Nix packages with corresponding GitHub matches:")
    for match in matches:
        print(f"  - Nixpkgs Path: {match['path']}")
        print(f"    Repository:   {match['owner']}/{match['repo']}\n")