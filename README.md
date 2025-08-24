# GovAI Secure Intelligence Assistant (G-SIA)

## Overview

GovAI Secure Intelligence Assistant (G-SIA) is a compliance-aware AI chatbot that enables secure, policy-driven access to de-identified patient data. It uses multi-agent workflows orchestrated with LangGraph, Retrieval-Augmented Generation (RAG) for regulatory policy enforcement, and LangSmith for observability. This project demonstrates how AI can safely operate in regulated environments like healthcare and public services.

## Objectives

* Enforce data privacy and regulatory compliance (HIPAA, GDPR, CCPA).
* Enable secure structured database access through AI agents.
* Provide explainable, policy-backed responses to user queries.
* Demonstrate robust agent orchestration and monitoring using LangChain ecosystem.

## Key Features

* **Policy-Aware Reasoning**: Validates every query against policies using RAG.
* **SQL Query Agent**: Generates and executes parameterized queries.
* **Query Rewriting**: Modifies unsafe queries to meet regulations.
* **Audit Logging**: Tracks queries, decisions, and database interactions.
* **Agent Observability**: LangSmith for debugging and tracing.
* **Scalability**: Modular agents that can extend to new compliance rules.

## System Architecture

```
+---------------------------------------------------+
|                User Interface / API               |
+---------------------------------------------------+
                       │
                       ▼
+---------------------------------------------------+
|         LangGraph Orchestration Controller        |
|  (manages workflow between agents and tools)      |
+---------------------------------------------------+
       │                       │                   │
       ▼                       ▼                   ▼
+--------------+      +-----------------+   +----------------+
| Policy Agent |----->| Query Rewriter |   | Audit Logger   |
|  (RAG over   |      | (only if needed)|   | (logs decisions|
| HIPAA/GDPR)  |      +-----------------+   | and executions)|
+--------------+              │             +----------------+
       │                     ▼
       │            +------------------+
       │            | SQL Query Agent  |
       │            | (LangChain SQL   |
       │            | toolkit)         |
       │            +------------------+
       │                     │
       ▼                     ▼
+---------------------------------------------------+
| Secure PostgreSQL (De-identified Patient Database) |
+---------------------------------------------------+
                       │
                       ▼
+---------------------------------------------------+
| Response Formatter → Sends Compliant Response     |
+---------------------------------------------------+
                       │
                       ▼
+---------------------------------------------------+
|    Monitoring & Observability (LangSmith & Azure) |
+---------------------------------------------------+
```

## Agent Descriptions

### **1. Policy Agent**

* **Purpose**: Determines if a user query complies with regulations.
* **Functionality**:

  * Uses RAG to retrieve and interpret policies from HIPAA, GDPR, and CCPA.
  * Classifies queries as **Allowed**, **Partially Allowed**, or **Blocked**.
  * Provides reasons for blocking or modifying queries.

### **2. Query Rewriter**

* **Purpose**: Adjusts non-compliant queries to make them compliant.
* **Functionality**:

  * Removes sensitive fields or replaces them with aggregated metrics.
  * Ensures the rewritten query still provides useful information without violating policies.

### **3. SQL Query Agent**

* **Purpose**: Executes secure data retrieval from the PostgreSQL database.
* **Functionality**:

  * Converts natural language into parameterized SQL using LangChain SQL Toolkit.
  * Prevents direct access to identifiers, enforces aggregation thresholds.
  * Only executes queries approved by the Policy Agent.

### **4. Audit Logger**

* **Purpose**: Provides complete traceability of system actions.
* **Functionality**:

  * Logs every query, decision, SQL command, and response metadata.
  * Integrates with Azure Monitor & SIEM for compliance-friendly storage.

## Workflow

1. **User Query**: User asks a question (e.g., patient statistics).
2. **Policy Agent**: Checks query legality using policy embeddings.
3. **Decision**:

   * ✅ Allowed: Forward to SQL Agent.
   * ⚠ Partial: Query Rewriter modifies it.
   * ❌ Blocked: Returns explanation of violated policy.
4. **SQL Agent**: Generates secure SQL, queries PostgreSQL.
5. **Audit Logger**: Records the complete interaction.
6. **Response Formatter**: Returns answer with compliance notes.
7. **LangSmith & Azure Monitor**: Capture reasoning and security logs.

## Data Layer

**Dataset**: Synthea Synthetic Patient Dataset (fully de-identified).

**Core Tables**:

* `patients` – demographics
* `conditions` – diagnoses
* `encounters` – hospital visits
* `medications` – prescriptions
* `organizations` – hospital details
* `audit_logs` – query history & policy decisions

## Tech Stack

* **LLM**: OpenAI models
* **RAG**: (Any vector database) + LangChain Retriever
* **Agents**: LangChain + LangGraph for orchestration
* **Observability**: LangSmith
* **Database**: PostgreSQL
* **Backend**: FastAPI
* **Security**: RBAC, TLS, PII masking
* **Logging**: SIEM

## Project Structure

```
govai-secure-assistant/
│── data/             # Synthea CSV files
│── db/               # SQL schema & migration scripts
│── agents/           # PolicyAgent, SQLAgent, QueryRewriter
│── retrievers/       # Policy document loaders
│── logs/             # Dev logs
│── app/              # FastAPI backend
│── notebooks/        # Jupyter tests
│── README.md         # Documentation
│── requirements.txt  # Dependencies
```

## Installation

```bash
git clone https://github.com/your-username/govai-secure-assistant.git
cd govai-secure-assistant
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Project

```bash
# Load Synthea CSVs into PostgreSQL
data/load_data.py

# Start FastAPI backend
uvicorn app.main:app --reload
```

## Monitoring & Logging

* **LangSmith**: Traces agent reasoning for debugging.
* **Azure Monitor + SIEM**: Stores immutable logs for compliance.

## Example Query Flow

**User Query:** "How many patients with hypertension were treated in Denver hospitals?"

* Policy Agent: ✅ Allowed (aggregated query)
* SQL Agent: Generates secure SQL → Executes
* Audit Logger: Logs full trace
* Response: "There were 184 patients diagnosed with hypertension treated in Denver hospitals. (HIPAA compliant)."

## Compliance Considerations

* Uses only de-identified synthetic data.
* Policy Agent enforces regulatory checks before any data access.
* Audit logs provide full traceability for compliance audits.

## Future Enhancements

* Add differential privacy for aggregate queries.
* FHIR API support.
* Extend to other regulated domains.

## Why This Project Stands Out

* ✅ Advanced **multi-agent orchestration** with LangGraph.
* ✅ Implements **policy-driven AI reasoning**.
* ✅ Provides a **secure and auditable AI** solution.
* ✅ Ideal for showcasing **AI Solution Architect** expertise.

## Author

**Sai Pratheek Kerthi Venkata**
AI/ML Engineer | Cloud & Data Security Enthusiast
[LinkedIn](https://linkedin.com/in/pratheekkv) | [GitHub](https://github.com/pratheekkerthivenkata)
