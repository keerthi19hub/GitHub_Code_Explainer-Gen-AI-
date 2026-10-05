"""Clone, inspect, and select important files from a repository."""

import ast
import io
import logging
import os
import re
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from git import Repo

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


logger = logging.getLogger(__name__)

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".vscode",
    ".idea",
    "dist",
    "build",
    "coverage",
    ".cache",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".kt",
    ".swift",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".gradle",
    ".mod",
    ".txt",
}

SOURCE_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".kt",
    ".swift",
    ".html",
    ".css",
    ".scss",
    ".sql",
}

ENTRY_POINT_NAMES = {
    "app.py",
    "main.py",
    "server.py",
    "index.py",
    "application.py",
    "manage.py",
    "app.js",
    "main.js",
    "server.js",
    "index.js",
    "app.ts",
    "main.ts",
    "index.ts",
    "index.tsx",
    "main.go",
    "main.rs",
}

MANIFEST_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "gemfile",
}

DOCUMENT_EXTENSIONS = {".md", ".txt", ".rst"}
DATA_EXTENSIONS = {".csv", ".json", ".xml", ".yaml", ".yml"}
CONFIGURATION_NAMES = {
    "dockerfile",
    ".gitignore",
    ".dockerignore",
    "makefile",
}
POWER_BI_EXTENSIONS = {".pbix", ".pbit"}
BINARY_EXTENSIONS = {
    ".exe",
    ".dll",
    ".zip",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mov",
    ".avi",
}

MAX_FILE_SIZE_BYTES = 100_000
MAX_FILE_CONTENT_CHARACTERS = 4_000
MAX_FILES_FOR_DEEP_ANALYSIS = 8
MAX_DEEP_SOURCE_CHARACTERS = 6_000
MAX_STRUCTURE_ENTRIES = 80
MAX_PDF_FILE_BYTES = 8_000_000
MAX_PDF_PAGES = 12
MAX_PDF_TEXT_CHARACTERS = 700
MAX_DOCUMENT_CONTENT_CHARACTERS = 7_000
MAX_README_CONTENT_CHARACTERS = 1_500
MAX_EXPERIMENT_README_CHARACTERS = 600
MAX_OTHER_DOCUMENT_CHARACTERS = 1_200


def clone_repository(github_url, destination_path):
    """Fetch a public repository's Git objects without checking out its files."""
    parsed_url = urlparse(github_url)
    path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]

    # Restrict cloning to GitHub and use only its owner/repository path.
    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError("The repository URL must start with http:// or https://.")
    if parsed_url.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("Please enter a public GitHub repository URL.")
    if len(path_parts) < 2:
        raise ValueError("The URL must include a GitHub username and repository name.")

    owner = path_parts[0]
    repository_name = path_parts[1]
    clone_url = f"https://github.com/{owner}/{repository_name}"
    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    # A no-checkout clone can inspect Git blobs without creating unsafe Windows paths.
    return Repo.clone_from(clone_url, str(destination_path), no_checkout=True)


@contextmanager
def open_repository(github_url, destination_path):
    """Open a no-checkout clone and close GitPython handles before temp cleanup."""
    repository = clone_repository(github_url, destination_path)
    try:
        yield repository
    finally:
        repository.close()


def get_file_priority(file_path):
    """Give application files a higher priority than tests and documentation."""
    file_path = Path(file_path)
    file_name = file_path.name.lower()
    path_parts = {part.lower() for part in file_path.parts}

    if file_name.startswith("readme"):
        return -3 if len(file_path.parts) == 1 else -2
    if file_path.suffix.lower() == ".pdf":
        return -1
    if (
        any(part in {"test", "tests", "spec", "specs"} for part in path_parts)
        or file_name.startswith("test_")
        or ".test." in file_name
        or "bench" in file_name
    ):
        return 8
    if file_name in ENTRY_POINT_NAMES:
        return 0
    if "backend" in path_parts or "server" in path_parts:
        return 1
    if path_parts.intersection({"frontend", "client", "src"}):
        return 2
    if "models" in path_parts or "model" in path_parts:
        return 3
    if "database" in path_parts or "db" in path_parts:
        return 4
    if path_parts.intersection({"api", "service", "services"}):
        return 5
    if file_name in MANIFEST_NAMES:
        return 6
    if path_parts.intersection({"docs", ".github", ".devcontainer"}) or file_name.startswith(
        "readme"
    ):
        return 9
    if file_path.suffix.lower() in SOURCE_CODE_EXTENSIONS:
        return 6
    return 9


