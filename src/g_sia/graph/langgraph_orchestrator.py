"""
LangGraph orchestrator for G-SIA multi-agent workflow.

This module implements the main LangGraph workflow that orchestrates
the Policy Agent, Query Rewriter, and SQL Agent based on conditional routing.
"""

import sys
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.graph.workflow_state import (
    WorkflowState, 
    WorkflowStatus,
    PolicyVerdict,
    create_initial_state,
    get_state_summary
)
from g_sia.graph.workflow_nodes import WorkflowNodes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """
    LangGraph-based orchestrator for the G-SIA multi-agent workflow.
    """
    
    def __init__(
        self,
        policy_collection_name: str = "policy_documents",
        qdrant_url: str = "http://localhost:6333",
        enable_sql_execution: bool = True,
        enable_checkpoints: bool = True
    ):
        """
        Initialize the LangGraph orchestrator.
        
        Args:
            policy_collection_name: Qdrant collection name for policies
            qdrant_url: Qdrant server URL
            enable_sql_execution: Whether to execute SQL queries
            enable_checkpoints: Whether to enable workflow checkpointing
        """
        self.policy_collection_name = policy_collection_name
        self.qdrant_url = qdrant_url
        self.enable_sql_execution = enable_sql_execution
        self.enable_checkpoints = enable_checkpoints
        
        # Initialize workflow nodes
        self.nodes = WorkflowNodes(
            policy_collection_name=policy_collection_name,
            qdrant_url=qdrant_url,
            enable_sql_execution=enable_sql_execution
        )
        
        # Build the workflow graph
        self.workflow = self._build_workflow_graph()
        
        logger.info("LangGraph orchestrator initialized successfully")
    
    def _build_workflow_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with nodes and conditional edges.
        
        Returns:
            Compiled StateGraph workflow
        """
        logger.info("Building LangGraph workflow...")
        
        # Create the state graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("policy_check", self.nodes.policy_check_node)
        workflow.add_node("query_rewrite", self.nodes.query_rewrite_node)
        workflow.add_node("sql_generation", self.nodes.sql_generation_node)
        workflow.add_node("blocked_response", self.nodes.blocked_response_node)
        workflow.add_node("audit_logging", self.nodes.audit_logging_node)
        
        # Set entry point
        workflow.set_entry_point("policy_check")
        
        # Add conditional edges based on policy verdict
        workflow.add_conditional_edges(
            "policy_check",
            self._route_after_policy_check,
            {
                "allow": "sql_generation",
                "rewrite": "query_rewrite", 
                "block": "blocked_response"
            }
        )
        
        # Add direct edge from query_rewrite to sql_generation 
        # (we'll implement policy re-check within the query_rewrite node)
        workflow.add_edge("query_rewrite", "sql_generation")
        
        # Add edges from terminal nodes to audit logging
        workflow.add_edge("sql_generation", "audit_logging")
        workflow.add_edge("blocked_response", "audit_logging")
        
        # Add edge from audit logging to end
        workflow.add_edge("audit_logging", END)
        
        # Compile the workflow
        checkpointer = MemorySaver() if self.enable_checkpoints else None
        compiled_workflow = workflow.compile(checkpointer=checkpointer)
        
        logger.info("LangGraph workflow built successfully")
        return compiled_workflow
    
    def _route_after_policy_check(self, state: WorkflowState) -> str:
        """
        Conditional routing logic after policy check.
        
        Args:
            state: Current workflow state
            
        Returns:
            Next node name to route to
        """
        verdict = state.get("policy_verdict", "BLOCK")
        
        logger.info(f"[{state['workflow_id']}] Routing after policy check: {verdict}")
        
        if verdict == PolicyVerdict.ALLOW.value:
            return "allow"
        elif verdict == PolicyVerdict.REWRITE.value:
            return "rewrite"
        else:  # BLOCK or any other value
            return "block"
    
    def _route_after_rewrite(self, state: WorkflowState) -> str:
        """
        Conditional routing logic after query rewrite.
        
        Args:
            state: Current workflow state
            
        Returns:
            Next node name to route to
        """
        # This method is no longer used since we simplified the flow
        # Policy re-check is now handled within the query_rewrite node
        logger.info(f"[{state['workflow_id']}] Routing after rewrite - proceeding to SQL generation")
        return "proceed_to_sql"
    
    def _prepare_rewritten_query_for_policy_check(self, state: WorkflowState) -> WorkflowState:
        """
        Prepare state for policy re-check of rewritten query.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with rewritten query as the query to check
        """
        if state.get("rewritten_query"):
            # Temporarily replace original_query with rewritten_query for policy check
            updated_state = state.copy()
            updated_state["metadata"]["temp_original_query"] = state["original_query"]
            updated_state["original_query"] = state["rewritten_query"]
            return updated_state
        
        return state
    
    def _restore_original_query(self, state: WorkflowState) -> WorkflowState:
        """
        Restore original query after policy re-check.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with original query restored
        """
        if state.get("metadata", {}).get("temp_original_query"):
            updated_state = state.copy()
            updated_state["original_query"] = state["metadata"]["temp_original_query"]
            updated_state["metadata"].pop("temp_original_query", None)
            return updated_state
        
        return state
    
    def process_query(
        self,
        user_query: str,
        workflow_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query through the complete LangGraph workflow.
        
        Args:
            user_query: User's natural language query
            workflow_id: Optional workflow ID for tracking
            config: Optional configuration for the workflow
            
        Returns:
            Complete processing result
        """
        try:
            logger.info(f"Processing query through LangGraph workflow: '{user_query}'")
            
            # Create initial state
            initial_state = create_initial_state(user_query, workflow_id)
            
            # Configure workflow execution
            if config is None:
                config = {}
            
            # Always provide configurable keys when checkpointing is enabled
            if self.enable_checkpoints:
                config["configurable"] = {
                    "thread_id": workflow_id or "default-thread"
                }
            
            # Execute the workflow
            final_state = None
            for state in self.workflow.stream(initial_state, config=config):
                final_state = state
                
                # Log intermediate state for debugging
                if logger.isEnabledFor(logging.DEBUG):
                    summary = get_state_summary(final_state)
                    logger.debug(f"[{initial_state['workflow_id']}] Workflow state: {summary}")
            
            # Extract final results
            if final_state:
                # The final state contains all the nodes' outputs
                # We need to get the actual final state from the last node
                final_workflow_state = None
                for node_name, node_state in final_state.items():
                    final_workflow_state = node_state
                    break  # Take the first (and should be only) state
                
                if final_workflow_state:
                    result = self._format_final_result(final_workflow_state)
                    logger.info(f"[{initial_state['workflow_id']}] Workflow completed successfully")
                    return result
            
            # Fallback if no final state
            logger.error(f"[{initial_state['workflow_id']}] Workflow execution failed - no final state")
            return {
                "success": False,
                "error": "Workflow execution failed - no final state",
                "workflow_id": initial_state['workflow_id']
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "success": False,
                "error": f"Workflow execution error: {str(e)}",
                "workflow_id": workflow_id or "unknown"
            }
    
    def _format_final_result(self, final_state: WorkflowState) -> Dict[str, Any]:
        """
        Format the final workflow state into a standardized result.
        
        Args:
            final_state: Final workflow state
            
        Returns:
            Formatted result dictionary
        """
        result = {
            "success": final_state.get("success", False),
            "workflow_id": final_state["workflow_id"],
            "status": final_state["status"],
            "original_query": final_state["original_query"],
            "policy_verdict": final_state.get("policy_verdict"),
            "agent_trail": final_state["agent_trail"],
            "processing_time": final_state.get("processing_time"),
        }
        
        # Add final response if available
        if final_state.get("final_response"):
            result.update(final_state["final_response"])
        
        # Add rewrite information if applicable
        if final_state.get("rewritten_query"):
            result["rewritten_query"] = final_state["rewritten_query"]
            result["rewrite_strategy"] = final_state.get("rewrite_strategy")
        
        # Add SQL information if applicable
        if final_state.get("generated_sql"):
            result["sql_query"] = final_state["generated_sql"]
            result["row_count"] = final_state.get("row_count", 0)
        
        # Add warnings and errors
        if final_state.get("warnings"):
            result["warnings"] = final_state["warnings"]
        
        if final_state.get("error_message"):
            result["error"] = final_state["error_message"]
        
        # Add audit information
        if final_state.get("audit_log_id"):
            result["audit_log_id"] = final_state["audit_log_id"]
        
        return result
    
    def check_system_readiness(self) -> Dict[str, bool]:
        """
        Check if the orchestrator and all agents are ready for processing.
        
        Returns:
            Dictionary showing readiness status
        """
        return self.nodes.check_readiness()
    
    def get_workflow_graph_visualization(self) -> str:
        """
        Get a text representation of the workflow graph.
        
        Returns:
            String representation of the workflow
        """
        return """
G-SIA LangGraph Workflow:

┌─────────────────┐
│   User Query    │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│  Policy Check   │
└─────────┬───────┘
          │
          ▼
    ┌─────────────┐
    │   Route     │
    │   Based     │
    │   on        │
    │   Verdict   │
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
    │    │  Query   │       │
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
│      SQL Generation         │
│         (if ALLOW)          │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│      Blocked Response       │
│        (if BLOCK)           │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│       Audit Logging         │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│         END                 │
└─────────────────────────────┘
"""


