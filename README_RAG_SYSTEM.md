# G-SIA Policy RAG System

This document provides comprehensive information about the newly implemented content-aware RAG system for policy document analysis.

## 🏗️ System Architecture

The RAG system consists of several sophisticated components working together:

### Core Components

1. **Document Parser** (`src/g_sia/core/document_parser.py`)
   - NLP-based extraction of document structure
   - Preserves GDPR recitals/chapters and HIPAA titles/sections
   - Automatic document type detection
   - OCR artifact cleaning and text normalization

2. **Content-Aware Chunker** (`src/g_sia/core/content_aware_chunker.py`)
   - Dynamic chunking that respects document boundaries
   - Optimized chunk sizes (800 tokens target, 1200 max)
   - Intelligent overlapping for context preservation
   - Sentence-boundary awareness

3. **Qdrant Vector Store** (`src/g_sia/core/qdrant_vector_store.py`)
   - High-performance vector storage and retrieval
   - Metadata-rich indexing for precise filtering
   - Optimized search with configurable thresholds
   - Support for document-type and section-type filtering

4. **Streamlined Processing**
   - Synchronous processing for simplicity
   - Efficient batch processing for embeddings
   - Comprehensive error handling and logging

5. **Policy Agent** (`src/g_sia/agents/policy_agent.py`)
   - Advanced compliance analysis using RAG
   - Multi-regulation support (GDPR, HIPAA, CCPA)
   - Structured verdict system (ALLOW/REWRITE/BLOCK)
   - Confidence scoring and risk assessment

## 🚀 Quick Start

### Prerequisites

1. **Qdrant Server**: Install and run Qdrant
   ```bash
   # Using Docker (recommended)
   docker run -p 6333:6333 qdrant/qdrant
   
   # Or download from https://qdrant.tech/
   ```

2. **Dependencies**: Install required packages
   ```bash
   uv sync  # This installs all dependencies including spacy and qdrant-client
   ```

3. **SpaCy Model**: Download English language model
   ```bash
   uv run python -m spacy download en_core_web_sm
   ```

4. **Environment Variables**: Set up your `.env` file
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### Build the RAG System

Run the automated build script:

```bash
# Basic build
uv run python scripts/build_rag_system.py

# Clear existing data and rebuild
uv run python scripts/build_rag_system.py --clear

# Custom configuration
uv run python scripts/build_rag_system.py \
  --policy-docs policy_corpus/output \
  --collection my_policy_docs \
  --qdrant-url http://localhost:6333 \
  --verbose
```

The build process will:
1. Parse all policy documents in `policy_corpus/output/`
2. Create content-aware chunks preserving document structure
3. Generate embeddings using OpenAI's text-embedding-ada-002
4. Store everything in Qdrant with rich metadata
5. Test the system with sample queries

## 📋 Usage Examples

### Basic Policy Analysis

```python
from src.g_sia.agents.policy_agent import PolicyAgent

# Initialize agent
agent = PolicyAgent()

# Analyze a query
verdict = agent.get_policy_verdict("How many patients have diabetes?")

print(f"Verdict: {verdict['verdict']}")
print(f"Reasoning: {verdict['reasoning']}")
print(f"Risk Level: {verdict['risk_level']}")
```

### Advanced Usage

```python
# Analyze against specific regulation
hipaa_verdict = agent.analyze_query_by_regulation(
    "Can I access patient records?", 
    "hipaa"
)

# Custom retrieval parameters
verdict = agent.get_policy_verdict(
    "Show me patient email addresses",
    limit=10,
    score_threshold=0.8,
    document_types=["gdpr", "hipaa"]
)
```

### Simple Processing

```python
# Initialize agent and process documents directly
agent = PolicyAgent()

# Process all policy documents at once
result = agent.initialize_vector_store(clear_existing=True)

print(f"Processed {result['chunks_count']} chunks from {result['documents_count']} documents")
```

## 🔍 Document Structure Preservation

The system intelligently preserves document-specific structures:

### GDPR Structure
- **Recitals**: Numbered explanatory statements (1-173)
- **Chapters**: Main organizational units (I-XI)
- **Articles**: Specific legal provisions (1-99)
- **Sections**: Sub-divisions within articles

### HIPAA Structure  
- **Parts**: Major regulatory sections (160, 162, 164)
- **Subparts**: Subdivisions within parts (A, B, C, etc.)
- **Sections**: Specific rules (§ 160.101, § 164.502, etc.)
- **Titles**: High-level organizational units

### Metadata Enrichment

