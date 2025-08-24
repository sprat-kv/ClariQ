#!/usr/bin/env python3
"""
Test script for Phase 3 agents and multi-agent workflow.

This script tests the complete G-SIA multi-agent system including:
- Policy Agent (from Phase 2)
- SQL Agent  
- Query Rewriter
- Agent Coordinator
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from g_sia.core.agent_coordinator import AgentCoordinator
from g_sia.agents.policy_agent import PolicyAgent
from g_sia.agents.sql_agent import SQLAgent
from g_sia.agents.query_rewriter import QueryRewriter
from g_sia.core.database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase3Tester:
    """
    Comprehensive tester for Phase 3 agents and workflow.
    """
    
    def __init__(self):
        """Initialize the tester."""
        self.test_results = []
    
    def test_individual_agents(self) -> Dict[str, bool]:
        """Test each agent individually."""
        results = {}
        
        print("🧪 Testing Individual Agents")
        print("=" * 50)
        
        # Test Policy Agent
        print("\n1. Testing Policy Agent...")
        try:
            policy_agent = PolicyAgent()
            if policy_agent.is_ready():
                test_verdict = policy_agent.get_policy_verdict("How many patients have diabetes?")
                results["policy_agent"] = test_verdict.get("verdict") in ["ALLOW", "REWRITE", "BLOCK"]
                print(f"   ✅ Policy Agent: Working (Verdict: {test_verdict.get('verdict', 'N/A')})")
            else:
                results["policy_agent"] = False
                print("   ❌ Policy Agent: Not ready (missing vector store)")
        except Exception as e:
            results["policy_agent"] = False
            print(f"   ❌ Policy Agent: Error - {e}")
        
        # Test Database Connection
        print("\n2. Testing Database Connection...")
        try:
            db = DatabaseManager()
            if db.test_connection():
                results["database"] = True
                print("   ✅ Database: Connected successfully")
            else:
                results["database"] = False
                print("   ❌ Database: Connection failed")
        except Exception as e:
            results["database"] = False
            print(f"   ❌ Database: Error - {e}")
        
        # Test SQL Agent
        print("\n3. Testing SQL Agent...")
        try:
            if results.get("database", False):
                sql_agent = SQLAgent()
                test_sql = sql_agent.generate_sql("How many patients are there?")
                if test_sql.get("success", False):
                    results["sql_agent"] = True
                    print(f"   ✅ SQL Agent: Generated SQL - {test_sql.get('sql_query', '')[:50]}...")
                else:
                    results["sql_agent"] = False
                    print(f"   ❌ SQL Agent: Failed to generate SQL - {test_sql.get('error', '')}")
            else:
                results["sql_agent"] = False
                print("   ❌ SQL Agent: Skipped (database not available)")
        except Exception as e:
            results["sql_agent"] = False
            print(f"   ❌ SQL Agent: Error - {e}")
        
        # Test Query Rewriter
        print("\n4. Testing Query Rewriter...")
        try:
            rewriter = QueryRewriter()
            test_rewrite = rewriter.rewrite_query(
                "Show me John Doe's medical records",
                ["Contains patient name", "Individual record request"],
                ["HIPAA compliance", "Remove PII"]
            )
            if test_rewrite.get("success", False):
                results["query_rewriter"] = True
                print(f"   ✅ Query Rewriter: Working")
                print(f"      Rewritten: {test_rewrite.get('rewritten_query', '')[:50]}...")
            else:
                results["query_rewriter"] = False
                print(f"   ❌ Query Rewriter: Failed - {test_rewrite.get('error', '')}")
        except Exception as e:
            results["query_rewriter"] = False
            print(f"   ❌ Query Rewriter: Error - {e}")
        
        return results
    
    def test_multi_agent_workflow(self) -> List[Dict[str, Any]]:
        """Test the complete multi-agent workflow."""
        print("\n🔄 Testing Multi-Agent Workflow")
        print("=" * 50)
        
        # Test scenarios covering different policy outcomes
        test_scenarios = [
            {
                "name": "Compliant Aggregation Query",
                "query": "How many patients have diabetes?",
                "expected_verdict": "ALLOW",
                "should_execute_sql": True
            },
            {
                "name": "PII Request (Should Block)",
                "query": "Show me John Doe's social security number",
                "expected_verdict": "BLOCK", 
                "should_execute_sql": False
            },
            {
                "name": "Individual Records (Should Rewrite)",
                "query": "List all patients with hypertension",
                "expected_verdict": "REWRITE",
                "should_execute_sql": True
            },
            {
                "name": "Statistical Query",
                "query": "What is the average age of patients by gender?",
                "expected_verdict": "ALLOW",
                "should_execute_sql": True
            },
            {
                "name": "Demographic Analysis",
                "query": "Show patient distribution by state and condition",
                "expected_verdict": "ALLOW",
                "should_execute_sql": True
            }
        ]
        
        results = []
        
        try:
            # Initialize coordinator
            coordinator = AgentCoordinator(enable_sql_execution=True)
            
            # Check system readiness
            status = coordinator.get_system_status()
            print(f"System Ready: {'✅' if status['system_ready'] else '❌'}")
            
            if not status['system_ready']:
                print("⚠️  System not fully ready. Some tests may fail.")
                print("Agent Status:")
                for agent, ready in status["agent_readiness"].items():
                    print(f"  {agent}: {'✅' if ready else '❌'}")
            
            # Run test scenarios
            for i, scenario in enumerate(test_scenarios, 1):
                print(f"\nScenario {i}: {scenario['name']}")
                print(f"Query: {scenario['query']}")
                print("-" * 40)
                
                try:
                    result = coordinator.process_query(scenario['query'])
                    
                    # Analyze result
                    actual_verdict = result.policy_verdict.get('verdict', 'UNKNOWN')
                    test_passed = True
                    issues = []
                    
                    # Check verdict expectation
                    if actual_verdict != scenario['expected_verdict']:
                        test_passed = False
                        issues.append(f"Expected {scenario['expected_verdict']}, got {actual_verdict}")
                    
                    # Check SQL execution expectation
                    has_sql_result = result.execution_result is not None
                    if scenario['should_execute_sql'] and not has_sql_result:
                        issues.append("Expected SQL execution but didn't occur")
                    elif not scenario['should_execute_sql'] and has_sql_result:
                        issues.append("Unexpected SQL execution")
                    
                    # Display results
                    print(f"Verdict: {actual_verdict} {'✅' if actual_verdict == scenario['expected_verdict'] else '❌'}")
                    print(f"Status: {result.status.value}")
                    print(f"Agent Trail: {' → '.join(result.agent_trail) if result.agent_trail else 'None'}")
                    
                    if result.rewritten_query:
                        print(f"Rewritten: {result.rewritten_query[:60]}...")
                    
                    if result.sql_query:
                        print(f"SQL: {result.sql_query[:60]}...")
                    
                    if result.final_result.get("data"):
                        print(f"Data: {len(result.final_result['data'])} rows returned")
                    
                    if result.warnings:
                        print(f"Warnings: {', '.join(result.warnings)}")
                    
                    if result.error:
                        print(f"Error: {result.error}")
                        test_passed = False
                    
                    print(f"Processing Time: {result.processing_time:.2f}s" if result.processing_time else "N/A")
                    print(f"Test Result: {'✅ PASSED' if test_passed else '❌ FAILED'}")
                    
                    if issues:
                        print(f"Issues: {', '.join(issues)}")
                    
                    # Store result
                    results.append({
                        "scenario": scenario['name'],
                        "query": scenario['query'],
                        "expected_verdict": scenario['expected_verdict'],
                        "actual_verdict": actual_verdict,
                        "test_passed": test_passed,
                        "processing_time": result.processing_time,
                        "agent_trail": result.agent_trail,
                        "has_data": bool(result.final_result.get("data")),
                        "issues": issues
                    })
                    
                except Exception as e:
                    print(f"❌ Scenario failed with error: {e}")
                    results.append({
                        "scenario": scenario['name'],
                        "query": scenario['query'],
                        "test_passed": False,
                        "error": str(e)
                    })
        
        except Exception as e:
            print(f"❌ Failed to initialize coordinator: {e}")
            return []
        
        return results
    
    def generate_test_report(self, individual_results: Dict[str, bool], workflow_results: List[Dict[str, Any]]):
        """Generate comprehensive test report."""
        print("\n📊 Phase 3 Test Report")
        print("=" * 60)
        
        # Individual agent results
        print("\n🔧 Individual Agent Tests:")
        total_agents = len(individual_results)
        passed_agents = sum(individual_results.values())
        
        for agent, passed in individual_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {agent.replace('_', ' ').title()}: {status}")
        
        print(f"\nAgent Tests: {passed_agents}/{total_agents} passed")
        
        # Workflow results
        print("\n🔄 Multi-Agent Workflow Tests:")
        total_scenarios = len(workflow_results)
        passed_scenarios = sum(1 for r in workflow_results if r.get('test_passed', False))
        
        for result in workflow_results:
            status = "✅ PASS" if result.get('test_passed', False) else "❌ FAIL"
            print(f"  {result['scenario']}: {status}")
            if result.get('issues'):
                for issue in result['issues']:
                    print(f"    - {issue}")
        
        print(f"\nWorkflow Tests: {passed_scenarios}/{total_scenarios} passed")
        
        # Overall assessment
        overall_score = (passed_agents / total_agents + passed_scenarios / total_scenarios) / 2
        print(f"\n🎯 Overall Phase 3 Score: {overall_score:.1%}")
        
        if overall_score >= 0.8:
            print("🎉 Phase 3 implementation is EXCELLENT!")
        elif overall_score >= 0.6:
            print("✅ Phase 3 implementation is GOOD - minor issues to address")
        elif overall_score >= 0.4:
            print("⚠️  Phase 3 implementation needs IMPROVEMENT")
        else:
            print("❌ Phase 3 implementation has SIGNIFICANT ISSUES")
        
        # Recommendations
        print("\n💡 Recommendations:")
        if not individual_results.get('database', False):
            print("  - Set up PostgreSQL database with patient data")
            print("  - Ensure database credentials are in .env file")
        
        if not individual_results.get('policy_agent', False):
            print("  - Run RAG system build: uv run python scripts/build_rag_system.py")
            print("  - Ensure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")
        
        if passed_scenarios < total_scenarios:
            print("  - Review failed workflow scenarios")
            print("  - Check agent integration and error handling")
        
        return overall_score


def main():
    """Run comprehensive Phase 3 testing."""
    print("🚀 G-SIA Phase 3 Agent Testing")
    print("=" * 60)
    print("Testing SQL Agent, Query Rewriter, and Multi-Agent Coordination")
    
    tester = Phase3Tester()
    
    try:
        # Test individual agents
        individual_results = tester.test_individual_agents()
        
        # Test multi-agent workflow
        workflow_results = tester.test_multi_agent_workflow()
        
        # Generate report
        overall_score = tester.generate_test_report(individual_results, workflow_results)
        
        # Exit with appropriate code
        if overall_score >= 0.6:
            print(f"\n✅ Phase 3 testing completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Phase 3 testing revealed significant issues")
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Testing failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
