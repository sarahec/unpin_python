import sqlite3
from datetime import datetime, timezone

class Database:
    """A wrapper class for all database interactions using a normalized SQLite schema."""

    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Creates the necessary tables with a normalized schema."""
        # Table to store which nixpkgs files are associated with a package scan
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                package_name TEXT,
                nix_path TEXT,
                owner TEXT,
                repo TEXT,
                PRIMARY KEY (package_name, owner, repo)
            )
        ''')
        # Table to store the metadata for each search run
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT,
                search_string TEXT,
                last_update TEXT
            )
        ''')
        # Table to link search runs to the repositories found on GitHub
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_matches (
                search_id INTEGER,
                repo_full_name TEXT, -- owner/repo
                FOREIGN KEY (search_id) REFERENCES search_runs(id)
            )
        ''')
        self.conn.commit()

    def upsert_scan_result(self, package_name, repositories):
        """
        Inserts or replaces the repositories found for a given package scan.
        It first clears old results for the package to ensure the scan is fresh.
        """
        self.cursor.execute('DELETE FROM scan_results WHERE package_name = ?', (package_name,))
        
        repo_data = [
            (package_name, repo['path'], repo['owner'], repo['repo'])
            for repo in repositories
        ]
        self.cursor.executemany('''
            INSERT OR REPLACE INTO scan_results (package_name, nix_path, owner, repo)
            VALUES (?, ?, ?, ?)
        ''', repo_data)
        self.conn.commit()
        return len(repositories)

    def get_scan_repositories(self, package_name):
        """
        Retrieves all repositories associated with a given package name from a scan.
        """
        self.cursor.execute('SELECT nix_path, owner, repo FROM scan_results WHERE package_name = ?', (package_name,))
        rows = self.cursor.fetchall()
        return [{'path': r[0], 'owner': r[1], 'repo': r[2]} for r in rows]

    def insert_search_result(self, package_name, search_string, found_repos_on_github):
        """
        Inserts a new search run and its associated matches into the database.
        """
        # 1. Insert the search run metadata
        self.cursor.execute('''
            INSERT INTO search_runs (package_name, search_string, last_update)
            VALUES (?, ?, ?)
        ''', (package_name, search_string, datetime.now(timezone.utc).isoformat()))
        search_id = self.cursor.lastrowid
        
        # 2. Insert all the repos that were found on GitHub for this search
        if found_repos_on_github:
            match_data = [(search_id, repo_full_name) for repo_full_name in found_repos_on_github]
            self.cursor.executemany('''
                INSERT INTO search_matches (search_id, repo_full_name)
                VALUES (?, ?)
            ''', match_data)

        self.conn.commit()
        return search_id

    def get_latest_search_report(self, package_name, search_string):
        """
        Finds the most recent search and joins its results with scanned repositories.
        """
        # 1. Find the ID of the most recent relevant search
        self.cursor.execute('''
            SELECT id FROM search_runs
            WHERE package_name = ? AND search_string = ?
            ORDER BY last_update DESC
            LIMIT 1
        ''', (package_name, search_string))
        row = self.cursor.fetchone()
        if not row:
            return None
        latest_search_id = row[0]
        
        # 2. Join the results of that search with the scan data
        self.cursor.execute('''
            SELECT DISTINCT
                s.nix_path,
                s.owner,
                s.repo
            FROM scan_results s
            JOIN search_matches sm ON (s.owner || '/' || s.repo) = sm.repo_full_name
            WHERE sm.search_id = ?
        ''', (latest_search_id,))
        
        rows = self.cursor.fetchall()
        return [{'path': r[0], 'owner': r[1], 'repo': r[2]} for r in rows]

    def close(self):
        """Closes the database connection."""
        self.conn.close()