Each chunk includes rich metadata:
```json
{
  "chunk_id": "gdpr_article_6_chunk_0",
  "document_type": "gdpr",
  "section_type": "article", 
  "section_id": "6",
  "section_title": "Lawfulness of processing",
  "parent_section": "II",
  "word_count": 245,
  "estimated_tokens": 318,
  "confidence_score": 0.95
}
```

## 🎯 Chunking Strategy

The content-aware chunker uses several sophisticated techniques:

### Intelligent Boundaries
- Respects sentence boundaries to maintain coherence
- Preserves section boundaries when possible
- Creates meaningful overlaps for context

### Size Optimization
- **Target Size**: 800 tokens (optimal for embeddings)
- **Maximum Size**: 1200 tokens (prevents truncation)
- **Minimum Size**: 200 tokens (avoids tiny fragments)
- **Overlap**: 100 tokens (maintains context)

### Context Preservation
- Previous/next chunk overlaps
- Section headers included for context
- Parent section information maintained

## 🔧 Configuration Options

### Vector Store Settings
```python
vector_store = QdrantPolicyVectorStore(
    collection_name="custom_policies",
    qdrant_url="http://localhost:6333",
    embedding_model="text-embedding-ada-002",
    vector_size=1536,
    distance_metric="cosine"
)
```

### Chunker Settings
```python
chunker = ContentAwareChunker(
    target_chunk_size=800,      # Preferred chunk size
    max_chunk_size=1200,        # Maximum allowed size
    min_chunk_size=200,         # Minimum chunk size
    overlap_size=100,           # Overlap between chunks
    respect_sentence_boundaries=True,
    respect_section_boundaries=True
)
```

### Policy Agent Settings
```python
agent = PolicyAgent(
    collection_name="policy_documents",
    model="gpt-4",              # OpenAI model
    temperature=0.0             # Deterministic responses
)
```

## 📊 Performance Metrics

The system provides detailed performance information:

### Processing Statistics
- Documents processed: Count of source documents
- Sections extracted: Number of structural sections found
- Chunks created: Total content chunks generated
- Processing time: End-to-end processing duration

### Search Performance
- Relevance scores: Similarity scores for retrieved chunks
- Response time: Query processing latency
- Confidence scores: LLM confidence in verdicts
- Coverage: Percentage of regulations covered

### Vector Store Metrics
- Collection size: Total number of vectors stored
- Index status: Indexing completion status
- Memory usage: Storage requirements
- Query throughput: Searches per second

## 🔐 Security Considerations

### Data Privacy
- No raw policy content is logged
- Embeddings are anonymized representations
- Query history can be disabled
- Local processing option available

### Access Control
- Qdrant supports authentication
- API key protection for OpenAI
- Role-based access possible
- Audit logging available

## 🛠️ Troubleshooting

### Common Issues

1. **Qdrant Connection Failed**
   ```bash
   # Check if Qdrant is running
   curl http://localhost:6333/health
   
   # Start Qdrant if needed
   docker run -p 6333:6333 qdrant/qdrant
   ```

2. **OpenAI API Errors**
   ```bash
   # Check API key
   echo $OPENAI_API_KEY
   
   # Test API access
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
        https://api.openai.com/v1/models
   ```

3. **SpaCy Model Missing**
   ```bash
   # Download English model
   uv run python -m spacy download en_core_web_sm
   ```

4. **Memory Issues**
   - Reduce batch size in background processor
   - Use smaller chunk sizes
   - Process documents individually

### Debug Mode

Enable verbose logging:
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

Or use the verbose flag:
```bash
uv run python scripts/build_rag_system.py --verbose
```

## 📈 Next Steps

With the RAG system complete, you're ready for:

1. **Phase 3**: Core Agent Implementation
   - SQL Agent for database queries
   - Query Rewriter for compliance modifications
   - Multi-agent coordination

2. **Phase 4**: LangGraph Orchestration
   - Workflow state management
   - Conditional routing logic
   - Agent coordination

3. **Phase 5**: API & Backend Integration
   - FastAPI endpoints
   - Authentication and authorization
   - Production deployment

## 🤝 Contributing

When extending the RAG system:

1. Follow the established patterns
2. Add comprehensive tests
3. Update documentation
4. Consider backward compatibility
5. Profile performance impact

## 📚 Additional Resources

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [LangChain RAG Guide](https://python.langchain.com/docs/use_cases/question_answering/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [SpaCy Documentation](https://spacy.io/usage)

---

The G-SIA Policy RAG System provides a solid foundation for compliance-aware AI applications. The content-aware chunking and sophisticated retrieval ensure that policy analysis is both accurate and explainable.
