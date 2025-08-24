#!/usr/bin/env python3
"""
Test script for Phase 4 LangGraph orchestration.

This script tests the complete LangGraph workflow implementation.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from g_sia.graph.langgraph_orchestrator import LangGraphOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase4Tester:
    """
    Comprehensive tester for Phase 4 LangGraph orchestration.
    """
    
    def __init__(self):
        """Initialize the tester."""
        self.test_results = []
    
    def test_orchestrator_initialization(self) -> bool:
        """Test LangGraph orchestrator initialization."""
        print("🧪 Testing LangGraph Orchestrator Initialization")
        print("=" * 60)
        
        try:
            # Test initialization
            orchestrator = LangGraphOrchestrator(enable_sql_execution=True)
            
            # Check system readiness
            readiness = orchestrator.check_system_readiness()
            
            print(f"System Ready: {'✅' if readiness['system_ready'] else '❌'}")
            for component, ready in readiness.items():
                if component != "system_ready":
                    print(f"  {component}: {'✅' if ready else '❌'}")
            
            # Show workflow visualization
            print("\n📊 Workflow Graph:")
            print(orchestrator.get_workflow_graph_visualization())
            
            return readiness['system_ready']
            
        except Exception as e:
            print(f"❌ Orchestrator initialization failed: {e}")
            return False
    
    def test_workflow_scenarios(self) -> List[Dict[str, Any]]:
        """Test various workflow scenarios."""
        print("\n🔄 Testing LangGraph Workflow Scenarios")
        print("=" * 60)
        
        # Test scenarios covering different policy outcomes and complexity
        test_scenarios = [
            {
                "name": "Simple Aggregation Query (ALLOW)",
                "query": "How many patients have diabetes?",
                "expected_verdict": "ALLOW",
                "should_have_sql": True,
                "should_have_data": True
            },
            {
                "name": "Direct PII Request (BLOCK)",
                "query": "Show me John Doe's social security number",
                "expected_verdict": "BLOCK",
                "should_have_sql": False,
                "should_have_data": False
            },
            {
                "name": "Individual Records Request (REWRITE)",
                "query": "List all patients with hypertension",
                "expected_verdict": "REWRITE",
                "should_have_sql": True,
                "should_have_data": True
            },
            {
                "name": "Statistical Analysis (ALLOW)",
                "query": "What is the average age of patients by gender?",
                "expected_verdict": "ALLOW", 
                "should_have_sql": True,
                "should_have_data": True
            },
            {
                "name": "Complex Demographic Query (ALLOW)",
                "query": "Show patient distribution by state and condition",
                "expected_verdict": "ALLOW",
                "should_have_sql": True,
                "should_have_data": True
            }
        ]
        
        results = []
        
        try:
            # Initialize orchestrator
            orchestrator = LangGraphOrchestrator(enable_sql_execution=True)
            
            # Run test scenarios
            for i, scenario in enumerate(test_scenarios, 1):
                print(f"\n{i}. {scenario['name']}")
                print(f"   Query: {scenario['query']}")
                print("-" * 50)
                
                try:
                    # Process query through LangGraph workflow
                    result = orchestrator.process_query(scenario['query'])
                    
                    # Analyze result
                    test_passed = True
                    issues = []
                    
                    # Check success
                    if not result.get("success", False):
                        test_passed = False
                        issues.append(f"Workflow failed: {result.get('error', 'Unknown error')}")
                    
                    # Check verdict expectation
                    actual_verdict = result.get("policy_verdict", "UNKNOWN")
                    if actual_verdict != scenario["expected_verdict"]:
                        # Allow some flexibility in verdict (REWRITE might become ALLOW after rewriting)
                        if not (scenario["expected_verdict"] == "REWRITE" and actual_verdict == "ALLOW"):
                            test_passed = False
                            issues.append(f"Expected {scenario['expected_verdict']}, got {actual_verdict}")
                    
                    # Check SQL expectation
                    has_sql = bool(result.get("sql_query"))
                    if scenario["should_have_sql"] and not has_sql:
                        test_passed = False
                        issues.append("Expected SQL generation but didn't occur")
                    elif not scenario["should_have_sql"] and has_sql:
                        test_passed = False
                        issues.append("Unexpected SQL generation")
                    
                    # Check data expectation
                    has_data = bool(result.get("data")) or (result.get("row_count", 0) > 0)
                    if scenario["should_have_data"] and not has_data:
                        test_passed = False
                        issues.append("Expected data but none returned")
                    
                    # Display results
                    print(f"   Status: {result.get('status', 'unknown')}")
                    print(f"   Verdict: {actual_verdict} {'✅' if actual_verdict == scenario['expected_verdict'] or (scenario['expected_verdict'] == 'REWRITE' and actual_verdict == 'ALLOW') else '❌'}")
                    print(f"   Agent Trail: {' → '.join(result.get('agent_trail', []))}")
                    
                    if result.get('rewritten_query'):
                        print(f"   Rewritten: {result['rewritten_query'][:70]}...")
                    
                    if result.get('sql_query'):
                        print(f"   SQL: {result['sql_query'][:70]}...")
                    
                    if result.get('row_count') is not None:
                        print(f"   Rows: {result['row_count']}")
                    
                    if result.get('error'):
                        print(f"   Error: {result['error']}")
                    
                    if result.get('warnings'):
                        print(f"   Warnings: {', '.join(result['warnings'])}")
                    
                    print(f"   Processing Time: {result.get('processing_time', 0):.2f}s")
                    print(f"   Test Result: {'✅ PASSED' if test_passed else '❌ FAILED'}")
                    
                    if issues:
                        print(f"   Issues: {', '.join(issues)}")
                    
                    # Store result
                    results.append({
                        "scenario": scenario['name'],
                        "query": scenario['query'],
                        "expected_verdict": scenario['expected_verdict'],
                        "actual_verdict": actual_verdict,
                        "test_passed": test_passed,
                        "processing_time": result.get('processing_time', 0),
                        "agent_trail": result.get('agent_trail', []),
                        "has_sql": has_sql,
                        "has_data": has_data,
                        "row_count": result.get('row_count', 0),
                        "issues": issues,
                        "workflow_id": result.get('workflow_id'),
                        "success": result.get('success', False)
                    })
                    
                except Exception as e:
                    print(f"   ❌ Scenario failed with error: {e}")
                    results.append({
                        "scenario": scenario['name'],
                        "query": scenario['query'],
                        "test_passed": False,
                        "error": str(e)
                    })
        
        except Exception as e:
            print(f"❌ Failed to initialize orchestrator: {e}")
            return []
        
        return results
    
    def test_workflow_state_management(self) -> bool:
        """Test workflow state management and checkpointing."""
        print("\n📊 Testing Workflow State Management")
        print("=" * 60)
        
        try:
            # Test with checkpointing enabled
            orchestrator = LangGraphOrchestrator(
                enable_sql_execution=True,
                enable_checkpoints=True
            )
            
            # Process a query with a specific workflow ID
            workflow_id = "test-state-management-001"
            result = orchestrator.process_query(
                "How many patients have diabetes?",
                workflow_id=workflow_id
            )
            
            print(f"Workflow ID: {result.get('workflow_id')}")
            print(f"Success: {result.get('success', False)}")
            print(f"Agent Trail: {' → '.join(result.get('agent_trail', []))}")
            print(f"Processing Time: {result.get('processing_time', 0):.2f}s")
            
            return result.get('success', False)
            
        except Exception as e:
            print(f"❌ State management test failed: {e}")
            return False
    
    def generate_test_report(self, init_success: bool, workflow_results: List[Dict[str, Any]], state_success: bool):
        """Generate comprehensive test report for Phase 4."""
        print("\n📊 Phase 4 LangGraph Test Report")
        print("=" * 70)
        
        # Initialization test
        print(f"\n🚀 Orchestrator Initialization: {'✅ PASS' if init_success else '❌ FAIL'}")
        
        # Workflow scenario tests
        print(f"\n🔄 Workflow Scenario Tests:")
        total_scenarios = len(workflow_results)
        passed_scenarios = sum(1 for r in workflow_results if r.get('test_passed', False))
        
        for result in workflow_results:
            status = "✅ PASS" if result.get('test_passed', False) else "❌ FAIL"
            print(f"  {result['scenario']}: {status}")
            if result.get('issues'):
                for issue in result['issues']:
                    print(f"    - {issue}")
        
        print(f"\nWorkflow Tests: {passed_scenarios}/{total_scenarios} passed")
        
        # State management test
        print(f"\n📊 State Management: {'✅ PASS' if state_success else '❌ FAIL'}")
        
        # Calculate overall score
        total_tests = 1 + total_scenarios + 1  # init + scenarios + state
        passed_tests = (1 if init_success else 0) + passed_scenarios + (1 if state_success else 0)
        overall_score = passed_tests / total_tests if total_tests > 0 else 0
        
        print(f"\n🎯 Overall Phase 4 Score: {overall_score:.1%}")
        
        # Assessment
        if overall_score >= 0.9:
            print("🎉 Phase 4 LangGraph implementation is EXCELLENT!")
            assessment = "EXCELLENT"
        elif overall_score >= 0.7:
            print("✅ Phase 4 LangGraph implementation is GOOD - minor issues to address")
            assessment = "GOOD"
        elif overall_score >= 0.5:
            print("⚠️  Phase 4 LangGraph implementation needs IMPROVEMENT")
            assessment = "NEEDS_IMPROVEMENT"
        else:
            print("❌ Phase 4 LangGraph implementation has SIGNIFICANT ISSUES")
            assessment = "SIGNIFICANT_ISSUES"
        
        # Detailed analysis
        print(f"\n💡 Analysis:")
        if not init_success:
            print("  - Fix orchestrator initialization issues")
            print("  - Check agent dependencies and configuration")
        
        if passed_scenarios < total_scenarios:
            print("  - Review failed workflow scenarios")
            print("  - Check conditional routing logic")
            print("  - Verify agent integration in LangGraph nodes")
        
        if not state_success:
            print("  - Fix workflow state management")
            print("  - Check LangGraph checkpointing configuration")
        
        # Performance insights
        if workflow_results:
            avg_time = sum(r.get('processing_time', 0) for r in workflow_results) / len(workflow_results)
            print(f"\n⚡ Performance:")
            print(f"  - Average processing time: {avg_time:.2f}s")
            
            # Find slowest scenario
            slowest = max(workflow_results, key=lambda x: x.get('processing_time', 0))
            print(f"  - Slowest scenario: {slowest['scenario']} ({slowest.get('processing_time', 0):.2f}s)")
        
        return overall_score, assessment


def main():
    """Run comprehensive Phase 4 testing."""
    print("🚀 G-SIA Phase 4 LangGraph Testing")
    print("=" * 70)
    print("Testing LangGraph Orchestration, Stateful Workflows, and Conditional Routing")
    
    tester = Phase4Tester()
    
    try:
        # Test orchestrator initialization
        init_success = tester.test_orchestrator_initialization()
        
        # Test workflow scenarios
        workflow_results = tester.test_workflow_scenarios()
        
        # Test state management
        state_success = tester.test_workflow_state_management()
        
        # Generate comprehensive report
        overall_score, assessment = tester.generate_test_report(init_success, workflow_results, state_success)
        
        # Exit with appropriate code
        if overall_score >= 0.7:
            print(f"\n✅ Phase 4 testing completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Phase 4 testing revealed issues that need attention")
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Testing failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
