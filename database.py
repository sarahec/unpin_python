import sqlite3
import json # Added import for json
from datetime import datetime, timezone

class Database:
    """A wrapper class for all database interactions using SQLite."""

    def __init__(self, db_path):
        """Initializes the SQLite database and creates tables if they don't exist."""
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Creates the necessary tables for scans and searches."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                package_name TEXT PRIMARY KEY,
                last_scan TEXT,
                repositories TEXT -- Stored as JSON string
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT,
                search_string TEXT,
                last_update TEXT,
                results TEXT, -- Stored as JSON string
                FOREIGN KEY (package_name) REFERENCES scans(package_name)
            )
        ''')
        self.conn.commit()

    def upsert_scan_result(self, package_name, repositories):
        """
        Inserts or updates a scan result for a given package name.
        """
        repositories_json = self.dumps_json(repositories)
        self.cursor.execute('''
            INSERT OR REPLACE INTO scans (package_name, last_scan, repositories)
            VALUES (?, ?, ?)
        ''', (package_name, datetime.now(timezone.utc).isoformat(), repositories_json))
        self.conn.commit()
        return len(repositories)

    def get_scan_result(self, package_name):
        """
        Retrieves the latest scan result for a given package name.
        """
        self.cursor.execute('SELECT package_name, last_scan, repositories FROM scans WHERE package_name = ?', (package_name,))
        row = self.cursor.fetchone()
        if row:
            return {
                'package_name': row[0],
                'last_scan': row[1],
                'repositories': self.loads_json(row[2])
            }
        return None

    def insert_search_result(self, package_name, search_string, matches):
        """
        Inserts a new search result into the database.
        """
        matches_json = self.dumps_json(matches)
        self.cursor.execute('''
            INSERT INTO searches (package_name, search_string, last_update, results)
            VALUES (?, ?, ?, ?)
        ''', (package_name, search_string, datetime.now(timezone.utc).isoformat(), matches_json))
        self.conn.commit()
        return len(matches)

    def get_latest_search_report(self, package_name, search_string):
        """
        Finds the most recent search result for a given package and search string.
        """
        self.cursor.execute('''
            SELECT package_name, search_string, last_update, results
            FROM searches
            WHERE package_name = ? AND search_string = ?
            ORDER BY last_update DESC
            LIMIT 1
        ''', (package_name, search_string))
        row = self.cursor.fetchone()
        if row:
            return {
                'package_name': row[0],
                'search_string': row[1],
                'last_update': row[2],
                'results': self.loads_json(row[3])
            }
        return None

    def close(self):
        """Closes the database connection."""
        self.conn.close()

    @staticmethod
    def dumps_json(data):
        """Helper to dump data to JSON string for storage."""
        return json.dumps(data)

    @staticmethod
    def loads_json(json_string):
        """Helper to load data from JSON string from storage."""
        return json.loads(json_string)
