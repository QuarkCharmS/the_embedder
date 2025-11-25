"""
Extract project structure and generate metadata documents.

Functions:
- generate_project_tree(): Visual directory structure
- analyze_python_dependencies(): Dependency graph and module analysis

See ARCHITECTURE.md for detailed flow and logic.
"""

import os
import ast
from pathlib import Path
from typing import List, Tuple
from collections import defaultdict

_SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    'dist', 'build', '.pytest_cache', '.tox', 'htmlcov',
    'egg-info', '.eggs', 'wheels', 'pip-wheel-metadata',
    'test-venv', 'site-packages'
}


def format_size(file_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if file_bytes < 1024.0:
            return f"{file_bytes:.1f}{unit}"
        file_bytes /= 1024.0
    return f"{file_bytes:.1f}TB"


def should_skip_file(file_path: Path, directory: Path = None, gitignore_spec=None) -> bool:
    """Check if file should be skipped during analysis."""
    if gitignore_spec and directory:
        try:
            rel_path = file_path.relative_to(directory)
            rel_path_str = str(rel_path).replace(os.sep, '/')
            if gitignore_spec.match_file(rel_path_str):
                return True
        except ValueError:
            pass

    parts = file_path.parts
    return any(skip_dir in parts for skip_dir in _SKIP_DIRS)


def _should_skip_dir(path: Path, directory: Path, gitignore_spec) -> bool:
    """Check if directory path should be skipped."""
    if gitignore_spec:
        try:
            rel_path = path.relative_to(directory)
            rel_path_str = str(rel_path).replace(os.sep, '/')
            if path.is_dir():
                rel_path_str += '/'
            if gitignore_spec.match_file(rel_path_str):
                return True
        except ValueError:
            pass

    parts = path.parts
    return any(skip_dir in parts for skip_dir in _SKIP_DIRS)


def generate_project_tree(
    directory: Path, repo_name: str, max_depth: int = None, gitignore_spec=None
) -> str:
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
    lines = [f"# Project Structure: {repo_name}\n", "```"]

    def walk_tree(path: Path, prefix: str = "", depth: int = 0):
        """Recursively walk and format directory tree."""
        if max_depth is not None and depth > max_depth:
            return

        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return

        items = [item for item in items if not _should_skip_dir(item, directory, gitignore_spec)]

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if item.is_dir():
                lines.append(f"{prefix}{connector}{item.name}/")
                walk_tree(item, prefix + extension, depth + 1)
            else:
                size = item.stat().st_size
                size_str = format_size(size)
                lines.append(f"{prefix}{connector}{item.name} ({size_str})")

    lines.append(f"{repo_name}/")
    walk_tree(directory, "", 0)
    lines.append("```")

    return "\n".join(lines)


def _parse_python_file(py_file: Path, directory: Path):
    """Parse a Python file and extract module info, imports, classes, and functions."""
    rel_path = py_file.relative_to(directory)
    module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

    module_info = {
        'module_name': module_name,
        'imports': set(),
        'classes': set(),
        'functions': set()
    }

    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=str(py_file))

            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_info['imports'].add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_info['imports'].add(node.module)

            # Extract top-level classes and functions
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    module_info['classes'].add(node.name)
                elif isinstance(node, ast.FunctionDef):
                    module_info['functions'].add(node.name)

    except (SyntaxError, OSError):
        pass

    return module_info


def _format_summary_statistics(
    python_files_count: int, module_imports, module_classes, module_functions
):
    """Format summary statistics section."""
    lines = [
        "## Summary Statistics",
        f"- Total modules analyzed: {len(module_imports)}",
        f"- Total classes defined: {sum(len(v) for v in module_classes.values())}",
        f"- Total functions defined: {sum(len(v) for v in module_functions.values())}",
        ""
    ]
    return lines


