# chunker_config.py
# === Node types to extract per language (Tree-sitter based) ===
# Updated to match actual tree-sitter-languages package node types
LANG_FUNCTION_NODES = {
    # === Core Programming Languages ===
    "python": {"function_definition", "class_definition"},  # removed async_function_definition (doesn't exist separately)
    "javascript": {"function_declaration", "method_definition", "arrow_function", "function_expression", "class_declaration", "generator_function_declaration"},
    "typescript": {"function_declaration", "method_definition", "arrow_function", "function_expression", "class_declaration", "interface_declaration", "type_alias_declaration"},
    "tsx": {"function_declaration", "method_definition", "arrow_function", "function_expression", "class_declaration", "interface_declaration", "type_alias_declaration"},
    "java": {"class_declaration", "method_declaration", "constructor_declaration", "interface_declaration", "enum_declaration"},
    "c": {"function_definition", "struct_specifier", "union_specifier", "enum_specifier"},
    "cpp": {"function_definition", "class_specifier", "struct_specifier", "namespace_definition", "template_declaration"},
    "csharp": {"class_declaration", "method_declaration", "constructor_declaration", "interface_declaration", 
               "struct_declaration", "enum_declaration", "namespace_declaration", "property_declaration",
               "field_declaration", "event_declaration"},  # added more node types
    "go": {"function_declaration", "method_declaration", "type_declaration"},  # removed package_clause (usually top-level)
    "rust": {"function_item", "impl_item", "struct_item", "enum_item", "trait_item", "mod_item", "macro_definition"},
    "ruby": {"class", "module", "method", "singleton_method"},  # removed 'def' (it's part of method)
    
    # === Functional Languages ===
    "haskell": {"function", "data", "type", "class", "instance"},  # simplified node names
    "elixir": {"call", "do_block"},  # elixir uses 'call' nodes for function definitions
    "erlang": {"function_clause", "module_attribute", "record_declaration"},
    "ocaml": {"value_definition", "type_definition", "module_definition", "class_definition"},
    "commonlisp": {"list_lit", "defun"},  # commonlisp uses list_lit for most constructs
    "elisp": {"list"},  # elisp is also just lists
    
    # === JVM Languages ===
    "kotlin": {"function_declaration", "class_declaration", "object_declaration", "interface_declaration", "property_declaration"},
    "scala": {"function_definition", "class_definition", "object_definition", "trait_definition", "val_definition", "var_definition"},  # changed declaration to definition
    
    # === Web & Mobile ===
    "php": {"function_definition", "method_declaration", "class_declaration", "interface_declaration", "trait_declaration"},  # changed function_declaration to function_definition
    "objc": {"method_declaration", "interface_declaration", "implementation_declaration", "protocol_declaration"},  # updated node types
    
    # === Scripting Languages ===
    "bash": {"function_definition", "compound_statement"},
    "perl": {"subroutine_declaration", "package_statement", "use_statement"},
    "lua": {"function_definition_statement", "local_function_definition_statement", "variable_assignment"},  # correct lua node types
    
    # === Data Science & Numeric ===
    "r": {"function_definition", "assignment", "call"},
    "julia": {"function_definition", "struct_definition", "module_definition", "macro_definition"},  # removed abstract_definition
    "fortran": {"program", "subroutine", "function", "module"},  # simplified node names
    
    # === Query Languages ===
    "sql": {"create_statement", "select_statement", "insert_statement", "update_statement", "delete_statement"},  # simplified names
    "ql": {"select", "from", "where", "predicate"},
    
    # === Configuration & Build Languages ===
    "hcl": {"block", "attribute", "function_call"},
    "dockerfile": {"from_instruction", "run_instruction", "cmd_instruction", "copy_instruction", 
                   "workdir_instruction", "env_instruction", "expose_instruction", "label_instruction",
                   "arg_instruction", "add_instruction", "entrypoint_instruction", "volume_instruction",
                   "user_instruction", "healthcheck_instruction", "shell_instruction", "stopsignal_instruction",
                   "onbuild_instruction", "maintainer_instruction"},  # actual tree-sitter-dockerfile node types
    "yaml": {"block_mapping", "block_sequence", "flow_mapping", "flow_sequence"},
    "toml": {"table", "table_array_element", "pair"},  # changed array_of_tables
    "json": {"object", "array", "pair"},
    "make": {"rule", "variable_assignment", "function_call"},
    
    # === Web Technologies ===
    "html": {"element", "doctype"},  # removed comment (usually not needed for chunking)
    "css": {"rule_set", "at_rule", "declaration"},  # removed media_query_list
    "embedded-template": {"content", "directive"},  # changed embedded_template to embedded-template
    
    # === Documentation ===
    "markdown": {"section", "heading", "fenced_code_block", "code_span"},  # updated node types
    "rst": {"section", "directive", "literal_block"},  # changed code_block to literal_block
    "jsdoc": {"description", "tag"},  # removed type (part of tag)
    
    # === Specialized Languages ===
    "hack": {"function_declaration", "class_declaration", "method_declaration", "interface_declaration"},
    "elm": {"function_declaration", "type_declaration", "type_alias_declaration", "port_declaration"},  # updated node types
    "dot": {"edge_stmt", "node_stmt", "block", "stmt_list"},  # actual dot node types
    "regex": {"pattern", "group", "character_class"},  # updated node types
    
    # === Languages NOT in tree-sitter-languages (removed) ===
    # Removed: tsq (tree-sitter query language - not in package)
    
    # === Fallback for unknown languages ===
    "default": {
        "function", "method", "function_definition", "function_declaration",
        "procedure", "block", "section", "class", "module", "struct",
        "interface", "enum", "type", "namespace", "package"
    }
}