def classify_file(path):
    """Return a simple content category based on a tracked file's name/type."""
    file_path = Path(path)
    file_name = file_path.name.lower()
    extension = file_path.suffix.lower()

    if file_name.startswith("readme"):
        return "README/documentation"
    if extension in SOURCE_CODE_EXTENSIONS:
        return "source code"
    if extension in DOCUMENT_EXTENSIONS:
        return "documentation"
    if extension in DATA_EXTENSIONS:
        return "data/configuration"
    if extension == ".pdf":
        return "PDF document"
    if extension in POWER_BI_EXTENSIONS:
        return "Power BI report"
    if extension in BINARY_EXTENSIONS:
        return "binary/special file"
    if file_name in MANIFEST_NAMES or file_name in CONFIGURATION_NAMES:
        return "project/configuration file"
    return "other file"


def find_repository_files(repository):
    """Inventory every tracked blob from Git without checking out its path."""
    repository_files = []
    tree = repository.head.commit.tree

    for git_object in tree.traverse():
        if git_object.type != "blob":
            continue

        path = git_object.path
        path_parts = Path(path).parts
        if any(part.lower() in IGNORED_DIRECTORIES for part in path_parts):
            continue

        repository_files.append(
            {
                "path": path,
                "extension": Path(path).suffix.lower(),
                "size_bytes": git_object.size,
                "kind": classify_file(path),
                "priority": get_file_priority(path),
                "blob": git_object,
            }
        )

    repository_files.sort(
        key=lambda item: (item["priority"], item["path"].lower())
    )
    return repository_files


def format_file_type_summary(repository_files):
    """Count tracked files by category and extension."""
    category_counts = Counter(item["kind"] for item in repository_files)
    extension_counts = Counter(
        item["extension"] or "[no extension]" for item in repository_files
    )
    return {
        "categories": dict(sorted(category_counts.items())),
        "extensions": dict(sorted(extension_counts.items())),
    }


def detect_repository_type(file_summaries):
    """Classify a repository using its actual extensions and extracted text."""
    all_paths = [summary["path"] for summary in file_summaries]
    extensions = {Path(path).suffix.lower() for path in all_paths}
    readme_text = "\n".join(
        summary.get("content_excerpt", "")
        for summary in file_summaries
        if summary["kind"] == "README/documentation"
    ).lower()
    has_power_bi = bool(extensions.intersection(POWER_BI_EXTENSIONS))
    has_source = bool(extensions.intersection(SOURCE_CODE_EXTENSIONS))

    if has_power_bi and (
        "business analytics" in readme_text
        or "power bi" in readme_text
        or "dashboard" in readme_text
    ):
        return {
            "type": "Business Analytics / Power BI project",
            "evidence": "README text and tracked .pbix files",
        }

    if "machine learning" in readme_text or "model training" in readme_text:
        return {
            "type": "Machine Learning project",
            "evidence": "README text describes machine learning or model training",
        }

    if "data science" in readme_text and extensions.intersection(DATA_EXTENSIONS):
        return {
            "type": "Data Science project",
            "evidence": "README text and tracked data files",
        }

    if has_source:
        languages = []
        for extension, language in (
            (".py", "Python"),
            (".java", "Java"),
            (".js", "JavaScript"),
            (".ts", "TypeScript"),
            (".go", "Go"),
            (".rs", "Rust"),
        ):
            if extension in extensions:
                languages.append(language)
        if extensions.intersection({".html", ".css", ".js", ".ts", ".jsx", ".tsx"}):
            return {
                "type": "Web application or web project",
                "evidence": "tracked web source file extensions",
            }
        if len(languages) == 1:
            return {"type": f"{languages[0]} project", "evidence": ".".join(sorted(extensions))}
        return {"type": "Mixed software project", "evidence": ".".join(sorted(extensions))}

    if any(summary["kind"] == "PDF document" for summary in file_summaries):
        return {
            "type": "Documentation / document-based repository",
            "evidence": "README/documentation files and tracked PDF documents",
        }

    if any(summary["kind"] == "README/documentation" for summary in file_summaries):
        return {
            "type": "Documentation repository",
            "evidence": "tracked README/documentation files",
        }

    return {"type": "Other repository", "evidence": "available tracked file types"}