def main():
    """Test the LangGraph orchestrator."""
    try:
        # Initialize orchestrator
        orchestrator = LangGraphOrchestrator(enable_sql_execution=True)
        
        # Check system readiness
        readiness = orchestrator.check_system_readiness()
        print("🚀 LangGraph Orchestrator Test")
        print("=" * 50)
        print(f"System Ready: {'✅' if readiness['system_ready'] else '❌'}")
        
        for component, ready in readiness.items():
            if component != "system_ready":
                print(f"  {component}: {'✅' if ready else '❌'}")
        
        if not readiness["system_ready"]:
            print("⚠️  System not ready - some tests may fail")
        
        # Test queries
        test_queries = [
            "How many patients have diabetes?",
            "Show me John Doe's SSN",
            "List all patients with hypertension",
            "What is the average age by gender?"
        ]
        
        print(f"\n🧪 Testing LangGraph Workflow")
        print("=" * 50)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\nTest {i}: {query}")
            print("-" * 40)
            
            result = orchestrator.process_query(query)
            
            print(f"Success: {result.get('success', False)}")
            print(f"Verdict: {result.get('policy_verdict', 'N/A')}")
            print(f"Status: {result.get('status', 'N/A')}")
            print(f"Agent Trail: {' → '.join(result.get('agent_trail', []))}")
            
            if result.get('rewritten_query'):
                print(f"Rewritten: {result['rewritten_query'][:60]}...")
            
            if result.get('sql_query'):
                print(f"SQL: {result['sql_query'][:60]}...")
            
            if result.get('row_count') is not None:
                print(f"Rows: {result['row_count']}")
            
            if result.get('error'):
                print(f"Error: {result['error']}")
            
            print(f"Processing Time: {result.get('processing_time', 0):.2f}s")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    main()
