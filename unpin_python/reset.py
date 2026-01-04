from .database import Database

def run_reset(package_names, db_path):
    """Deletes all data for the specified package(s) from the database."""
    db = Database(db_path)
    
    if not package_names:
        print("No package names provided to reset.")
        db.close()
        return

    if "*" in package_names:
        print("--- Resetting the entire database ---")
        db.delete_all_data()
        print("Database has been cleared.")
    else:
        for package_name in package_names:
            print(f"--- Resetting data for package: '{package_name}' ---")
            db.delete_package_data(package_name)
            print(f"All data for '{package_name}' has been removed from the database.")
    
    db.close()
