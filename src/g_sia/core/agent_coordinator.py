"""
Agent Coordinator for G-SIA multi-agent system.

This module coordinates the workflow between Policy Agent, Query Rewriter, 
and SQL Agent to process user queries in a compliant manner.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.agents.policy_agent import PolicyAgent
from g_sia.agents.query_rewriter import QueryRewriter
from g_sia.agents.sql_agent import SQLAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryStatus(Enum):
    """Query processing status."""
    RECEIVED = "received"
    POLICY_CHECK = "policy_check"
    REWRITING = "rewriting"
    SQL_GENERATION = "sql_generation"
    EXECUTION = "execution"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueryProcessingResult:
    """Complete result of query processing through all agents."""
    original_query: str
    final_result: Dict[str, Any]
    status: QueryStatus
    policy_verdict: Dict[str, Any]
    rewritten_query: Optional[str] = None
    sql_query: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    agent_trail: Optional[list] = None
    warnings: Optional[list] = None
    error: Optional[str] = None


class AgentCoordinator:
    """
    Coordinates the multi-agent workflow for G-SIA.
    """
    
    def __init__(
        self,
        policy_collection_name: str = "policy_documents",
        qdrant_url: str = "http://localhost:6333",
        enable_sql_execution: bool = True
    ):
        """
        Initialize Agent Coordinator.
        
        Args:
            policy_collection_name: Qdrant collection name for policies
            qdrant_url: Qdrant server URL
            enable_sql_execution: Whether to actually execute SQL queries
        """
        self.enable_sql_execution = enable_sql_execution
        
        # Initialize agents
        try:
            logger.info("Initializing agents...")
            
            self.policy_agent = PolicyAgent(
                collection_name=policy_collection_name,
                qdrant_url=qdrant_url
            )
            
            self.query_rewriter = QueryRewriter()
            
            if enable_sql_execution:
                self.sql_agent = SQLAgent()
            else:
                self.sql_agent = None
                logger.info("SQL execution disabled - SQL Agent not initialized")
            
            logger.info("All agents initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            raise
    
    def check_agent_readiness(self) -> Dict[str, bool]:
        """
        Check if all agents are ready for processing.
        
        Returns:
            Dictionary showing readiness status of each agent
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
                readiness["sql_agent"] = self.sql_agent.db_manager.test_connection()
            except Exception as e:
                logger.error(f"SQL Agent readiness check failed: {e}")
                readiness["sql_agent"] = False
        else:
            readiness["sql_agent"] = False
        
        return readiness
    
    def process_query(self, user_query: str) -> QueryProcessingResult:
        """
        Process a user query through the complete multi-agent workflow.
        
        Args:
            user_query: User's natural language query
            
        Returns:
            Complete processing result
        """
        start_time = datetime.now()
        agent_trail = []
        warnings = []
        
        try:
            logger.info(f"Processing query: '{user_query}'")
            
            # Step 1: Policy Check
            logger.info("Step 1: Policy compliance check...")
            agent_trail.append("policy_agent")
            
            policy_verdict = self.policy_agent.get_policy_verdict(user_query)
            
            if not policy_verdict:
                return QueryProcessingResult(
                    original_query=user_query,
                    final_result={"error": "Policy agent failed to respond"},
                    status=QueryStatus.FAILED,
                    policy_verdict={},
                    error="Policy agent failure"
                )
            
            verdict = policy_verdict.get("verdict", "BLOCK")
            logger.info(f"Policy verdict: {verdict}")
            
            # Step 2: Handle based on policy verdict
            if verdict == "BLOCK":
                # Query is blocked - return policy explanation
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                
                return QueryProcessingResult(
                    original_query=user_query,
                    final_result={
                        "status": "blocked",
                        "verdict": "BLOCK",
                        "reasoning": policy_verdict.get("reasoning", "Query violates compliance policies"),
                        "violated_policies": policy_verdict.get("violated_policies", []),
                        "risk_level": policy_verdict.get("risk_level", "HIGH"),
                        "confidence": policy_verdict.get("confidence_score", 1.0)
                    },
                    status=QueryStatus.COMPLETED,
                    policy_verdict=policy_verdict,
                    processing_time=processing_time,
                    agent_trail=agent_trail
                )
            
            elif verdict == "REWRITE":
                # Query needs rewriting
                logger.info("Step 2: Rewriting non-compliant query...")
                agent_trail.append("query_rewriter")
                
                rewrite_result = self.query_rewriter.rewrite_query(
                    user_query,
                    policy_verdict.get("violated_policies", []),
                    policy_verdict.get("compliance_requirements", []),
                    policy_verdict.get("suggested_modifications", "")
                )
                
                if not rewrite_result.get("success", False):
                    return QueryProcessingResult(
                        original_query=user_query,
                        final_result={"error": f"Query rewriting failed: {rewrite_result.get('error')}"},
                        status=QueryStatus.FAILED,
                        policy_verdict=policy_verdict,
                        error="Query rewriting failure"
                    )
                
                rewritten_query = rewrite_result["rewritten_query"]
                logger.info(f"Query rewritten to: '{rewritten_query}'")
                
                # Re-check policy compliance of rewritten query
                logger.info("Step 2b: Re-checking policy compliance of rewritten query...")
                rewrite_policy_check = self.policy_agent.get_policy_verdict(rewritten_query)
                
                if rewrite_policy_check.get("verdict") == "BLOCK":
                    warnings.append("Rewritten query still violates policies")
                    return QueryProcessingResult(
                        original_query=user_query,
                        final_result={
                            "status": "rewrite_failed",
                            "original_query": user_query,
                            "rewritten_query": rewritten_query,
                            "error": "Rewritten query still violates compliance policies",
                            "rewrite_reasoning": rewrite_policy_check.get("reasoning")
                        },
                        status=QueryStatus.FAILED,
                        policy_verdict=policy_verdict,
                        rewritten_query=rewritten_query,
                        error="Rewrite still non-compliant"
                    )
                
                # Use rewritten query for SQL generation
                query_for_sql = rewritten_query
                
            elif verdict == "ALLOW":
                # Query is compliant - proceed directly
                query_for_sql = user_query
                rewrite_result = None
                logger.info("Query approved - proceeding to SQL generation")
            
            else:
                # Unknown verdict
                return QueryProcessingResult(
                    original_query=user_query,
                    final_result={"error": f"Unknown policy verdict: {verdict}"},
                    status=QueryStatus.FAILED,
                    policy_verdict=policy_verdict,
                    error="Unknown policy verdict"
                )
            
            # Step 3: SQL Generation and Execution
            if self.sql_agent and self.enable_sql_execution:
                logger.info("Step 3: SQL generation and execution...")
                agent_trail.append("sql_agent")
                
                sql_result = self.sql_agent.process_query(query_for_sql)
                
                if not sql_result.get("success", False):
                    return QueryProcessingResult(
                        original_query=user_query,
                        final_result={
                            "error": f"SQL processing failed: {sql_result.get('error')}",
                            "sql_violations": sql_result.get("violations", [])
                        },
                        status=QueryStatus.FAILED,
                        policy_verdict=policy_verdict,
                        rewritten_query=rewritten_query if verdict == "REWRITE" else None,
                        error="SQL processing failure"
                    )
                
                # Add SQL warnings if any
                if sql_result.get("warnings"):
                    warnings.extend(sql_result["warnings"])
                
                # Success! Return complete result
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                
                final_result = {
                    "status": "success",
                    "verdict": verdict,
                    "data": sql_result.get("data", []),
                    "row_count": sql_result.get("row_count", 0),
                    "sql_query": sql_result.get("generated_sql", ""),
                    "original_query": user_query,
                    "processing_time_seconds": processing_time,
                    "compliance_info": {
                        "policy_confidence": policy_verdict.get("confidence_score", 0),
                        "risk_level": policy_verdict.get("risk_level", "UNKNOWN"),
                        "applicable_regulations": policy_verdict.get("applicable_regulations", [])
                    }
                }
                
                if verdict == "REWRITE":
                    final_result["rewritten_query"] = rewritten_query
                    final_result["rewrite_strategy"] = rewrite_result.get("rewrite_strategy", "")
                
                return QueryProcessingResult(
                    original_query=user_query,
                    final_result=final_result,
                    status=QueryStatus.COMPLETED,
                    policy_verdict=policy_verdict,
                    rewritten_query=rewritten_query if verdict == "REWRITE" else None,
                    sql_query=sql_result.get("generated_sql"),
                    execution_result=sql_result,
                    processing_time=processing_time,
                    agent_trail=agent_trail,
                    warnings=warnings if warnings else None
                )
            
            else:
                # SQL execution disabled - return policy result only
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                
                final_result = {
                    "status": "policy_check_only",
                    "verdict": verdict,
                    "message": "SQL execution disabled - query passed policy check",
                    "original_query": user_query,
                    "processing_time_seconds": processing_time
                }
                
                if verdict == "REWRITE":
                    final_result["rewritten_query"] = rewritten_query
                    final_result["rewrite_strategy"] = rewrite_result.get("rewrite_strategy", "")
                
                return QueryProcessingResult(
                    original_query=user_query,
                    final_result=final_result,
                    status=QueryStatus.COMPLETED,
                    policy_verdict=policy_verdict,
                    rewritten_query=rewritten_query if verdict == "REWRITE" else None,
                    processing_time=processing_time,
                    agent_trail=agent_trail,
                    warnings=warnings if warnings else None
                )
        
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return QueryProcessingResult(
                original_query=user_query,
                final_result={"error": f"System error: {str(e)}"},
                status=QueryStatus.FAILED,
                policy_verdict={},
                processing_time=processing_time,
                agent_trail=agent_trail,
                error=str(e)
            )
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            System status information
        """
        readiness = self.check_agent_readiness()
        
        status = {
            "system_ready": all(readiness.values()),
            "agent_readiness": readiness,
            "sql_execution_enabled": self.enable_sql_execution,
            "components": {
                "policy_agent": {
                    "ready": readiness["policy_agent"],
                    "vector_store_info": None
                },
                "query_rewriter": {
                    "ready": readiness["query_rewriter"]
                },
                "sql_agent": {
                    "ready": readiness["sql_agent"],
                    "database_info": None
                }
            }
        }
        
        # Get additional info if agents are ready
        if readiness["policy_agent"]:
            try:
                status["components"]["policy_agent"]["vector_store_info"] = self.policy_agent.get_vector_store_info()
            except Exception as e:
                logger.warning(f"Could not get vector store info: {e}")
        
        if readiness["sql_agent"] and self.sql_agent:
            try:
                db_info = self.sql_agent.get_database_info()
                status["components"]["sql_agent"]["database_info"] = {
                    "tables_count": len(db_info),
                    "tables": list(db_info.keys())
                }
            except Exception as e:
                logger.warning(f"Could not get database info: {e}")
        
        return status


def main():
    """Test Agent Coordinator functionality."""
    try:
        # Initialize coordinator
        print("🚀 Initializing Agent Coordinator...")
        coordinator = AgentCoordinator(enable_sql_execution=True)
        
        # Check system status
        print("\n📊 System Status:")
        status = coordinator.get_system_status()
        print(f"  System Ready: {'✅' if status['system_ready'] else '❌'}")
        for agent, ready in status["agent_readiness"].items():
            print(f"  {agent}: {'✅' if ready else '❌'}")
        
        if not status["system_ready"]:
            print("⚠️  System not fully ready. Some tests may fail.")
        
        # Test queries
        test_queries = [
            "How many patients are in the database?",  # Should ALLOW
            "Show me John Doe's medical records",      # Should BLOCK  
            "List all patients with diabetes",         # Should REWRITE
            "What are the most common conditions by age group?"  # Should ALLOW
        ]
        
        print(f"\n🧪 Testing Multi-Agent Workflow")
        print("=" * 60)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\nTest {i}: {query}")
            print("-" * 40)
            
            result = coordinator.process_query(query)
            
            print(f"Status: {result.status.value}")
            print(f"Verdict: {result.policy_verdict.get('verdict', 'N/A')}")
            print(f"Agent Trail: {' → '.join(result.agent_trail) if result.agent_trail else 'None'}")
            
            if result.rewritten_query:
                print(f"Rewritten: {result.rewritten_query}")
            
            if result.sql_query:
                print(f"SQL: {result.sql_query}")
            
            if result.final_result.get("data"):
                print(f"Results: {len(result.final_result['data'])} rows")
            
            if result.warnings:
                print(f"Warnings: {', '.join(result.warnings)}")
            
            if result.error:
                print(f"Error: {result.error}")
            
            print(f"Processing Time: {result.processing_time:.2f}s" if result.processing_time else "N/A")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    main()
