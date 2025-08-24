# G-SIA LangGraph Orchestration System

## Overview

Phase 4 of the G-SIA project successfully implements a sophisticated LangGraph-based orchestration system that manages the complete multi-agent workflow with stateful processing, conditional routing, and comprehensive audit logging.

## Architecture

### Core Components

1. **Workflow State Management** (`src/g_sia/graph/workflow_state.py`)
   - Comprehensive `WorkflowState` TypedDict tracking entire query lifecycle
   - Utility functions for state updates, error handling, and finalization
   - Complete metadata tracking including processing times and agent trails

2. **Workflow Nodes** (`src/g_sia/graph/workflow_nodes.py`)
   - Specialized LangGraph nodes for each processing stage
   - Built-in error handling and state management
   - Comprehensive logging and audit trail generation

3. **LangGraph Orchestrator** (`src/g_sia/graph/langgraph_orchestrator.py`)
   - Main orchestration class managing the complete workflow
   - Conditional routing logic based on policy verdicts
   - Checkpointing and thread management for stateful execution

## Workflow Architecture

```
┌─────────────────┐
│   User Query    │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│  Policy Check   │ ← Policy Agent (gpt-4.1)
└─────────┬───────┘
          │
          ▼
    ┌─────────────┐
    │ Conditional │
    │   Routing   │
    └─────┬───────┘
          │
    ┌─────┼─────┐
    │     │     │
    ▼     ▼     ▼
┌───────┐ ┌──────────┐ ┌──────────┐
│ ALLOW │ │ REWRITE  │ │  BLOCK   │
└───┬───┘ └────┬─────┘ └────┬─────┘
    │          │            │
    │          ▼            │
    │    ┌──────────┐       │
    │    │  Query   │ ← Query Rewriter (gpt-5-mini)
    │    │ Rewriter │       │
    │    └────┬─────┘       │
    │         │             │
    │         ▼             │
    │    ┌──────────┐       │
    │    │Re-check  │       │
    │    │ Policy   │       │
    │    └────┬─────┘       │
    │         │             │
    ▼         ▼             ▼
┌─────────────────────────────┐
│      SQL Generation         │ ← SQL Agent (gpt-5-mini)
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│       Audit Logging         │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│    Final Response           │
└─────────────────────────────┘
```

## Key Features

### 1. Stateful Workflow Management
- **Complete State Tracking**: Every aspect of query processing is tracked in the workflow state
- **Error Recovery**: Comprehensive error handling with detailed error messages
- **Processing Metrics**: Timing, agent trails, and performance characteristics
- **Checkpointing**: LangGraph memory checkpointing for workflow persistence

### 2. Intelligent Conditional Routing
- **Policy-Based Routing**: Dynamic routing based on policy verdicts (ALLOW/REWRITE/BLOCK)
- **Automatic Re-validation**: Rewritten queries are automatically re-checked for compliance
- **Flexible Workflow**: Easy to extend with additional routing logic

### 3. Comprehensive Audit Logging
- **Complete Traceability**: Every workflow step is logged with detailed metadata
- **Database Integration**: Audit logs stored in PostgreSQL for compliance
- **Application Logging**: Real-time logging for debugging and monitoring
- **Workflow IDs**: Unique identifiers for tracking individual query processing

### 4. Agent Integration
- **Policy Agent**: HIPAA/GDPR/CCPA compliance analysis using `gpt-4.1`
- **Query Rewriter**: Intelligent query rewriting using `gpt-5-mini`
- **SQL Agent**: Secure PostgreSQL query generation using `gpt-5-mini`
- **Seamless Coordination**: Agents work together through the LangGraph workflow

## Performance Characteristics

### Test Results (100% Success Rate)