# === File extension to language mapping ===
# Updated to match tree-sitter-languages package language names
EXT_TO_LANG = {
    # === Core Programming Languages ===
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript", 
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".java": "java",
    ".cs": "csharp",  # changed from c_sharp
    ".rb": "ruby",
    ".rbx": "ruby",
    ".rbi": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".h++": "cpp",
    
    # === Functional Languages ===
    ".hs": "haskell",
    ".lhs": "haskell",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".lisp": "commonlisp",
    ".cl": "commonlisp",
    ".el": "elisp",
    
    # === JVM Languages ===
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sc": "scala",
    
    # === Web & Mobile ===
    ".php": "php",
    ".php3": "php",
    ".php4": "php",
    ".php5": "php",
    ".phtml": "php",
    ".m": "objc",
    ".mm": "objc",
    
    # === Shell / scripting ===
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ksh": "bash",
    ".pl": "perl",
    ".pm": "perl",
    ".t": "perl",
    ".lua": "lua",
    
    # === Data Science & Numeric ===
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
    ".f": "fortran",
    ".f90": "fortran",
    ".f95": "fortran",
    ".f03": "fortran",
    ".f08": "fortran",
    ".for": "fortran",
    ".ftn": "fortran",
    
    # === Query Languages ===
    ".sql": "sql",
    ".ql": "ql",
    
    # === Configuration & Build ===
    ".tf": "hcl",
    ".tfvars": "hcl",
    ".hcl": "hcl",
    ".dockerfile": "dockerfile",
    ".containerfile": "dockerfile",
    "Dockerfile": "dockerfile",
    "Containerfile": "dockerfile",
    "dockerfile": "dockerfile",  # for test files named exactly "dockerfile"
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".jsonc": "json",
    ".json5": "json",
    ".make": "make",
    "Makefile": "make",
    "makefile": "make",
    "GNUmakefile": "make",
    "Makefile.am": "make",
    "Makefile.in": "make",
    
    # === Web Technologies ===
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".css": "css",
    ".erb": "embedded-template",  # changed from embedded_template
    ".ejs": "embedded-template",
    
    # === Documentation ===
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".mkd": "markdown",
    ".rst": "rst",
    
    # === Specialized Languages ===
    ".hack": "hack",
    ".hh": "hack",  # Hack also uses .hh extension
    ".elm": "elm",
    ".dot": "dot",
    ".gv": "dot",
    ".re": "regex",
    # Removed .tsq - not in tree-sitter-languages
    
    # === Assembly & Low-level (NOT SUPPORTED - will use fallback) ===
    ".s": "default",
    ".S": "default", 
    ".asm": "default",
    
    # === Misc / fallback ===
    ".txt": "markdown",
    ".log": "markdown",
    ".text": "markdown",
    
    # === Non-chunkable formats (fallback to default) ===
    ".ini": "default",
    ".cfg": "default",
    ".conf": "default",
    ".config": "default",
    ".env": "default",
    ".properties": "default",
}

