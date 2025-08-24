"""
LangGraph workflow state definition for G-SIA multi-agent system.

This module defines the state structure that flows through the LangGraph workflow,
tracking the query processing from policy analysis through SQL execution.
"""

from typing import Dict, Any, List, Optional, TypedDict, Literal
from datetime import datetime
from enum import Enum


class WorkflowStatus(Enum):
    """Status of the workflow processing."""
    INITIALIZED = "initialized"
    POLICY_CHECK = "policy_check"
    POLICY_COMPLETE = "policy_complete"
    REWRITING = "rewriting"
    REWRITE_COMPLETE = "rewrite_complete"
    SQL_GENERATION = "sql_generation"
    SQL_EXECUTION = "sql_execution"
    AUDIT_LOGGING = "audit_logging"
    COMPLETED = "completed"
    FAILED = "failed"


class PolicyVerdict(Enum):
    """Policy verdict types."""
    ALLOW = "ALLOW"
    REWRITE = "REWRITE"
    BLOCK = "BLOCK"


class WorkflowState(TypedDict):
    """
    State structure for the G-SIA LangGraph workflow.
    
    This state is passed between nodes and tracks the complete
    query processing lifecycle.
    """
    # Original user input
    original_query: str
    
    # Workflow metadata
    workflow_id: str
    status: str  # WorkflowStatus enum as string
    start_time: datetime
    current_step: str
    agent_trail: List[str]
    
    # Policy Agent results
    policy_verdict: Optional[str]  # PolicyVerdict enum as string
    policy_reasoning: Optional[str]
    policy_confidence: Optional[float]
    violated_policies: Optional[List[str]]
    compliance_requirements: Optional[List[str]]
    risk_level: Optional[str]
    applicable_regulations: Optional[List[str]]
    
    # Query Rewriter results
    rewritten_query: Optional[str]
    rewrite_strategy: Optional[str]
    rewrite_reasoning: Optional[str]
    rewrite_confidence: Optional[float]
    
    # SQL Agent results
    generated_sql: Optional[str]
    sql_security_validation: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    data_returned: Optional[List[Dict[str, Any]]]
    row_count: Optional[int]
    
    # Final results
    final_response: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    warnings: List[str]
    
    # Audit information
    processing_time: Optional[float]
    audit_log_id: Optional[str]
    
    # Additional metadata
    metadata: Dict[str, Any]


def create_initial_state(
    original_query: str,
    workflow_id: Optional[str] = None
) -> WorkflowState:
    """
    Create an initial workflow state for a new query.
    
    Args:
        original_query: The user's original query
        workflow_id: Optional workflow ID (generated if not provided)
        
    Returns:
        Initial workflow state
    """
    import uuid
    
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())
    
    return WorkflowState(
        # Original input
        original_query=original_query,
        
        # Workflow metadata
        workflow_id=workflow_id,
        status=WorkflowStatus.INITIALIZED.value,
        start_time=datetime.now(),
        current_step="initialization",
        agent_trail=[],
        
        # Policy Agent results (empty initially)
        policy_verdict=None,
        policy_reasoning=None,
        policy_confidence=None,
        violated_policies=None,
        compliance_requirements=None,
        risk_level=None,
        applicable_regulations=None,
        
        # Query Rewriter results (empty initially)
        rewritten_query=None,
        rewrite_strategy=None,
        rewrite_reasoning=None,
        rewrite_confidence=None,
        
        # SQL Agent results (empty initially)
        generated_sql=None,
        sql_security_validation=None,
        execution_result=None,
        data_returned=None,
        row_count=None,
        
        # Final results (empty initially)
        final_response=None,
        success=False,
        error_message=None,
        warnings=[],
        
        # Audit information (empty initially)
        processing_time=None,
        audit_log_id=None,
        
        # Additional metadata
        metadata={}
    )


def update_state_status(
    state: WorkflowState,
    new_status: WorkflowStatus,
    current_step: str,
    agent_name: Optional[str] = None
) -> WorkflowState:
    """
    Update the workflow state with new status information.
    
    Args:
        state: Current workflow state
        new_status: New status to set
        current_step: Description of current processing step
        agent_name: Name of agent being executed (if applicable)
        
    Returns:
        Updated workflow state
    """
    updated_state = state.copy()
    updated_state["status"] = new_status.value
    updated_state["current_step"] = current_step
    
    if agent_name:
        updated_state["agent_trail"] = state["agent_trail"] + [agent_name]
    
    return updated_state


def add_warning(state: WorkflowState, warning: str) -> WorkflowState:
    """
    Add a warning to the workflow state.
    
    Args:
        state: Current workflow state
        warning: Warning message to add
        
    Returns:
        Updated workflow state
    """
    updated_state = state.copy()
    updated_state["warnings"] = state["warnings"] + [warning]
    return updated_state


def set_error(state: WorkflowState, error_message: str) -> WorkflowState:
    """
    Set an error state in the workflow.
    
    Args:
        state: Current workflow state
        error_message: Error message to set
        
    Returns:
        Updated workflow state with error
    """
    updated_state = state.copy()
    updated_state["status"] = WorkflowStatus.FAILED.value
    updated_state["success"] = False
    updated_state["error_message"] = error_message
    
    # Calculate processing time
    if state["start_time"]:
        processing_time = (datetime.now() - state["start_time"]).total_seconds()
        updated_state["processing_time"] = processing_time
    
    return updated_state


def finalize_state(state: WorkflowState, success: bool = True) -> WorkflowState:
    """
    Finalize the workflow state with completion information.
    
    Args:
        state: Current workflow state
        success: Whether the workflow completed successfully
        
    Returns:
        Finalized workflow state
    """
    updated_state = state.copy()
    updated_state["status"] = WorkflowStatus.COMPLETED.value if success else WorkflowStatus.FAILED.value
    updated_state["success"] = success
    
    # Calculate processing time
    if state["start_time"]:
        processing_time = (datetime.now() - state["start_time"]).total_seconds()
        updated_state["processing_time"] = processing_time
    
    return updated_state


def get_state_summary(state: WorkflowState) -> Dict[str, Any]:
    """
    Get a summary of the current workflow state for logging/debugging.
    
    Args:
        state: Current workflow state
        
    Returns:
        Summary dictionary
    """
    return {
        "workflow_id": state["workflow_id"],
        "status": state["status"],
        "current_step": state["current_step"],
        "agent_trail": state["agent_trail"],
        "policy_verdict": state["policy_verdict"],
        "has_rewritten_query": bool(state["rewritten_query"]),
        "has_sql": bool(state["generated_sql"]),
        "has_data": bool(state["data_returned"]),
        "success": state["success"],
        "error": state["error_message"],
        "warnings_count": len(state["warnings"]),
        "processing_time": state["processing_time"]
    }
