"""FastAPI API for explaining public GitHub repositories with local Ollama."""

import logging
import tempfile
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from git.exc import GitCommandError
from pydantic import BaseModel, HttpUrl

from backend.llm_service import generate_repository_explanation
from backend.repo_processor import (
    MANIFEST_NAMES,
    detect_repository_type,
    find_repository_files,
    format_file_type_summary,
    format_local_file_summaries,
    format_repository_structure,
    open_repository,
    prepare_code,
    read_source_files,
    scan_repository_structure,
    select_deep_analysis_files,
)


logger = logging.getLogger(__name__)
app = FastAPI(title="Local GitHub Repository Code Explainer")


class ExplainRequest(BaseModel):
    """The GitHub repository URL submitted by the frontend."""

    github_url: HttpUrl


@app.get("/")
def check_api():
    """Return a short message to show that the API is running."""
    return {"message": "GitHub Code Explainer API is running."}


def analyze_repository(repository, repository_url, analysis_started):
    """Scan a no-checkout Git repository and generate one local Qwen report."""
    repository_files = find_repository_files(repository)
    if not repository_files:
        raise HTTPException(
            status_code=400,
            detail="This public GitHub repository has no tracked files.",
        )

    file_summaries, skipped_files = scan_repository_structure(
        repository, repository_files
    )
    repository_tree = format_repository_structure(repository_files)
    file_type_summary = format_file_type_summary(repository_files)
    repository_type = detect_repository_type(file_summaries)

    records_by_path = {item["path"]: item for item in repository_files}
    selected_paths = select_deep_analysis_files(file_summaries)
    selected_files, deep_read_skipped = read_source_files(
        repository,
        [records_by_path[path] for path in selected_paths],
    )
    if deep_read_skipped:
        skipped_files.extend(deep_read_skipped)
        failed_paths = set(deep_read_skipped)
        file_summaries = [
            item for item in file_summaries if item["path"] not in failed_paths
        ]

    deep_paths = [item["path"] for item in selected_files]
    deep_path_set = set(deep_paths)
    deep_structures = [
        item for item in file_summaries if item["path"] in deep_path_set
    ]
    summarized_files = [
        item for item in file_summaries if item["path"] not in deep_path_set
    ]

    analysis_notes = []
    if selected_files:
        analysis_notes.append(
            f"Qwen deeply analyzed {len(selected_files)} prioritized source file(s)."
        )
    else:
        analysis_notes.append(
            "No source code was found. The explanation uses available README, PDF, "
            "data/configuration text, and file metadata."
        )

    readable_documents = [
        item
        for item in file_summaries
        if item["content_extracted"]
        and item["kind"] in {"README/documentation", "documentation", "PDF document"}
    ]
    if readable_documents:
        analysis_notes.append(
            f"Extracted text from {len(readable_documents)} README/document/PDF file(s)."
        )

    power_bi_files = [
        item for item in file_summaries if item["kind"] == "Power BI report"
    ]
    if power_bi_files:
        analysis_notes.append(
            f"Found {len(power_bi_files)} Power BI file(s); their internal report contents were not inspected."
        )
    if skipped_files:
        analysis_notes.append(
            f"{len(set(skipped_files))} file(s) had internal contents that could not be extracted."
        )

    local_context = format_local_file_summaries(file_summaries)
    # Document repositories need their README/PDF excerpts; source repositories also send code.
    context_limit = 8_000 if not selected_files else 3_000
    if len(local_context) > context_limit:
        local_context = (
            local_context[:context_limit]
            + "\n[Remaining file summaries were scanned locally but omitted from the model context.]"
        )
        analysis_notes.append(
            "Some lower-priority local summaries were omitted from the Qwen context limit."
        )

    manifest_summaries = [
        summary
        for summary in file_summaries
        if Path(summary["path"]).name.lower() in MANIFEST_NAMES
        and summary.get("content_excerpt")
    ]
    manifest_context = format_local_file_summaries(manifest_summaries)
    explanation = generate_repository_explanation(
        repository_type["type"],
        repository_type["evidence"],
        repository_tree,
        file_type_summary,
        local_context,
        prepare_code(selected_files) if selected_files else "",
        deep_structures,
        manifest_context,
    )

    important_files = [item["path"] for item in file_summaries[:12]]
    function_sections = []
    class_sections = []
    for summary in file_summaries:
        if summary["priority"] >= 8:
            continue
        if summary["functions"]:
            function_sections.append(
                f"### {summary['path']}\n- "
                + "\n- ".join(summary["functions"][:10])
            )
        if summary["classes"]:
            class_sections.append(
                f"### {summary['path']}\n"
                + "\n".join(
                    f"- `{item['name']}`"
                    + (": " + ", ".join(item["methods"][:6]) if item["methods"] else "")
                    for item in summary["classes"][:6]
                )
            )

    content_notes = [
        f"- `{item['path']}`: {item['content_note']}"
        for item in file_summaries
        if item.get("content_note")
    ]
    explanation_parts = [
        f"# Repository Type\n\n**{repository_type['type']}**\n\n"
        f"Evidence: {repository_type['evidence']}.",
        "# Repository Structure\n\n```text\n" + repository_tree + "\n```",
        "# File Type Summary\n\n"
        + "\n".join(
            f"- {kind}: {count}"
            for kind, count in file_type_summary["categories"].items()
        ),
        "# Important Files\n\n"
        + "\n".join(f"- `{path}`" for path in important_files),
        explanation,
        "# Important Functions\n\n"
        + ("\n\n".join(function_sections) or "No functions were found in source files."),
        "# Important Classes\n\n"
        + ("\n\n".join(class_sections) or "No classes were found in source files."),
        "# Additional Files Summarized Locally\n\n"
        + (format_local_file_summaries(summarized_files) or "No additional files were summarized."),
        "# Files Not Fully Analyzed\n\n"
        + ("\n".join(content_notes) or "No content extraction failures were recorded."),
    ]

    total_analysis_time = round(time.perf_counter() - analysis_started, 1)
    return {
        "success": True,
        "repository_url": repository_url,
        "repository_type": repository_type["type"],
        "repository_type_evidence": repository_type["evidence"],
        "files_found": len(repository_files),
        "files_analyzed": sum(1 for item in file_summaries if item["content_extracted"]),
        "files_analyzed_deeply": len(selected_files),
        "files_summarized": len(summarized_files),
        "files_skipped": len(set(skipped_files)),
        "file_type_summary": file_type_summary,
        "analyzed_files": deep_paths,
        "summarized_files": [item["path"] for item in summarized_files[:100]],
        "skipped_files": list(dict.fromkeys(skipped_files))[:100],
        "analysis_notes": analysis_notes,
        "ollama_requests": 1,
        "total_analysis_time_seconds": total_analysis_time,
        "explanation": "\n\n".join(explanation_parts),
    }