def read_git_blob(file_record, maximum_bytes=None):
    """Read a tracked Git blob directly without creating its path on disk."""
    blob_stream = file_record["blob"].data_stream
    if maximum_bytes is None:
        return blob_stream.read()
    return blob_stream.read(maximum_bytes)


def format_python_parameters(function_node):
    """Return a readable parameter list from a Python function definition."""
    arguments = function_node.args
    parameter_names = [
        argument.arg for argument in arguments.posonlyargs + arguments.args
    ]

    if arguments.vararg:
        parameter_names.append("*" + arguments.vararg.arg)
    parameter_names.extend(argument.arg for argument in arguments.kwonlyargs)
    if arguments.kwarg:
        parameter_names.append("**" + arguments.kwarg.arg)

    return f"{function_node.name}({', '.join(parameter_names)})"


def extract_python_structure(content):
    """Extract imports, functions, classes, and constants with Python's AST."""
    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return None

    imports = []
    functions = []
    classes = []
    constants = []

    for node in syntax_tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_names = ", ".join(alias.name for alias in node.names)
            imports.append(f"from {node.module or ''} import {imported_names}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(format_python_parameters(node))
        elif isinstance(node, ast.ClassDef):
            methods = [
                format_python_parameters(method)
                for method in node.body
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            classes.append({"name": node.name, "methods": methods})
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id.isupper():
                constants.append(node.target.id)

    return {
        "imports": list(dict.fromkeys(imports)),
        "functions": functions,
        "classes": classes,
        "constants": list(dict.fromkeys(constants)),
    }


def extract_text_structure(content):
    """Extract common imports, function signatures, classes, and constants by pattern."""
    imports = []
    classes = []
    functions = []
    constants = []

    for line in content.splitlines():
        stripped_line = line.strip()
        if re.match(r"(?:import\s|from\s|#include\b|using\s)", stripped_line):
            imports.append(stripped_line)

    class_pattern = re.compile(
        r"\b(?:class|interface|struct|enum)\s+([A-Za-z_$][\w$]*)"
    )
    for match in class_pattern.finditer(content):
        classes.append({"name": match.group(1), "methods": []})

    function_patterns = [
        re.compile(
            r"\b(?:async\s+)?(?:function|def|func|fn)\s+"
            r"([A-Za-z_$][\w$]*)\s*\(([^)]*)\)"
        ),
        re.compile(
            r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"(?:async\s*)?\(([^)]*)\)\s*=>"
        ),
        re.compile(
            r"^\s*(?:public|private|protected|static|async|export|inline|virtual|"
            r"override|final|suspend|[\w:<>,\[\]*&.?]+)\s+"
            r"([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*(?:\{|;)",
            re.MULTILINE,
        ),
    ]
    seen_functions = set()
    for pattern in function_patterns:
        for match in pattern.finditer(content):
            function_name = match.group(1)
            parameters = ", ".join(
                parameter.strip() for parameter in match.group(2).split(",")
                if parameter.strip()
            )
            signature = f"{function_name}({parameters})"
            if signature not in seen_functions:
                seen_functions.add(signature)
                functions.append(signature)

    constant_pattern = re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var|#define|static\s+final)\s+"
        r"([A-Z_][A-Z0-9_]*)\b",
        re.MULTILINE,
    )
    constants.extend(constant_pattern.findall(content))

    return {
        "imports": list(dict.fromkeys(imports)),
        "functions": functions,
        "classes": classes,
        "constants": list(dict.fromkeys(constants)),
    }


def extract_file_structure(file_path, content):
    """Create compact local structure facts for one supported text file."""
    file_path = Path(file_path)
    if file_path.suffix.lower() == ".py":
        structure = extract_python_structure(content)
    else:
        structure = None

    if structure is None:
        structure = extract_text_structure(content)

    return {
        "path": file_path.as_posix(),
        "extension": file_path.suffix.lower(),
        "priority": get_file_priority(file_path),
        "characters": len(content),
        "lines": len(content.splitlines()),
        "imports": structure["imports"][:8],
        "functions": structure["functions"][:12],
        "classes": structure["classes"][:6],
        "constants": structure["constants"][:8],
    }


def scan_repository_structure(repository_path, source_files):
    """Inspect Git blobs locally and extract bounded text or structural facts."""
    file_summaries = []
    skipped_files = []
    remaining_document_characters = MAX_DOCUMENT_CONTENT_CHARACTERS

    for file_record in source_files:
        path = file_record["path"]
        extension = file_record["extension"]
        kind = file_record["kind"]
        file_size = file_record["size_bytes"]
        summary = {
            "path": path,
            "extension": extension,
            "kind": kind,
            "priority": file_record["priority"],
            "size_bytes": file_size,
            "characters": 0,
            "lines": 0,
            "imports": [],
            "functions": [],
            "classes": [],
            "constants": [],
            "content_excerpt": "",
            "content_note": "",
            "content_extracted": False,
        }

        if kind == "Power BI report":
            summary["content_note"] = (
                "Power BI .pbix file; internal report content was not inspected."
            )
            skipped_files.append(path)
        elif extension == ".pdf":
            if PdfReader is None:
                summary["content_note"] = (
                    "PDF found; install pypdf to extract its text."
                )
                skipped_files.append(path)
            elif file_size > MAX_PDF_FILE_BYTES:
                summary["content_note"] = (
                    f"PDF exceeds the {MAX_PDF_FILE_BYTES}-byte extraction limit."
                )
                skipped_files.append(path)
            elif remaining_document_characters <= 0:
                summary["content_note"] = "PDF text budget was reached."
                skipped_files.append(path)
            else:
                try:
                    pdf_bytes = read_git_blob(file_record, MAX_PDF_FILE_BYTES + 1)
                    pdf_text = extract_pdf_text(pdf_bytes)
                except Exception as error:
                    logger.warning("Could not extract PDF %s: %s", path, error)
                    pdf_text = ""
                    summary["content_note"] = "PDF was found but its text could not be extracted."

                if pdf_text.strip():
                    excerpt_length = min(
                        MAX_PDF_TEXT_CHARACTERS,
                        remaining_document_characters,
                    )
                    summary["content_excerpt"] = pdf_text[:excerpt_length]
                    summary["characters"] = len(pdf_text)
                    summary["lines"] = len(pdf_text.splitlines())
                    summary["content_extracted"] = True
                    remaining_document_characters -= len(summary["content_excerpt"])
                    if len(pdf_text) > excerpt_length:
                        summary["content_note"] = "PDF text excerpt was truncated."
                else:
                    if not summary["content_note"]:
                        summary["content_note"] = "PDF was found but contained no extractable text."
                    skipped_files.append(path)
        elif kind in {
            "source code",
            "README/documentation",
            "documentation",
            "data/configuration",
            "project/configuration file",
        }:
            if file_size > MAX_FILE_SIZE_BYTES:
                summary["content_note"] = "File exceeds the local text-inspection size limit."
                skipped_files.append(path)
            elif kind != "source code" and remaining_document_characters <= 0:
                summary["content_note"] = "Text excerpt budget was reached."
                skipped_files.append(path)
            else:
                try:
                    file_bytes = read_git_blob(
                        file_record,
                        MAX_FILE_SIZE_BYTES + 1,
                    )
                except Exception as error:
                    logger.warning("Could not inspect %s: %s", path, error)
                    summary["content_note"] = "File was found but could not be read."
                    skipped_files.append(path)
                    file_summaries.append(summary)
                    continue

                if b"\0" in file_bytes:
                    summary["content_note"] = "Binary content was not inspected."
                    skipped_files.append(path)
                else:
                    content = file_bytes.decode("utf-8", errors="replace")
                    if not content.strip():
                        summary["content_note"] = "File is empty."
                        skipped_files.append(path)
                    else:
                        summary["characters"] = len(content)
                        summary["lines"] = len(content.splitlines())
                        summary["content_extracted"] = True
                        if kind == "source code":
                            structure = extract_file_structure(path, content)
                            for key in ("imports", "functions", "classes", "constants"):
                                summary[key] = structure[key]
                        else:
                            if kind == "README/documentation":
                                excerpt_limit = (
                                    MAX_README_CONTENT_CHARACTERS
                                    if len(Path(path).parts) == 1
                                    else MAX_EXPERIMENT_README_CHARACTERS
                                )
                            else:
                                excerpt_limit = MAX_OTHER_DOCUMENT_CHARACTERS
                            excerpt_limit = min(
                                excerpt_limit,
                                remaining_document_characters,
                            )
                            summary["content_excerpt"] = content[:excerpt_limit]
                            remaining_document_characters -= len(summary["content_excerpt"])
                            if len(content) > excerpt_limit:
                                summary["content_note"] = "Text excerpt was truncated."
        else:
            summary["content_note"] = (
                "File type was identified from its path; internal content was not inspected."
            )
            skipped_files.append(path)

        file_summaries.append(summary)

    return file_summaries, skipped_files


def extract_pdf_text(pdf_bytes):
    """Extract a bounded amount of text from the first few PDF pages."""
    if PdfReader is None:
        return ""

    reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
    if reader.is_encrypted:
        return ""

    extracted_pages = []
    page_count = min(len(reader.pages), MAX_PDF_PAGES)
    remaining_characters = MAX_PDF_TEXT_CHARACTERS

    for page_number in range(page_count):
        page_text = reader.pages[page_number].extract_text() or ""
        page_text = page_text.strip()
        if page_text:
            extracted_pages.append(page_text[:remaining_characters])
            remaining_characters -= min(len(page_text), remaining_characters)
        if remaining_characters <= 0:
            break

    return "\n".join(extracted_pages)[:MAX_PDF_TEXT_CHARACTERS]


def select_deep_analysis_files(file_summaries):
    """Select the highest-priority source files within the model's code budget."""
    selected_files = []
    remaining_characters = MAX_DEEP_SOURCE_CHARACTERS

    for summary in file_summaries:
        if summary["extension"] not in SOURCE_CODE_EXTENSIONS:
            continue
        if summary["priority"] >= 8:
            continue
        if len(selected_files) >= MAX_FILES_FOR_DEEP_ANALYSIS:
            break
        if remaining_characters <= 0:
            break

        selected_files.append(summary["path"])
        remaining_characters -= min(
            summary["characters"], MAX_FILE_CONTENT_CHARACTERS
        ) + len(summary["path"]) + 16

    return selected_files


def format_local_file_summaries(file_summaries):
    """Format local structure facts compactly for the final repository prompt."""
    summary_lines = []

    for summary in file_summaries:
        summary_lines.append(
            f"{summary['path']} ({summary['lines']} lines, "
            f"{summary['characters']} characters)"
        )
        if summary["imports"]:
            summary_lines.append("  imports: " + "; ".join(summary["imports"][:5]))
        if summary["classes"]:
            class_names = [item["name"] for item in summary["classes"]]
            summary_lines.append("  classes: " + ", ".join(class_names))
        if summary["functions"]:
            summary_lines.append(
                "  functions: " + "; ".join(summary["functions"][:8])
            )
        if summary["constants"]:
            summary_lines.append(
                "  constants: " + ", ".join(summary["constants"][:6])
            )
        if summary.get("content_excerpt"):
            summary_lines.append(
                "  extracted content:\n    "
                + summary["content_excerpt"].replace("\n", "\n    ")
            )
        if summary.get("content_note"):
            summary_lines.append("  content note: " + summary["content_note"])

    return "\n".join(summary_lines)


def find_source_files(repository_path):
    """Find supported files and put likely application files first."""
    repository_path = Path(repository_path)
    source_files = []

    for current_directory, directory_names, file_names in os.walk(repository_path):
        # Prune ignored folders so their contents are not visited at all.
        directory_names[:] = [
            name
            for name in directory_names
            if name.lower() not in IGNORED_DIRECTORIES
        ]

        for file_name in file_names:
            file_path = Path(current_directory) / file_name
            if (
                file_path.suffix.lower() not in SUPPORTED_EXTENSIONS
                and file_name.lower() not in MANIFEST_NAMES
            ):
                continue

            try:
                file_path.stat()
                source_files.append(file_path)
            except OSError:
                continue

    source_files.sort(
        key=lambda path: (
            path.stat().st_size > MAX_FILE_SIZE_BYTES,
            get_file_priority(path),
            path.suffix.lower() not in SOURCE_CODE_EXTENSIONS,
            str(path).lower(),
        )
    )
    return source_files


def read_source_files(repository_path, source_files):
    """Read selected tracked source blobs without materializing repository paths."""
    readable_files = []
    skipped_files = []

    for file_record in source_files:
        relative_path = file_record["path"]
        try:
            if file_record["size_bytes"] > MAX_FILE_SIZE_BYTES:
                logger.warning("Skipping oversized source file %s", relative_path)
                skipped_files.append(relative_path)
                continue
            # Only the selected code prefix is read from the Git object.
            file_bytes = read_git_blob(
                file_record,
                MAX_FILE_CONTENT_CHARACTERS + 1,
            )
            # A null byte usually means this is a binary file, even if its extension matches.
            if b"\0" in file_bytes:
                skipped_files.append(relative_path)
                continue
            file_content = file_bytes.decode("utf-8", errors="replace")
        except OSError as error:
            logger.warning("Could not read %s: %s", relative_path, error)
            skipped_files.append(relative_path)
            continue

        if file_content.strip():
            is_truncated = (
                file_record["size_bytes"] > MAX_FILE_CONTENT_CHARACTERS
                or len(file_content) > MAX_FILE_CONTENT_CHARACTERS
            )
            readable_files.append(
                {
                    "path": relative_path,
                    "content": file_content[:MAX_FILE_CONTENT_CHARACTERS],
                    "truncated": is_truncated,
                    "original_characters": file_record["size_bytes"],
                }
            )
        else:
            skipped_files.append(relative_path)

    return readable_files, skipped_files


def prepare_code(readable_files, maximum_characters=MAX_DEEP_SOURCE_CHARACTERS):
    """Combine selected source files without exceeding a compact prompt budget."""
    code_parts = []
    remaining_characters = maximum_characters

    for source_file in readable_files:
        file_header = f"\n\n--- File: {source_file['path']} ---\n"
        file_content = source_file["content"]
        if source_file.get("truncated"):
            file_content += (
                f"\n[File truncated at {MAX_FILE_CONTENT_CHARACTERS} characters; "
                f"original size: {source_file['original_characters']} characters.]"
            )
        file_block = file_header + file_content

        if len(file_block) > remaining_characters:
            truncation_note = "\n[Code input shortened to fit the model limit.]"
            content_limit = max(0, remaining_characters - len(truncation_note))
            code_parts.append(file_block[:content_limit] + truncation_note)
            break

        code_parts.append(file_block)
        remaining_characters -= len(file_block)

        if remaining_characters <= 0:
            break

    return "".join(code_parts).strip()


def format_repository_structure(repository_files):
    """Build a tree from Git paths without resolving them on the local filesystem."""
    tree = {}
    shown_files = repository_files[:MAX_STRUCTURE_ENTRIES]

    for file_record in shown_files:
        relative_parts = Path(file_record["path"]).parts
        current_node = tree
        for part in relative_parts:
            current_node = current_node.setdefault(part, {})

    lines = ["repository/"]

    def add_tree_lines(directory, depth):
        for name, contents in sorted(directory.items()):
            indentation = "  " * depth
            if contents:
                lines.append(f"{indentation}- {name}/")
                add_tree_lines(contents, depth + 1)
            else:
                lines.append(f"{indentation}- {name}")

    add_tree_lines(tree, 1)
    if len(repository_files) > MAX_STRUCTURE_ENTRIES:
        extra_count = len(repository_files) - MAX_STRUCTURE_ENTRIES
        lines.append(f"  ... {extra_count} more supported files not shown")

    return "\n".join(lines)
