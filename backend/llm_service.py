"""Make two bounded local Qwen requests for a repository explanation."""

import json

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"
REQUEST_TIMEOUT_SECONDS = 240
UNKNOWN_DETAIL = "Not clearly determined from the available source code."

SYSTEM_PROMPT = """Explain only the supplied repository evidence to a beginner.
Do not invent files, functions, classes, dependencies, behavior, or project details.
Do not use general knowledge about libraries. Do not review code or suggest changes.
Return valid JSON matching the requested structure."""

FILE_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "maxLength": 200},
                    "purpose": {"type": "string", "maxLength": 180},
                    "imports": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "maxLength": 100},
                                "explanation": {"type": "string", "maxLength": 100},
                            },
                            "required": ["name", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                    "functions": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "maxLength": 120},
                                "explanation": {"type": "string", "maxLength": 220},
                            },
                            "required": ["name", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                    "classes": {
                        "type": "array",
                        "maxItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "maxLength": 100},
                                "explanation": {"type": "string", "maxLength": 180},
                            },
                            "required": ["name", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["path", "purpose", "imports", "functions", "classes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["files"],
    "additionalProperties": False,
}

FINAL_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "project_overview": {"type": "string", "maxLength": 280},
        "purpose": {"type": "string", "maxLength": 260},
        "main_features": {"type": "string", "maxLength": 400},
        "technologies_used": {"type": "string", "maxLength": 420},
        "file_relationships": {"type": "string", "maxLength": 350},
        "data_flow": {"type": "string", "maxLength": 350},
        "execution_flow": {"type": "string", "maxLength": 350},
        "dependencies": {"type": "string", "maxLength": 300},
        "data_information": {"type": "string", "maxLength": 280},
        "setup_usage": {"type": "string", "maxLength": 300},
        "key_observations": {"type": "string", "maxLength": 300},
        "limitations": {"type": "string", "maxLength": 300},
        "final_summary": {"type": "string", "maxLength": 240},
    },
    "required": [
        "project_overview",
        "purpose",
        "main_features",
        "technologies_used",
        "file_relationships",
        "data_flow",
        "execution_flow",
        "dependencies",
        "data_information",
        "setup_usage",
        "key_observations",
        "limitations",
        "final_summary",
    ],
    "additionalProperties": False,
}
REPOSITORY_EXPLANATION_SCHEMA = {
    "type": "object",
    "properties": {
        "project_overview": {"type": "string", "maxLength": 240},
        "purpose": {"type": "string", "maxLength": 200},
        "main_features": {"type": "string", "maxLength": 320},
        "technologies_used": {"type": "string", "maxLength": 350},
        "file_explanations": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "maxLength": 180},
                    "purpose": {"type": "string", "maxLength": 160},
                    "functions": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "maxLength": 100},
                                "explanation": {"type": "string", "maxLength": 130},
                            },
                            "required": ["name", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                    "classes": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "maxLength": 100},
                                "explanation": {"type": "string", "maxLength": 120},
                            },
                            "required": ["name", "explanation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["path", "purpose", "functions", "classes"],
                "additionalProperties": False,
            },
        },
        "file_relationships": {"type": "string", "maxLength": 260},
        "data_flow": {"type": "string", "maxLength": 250},
        "execution_flow": {"type": "string", "maxLength": 250},
        "dependencies": {"type": "string", "maxLength": 240},
        "data_information": {"type": "string", "maxLength": 200},
        "setup_usage": {"type": "string", "maxLength": 200},
        "key_observations": {"type": "string", "maxLength": 200},
        "limitations": {"type": "string", "maxLength": 240},
        "final_summary": {"type": "string", "maxLength": 220},
    },
    "required": [
        "project_overview",
        "purpose",
        "main_features",
        "technologies_used",
        "file_explanations",
        "file_relationships",
        "data_flow",
        "execution_flow",
        "dependencies",
        "data_information",
        "setup_usage",
        "key_observations",
        "limitations",
        "final_summary",
    ],
    "additionalProperties": False,
}