def _format_external_dependencies(all_imports):
    """Format external dependencies section."""
    lines = []
    external_deps = sorted([imp for imp in all_imports if not imp.startswith('.')])

    if external_deps:
        lines.append("## External Dependencies")
        lines.append("```")
        for dep in external_deps[:50]:
            lines.append(f"  - {dep}")
        if len(external_deps) > 50:
            lines.append(f"  ... and {len(external_deps) - 50} more")
        lines.append("```")
        lines.append("")

    return lines


def _format_module_structure(module_imports, module_classes, module_functions):
    """Format module structure section."""
    lines = ["## Module Structure", "```"]
    sorted_modules = sorted(module_imports.keys())

    for module_name in sorted_modules[:100]:
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
            internal_imports = [imp for imp in imports if '.' in imp or imp in sorted_modules]
            if internal_imports:
                lines.append(f"  Internal imports: {', '.join(sorted(internal_imports)[:5])}")
                if len(internal_imports) > 5:
                    lines.append(f"    ... and {len(internal_imports) - 5} more")

    if len(sorted_modules) > 100:
        lines.append(f"\n... and {len(sorted_modules) - 100} more modules")

    lines.append("```")
    return lines


def _format_dependency_graph(module_imports):
    """Format internal dependency graph section."""
    lines = ["\n## Internal Dependency Graph", "```", "Module dependencies (internal only):"]
    sorted_modules = sorted(module_imports.keys())

    for module_name in sorted_modules[:50]:
        imports = module_imports[module_name]
        internal_deps = [imp for imp in imports if imp in sorted_modules]
        if internal_deps:
            lines.append(f"{module_name}")
            for dep in sorted(internal_deps):
                lines.append(f"  → {dep}")

    if len(sorted_modules) > 50:
        lines.append(f"\n... and {len(sorted_modules) - 50} more modules with dependencies")

    lines.append("```")
    return lines


def analyze_python_dependencies(directory: Path, repo_name: str, gitignore_spec=None) -> str:
    """
    Analyze Python files to create a dependency graph.

    Uses AST to parse imports and create a module-level dependency graph.
    """
    python_files = list(directory.rglob("*.py"))
    python_files = [f for f in python_files if not should_skip_file(f, directory, gitignore_spec)]

    if not python_files:
        return f"# Python Dependency Analysis: {repo_name}\n\nNo Python files found."

    module_imports = defaultdict(set)
    module_classes = defaultdict(set)
    module_functions = defaultdict(set)

    # Parse all Python files
    for py_file in python_files:
        try:
            module_info = _parse_python_file(py_file, directory)
            module_name = module_info['module_name']
            module_imports[module_name] = module_info['imports']
            module_classes[module_name] = module_info['classes']
            module_functions[module_name] = module_info['functions']
        except Exception:
            continue

    # Collect all imports
    all_imports = set()
    for imports in module_imports.values():
        all_imports.update(imports)

    # Build the output
    lines = [
        f"# Python Dependency Analysis: {repo_name}\n",
        f"Total Python Files: {len(python_files)}\n"
    ]

    lines.extend(_format_summary_statistics(
        len(python_files), module_imports, module_classes, module_functions
    ))
    lines.extend(_format_external_dependencies(all_imports))
    lines.extend(_format_module_structure(module_imports, module_classes, module_functions))
    lines.extend(_format_dependency_graph(module_imports))

    return "\n".join(lines)


def generate_project_metadata(
    directory: Path, repo_name: str, gitignore_spec=None
) -> List[Tuple[str, str]]:
    """
    Generate all project metadata documents.

    Returns list of (title, content) tuples that can be uploaded as chunks.
    """
    metadata_docs = []

    tree = generate_project_tree(directory, repo_name, max_depth=10, gitignore_spec=gitignore_spec)
    metadata_docs.append((f"{repo_name}/PROJECT_TREE.md", tree))

    deps = analyze_python_dependencies(directory, repo_name, gitignore_spec=gitignore_spec)
    metadata_docs.append((f"{repo_name}/PYTHON_DEPENDENCIES.md", deps))

    return metadata_docs
