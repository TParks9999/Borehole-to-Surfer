# Contributing

## Development Setup

1. Install Python 3.10 or later on Windows.
2. Create and activate a virtual environment.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

## Running Tests

Run the test suite before opening a pull request:

```powershell
python -m pytest -q
```

If you change export logic, CSV parsing, map behavior, or geometry calculations, add or update tests in `tests/`.

## Pull Requests

- Keep changes focused.
- Update documentation when behavior or workflows change.
- Do not commit generated outputs, local settings, virtual environments, or build artifacts.
- Include a short summary of user-visible changes and any manual verification performed.

## Issues

When reporting a bug, include:

- what you expected to happen
- what actually happened
- steps to reproduce
- sample input structure when relevant
- screenshots or exported output examples if they clarify the problem

For security-sensitive issues, use the process in `SECURITY.md`.
