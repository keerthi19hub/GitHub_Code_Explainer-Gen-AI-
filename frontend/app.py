"""Streamlit page for submitting a GitHub repository to the API."""

import requests
import streamlit as st


API_URL = "http://127.0.0.1:8000/explain"

st.title("Local GitHub Repository Code Explainer")
st.write(
    "Enter a public GitHub repository URL to analyze its source files and get "
    "a beginner-friendly explanation from the local Qwen model."
)

github_url = st.text_input("GitHub Repository URL")

if st.button("Explain This Repository"):
    if not github_url.strip():
        st.error("Enter a GitHub repository URL first.")
    else:
        with st.spinner(
            "Scanning source files and asking the local Qwen model to explain them..."
        ):
            try:
                response = requests.post(
                    API_URL,
                    json={"github_url": github_url.strip()},
                    timeout=360,
                )
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.ConnectionError:
                st.error("Could not reach FastAPI. Start the backend and try again.")
            except requests.exceptions.Timeout:
                st.error("The request took too long. Check Ollama and try again.")
            except requests.exceptions.HTTPError:
                try:
                    error_message = response.json().get("detail", response.text)
                except ValueError:
                    error_message = response.text
                st.error(f"API error ({response.status_code}): {error_message}")
            except requests.exceptions.RequestException as error:
                st.error(f"The request failed: {error}")
            except ValueError:
                st.error("The API returned a response that was not valid JSON.")
            else:
                if result.get("success"):
                    st.write(f"Repository: {result.get('repository_url', github_url)}")
                    st.write(
                        "Repository type: "
                        f"**{result.get('repository_type', 'Not classified')}**"
                    )
                    if result.get("repository_type_evidence"):
                        st.caption(f"Classification evidence: {result['repository_type_evidence']}")

                    file_type_summary = result.get("file_type_summary", {})
                    category_counts = file_type_summary.get("categories", {})
                    if category_counts:
                        with st.expander("File type summary", expanded=True):
                            st.write(
                                "\n".join(
                                    f"- {category}: {count}"
                                    for category, count in category_counts.items()
                                )
                            )

                    first_metrics = st.columns(3)
                    first_metrics[0].metric("Files found", result.get("files_found", 0))
                    first_metrics[1].metric(
                        "Content analyzed",
                        result.get("files_analyzed", 0),
                    )
                    first_metrics[2].metric(
                        "Analyzed deeply",
                        result.get("files_analyzed_deeply", 0),
                    )

                    second_metrics = st.columns(3)
                    second_metrics[0].metric(
                        "Summarized", result.get("files_summarized", 0)
                    )
                    second_metrics[1].metric(
                        "Skipped", result.get("files_skipped", result.get("skipped_file_count", 0))
                    )
                    second_metrics[2].metric(
                        "Ollama requests", result.get("ollama_requests", 0)
                    )
                    st.metric(
                        "Analysis time",
                        f"{result.get('total_analysis_time_seconds', 0)} s",
                    )

                    analysis_notes = result.get("analysis_notes", [])
                    if analysis_notes:
                        st.info("\n\n".join(analysis_notes))

                    analyzed_files = result.get("analyzed_files", [])
                    if analyzed_files:
                        with st.expander("Files analyzed deeply"):
                            st.write("\n".join(f"- {path}" for path in analyzed_files))

                    summarized_files = result.get("summarized_files", [])
                    if summarized_files:
                        with st.expander("Files summarized locally"):
                            st.write("\n".join(f"- {path}" for path in summarized_files))

                    skipped_files = result.get("skipped_files", [])
                    skipped_file_count = result.get(
                        "files_skipped", result.get("skipped_file_count", 0)
                    )
                    if skipped_file_count:
                        with st.expander(
                            f"Skipped files ({skipped_file_count})"
                        ):
                            st.write("\n".join(f"- {path}" for path in skipped_files))

                    st.markdown(result.get("explanation", "No explanation was returned."))
                else:
                    st.error(result.get("detail", "The repository could not be explained."))
