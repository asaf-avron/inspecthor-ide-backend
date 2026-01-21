# Guardian Gateway

**Autonomous Infrastructure for Mathematical AI Verification**

## Overview

Guardian Gateway is a "Shift Left" security platform that uses Formal Verification (Dafny) to mathematically prove the correctness of AI-generated code. It bridges the "Trust Gap" by enforcing a strict "Functional Core, Imperative Shell" architecture.

## Architecture

- **The Auditor (Design)**: Gemini analyzes English specs for ambiguity and generates Dafny skeletons.
- **The Gateway (Build)**: Transpiles Python to Dafny and verifies against contracts.
- **The Lens (Visualization)**: A Streamlit dashboard that translates formal proofs into human-readable cards.

## Quick Start (Docker - Recommended)

Docker bundles Dafny, Python, and all dependencies. No local installation needed.

**Prerequisites:** Docker and Docker Compose installed.

1. Create a `.env` file with your Gemini API key:

```bash
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

2. Build and run:

```bash
docker-compose up --build
```

3. Open http://localhost:8501

To stop: `docker-compose down`

## Quick Start (Local Development)

If you prefer running locally (requires Dafny installed):

1. Install Dafny:

```bash
# Windows/Linux (requires .NET SDK 6.0+)
dotnet tool install --global dafny

# macOS
brew install dafny
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` with your API key:

```bash
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

4. Run:

```bash
streamlit run app.py
```

## Structure

- `core_parser.py`: Pure Python logic for parsing Dafny contracts.
- `core_auditor.py`: LLM-powered specification analysis using Gemini.
- `core_gateway.py`: Verification engine (Python to Dafny transpilation + verification).
- `app.py`: The Streamlit frontend with three tabs (Lens, Auditor, Gateway).
- `docs/`: Architecture and specification documents.
- `tests/fixtures/`: Sample Dafny contract files.