def send_prompt_to_ollama(prompt, response_schema, maximum_output_tokens):
    """Send one non-streaming request to the local Ollama API."""
    request_data = {
        "model": MODEL_NAME,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "format": response_schema,
        "stream": False,
        "options": {"num_predict": maximum_output_tokens, "temperature": 0.0},
    }

    response = requests.post(
        OLLAMA_URL,
        json=request_data,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    result = response.json()
    generated_text = result.get("response", "").strip()

    if not generated_text:
        raise RuntimeError("Ollama returned an empty explanation.")
    if result.get("done_reason") == "length":
        raise RuntimeError("Ollama reached its output limit before completing JSON.")

    try:
        return json.loads(generated_text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Ollama did not return valid JSON.") from error


def _local_file_structure(structure):
    """Keep only compact, useful local facts for a deep-analysis request."""
    return {
        "path": structure["path"],
        "lines": structure["lines"],
        "characters": structure["characters"],
        "imports": structure["imports"][:5],
        "functions": structure["functions"][:8],
        "classes": [
            {
                "name": class_info["name"],
                "methods": class_info["methods"][:5],
            }
            for class_info in structure["classes"][:5]
        ],
        "constants": structure["constants"][:8],
    }


def analyze_selected_files(source_code, file_structures):
    """Explain the selected source files in one structured Qwen request."""
    local_structure = json.dumps(
        [_local_file_structure(item) for item in file_structures],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    prompt = f"""Explain the selected source files using the actual code and local structure facts below.
The local structure facts provide the authoritative file paths, imports, function signatures, class names, and constants. Do not create different names.
For each file, describe its purpose, up to four important imports, up to three important functions with their inputs/behavior/output, and up to two important classes and their role. Keep each description short and beginner-friendly.
Return one JSON file object for every supplied source path. Do not include files that are not supplied.

Local structure facts:
{local_structure}

Selected source code:
{source_code}
"""
    report = send_prompt_to_ollama(prompt, FILE_ANALYSIS_SCHEMA, 1_300)
    report_files = report.get("files", [])
    files_by_path = {
        item.get("path"): item
        for item in report_files
        if isinstance(item, dict)
        and item.get("path") in {structure["path"] for structure in file_structures}
    }

    file_sections = []
    for structure in file_structures:
        file_path = structure["path"]
        file_report = files_by_path.get(file_path, {})
        section = [
            f"### {file_path}",
            f"**Approximate size:** {structure['lines']} lines, "
            f"{structure['characters']} characters.",
            f"**Purpose:** {file_report.get('purpose') or UNKNOWN_DETAIL}",
        ]

        if structure["imports"]:
            section.append("**Imports found locally:** " + ", ".join(structure["imports"][:8]))

        import_explanations = {
            item.get("name"): item.get("explanation")
            for item in file_report.get("imports", [])
            if isinstance(item, dict)
        }
        for import_name, explanation in import_explanations.items():
            if import_name in structure["imports"] and explanation:
                section.append(f"- `{import_name}`: {explanation}")

        local_functions = structure["functions"]
        explained_functions = {}
        for function in file_report.get("functions", []):
            if not isinstance(function, dict):
                continue
            function_name = (function.get("name") or "").split("(", 1)[0].strip()
            if function_name:
                explained_functions[function_name] = function.get("explanation")
        if local_functions:
            section.append("**Important Functions:**")
            for signature in local_functions[:8]:
                function_name = signature.split("(", 1)[0]
                explanation = explained_functions.get(function_name)
                if explanation:
                    section.append(f"- `{signature}`: {explanation}")
                else:
                    section.append(f"- `{signature}` (identified locally).")

        local_classes = structure["classes"]
        explained_classes = {
            item.get("name"): item.get("explanation")
            for item in file_report.get("classes", [])
            if isinstance(item, dict)
        }
        if local_classes:
            section.append("**Important Classes:**")
            for class_info in local_classes[:5]:
                class_line = f"- `{class_info['name']}`"
                if explained_classes.get(class_info["name"]):
                    class_line += f": {explained_classes[class_info['name']]}"
                if class_info["methods"]:
                    class_line += "; methods: " + ", ".join(class_info["methods"][:6])
                section.append(class_line)

        if structure["constants"]:
            section.append(
                "**Important Constants:** " + ", ".join(structure["constants"][:8])
            )

        file_sections.append("\n".join(section))

    return "\n\n".join(file_sections)


def generate_final_repository_report(
    repository_tree,
    local_file_summaries,
    deep_file_explanations,
    analysis_note,
    repository_type,
    file_type_summary,
    dependency_context="",
):
    """Create one repository-level synthesis from local and deep file summaries."""
    prompt = f"""Explain this GitHub repository to a beginner using only the extracted repository information below.
Do not invent features, functions, datasets, technologies, setup steps, or behavior. Use an exact source only when the supplied content shows it.
README and PDF excerpts are evidence. A .pbix entry is only file metadata; its internal report content was not inspected.
For dependencies, list a package only when it appears in the actual dependency manifest text below. A README/PDF saying a tool is used does not prove it is a required dependency. If the manifest text is empty, leave the dependencies field empty.
When a README or PDF describes a workflow, attribute it to that document instead of presenting it as verified execution behavior. Never claim to have opened or inspected PBIX internals.
Keep each value concise. The selected-file explanations already contain detailed function/class notes; do not repeat them.
Return a JSON object with these fields: project_overview, purpose, main_features, technologies_used, file_relationships, data_flow, execution_flow, dependencies, data_information, setup_usage, key_observations, limitations, final_summary.

Repository type classified from file types and extracted README text: {repository_type}
File type counts: {json.dumps(file_type_summary, ensure_ascii=True)}

Repository tree:
{repository_tree}

Locally extracted structure summaries for relevant files:
{local_file_summaries}

Actual dependency manifest text:
{dependency_context or "No dependency manifest with package requirements was found."}

Qwen deep explanations for selected files:
{deep_file_explanations or "No source files were selected for deep analysis."}

Coverage note:
{analysis_note}
"""
    report = send_prompt_to_ollama(prompt, FINAL_REPORT_SCHEMA, 950)
    if not dependency_context.strip():
        report["dependencies"] = (
            "No dependency manifest with package requirements was found. "
            "Tools mentioned in README or PDF workflow descriptions are not treated as package dependencies."
        )

    section_labels = [
        ("Project Overview", "project_overview"),
        ("Purpose of the Repository", "purpose"),
        ("Main Features / Experiments", "main_features"),
        ("Technologies Used", "technologies_used"),
        ("File Relationships", "file_relationships"),
        ("Data Flow", "data_flow"),
        ("Execution Flow", "execution_flow"),
        ("Dependencies", "dependencies"),
        ("Data / Dataset Information", "data_information"),
        ("Setup / Usage Instructions", "setup_usage"),
        ("Key Observations", "key_observations"),
        ("Limitations / Files Not Analyzed", "limitations"),
        ("Final Beginner-Friendly Summary", "final_summary"),
    ]
    sections = []
    for label, field in section_labels:
        value = report.get(field)
        if isinstance(value, str) and value.strip():
            sections.append(f"## {label}\n\n{value.strip()}")
    return "\n\n".join(sections)


def generate_repository_explanation(
    repository_type,
    repository_type_evidence,
    repository_tree,
    file_type_summary,
    local_file_summaries,
    selected_source_code,
    selected_file_structures,
    dependency_context="",
):
    """Generate the complete repository explanation in one local Qwen request."""
    local_structure = json.dumps(
        [
            _local_file_structure(summary)
            for summary in selected_file_structures
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    response_schema = dict(REPOSITORY_EXPLANATION_SCHEMA)
    schema_properties = dict(response_schema["properties"])
    file_explanation_schema = dict(schema_properties["file_explanations"])
    file_explanation_schema["maxItems"] = len(selected_file_structures)
    schema_properties["file_explanations"] = file_explanation_schema
    response_schema["properties"] = schema_properties

    prompt = f"""Explain this GitHub repository to a beginner using only the supplied repository material.
Do not invent files, functions, classes, technologies, datasets, installation steps, dependencies, or behavior.
README and extracted PDF text are evidence about the repository. A .pbix/.pbit file is only metadata; its internal contents were not inspected. Never infer the dashboard contents from its name.
The detected repository type and file categories were computed from tracked Git files. Do not contradict them without evidence.
When there is no selected source-code structure, return an empty file_explanations array and explain the available documents and file metadata instead.
For dependencies, only the actual manifest excerpts below can prove package requirements. README/PDF tool mentions are tools described, not required package dependencies. If there is no manifest excerpt, state that no dependency manifest with package requirements was found.
Describe README/PDF workflows as documented instructions, not verified execution behavior. Include file explanations only for paths in local structure or selected code. Explain functions/classes only when names are present in local structure facts. Keep sections short and omit irrelevant details by returning empty strings.

Return the required JSON fields. File-by-file explanations are limited to important selected files. Cite paths in prose when useful.

Repository type: {repository_type}
Repository type evidence: {repository_type_evidence}
File type counts: {json.dumps(file_type_summary, ensure_ascii=True)}

Repository structure:
{repository_tree}

Local summaries for tracked files, including README/PDF excerpts and binary notes:
{local_file_summaries}

Actual dependency manifest excerpts:
{dependency_context or "No dependency manifest with package requirements was found."}

Selected source-code structure:
{local_structure}

Selected source-code content:
{selected_source_code or "No source code was available for deep analysis."}
"""
    maximum_output_tokens = 1_300 if not selected_file_structures else 1_800
    report = send_prompt_to_ollama(
        prompt,
        response_schema,
        maximum_output_tokens,
    )
    if not dependency_context.strip():
        report["dependencies"] = (
            "No dependency manifest with package requirements was found. "
            "README/PDF tool mentions are not treated as package dependencies."
        )
    structure_by_path = {
        item["path"]: item for item in selected_file_structures
    }
    model_files = {
        item.get("path"): item
        for item in report.get("file_explanations", [])
        if isinstance(item, dict) and item.get("path") in structure_by_path
    }

    section_labels = [
        ("Repository Overview", "project_overview"),
        ("Purpose of the Repository", "purpose"),
        ("Main Features / Experiments", "main_features"),
        ("Technologies Used", "technologies_used"),
        ("File Relationships", "file_relationships"),
        ("Data Flow", "data_flow"),
        ("Execution Flow", "execution_flow"),
        ("Dependencies", "dependencies"),
        ("Data / Dataset Information", "data_information"),
        ("Setup / Usage Instructions", "setup_usage"),
        ("Key Observations", "key_observations"),
        ("Limitations / Files Not Analyzed", "limitations"),
        ("Final Beginner-Friendly Summary", "final_summary"),
    ]
    sections = []
    for label, field in section_labels:
        value = report.get(field)
        if isinstance(value, str) and value.strip():
            sections.append(f"## {label}\n\n{value.strip()}")

    file_sections = []
    for structure in selected_file_structures:
        model_file = model_files.get(structure["path"], {})
        file_section = [
            f"### {structure['path']}",
            f"**Purpose:** {model_file.get('purpose') or UNKNOWN_DETAIL}",
            f"**Approximate size:** {structure['lines']} lines, "
            f"{structure['characters']} characters.",
        ]
        if structure["imports"]:
            file_section.append(
                "**Important Imports:** " + ", ".join(structure["imports"][:6])
            )

        model_functions = {
            (item.get("name") or "").split("(", 1)[0].strip(): item.get("explanation")
            for item in model_file.get("functions", [])
            if isinstance(item, dict)
        }
        if structure["functions"]:
            file_section.append("**Important Functions:**")
            for signature in structure["functions"][:12]:
                name = signature.split("(", 1)[0]
                explanation = model_functions.get(name)
                file_section.append(
                    f"- `{signature}`: {explanation}"
                    if explanation
                    else f"- `{signature}` (identified locally)."
                )

        model_classes = {
            item.get("name"): item.get("explanation")
            for item in model_file.get("classes", [])
            if isinstance(item, dict)
        }
        if structure["classes"]:
            file_section.append("**Important Classes:**")
            for class_info in structure["classes"][:6]:
                class_line = f"- `{class_info['name']}`"
                if model_classes.get(class_info["name"]):
                    class_line += f": {model_classes[class_info['name']]}"
                if class_info["methods"]:
                    class_line += "; methods: " + ", ".join(class_info["methods"][:8])
                file_section.append(class_line)
        file_sections.append("\n".join(file_section))

    if file_sections:
        sections.append(
            "## Detailed File-by-File Explanation\n\n" + "\n\n".join(file_sections)
        )

    return "\n\n".join(sections)