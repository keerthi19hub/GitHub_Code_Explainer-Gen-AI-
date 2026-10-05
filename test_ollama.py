"""Check that Python can generate a response using the local Ollama model."""

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"


def test_ollama_connection():
    """Send a short prompt to Ollama and print the model response."""
    request_data = {
        "model": MODEL_NAME,
        "prompt": "Reply with: Ollama connection successful.",
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=request_data, timeout=180)
        response.raise_for_status()
        result = response.json()
        print("Ollama is working.")
        print("Model response:", result.get("response", "No response text returned."))
    except requests.exceptions.ConnectionError:
        print("Could not connect to Ollama. Start the Ollama application first.")
    except requests.exceptions.HTTPError as error:
        print("Ollama returned an error:", error)
        print("Check that qwen2.5:3b is installed with: ollama pull qwen2.5:3b")
    except requests.exceptions.RequestException as error:
        print("The Ollama request failed:", error)


if __name__ == "__main__":
    test_ollama_connection()
