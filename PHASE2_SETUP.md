# Phase 2: Graph RAG Policy System Setup

This guide walks you through setting up and testing the Graph RAG-powered policy compliance system.

## 🎯 What You've Built

A **hybrid Graph RAG system** that combines:
- **Knowledge Graph**: Extracts entities and relationships from policy documents
- **Vector Search**: Semantic similarity search using embeddings  
- **LLM Analysis**: GPT-4 powered compliance reasoning

## 📋 Prerequisites

1. ✅ **Dependencies installed**: `uv add PyPDF2 networkx matplotlib spacy`
2. ✅ **Policy documents**: PDF files in `policy_corpus/` directory
3. ⚠️ **OpenAI API Key**: Set in `.env` file

## 🚀 Quick Start

### Step 1: Set up your `.env` file

Create `.env` in the project root:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_actual_openai_api_key_here

# Optional: Azure OpenAI (if using Azure)
# AZURE_OPENAI_ENDPOINT=your_azure_endpoint
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
```

### Step 2: Build the Graph RAG System

```bash
cd Compliance-Aware-AI-Chatbot
python scripts/embed_policies.py
```

This will:
- Extract text from your PDF policy documents
- Build a knowledge graph of compliance entities and relationships
- Create vector embeddings for semantic search
- Save everything to `./data/` directory

Expected output:
```
Found 3 policy files:
  - CaliforniaConsumerPrivacyAct.pdf
  - GDPR.pdf  
  - hipaa-simplification-201303.pdf

Building Graph RAG system...
📊 Knowledge Graph: 150+ nodes, 200+ edges
🔍 Vector Index: 500+ embeddings
✅ Graph RAG system built successfully!
```

### Step 3: Test the System

```bash
python test_graph_rag.py
```

This will run compliance analysis on various test queries and show you:
- How well the system classifies queries (ALLOW/REWRITE/BLOCK)
- Policy reasoning and risk assessment
- Accuracy metrics

## 🏗️ Architecture Overview

```
User Query → Graph RAG Retrieval → LLM Analysis → Compliance Verdict
              ↓
         [Knowledge Graph + Vector Search]
              ↓
         [HIPAA + GDPR + CCPA Context]
```

### Key Components

1. **`PolicyGraphRAG`** (`src/g_sia/core/graph_rag.py`):
   - Hybrid retrieval system
   - PDF text extraction
   - Entity/relationship extraction
   - Vector similarity search

2. **`PolicyAgent`** (`src/g_sia/agents/policy_agent.py`):
   - Compliance analysis using GPT-4
   - Structured verdict generation
   - Risk assessment

3. **Data Storage** (`./data/`):
   - `policy_graph.json`: Knowledge graph structure
   - `policy_vectors.faiss`: Vector embeddings index
   - `policy_documents.pkl`: Document chunks

## 🧪 Testing Different Query Types

The system handles various compliance scenarios:

| Query Type | Example | Expected Verdict |
|------------|---------|------------------|
| **Aggregate Safe** | "How many patients have diabetes?" | ALLOW |
| **PII Request** | "Show me John Doe's SSN" | BLOCK |
| **Statistical** | "Average age of patients" | ALLOW |
| **Bulk PII** | "List all patient names" | BLOCK |
| **Research** | "Anonymized data for research" | REWRITE |

## 🔧 Customization

### Adding New Policy Documents

1. Place PDF/MD files in `policy_corpus/`
2. Rebuild the system: `python scripts/embed_policies.py`

### Adjusting Compliance Rules

Edit the prompt in `PolicyAgent.analysis_prompt` to modify how the LLM evaluates compliance.

### Tuning Retrieval

- **Graph search**: Modify `graph_traversal_search()` in `PolicyGraphRAG`
- **Vector search**: Adjust `k` parameter in `hybrid_retrieve()`

## 🎉 Next Steps

With Phase 2 complete, you now have a fully functional Graph RAG policy enforcement engine! 

**Phase 3** will integrate this with:
- SQL Query Agent for database access
- Query Rewriter for compliance modifications  
- LangGraph orchestration for complete workflow

## 🐛 Troubleshooting

**Error: "No pre-built Graph RAG data found"**
- Run `python scripts/embed_policies.py` first

**Error: "OpenAI API key not found"**  
- Check your `.env` file has `OPENAI_API_KEY=...`

**Error: "No policy documents found"**
- Ensure PDF files are in `policy_corpus/` directory

**Poor accuracy in tests**
- Your policy PDFs might need better content
- Consider adding more detailed policy summaries
