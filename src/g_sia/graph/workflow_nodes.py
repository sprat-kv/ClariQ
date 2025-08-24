"""
LangGraph workflow nodes for G-SIA multi-agent system.

This module implements the individual nodes that make up the LangGraph workflow,
each representing a specific agent or processing step.
"""

import sys
import logging
from typing import Dict, Any
from pathlib import Path

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.graph.workflow_state import (
    WorkflowState, 
    WorkflowStatus, 
    PolicyVerdict,
    update_state_status, 
    add_warning, 
    set_error,
    finalize_state
)
from g_sia.agents.policy_agent import PolicyAgent
from g_sia.agents.query_rewriter import QueryRewriter
from g_sia.agents.sql_agent import SQLAgent
from g_sia.core.database import get_database_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowNodes:
    """
    Collection of LangGraph nodes for the G-SIA workflow.
    """
    
    def __init__(
        self,
        policy_collection_name: str = "policy_documents",
        qdrant_url: str = "http://localhost:6333",
        enable_sql_execution: bool = True
    ):
        """
        Initialize workflow nodes with agent instances.
        
        Args:
            policy_collection_name: Qdrant collection name for policies
            qdrant_url: Qdrant server URL
            enable_sql_execution: Whether to execute SQL queries
        """
        self.enable_sql_execution = enable_sql_execution
        
        # Initialize agents
        try:
            logger.info("Initializing workflow agents...")
            
            self.policy_agent = PolicyAgent(
                collection_name=policy_collection_name,
                qdrant_url=qdrant_url
            )
            
            self.query_rewriter = QueryRewriter()
            
            if enable_sql_execution:
                self.sql_agent = SQLAgent()
                self.db_manager = get_database_manager()
            else:
                self.sql_agent = None
                self.db_manager = None
            
            logger.info("All workflow agents initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize workflow agents: {e}")
            raise
    
    def policy_check_node(self, state: WorkflowState) -> WorkflowState:
        """
        Policy Agent node - checks query compliance.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with policy verdict
        """
        logger.info(f"[{state['workflow_id']}] Policy check node executing")
        
        try:
            # Update state to reflect policy checking
            state = update_state_status(
                state, 
                WorkflowStatus.POLICY_CHECK, 
                "Analyzing query compliance",
                "policy_agent"
            )
            
            # Get policy verdict
            policy_result = self.policy_agent.get_policy_verdict(state["original_query"])
            
            if not policy_result:
                return set_error(state, "Policy agent failed to respond")
            
            # Update state with policy results
            updated_state = state.copy()
            updated_state["policy_verdict"] = policy_result.get("verdict", "BLOCK")
            updated_state["policy_reasoning"] = policy_result.get("reasoning", "")
            updated_state["policy_confidence"] = policy_result.get("confidence_score", 0.0)
            updated_state["violated_policies"] = policy_result.get("violated_policies", [])
            updated_state["compliance_requirements"] = policy_result.get("compliance_requirements", [])
            updated_state["risk_level"] = policy_result.get("risk_level", "UNKNOWN")
            updated_state["applicable_regulations"] = policy_result.get("applicable_regulations", [])
            
            # Update status to complete
            updated_state = update_state_status(
                updated_state,
                WorkflowStatus.POLICY_COMPLETE,
                f"Policy analysis complete - Verdict: {updated_state['policy_verdict']}"
            )
            
            logger.info(f"[{state['workflow_id']}] Policy verdict: {updated_state['policy_verdict']} (confidence: {updated_state['policy_confidence']})")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"[{state['workflow_id']}] Policy check node failed: {e}")
            return set_error(state, f"Policy check failed: {str(e)}")
    
    def query_rewrite_node(self, state: WorkflowState) -> WorkflowState:
        """
        Query Rewriter node - rewrites non-compliant queries.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with rewritten query
        """
        logger.info(f"[{state['workflow_id']}] Query rewrite node executing")
        
        try:
            # Update state to reflect rewriting
            state = update_state_status(
                state,
                WorkflowStatus.REWRITING,
                "Rewriting non-compliant query",
                "query_rewriter"
            )
            
            # Perform query rewriting
            rewrite_result = self.query_rewriter.rewrite_query(
                state["original_query"],
                state.get("violated_policies", []),
                state.get("compliance_requirements", []),
                state.get("policy_reasoning", "")
            )
            
            if not rewrite_result.get("success", False):
                return set_error(state, f"Query rewriting failed: {rewrite_result.get('error', 'Unknown error')}")
            
            # Update state with rewrite results
            updated_state = state.copy()
            updated_state["rewritten_query"] = rewrite_result["rewritten_query"]
            updated_state["rewrite_strategy"] = rewrite_result.get("rewrite_strategy", "")
            updated_state["rewrite_reasoning"] = rewrite_result.get("compliance_rationale", "")
            updated_state["rewrite_confidence"] = rewrite_result.get("confidence_score", 0.0)
            
            # Re-check policy compliance of rewritten query
            logger.info(f"[{state['workflow_id']}] Re-checking policy compliance of rewritten query...")
            
            rewrite_policy_check = self.policy_agent.get_policy_verdict(updated_state["rewritten_query"])
            
            if rewrite_policy_check and rewrite_policy_check.get("verdict") == "BLOCK":
                return set_error(updated_state, 
                    f"Rewritten query still violates policies: {rewrite_policy_check.get('reasoning', 'Unknown reason')}")
            
            # Update status to complete
            updated_state = update_state_status(
                updated_state,
                WorkflowStatus.REWRITE_COMPLETE,
                f"Query rewritten and re-validated successfully - Strategy: {updated_state['rewrite_strategy']}"
            )
            
            logger.info(f"[{state['workflow_id']}] Query rewritten and validated: '{updated_state['rewritten_query'][:100]}...'")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"[{state['workflow_id']}] Query rewrite node failed: {e}")
            return set_error(state, f"Query rewriting failed: {str(e)}")
    
    def sql_generation_node(self, state: WorkflowState) -> WorkflowState:
        """
        SQL Agent node - generates and executes SQL queries.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with SQL results
        """
        logger.info(f"[{state['workflow_id']}] SQL generation node executing")
        
        try:
            # Check if SQL execution is enabled
            if not self.enable_sql_execution or not self.sql_agent:
                # Return state indicating SQL execution is disabled
                updated_state = state.copy()
                updated_state["final_response"] = {
                    "status": "policy_check_only",
                    "verdict": state["policy_verdict"],
                    "message": "SQL execution disabled - query passed policy check",
                    "original_query": state["original_query"]
                }
                if state.get("rewritten_query"):
                    updated_state["final_response"]["rewritten_query"] = state["rewritten_query"]
                    updated_state["final_response"]["rewrite_strategy"] = state.get("rewrite_strategy", "")
                
                return finalize_state(updated_state, success=True)
            
            # Update state to reflect SQL generation
            state = update_state_status(
                state,
                WorkflowStatus.SQL_GENERATION,
                "Generating and executing SQL query",
                "sql_agent"
            )
            
            # Determine which query to use
            query_to_process = state.get("rewritten_query") or state["original_query"]
            
            # Generate and execute SQL
            sql_result = self.sql_agent.process_query(query_to_process)
            
            if not sql_result.get("success", False):
                return set_error(state, f"SQL processing failed: {sql_result.get('error', 'Unknown error')}")
            
            # Update state with SQL results
            updated_state = state.copy()
            updated_state["generated_sql"] = sql_result.get("generated_sql", "")
            updated_state["sql_security_validation"] = sql_result.get("security_validation", {})
            updated_state["execution_result"] = sql_result.get("execution_result", {})
            updated_state["data_returned"] = sql_result.get("data", [])
            updated_state["row_count"] = sql_result.get("row_count", 0)
            
            # Add SQL warnings if any
            if sql_result.get("warnings"):
                for warning in sql_result["warnings"]:
                    updated_state = add_warning(updated_state, warning)
            
            # Create final response
            final_response = {
                "status": "success",
                "verdict": state["policy_verdict"],
                "data": updated_state["data_returned"],
                "row_count": updated_state["row_count"],
                "sql_query": updated_state["generated_sql"],
                "original_query": state["original_query"],
                "compliance_info": {
                    "policy_confidence": state.get("policy_confidence", 0),
                    "risk_level": state.get("risk_level", "UNKNOWN"),
                    "applicable_regulations": state.get("applicable_regulations", [])
                }
            }
            
            # Add rewrite information if applicable
            if state.get("rewritten_query"):
                final_response["rewritten_query"] = state["rewritten_query"]
                final_response["rewrite_strategy"] = state.get("rewrite_strategy", "")
            
            updated_state["final_response"] = final_response
            
            # Update status to complete
            updated_state = update_state_status(
                updated_state,
                WorkflowStatus.SQL_EXECUTION,
                f"SQL executed successfully - {updated_state['row_count']} rows returned"
            )
            
            logger.info(f"[{state['workflow_id']}] SQL executed successfully: {updated_state['row_count']} rows returned")
            
            return finalize_state(updated_state, success=True)
            
        except Exception as e:
            logger.error(f"[{state['workflow_id']}] SQL generation node failed: {e}")
            return set_error(state, f"SQL processing failed: {str(e)}")
    
    def blocked_response_node(self, state: WorkflowState) -> WorkflowState:
        """
        Blocked response node - handles blocked queries.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with blocked response
        """
        logger.info(f"[{state['workflow_id']}] Blocked response node executing")
        
        try:
            # Create blocked response
            final_response = {
                "status": "blocked",
                "verdict": "BLOCK",
                "reasoning": state.get("policy_reasoning", "Query violates compliance policies"),
                "violated_policies": state.get("violated_policies", []),
                "risk_level": state.get("risk_level", "HIGH"),
                "confidence": state.get("policy_confidence", 1.0),
                "original_query": state["original_query"]
            }
            
            updated_state = state.copy()
            updated_state["final_response"] = final_response
            
            logger.info(f"[{state['workflow_id']}] Query blocked - Risk level: {state.get('risk_level', 'HIGH')}")
            
            return finalize_state(updated_state, success=True)  # Successful blocking is still success
            
        except Exception as e:
            logger.error(f"[{state['workflow_id']}] Blocked response node failed: {e}")
            return set_error(state, f"Failed to create blocked response: {str(e)}")
    
    def audit_logging_node(self, state: WorkflowState) -> WorkflowState:
        """
        Audit logging node - logs the complete workflow for compliance.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with audit information
        """
        logger.info(f"[{state['workflow_id']}] Audit logging node executing")
        
        try:
            # Update state to reflect audit logging
            state = update_state_status(
                state,
                WorkflowStatus.AUDIT_LOGGING,
                "Recording audit log",
                "audit_logger"
            )
            
            # Create audit log entry
            audit_entry = {
                "workflow_id": state["workflow_id"],
                "timestamp": state["start_time"].isoformat(),
                "user_query": state["original_query"],
                "policy_verdict": state.get("policy_verdict"),
                "rewritten_query": state.get("rewritten_query"),
                "executed_sql": state.get("generated_sql"),
                "response_status": state.get("final_response", {}).get("status"),
                "row_count": state.get("row_count", 0),
                "processing_time": state.get("processing_time"),
                "agent_trail": state["agent_trail"],
                "warnings": state["warnings"],
                "success": state["success"],
                "error": state.get("error_message")
            }
            
            # Log to database if available
            if self.db_manager:
                try:
                    # Insert audit log into database
                    insert_sql = """
                        INSERT INTO audit_logs (
                            timestamp, user_query, policy_verdict, rewritten_query,
                            executed_sql, response, trace_id
                        ) VALUES (
                            CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s
                        ) RETURNING id
                    """
                    
                    audit_result = self.db_manager.execute_safe_query(
                        insert_sql,
                        [
                            state["original_query"],
                            state.get("policy_verdict"),
                            state.get("rewritten_query"),
                            state.get("generated_sql"),
                            str(state.get("final_response", {})),
                            state["workflow_id"]
                        ]
                    )
                    
                    if audit_result.get("success") and audit_result.get("data"):
                        audit_log_id = audit_result["data"][0]["id"]
                        logger.info(f"[{state['workflow_id']}] Audit log created with ID: {audit_log_id}")
                    else:
                        logger.warning(f"[{state['workflow_id']}] Failed to create database audit log")
                        
                except Exception as db_error:
                    logger.warning(f"[{state['workflow_id']}] Database audit logging failed: {db_error}")
            
            # Always log to application logs
            logger.info(f"[{state['workflow_id']}] AUDIT: {audit_entry}")
            
            # Update state with audit information
            updated_state = state.copy()
            updated_state["audit_log_id"] = audit_entry.get("audit_log_id")
            
            logger.info(f"[{state['workflow_id']}] Audit logging completed")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"[{state['workflow_id']}] Audit logging node failed: {e}")
            # Don't fail the entire workflow for audit logging issues
            return add_warning(state, f"Audit logging failed: {str(e)}")
    
    def check_readiness(self) -> Dict[str, bool]:
        """
        Check if all workflow nodes are ready for processing.
        
        Returns:
            Dictionary showing readiness status of each component
        """
        readiness = {}
        
        try:
            readiness["policy_agent"] = self.policy_agent.is_ready()
        except Exception as e:
            logger.error(f"Policy Agent readiness check failed: {e}")
            readiness["policy_agent"] = False
        
        readiness["query_rewriter"] = True  # Query rewriter doesn't need external dependencies
        
        if self.sql_agent:
            try:
                readiness["sql_agent"] = self.db_manager.test_connection()
            except Exception as e:
                logger.error(f"SQL Agent readiness check failed: {e}")
                readiness["sql_agent"] = False
        else:
            readiness["sql_agent"] = False
        
        readiness["system_ready"] = all(readiness.values())
        
        return readiness
