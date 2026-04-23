---
name: python_guidelines
description: Coding standards and guidelines for Python development in the smartrow_sync project, following Google style and strict typing.
---

# Python Coding Guidelines

All Python code in this repository must adhere to the following standards to ensure consistency, readability, and type safety.

## 1. Style Guide
Follow the **[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)** strictly.

### Key Conventions:
- **Indentation:** Use 4 spaces per indentation level.
- **Line Length:** Maximum line length is 80 characters.
- **Naming:**
    - `module_name` (lowercase with underscores)
    - `package_name` (lowercase, usually single word)
    - `ClassName` (CapWords)
    - `function_name()` (lowercase with underscores)
    - `variable_name` (lowercase with underscores)
    - `CONSTANT_NAME` (all caps with underscores)
- **Imports:**
    - Place imports at the top of the file, after any module comments and docstrings.
    - Group imports in the following order:
        1. Standard library imports.
        2. Related third-party imports.
        3. Local application/library-specific imports.
    - Use absolute imports.

## 2. Strict Typing
Every function and method must have complete type annotations.
- Use the `typing` module (or built-in types for Python 3.9+) for all type hints.
- **Avoid `Any`** unless absolutely necessary. Be specific (e.g., use `Union`, `Optional`, `Dict`, `List`).
- Annotate function parameters and return types:
    ```python
    def process_data(items: list[str], limit: int = 10) -> dict[str, int]:
        ...
    ```
- Use `TypedDict` or `dataclasses` for complex data structures instead of raw dictionaries where possible.

## 3. Documentation
- Use **Google-style docstrings** for all modules, classes, and functions.
- Include `Args`, `Returns`, and `Raises` sections where applicable.
    ```python
    def calculate_metrics(data: list[float]) -> float:
        """Calculates the average of the provided data.

        Args:
            data: A list of floats to process.

        Returns:
            The mean value of the data.

        Raises:
            ValueError: If the data list is empty.
        """
        ...
    ```

### Integration and Automation
The project uses **Ruff** for consistent formatting and linting, configured in `pyproject.toml`.

#### For the User (VS Code/Cursor)
Formatting and basic linting are **automatic**. Saving a file will trigger Ruff to:
1.  Format the code.
2.  Organize imports.
3.  Fix safe linting violations.
*Note: Ensure the Ruff extension is installed.*

#### For the Agent (Antigravity/Jetski)
When the agent modifies files directly on disk, VS Code's "format on save" **does not trigger**. Therefore:
1.  The agent should run `ruff format <file>` after modifying Python files.
2.  The agent should run `ruff check --fix <file>` to ensure compliance.

#### Bulk Operations
To check or format the entire project:
```powershell
# Format all files
ruff format .
# Check and fix all files
ruff check --fix .
```

## When to use this skill
- Whenever writing or refactoring Python code.
- Before committing changes to ensure linting passes.
- During code reviews to ensure compliance.
- When generating new modules or functions.
