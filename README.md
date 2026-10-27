# 🤖 GenAI Codebase Explainer — Automated Repository Documentation & Code Ingestion

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=0F172A,0369A1,0284C7&height=220&section=header&text=GenAI%20Codebase%20Explainer&fontSize=42&fontColor=ffffff&fontAlignY=38&desc=Automated%20Repository%20Documentation%20%26%20Code%20Ingestion&descSize=18&descAlignY=60&descAlign=50" width="100%" alt="GenAI Codebase Explainer Banner" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Architecture-Modular%20Backend%20%26%20Frontend-0F172A?style=for-the-badge" alt="Architecture" />
  <img src="https://img.shields.io/badge/Inference-Local%20Ollama-0369A1?style=for-the-badge" alt="Ollama" />
  <img src="https://img.shields.io/badge/Stage-Proof%20of%20Concept%20(PoC)-0284C7?style=for-the-badge" alt="PoC" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
</p>

---

## 📌 Table of Contents

- [📖 Executive Summary](#-executive-summary)
- [🎯 Research Objectives & Architecture Evolution](#-research-objectives--architecture-evolution)
- [✨ Key Technical Features](#-key-technical-features)
- [🏗️ Ingestion & Parsing Workflow](#️-ingestion--parsing-workflow)
- [🛠️ Tech Stack Matrix](#️-tech-stack-matrix)
- [⚙️ Reproducible Quickstart & Setup](#️-reproducible-quickstart--setup)
- [📁 Project Structure](#-project-structure)
- [👩‍💻 Author & Contributions](#-author--contributions)

---

## 📖 Executive Summary

The **GenAI Codebase Explainer (PoC)** is the foundational architectural prototype exploring the integration of local LLMs (via Ollama) with multi-language source code ingestion. This repository establishes the baseline client-server abstraction, token window chunking logic, and Ollama latency benchmarking harness (`test_ollama.py`) that catalyzed the production-ready [GITHUB-CODE-EXPLAINER](https://github.com/keerthi19hub/GITHUB-CODE-EXPLAINER) suite.

---

## 🎯 Research Objectives & Architecture Evolution

- **PoC Mission:** Validate whether local, quantized LLMs (7B parameter models like CodeLlama or Llama 3) running on consumer laptops could produce syntactically accurate codebase summaries without cloud GPU dependencies.
- **Key Breakthroughs:** Established modular backend decoupling, automated directory traversal ignoring binary artifacts, and prompt engineering protocols for architectural summarization.

---

## ✨ Key Technical Features

- **⚡ Ollama Connectivity Benchmarking:** Includes `test_ollama.py` to verify local daemon response latency and token generation rates before launching heavy ingestion runs.
- **📦 Clean Separation of Concerns:** Segregated `backend/` parsing algorithms from `frontend/` UI presentation.
- **🔒 Privacy-Guaranteed Analysis:** Executes all token parsing locally without external network transmissions.

---

## 🏗️ Ingestion & Parsing Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 GenAI Codebase Explainer Prototype Workflow                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Source Ingestion: Local Directory or Cloned GitHub Repository Tree          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Backend Chunking & Normalization (`backend/`):                              │
│ - Skip binary and virtualenv files                                          │
│ - Chunk code into prompt-sized token windows                                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Inference & Connectivity Bridge (`test_ollama.py` & LLM API):                │
│ - Stream prompts to local Ollama daemon                                     │
│ - Render architectural explanation to user interface                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack Matrix

| Domain | Technology | Implementation Details |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core language for token chunking and API interfacing |
| **Local LLM** | Ollama | Local model daemon running CodeLlama or Llama 3 |
| **Networking** | Requests / HTTP client | Communication bridge between backend and local Ollama port |
| **Testing** | Custom benchmarking script | `test_ollama.py` latency and connectivity test |

---

## ⚙️ Reproducible Quickstart & Setup

### Prerequisites
- Python 3.10+
- [Ollama installed](https://ollama.ai) with `ollama pull llama3` or `ollama pull codellama`

### 1. Clone the Repository
```bash
git clone https://github.com/keerthi19hub/GitHub_Code_Explainer-Gen-AI-.git
cd GitHub_Code_Explainer-Gen-AI-
```

### 2. Setup Environment & Install Dependencies
```bash
python -m venv venv
venv\Scripts\activate  # Linux/macOS: source venv/bin/activate

pip install -r requirements.txt
```

### 3. Verify Local Ollama Connectivity
```bash
python test_ollama.py
```

---

## 📁 Project Structure

```text
GitHub_Code_Explainer-Gen-AI-/
├── backend/            # Code parsing and token chunking algorithms
├── frontend/           # Prototype UI interface components
├── test_ollama.py      # Ollama daemon connectivity and latency benchmark
├── requirements.txt    # Application dependencies
└── README.md           # Production technical documentation
```

---

## 👩‍💻 Author & Contributions

**Keerthi N**  
- **GitHub:** [@keerthi19hub](https://github.com/keerthi19hub)  
- **Portfolio:** [keerthi19hub.github.io](https://keerthi19hub.github.io)  
- **Role:** PoC experimental design, Ollama integration, and code chunking logic.

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=0F172A,0369A1,0284C7&height=100&section=footer" width="100%" alt="Footer Banner" />
</p>