@app.post("/explain")
def explain_repository(request: ExplainRequest):
    """Explain any public repository without checking out unsafe Windows paths."""
    analysis_started = time.perf_counter()
    repositories_directory = Path(__file__).resolve().parent.parent / "repositories"
    repositories_directory.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(
            prefix="repo_", dir=str(repositories_directory)
        ) as temporary_directory:
            clone_path = Path(temporary_directory) / "repository"
            with open_repository(str(request.github_url), clone_path) as repository:
                return analyze_repository(
                    repository,
                    str(request.github_url),
                    analysis_started,
                )
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GitCommandError as error:
        error_text = str(error).lower()
        logger.warning("GitHub repository access failed for %s: %s", request.github_url, error)
        if "not found" in error_text or "authentication" in error_text:
            detail = "Could not access this GitHub repository. It may be private or unavailable."
        elif "resolve host" in error_text or "network" in error_text or "connection" in error_text:
            detail = "Could not connect to GitHub. Check the network connection and try again."
        else:
            detail = "Git could not fetch this repository. Check the URL and public access."
        raise HTTPException(status_code=400, detail=detail) from error
    except requests.exceptions.ConnectionError as error:
        logger.warning("Could not connect to local Ollama: %s", error)
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Please start Ollama and try again.",
        ) from error
    except requests.exceptions.Timeout as error:
        logger.warning("Local Ollama request timed out: %s", error)
        raise HTTPException(
            status_code=504,
            detail="Local Qwen analysis timed out. Try a smaller repository or less content.",
        ) from error
    except requests.exceptions.HTTPError as error:
        logger.warning("Ollama returned an HTTP error: %s", error)
        raise HTTPException(
            status_code=502,
            detail="Ollama could not generate the explanation. Check that qwen2.5:3b is installed.",
        ) from error
    except requests.exceptions.RequestException as error:
        logger.warning("Ollama request failed: %s", error)
        raise HTTPException(status_code=502, detail="The request to Ollama failed.") from error
    except RuntimeError as error:
        logger.warning("Ollama returned incomplete structured output: %s", error)
        raise HTTPException(
            status_code=502,
            detail="Qwen returned an incomplete explanation. Try again with this repository.",
        ) from error
    except Exception as error:
        logger.exception("Unexpected repository analysis error")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while analyzing the repository. Check the backend terminal.",
        ) from error
