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

## 4. Formatting and Linting with Ruff
The project uses **Ruff** for consistent formatting and linting, configured in `pyproject.toml` to match the Google Style Guide.

### Auto-Formatting
To auto-format files according to the guidelines:
```powershell
ruff format .
```

### Linting and Auto-Fixing
To run the linter and automatically fix safe violations (including import sorting):
```powershell
ruff check --fix .
```

### Integration in Jetski
To ensure files are auto-formatted when working with the agent:
1.  The agent should run `ruff format` after making significant changes to Python files.
2.  The agent should run `ruff check --fix` to ensure imports are sorted and common issues are resolved.

## When to use this skill
- Whenever writing or refactoring Python code.
- Before committing changes to ensure linting passes.
- During code reviews to ensure compliance.
- When generating new modules or functions.
