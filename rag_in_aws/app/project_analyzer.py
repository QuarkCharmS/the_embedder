"""
Project Analysis Utilities

Extracts structural information from code repositories:
1. Project tree structure
2. Python dependency graph using AST analysis
"""

import os
import ast
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict


def generate_project_tree(directory: Path, repo_name: str, max_depth: int = None, gitignore_spec=None) -> str:
    """
    Generate a text representation of the project directory structure.

    Args:
        directory: Root directory to analyze
        repo_name: Name of the repository
        max_depth: Maximum depth to traverse (None for unlimited)
        gitignore_spec: Optional pathspec.PathSpec object for .gitignore patterns

    Returns:
        Formatted tree structure as string
    """
    lines = [f"# Project Structure: {repo_name}\n"]
    lines.append("```")

    def should_skip(path: Path) -> bool:
        """Check if path should be skipped."""
        # First check .gitignore patterns if available
        if gitignore_spec:
            try:
                rel_path = path.relative_to(directory)
                # pathspec expects forward slashes
                rel_path_str = str(rel_path).replace(os.sep, '/')
                # Add trailing slash for directories
                if path.is_dir():
                    rel_path_str += '/'
                if gitignore_spec.match_file(rel_path_str):
                    return True
            except ValueError:
                pass  # path not relative to directory

        # Fallback to hardcoded common patterns
        parts = path.parts
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                     'dist', 'build', '.pytest_cache', '.tox', 'htmlcov',
                     'egg-info', '.eggs', 'wheels', 'pip-wheel-metadata'}
        return any(skip_dir in parts for skip_dir in skip_dirs)

    def walk_tree(path: Path, prefix: str = "", depth: int = 0):
        """Recursively walk and format directory tree."""
        if max_depth is not None and depth > max_depth:
            return

        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return

        # Filter out items we want to skip
        items = [item for item in items if not should_skip(item)]

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            # Add file/dir name
            if item.is_dir():
                lines.append(f"{prefix}{connector}{item.name}/")
                # Recurse into directory
                walk_tree(item, prefix + extension, depth + 1)
            else:
                # Add file size for files
                size = item.stat().st_size
                size_str = format_size(size)
                lines.append(f"{prefix}{connector}{item.name} ({size_str})")

    # Start from root
    lines.append(f"{repo_name}/")
    walk_tree(directory, "", 0)
    lines.append("```")

    return "\n".join(lines)


def format_size(bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}TB"


