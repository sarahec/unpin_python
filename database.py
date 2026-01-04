from tinydb import TinyDB, Query
from datetime import datetime, timezone

class Database:
    """A wrapper class for all database interactions."""

    def __init__(self, db_path):
        """Initializes the database and its tables."""
        self.db = TinyDB(db_path)
        self.scans_table = self.db.table('scans')
        self.searches_table = self.db.table('searches')

    def upsert_scan_result(self, package_name, repositories):
        """
        Inserts or updates a scan result for a given package name.
        """
        PackageScan = Query()
        scan_data = {
            'package_name': package_name,
            'last_scan': datetime.now(timezone.utc).isoformat(),
            'repositories': repositories
        }
        self.scans_table.upsert(scan_data, PackageScan.package_name == package_name)
        return len(repositories)

    def get_scan_result(self, package_name):
        """
        Retrieves the latest scan result for a given package name.
        """
        return self.scans_table.get(Query().package_name == package_name)

    def insert_search_result(self, package_name, search_string, matches):
        """
        Inserts a new search result into the database.
        """
        search_wrapper = {
            "package_name": package_name,
            "search_string": search_string,
            "last_update": datetime.now(timezone.utc).isoformat(),
            "results": matches
        }
        self.searches_table.insert(search_wrapper)
        return len(matches)

    def get_latest_search_report(self, package_name, search_string):
        """
        Finds the most recent search result for a given package and search string.
        """
        all_searches = sorted(
            self.searches_table.search((Query().package_name == package_name) & (Query().search_string == search_string)),
            key=lambda x: x['last_update'],
            reverse=True
        )
        return all_searches[0] if all_searches else None

    def close(self):
        """Closes the database connection."""
        self.db.close()
