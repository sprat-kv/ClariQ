# G-SIA Project Progress Tracker

This document tracks the implementation progress of the GovAI Secure Intelligence Assistant (G-SIA) project, broken down by phase.

---

### ✅ Phase 1: Foundational Setup & Data Layer (Completed)

*   **Goal**: Establish the project's structure, set up the database, and load it with the necessary data.
*   **Status**: **100% Complete and Verified.**
*   **Tasks Accomplished**:
    *   **Project Structure**: Created all necessary directories (`db`, `scripts`, `notebooks`, `src`, `policy_corpus`).
    *   **Dependency Management**: Switched from `requirements.txt` to `pyproject.toml` and configured the project to use `uv` for environment and package management.
    *   **Database Schema**: Defined the table structures for `patients`, `conditions`, `encounters`, etc., in `db/schema.sql`.
    *   **Data Loading**:
        *   Initially attempted to load data with a Python script (`scripts/load_data.py`).
        *   Debugged and resolved connection issues related to special characters in the password by implementing URL encoding.
        *   Identified schema mismatches between the CSV files and the database tables.
        *   Successfully loaded all data by manually transforming and inserting it using the `1.0-data-loading.ipynb` notebook.

---

### ⏳ Phase 2: Policy Enforcement Engine (RAG) (Up Next)

*   **Goal**: Build the core AI component that classifies user queries based on a corpus of compliance documents.
*   **Status**: **Scaffolding complete. Implementation is the next step.**
*   **Upcoming Tasks**:
    1.  **Install AI/ML Dependencies**: Add `langchain`, `langchain-openai`, a vector store library (like `faiss-cpu`), and other related packages to `pyproject.toml` and run `uv sync`.
    2.  **Implement Policy Embedding**: Flesh out the `scripts/embed_policies.py` script to:
        *   Load the markdown files from the `policy_corpus` directory.
        *   Split the documents into small, coherent chunks.
        *   Use an embedding model (e.g., Azure's `text-embedding-ada-002`) to convert text chunks into numerical vectors.
        *   Store these vectors in a local vector database (like FAISS) so they can be retrieved quickly.
    3.  **Implement the `PolicyAgent`**: Flesh out the `src/g_sia/agents/policy_agent.py` file to:
        *   Accept a user query.
        *   Use the vector store to perform a similarity search and retrieve the most relevant policy chunks.
        *   Combine the user query and the retrieved policy chunks into a single prompt for an LLM.
        *   Use the LLM (e.g., Azure's GPT-4o) to analyze the prompt and return a structured verdict: `ALLOW`, `REWRITE`, or `BLOCK`, along with its reasoning.

---

### 📋 Phase 3: Core Agent Implementation (Future)

*   **Goal**: Develop the other agents needed for the chatbot's workflow.
*   **Tasks**:
    *   **Implement `SQL Agent`**: Create an agent that can convert natural language questions (approved by the `Policy Agent`) into safe, parameterized SQL queries using the LangChain SQL Toolkit.
    *   **Implement `Query Rewriter`**: Create an agent that takes a query marked as `REWRITE` and modifies it to be compliant (e.g., by removing a request for PII or adding aggregation).

---

### 📋 Phase 4: LangGraph Orchestration (Future)

*   **Goal**: Connect all the agents into a logical, stateful workflow.
*   **Tasks**:
    *   Define a graph state that tracks the query, agent verdicts, and final results.
    *   Define nodes for each agent (`Policy Agent`, `Query Rewriter`, `SQL Agent`).
    *   Implement conditional edges to create the workflow logic (e.g., if the verdict is `REWRITE`, route to the `Query Rewriter`; if `ALLOW`, route to the `SQL Agent`).

---

### 📋 Phase 5: API & Backend Integration (Future)

*   **Goal**: Expose the AI system to the outside world through a secure API.
*   **Tasks**:
    *   Build a FastAPI application.
    *   Create a REST endpoint (e.g., `/query`) that accepts a user's question.
    *   This endpoint will invoke the LangGraph application and return the final, formatted response.

---

### 📋 Phase 6: Security & Observability (Future)

*   **Goal**: Harden the application and ensure all actions are traceable.
*   **Tasks**:
    *   **Secrets Management**: Integrate Azure Key Vault to manage all sensitive credentials (database connection strings, API keys) instead of using the `.env` file in production.
    *   **Observability**: Configure LangSmith to trace the internal reasoning of the agents for debugging and monitoring.
    *   **Auditing**: Implement a robust logging middleware in FastAPI to send audit logs to Azure Monitor for compliance purposes.

---

### 📋 Phase 7: Testing & Finalization (Future)

*   **Goal**: Ensure the application is reliable, well-documented, and ready for deployment.
*   **Tasks**:
    *   Write unit tests for individual agents and functions.
    *   Write integration tests for the complete LangGraph workflow.
    *   Create a `Dockerfile` to containerize the application.
    *   Refine the `README.md` with final, verified setup instructions.