# === Languages that can be chunked semantically using Tree-sitter ===
# Updated to match what's actually available in tree-sitter-languages
CHUNKABLE_LANGUAGES = {
    # ONLY ACTUAL PROGRAMMING LANGUAGES - non-code files use chonkie fallback

    # Core programming languages
    "python", "javascript", "typescript", "tsx", "java", "c", "cpp",
    "go", "rust", "ruby",

    # Functional languages
    "haskell", "elixir", "erlang", "ocaml", "commonlisp", "elisp",

    # JVM languages
    "kotlin", "scala",

    # Web & mobile
    "php", "objc",

    # Scripting languages
    "bash", "perl", "lua",

    # Data science & numeric
    "r", "julia", "fortran",

    # Query languages
    "sql", "ql",

    # Build tools
    "dockerfile", "make",

    # Specialized code languages
    "hack", "elm"

    # REMOVED (not code, use chonkie instead):
    # - markdown, rst, jsdoc (documentation - not code)
    # - yaml, toml, json (config files - not code)
    # - html, css (markup/styling - not code)
    # - hcl (config - not code)
    # - embedded-template (markup - not code)
    # - dot, regex (edge cases - not worth tree-sitter crashes)
}

# === Helper functions ===
def get_language_from_extension(file_path: str) -> str:
    """Get language identifier from file path/extension."""
    import os
    
    # Handle special cases first (exact filename matches)
    filename = os.path.basename(file_path)
    if filename in EXT_TO_LANG:
        return EXT_TO_LANG[filename]
    
    # Handle extensions
    _, ext = os.path.splitext(file_path)
    return EXT_TO_LANG.get(ext.lower(), "default")

def get_function_nodes(language: str) -> set:
    """Get the set of node types to extract for a given language."""
    return LANG_FUNCTION_NODES.get(language, LANG_FUNCTION_NODES["default"])

def is_chunkable(language: str) -> bool:
    """Check if a language can be chunked semantically."""
    return language in CHUNKABLE_LANGUAGES

# === Debugging helper ===
def list_available_languages():
    """List all languages that should be available in tree-sitter-languages."""
    return sorted(CHUNKABLE_LANGUAGES)

# === Additional helper to verify node types ===
def verify_language_setup():
    """
    Verify that tree-sitter-languages is installed and working.
    This can help debug issues with language identification.
    """
    try:
        from tree_sitter_languages import get_language, get_parser
        
        # Test a few common languages
        test_langs = ["python", "javascript", "typescript"]
        results = {}
        
        for lang in test_langs:
            try:
                language = get_language(lang)
                parser = get_parser(lang)
                results[lang] = "OK"
            except Exception as e:
                results[lang] = f"Error: {str(e)}"
        
        return results
    except ImportError:
        return "tree-sitter-languages not installed"

# === Example usage for debugging ===
if __name__ == "__main__":
    # Test the configuration
    print("Testing language detection:")
    test_files = [
        "test.py", "app.js", "main.ts", "Component.tsx",
        "Main.java", "program.cs", "main.go", "lib.rs"
    ]
    
    for file in test_files:
        lang = get_language_from_extension(file)
        nodes = get_function_nodes(lang)
        chunkable = is_chunkable(lang)
        print(f"{file:15} -> Language: {lang:12} Chunkable: {chunkable:5} Nodes: {len(nodes)}")
    
    print("\nVerifying tree-sitter-languages setup:")
    print(verify_language_setup())