def analyze_python_dependencies(directory: Path, repo_name: str, gitignore_spec=None) -> str:
    """
    Analyze Python files to create a dependency graph.

    Uses AST to parse imports and create a module-level dependency graph.

    Args:
        directory: Root directory containing Python files
        repo_name: Name of the repository
        gitignore_spec: Optional pathspec.PathSpec object for .gitignore patterns

    Returns:
        Formatted dependency analysis as string
    """
    # Find all Python files
    python_files = list(directory.rglob("*.py"))

    # Filter out common exclusions
    python_files = [f for f in python_files if not should_skip_file(f, directory, gitignore_spec)]

    if not python_files:
        return f"# Python Dependency Analysis: {repo_name}\n\nNo Python files found."

    # Module to imports mapping
    module_imports = defaultdict(set)
    # Module to classes mapping
    module_classes = defaultdict(set)
    # Module to functions mapping
    module_functions = defaultdict(set)

    # Parse each Python file
    for py_file in python_files:
        try:
            rel_path = py_file.relative_to(directory)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                try:
                    tree = ast.parse(f.read(), filename=str(py_file))

                    # Extract imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                module_imports[module_name].add(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                module_imports[module_name].add(node.module)

                    # Extract top-level classes and functions
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef):
                            module_classes[module_name].add(node.name)
                        elif isinstance(node, ast.FunctionDef):
                            module_functions[module_name].add(node.name)

                except SyntaxError:
                    # Skip files with syntax errors
                    continue

        except Exception:
            # Skip files that can't be read
            continue

    # Build the output
    lines = [f"# Python Dependency Analysis: {repo_name}\n"]
    lines.append(f"Total Python Files: {len(python_files)}\n")

    # Summary statistics
    lines.append("## Summary Statistics")
    lines.append(f"- Total modules analyzed: {len(module_imports)}")
    lines.append(f"- Total classes defined: {sum(len(v) for v in module_classes.values())}")
    lines.append(f"- Total functions defined: {sum(len(v) for v in module_functions.values())}")
    lines.append("")

    # External dependencies (stdlib and third-party)
    all_imports = set()
    for imports in module_imports.values():
        all_imports.update(imports)

    # Filter to likely external dependencies (exclude relative imports)
    external_deps = sorted([imp for imp in all_imports if not imp.startswith('.')])
    if external_deps:
        lines.append("## External Dependencies")
        lines.append("```")
        for dep in external_deps[:50]:  # Limit to first 50
            lines.append(f"  - {dep}")
        if len(external_deps) > 50:
            lines.append(f"  ... and {len(external_deps) - 50} more")
        lines.append("```")
        lines.append("")

    # Internal module structure
    lines.append("## Module Structure")
    lines.append("```")

    # Sort modules by path depth and name
    sorted_modules = sorted(module_imports.keys())

    for module_name in sorted_modules[:100]:  # Limit to first 100 modules
        imports = module_imports[module_name]
        classes = module_classes.get(module_name, set())
        functions = module_functions.get(module_name, set())

        lines.append(f"\n{module_name}")

        if classes:
            lines.append(f"  Classes: {', '.join(sorted(classes)[:10])}")
            if len(classes) > 10:
                lines.append(f"    ... and {len(classes) - 10} more")

        if functions:
            lines.append(f"  Functions: {', '.join(sorted(functions)[:10])}")
            if len(functions) > 10:
                lines.append(f"    ... and {len(functions) - 10} more")

        if imports:
            # Filter to likely internal imports (start with repo module structure)
            internal_imports = [imp for imp in imports if '.' in imp or imp in sorted_modules]
            if internal_imports:
                lines.append(f"  Internal imports: {', '.join(sorted(internal_imports)[:5])}")
                if len(internal_imports) > 5:
                    lines.append(f"    ... and {len(internal_imports) - 5} more")

    if len(sorted_modules) > 100:
        lines.append(f"\n... and {len(sorted_modules) - 100} more modules")

    lines.append("```")

    # Dependency graph (internal dependencies only)
    lines.append("\n## Internal Dependency Graph")
    lines.append("```")
    lines.append("Module dependencies (internal only):")

    for module_name in sorted_modules[:50]:  # Limit to first 50
        imports = module_imports[module_name]
        # Filter to internal dependencies
        internal_deps = [imp for imp in imports if imp in sorted_modules]
        if internal_deps:
            lines.append(f"{module_name}")
            for dep in sorted(internal_deps):
                lines.append(f"  → {dep}")

    if len(sorted_modules) > 50:
        lines.append(f"\n... and {len(sorted_modules) - 50} more modules with dependencies")

    lines.append("```")

    return "\n".join(lines)


def should_skip_file(file_path: Path, directory: Path = None, gitignore_spec=None) -> bool:
    """Check if file should be skipped during analysis."""
    # First check .gitignore patterns if available
    if gitignore_spec and directory:
        try:
            rel_path = file_path.relative_to(directory)
            # pathspec expects forward slashes
            rel_path_str = str(rel_path).replace(os.sep, '/')
            if gitignore_spec.match_file(rel_path_str):
                return True
        except ValueError:
            pass  # file_path not relative to directory

    # Fallback to hardcoded common patterns
    parts = file_path.parts
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                 'dist', 'build', '.pytest_cache', '.tox', 'htmlcov',
                 'egg-info', '.eggs', 'wheels', 'pip-wheel-metadata',
                 'test-venv', 'site-packages'}
    return any(skip_dir in parts for skip_dir in skip_dirs)


def generate_project_metadata(directory: Path, repo_name: str, gitignore_spec=None) -> List[Tuple[str, str]]:
    """
    Generate all project metadata documents.

    Returns list of (title, content) tuples that can be uploaded as chunks.

    Args:
        directory: Root directory of the project
        repo_name: Name of the repository
        gitignore_spec: Optional pathspec.PathSpec object for .gitignore patterns

    Returns:
        List of (title, content) tuples for metadata documents
    """
    metadata_docs = []

    tree = generate_project_tree(directory, repo_name, max_depth=10, gitignore_spec=gitignore_spec)
    metadata_docs.append((f"{repo_name}/PROJECT_TREE.md", tree))

    deps = analyze_python_dependencies(directory, repo_name, gitignore_spec=gitignore_spec)
    metadata_docs.append((f"{repo_name}/PYTHON_DEPENDENCIES.md", deps))

    return metadata_docs
