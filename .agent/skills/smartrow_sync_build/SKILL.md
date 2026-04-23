---
name: smartrow_sync_build
description: Instructions for managing the build environment and dependencies for the smartrow_sync project.
---

# Build Environment Management for SmartRow Sync

This skill ensures that the development and build environment for `smartrow_sync` is correctly configured and that all dependencies are satisfied.

## Prerequisites
- Conda must be installed on the system.

## Environment Activation
Before performing any build, test, or execution tasks, ensure the `smartrow_sync` conda environment is active.
- If not active, run: `conda activate smartrow_sync`

## Dependency Management
If you encounter any dependency-related failures (e.g., `ImportError`, `ModuleNotFoundError`, or version mismatches), follow these steps:
1. Verify that you are in the `smartrow_sync` conda environment.
2. Ensure all required packages from `requirements.txt` are installed.
3. If any packages are missing or the environment is stale, run:
   ```powershell
   python -m pip install -r requirements.txt
   ```

## When to use this skill
- Before running `main.py` or any sync scripts.
- Before running tests using `pytest`.
- Whenever a "module not found" error occurs.
