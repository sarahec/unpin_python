# Nixpkgs Version Correlation Tool (`unpin-python`)

The Nixpkgs Version Correlation Tool identifies pinned Python build tools and dependencies in Nixpkgs expressions. It correlates package definitions in a local Nixpkgs repository with GitHub code search results to find packages that are pinned to specific versions (e.g., `hatchling==1.27.0`).

## Features

- **Nixpkgs Scanning**: Efficiently scans Nixpkgs files for `fetchFromGitHub` blocks referencing target packages.
- **GitHub Code Search**: Queries the GitHub API to find repositories with specific version pins in `pyproject.toml`.
- **Correlation Reporting**: Produces reports linking Nixpkgs files to pinned versions found on GitHub.
- **Automated Workflow**: Combines scanning, searching, and reporting in a single command.

## Prerequisites

- **Python**: Version 3.8 or higher.
- **ripgrep (`rg`)**: Required for high-performance scanning of the Nixpkgs repository.
- **GitHub Token**: A GitHub Personal Access Token (PAT) for API access.

## Installation

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/sarahec/unpin_python.git
    cd unpin_python
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Environment Variables**:
    Create a `.env` file in the project root:
    ```env
    GITHUB_TOKEN=your_github_token_here
    NIXPKGS=/path/to/your/nixpkgs
    ```

## Usage

The tool is invoked via `python unpin_python/main.py` or the `unpin-python` script if installed.

### Command Format

```bash
python unpin_python/main.py [-n NIXPKGS_PATH] <command> <arguments>
```

### Commands

- **`scan <specifiers>...`**: Scans Nixpkgs for the given packages.
- **`search <specifiers>...`**: Searches GitHub for the given version specifiers.
- **`report <specifiers>...`**: Generates a report for the specifiers.
- **`all <specifiers>...`**: Runs scan, search, and report in sequence.
- **`reset <packages>...`**: Resets data for the named packages, or `*` for everything.

### Specifier Format

Specifiers follow the format `package[operator][version]`.
-   **Example**: `hatchling==1.27.0`
-   If no operator is provided (e.g., `hatchling`), the tool defaults to `==` and performs a generic scan.

### Examples

**Scan Nixpkgs for hatchling:**
```bash
python unpin_python/main.py scan hatchling
```

**Search GitHub for specific hatchling version:**
```bash
python unpin_python/main.py search hatchling==1.27.0
```

**Run the full pipeline:**
```bash
python unpin_python/main.py all hatchling==1.27.0
```

## Project Structure

- `unpin_python/`: Core logic modules.
  - `main.py`: CLI entry point.
  - `scan.py`: Nixpkgs scanning logic.
  - `search.py`: GitHub API interaction.
  - `report.py`: Report generation.
  - `reset.py`: Database management.
- `db.sqlite`: Local SQLite database for state management.
- `GEMINI.md`: Full functional specification.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