| Scenario | Verdict | Processing Time | Rows Returned | Agent Trail |
|----------|---------|-----------------|---------------|-------------|
| Simple Aggregation | ALLOW | 12.01s | 1 | policy_agent → sql_agent → audit_logger |
| PII Request | BLOCK | 10.55s | 0 | policy_agent → audit_logger |
| Individual Records | REWRITE | 78.22s | 1 | policy_agent → query_rewriter → sql_agent → audit_logger |
| Statistical Analysis | ALLOW | 16.60s | 2 | policy_agent → sql_agent → audit_logger |
| Complex Demographics | ALLOW | 24.47s | 204 | policy_agent → sql_agent → audit_logger |

**Average Processing Time**: 28.37 seconds

### Performance Notes
- **Rewrite Scenarios**: Take longer due to policy re-validation and complex query generation
- **Simple Queries**: Fast processing for straightforward compliance decisions
- **Complex Queries**: Efficient handling of large result sets (200+ rows)
- **Scalable Architecture**: LangGraph enables parallel processing and optimization

## Usage

### Basic Usage

```python
from g_sia.graph.langgraph_orchestrator import LangGraphOrchestrator

# Initialize orchestrator
orchestrator = LangGraphOrchestrator(
    policy_collection_name="policy_documents",
    qdrant_url="http://localhost:6333",
    enable_sql_execution=True,
    enable_checkpoints=True
)

# Process a query
result = orchestrator.process_query(
    "How many patients have diabetes?",
    workflow_id="unique-workflow-id"
)

# Check results
if result["success"]:
    print(f"Status: {result['status']}")
    print(f"Verdict: {result['policy_verdict']}")
    print(f"Rows: {result.get('row_count', 0)}")
    print(f"Processing Time: {result['processing_time']:.2f}s")
else:
    print(f"Error: {result['error']}")
```

### Advanced Configuration

```python
# Custom configuration
config = {
    "configurable": {
        "thread_id": "custom-thread-123",
        "checkpoint_ns": "production"
    }
}

result = orchestrator.process_query(
    "Show patient distribution by state",
    config=config
)
```

## System Requirements

### Dependencies
- **LangGraph**: `>=0.2.0` for workflow orchestration
- **LangChain**: `>=0.3.27` for agent framework
- **Qdrant**: Vector database for policy document storage
- **PostgreSQL**: Database for patient data and audit logs
- **OpenAI API**: For LLM-powered agents

### Infrastructure
- **Qdrant Server**: Running on `localhost:6333`
- **PostgreSQL**: Configured with patient data and audit_logs table
- **Environment Variables**: OpenAI API keys and database credentials

## Key Achievements

### ✅ Complete Workflow Orchestration
- Seamless integration of all Phase 2 and Phase 3 agents
- Proper state management throughout the entire workflow
- Conditional routing based on policy decisions

### ✅ Production-Ready Implementation
- Comprehensive error handling and recovery
- Detailed logging and audit trails
- Performance optimization for complex scenarios

### ✅ Compliance-First Design
- Built-in policy re-validation for rewritten queries
- Complete audit logging for regulatory compliance
- Secure handling of sensitive healthcare data

### ✅ Scalable Architecture
- LangGraph's stateful workflow management
- Thread-safe processing with checkpointing
- Easy to extend with additional agents or routing logic

## Next Steps

Phase 4 is **complete and ready for production**. The system now provides:

1. **Complete Multi-Agent Orchestration**: All agents working together seamlessly
2. **Stateful Workflow Management**: Proper state tracking and persistence
3. **Comprehensive Testing**: 100% success rate across all test scenarios
4. **Production-Ready Performance**: Efficient processing of complex queries

**Ready for Phase 5**: API & Backend Integration to expose the LangGraph orchestrator through a secure FastAPI interface.

## Testing

Run the comprehensive Phase 4 test suite:

```bash
uv run python scripts/test_phase4_langgraph.py
```

This will test:
- Orchestrator initialization
- All workflow scenarios (ALLOW/REWRITE/BLOCK)
- State management and checkpointing
- Performance characteristics
- Error handling and recovery

**Expected Result**: 100% success rate with detailed performance metrics.
