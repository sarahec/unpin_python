import sqlite3
import json
from datetime import datetime, timezone

class Database:
    """A wrapper class for all database interactions using a normalized SQLite schema."""

    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        # Enable foreign key support
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self):
        """Creates the necessary tables with a normalized schema."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                package_name TEXT PRIMARY KEY,
                last_scan TEXT
                -- repositories are in their own table now
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                package_name TEXT,
                nix_path TEXT,
                owner TEXT,
                repo TEXT,
                PRIMARY KEY (package_name, owner, repo),
                FOREIGN KEY (package_name) REFERENCES scans(package_name) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT,
                search_string TEXT,
                last_update TEXT,
                FOREIGN KEY (package_name) REFERENCES scans(package_name) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_matches (
                search_id INTEGER,
                repo_full_name TEXT, -- owner/repo
                PRIMARY KEY (search_id, repo_full_name),
                FOREIGN KEY (search_id) REFERENCES search_runs(id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def delete_all_data(self):
        """Deletes all rows from all tables."""
        self.cursor.execute('DELETE FROM search_matches')
        self.cursor.execute('DELETE FROM search_runs')
        self.cursor.execute('DELETE FROM repositories')
        self.cursor.execute('DELETE FROM scans')
        self.conn.commit()

    def delete_package_data(self, package_name):
        """Deletes all data associated with a specific package name."""
        # Due to "ON DELETE CASCADE", deleting from 'scans' will cascade
        # to repositories, search_runs, and search_matches.
        self.cursor.execute('DELETE FROM scans WHERE package_name = ?', (package_name,))
        self.conn.commit()

    def upsert_scan_result(self, package_name, repositories):
        self.cursor.execute('INSERT OR REPLACE INTO scans (package_name, last_scan) VALUES (?, ?)', 
                            (package_name, datetime.now(timezone.utc).isoformat()))
        
        # Clear old repositories for this package before inserting new ones
        self.cursor.execute('DELETE FROM repositories WHERE package_name = ?', (package_name,))
        
        repo_data = [(package_name, repo['path'], repo['owner'], repo['repo']) for repo in repositories]
        self.cursor.executemany('''
            INSERT OR REPLACE INTO repositories (package_name, nix_path, owner, repo)
            VALUES (?, ?, ?, ?)
        ''', repo_data)
        self.conn.commit()
        return len(repositories)

    def get_scan_repositories(self, package_name):
        self.cursor.execute('SELECT nix_path, owner, repo FROM repositories WHERE package_name = ?', (package_name,))
        rows = self.cursor.fetchall()
        return [{'path': r[0], 'owner': r[1], 'repo': r[2]} for r in rows]

    def insert_search_result(self, package_name, search_string, found_repos_on_github):
        self.cursor.execute('''
            INSERT INTO search_runs (package_name, search_string, last_update)
            VALUES (?, ?, ?)
        ''', (package_name, search_string, datetime.now(timezone.utc).isoformat()))
        search_id = self.cursor.lastrowid
        
        if found_repos_on_github:
            match_data = [(search_id, repo_full_name) for repo_full_name in found_repos_on_github]
            self.cursor.executemany('INSERT OR IGNORE INTO search_matches (search_id, repo_full_name) VALUES (?, ?)', match_data)
        self.conn.commit()
        return search_id

    def get_latest_search_report(self, package_name, search_string):
        self.cursor.execute('''
            SELECT id FROM search_runs
            WHERE package_name = ? AND search_string = ?
            ORDER BY last_update DESC
            LIMIT 1
        ''', (package_name, search_string))
        row = self.cursor.fetchone()
        if not row: return None
        latest_search_id = row[0]
        
        self.cursor.execute('''
            SELECT DISTINCT
                r.nix_path,
                r.package_name
            FROM repositories r
            JOIN search_matches sm ON (r.owner || '/' || r.repo) = sm.repo_full_name
            WHERE sm.search_id = ? AND r.package_name = ?
        ''', (latest_search_id, package_name))
        
        rows = self.cursor.fetchall()
        return [{'path': r[0], 'package': r[1]} for r in rows]

    def close(self):
        self.conn.close()
