"""
Query Rewriter Agent for G-SIA that modifies non-compliant queries.

This agent takes queries marked as 'REWRITE' by the Policy Agent and modifies 
them to be compliant while preserving the user's intent as much as possible.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryRewriter:
    """
    Query Rewriter Agent that modifies non-compliant queries to be compliant.
    """
    
    def __init__(
        self,
        model: str = "gpt-5-mini",
        temperature: float = 0.1
    ):
        """
        Initialize Query Rewriter.
        
        Args:
            model: OpenAI model to use
            temperature: LLM temperature setting (slightly higher for creativity)
        """
        self.model = model
        self.temperature = temperature
        
        # Initialize LLM
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
        # Define rewriting strategies
        self.rewrite_strategies = {
            "remove_pii": "Remove or replace personally identifiable information",
            "add_aggregation": "Convert individual record requests to aggregated statistics",
            "add_anonymization": "Add anonymization or de-identification requirements",
            "limit_scope": "Limit the scope of data access to compliant subsets",
            "add_consent_check": "Add requirements for explicit consent verification",
            "temporal_restriction": "Add time-based restrictions to limit data exposure"
        }
        
        # Common PII patterns to identify and replace
        self.pii_patterns = {
            "names": ["name", "first", "last", "full name", "patient name"],
            "identifiers": ["ssn", "social security", "id number", "patient id", "medical record number"],
            "contact": ["address", "phone", "email", "contact information"],
            "demographics": ["date of birth", "birthdate", "age", "gender", "race", "ethnicity"]
        }
        
        # Rewriting prompt template
        self.rewrite_prompt = ChatPromptTemplate.from_template("""
You are a healthcare data compliance expert specializing in query rewriting for HIPAA, GDPR, and CCPA compliance.

Your task is to rewrite a user query that has been flagged as non-compliant to make it compliant while preserving the user's analytical intent as much as possible.

ORIGINAL QUERY: {original_query}

POLICY VIOLATIONS: {violations}

COMPLIANCE REQUIREMENTS: {requirements}

REWRITING GUIDELINES:
1. **Remove PII**: Replace requests for names, SSNs, addresses, etc. with aggregate statistics
2. **Add Aggregation**: Convert individual record requests to counts, averages, or summaries
3. **Anonymization**: Ensure no individual can be identified from the results
4. **Minimum Necessary**: Only request data that's necessary to answer the analytical question
5. **Statistical Thresholds**: Ensure result sets are large enough to prevent re-identification
6. **Time Restrictions**: Add appropriate time boundaries if needed

REWRITING STRATEGIES:
- Instead of "Show me patient John Doe's records" → "Show me aggregated statistics for patients with similar conditions"
- Instead of "List all patients with diabetes" → "How many patients have diabetes?"
- Instead of "Patient names and addresses" → "How many patients are there by state?"
- Instead of "Individual medication history" → "What are the most common medications prescribed?"

KEEP REWRITTEN QUERIES SIMPLE:
- Focus on basic counts and statistics
- Avoid complex age grouping or multi-dimensional analysis
- Use simple aggregations that are easy to implement in SQL
- Prefer single-table queries over complex JOINs

OUTPUT FORMAT:
Return a JSON object with the following structure:
{{
    "rewritten_query": "The compliant version of the query",
    "rewrite_strategy": "Primary strategy used (e.g., 'add_aggregation', 'remove_pii')",
    "changes_made": ["List of specific changes made"],
    "compliance_rationale": "Explanation of how the rewritten query addresses compliance issues",
    "data_utility_preserved": "Explanation of how the analytical value is maintained",
    "additional_safeguards": ["Any additional safeguards recommended"],
    "confidence_score": 0.95
}}

Ensure the rewritten query:
- Maintains the analytical intent of the original question
- Provides useful insights without compromising privacy
- Follows healthcare data best practices
- Is specific enough to be actionable

Generate the rewritten query now:
""")
    
    def identify_violations(self, original_query: str, policy_violations: List[str]) -> Dict[str, List[str]]:
        """
        Identify specific types of violations in the query.
        
        Args:
            original_query: Original user query
            policy_violations: List of policy violations from Policy Agent
            
        Returns:
            Categorized violations
        """
        categorized = {
            "pii_requests": [],
            "individual_records": [],
            "insufficient_aggregation": [],
            "consent_issues": [],
            "scope_too_broad": []
        }
        
        query_lower = original_query.lower()
        
        # Check for PII patterns
        for category, patterns in self.pii_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    categorized["pii_requests"].append(f"Request for {pattern}")
        
        # Check for individual record requests
        individual_indicators = ["show me", "list", "give me", "patient", "specific", "individual"]
        if any(indicator in query_lower for indicator in individual_indicators):
            categorized["individual_records"].append("Request for individual records")
        
        # Check for aggregation needs
        aggregation_indicators = ["count", "average", "total", "sum", "statistics", "distribution"]
        if not any(indicator in query_lower for indicator in aggregation_indicators):
            categorized["insufficient_aggregation"].append("Query lacks aggregation")
        
        return categorized
    
    def suggest_rewrite_strategy(self, violations: Dict[str, List[str]]) -> str:
        """
        Suggest the best rewriting strategy based on violations.
        
        Args:
            violations: Categorized violations
            
        Returns:
            Recommended strategy
        """
        if violations["pii_requests"]:
            return "remove_pii"
        elif violations["individual_records"]:
            return "add_aggregation"
        elif violations["insufficient_aggregation"]:
            return "add_aggregation"
        elif violations["scope_too_broad"]:
            return "limit_scope"
        else:
            return "add_anonymization"
    
    def rewrite_query(
        self,
        original_query: str,
        policy_violations: List[str],
        compliance_requirements: List[str],
        suggested_modifications: str = ""
    ) -> Dict[str, Any]:
        """
        Rewrite a non-compliant query to make it compliant.
        
        Args:
            original_query: Original user query
            policy_violations: List of policy violations
            compliance_requirements: List of compliance requirements
            suggested_modifications: Optional suggestions from Policy Agent
            
        Returns:
            Rewriting result with new query and metadata
        """
        try:
            logger.info(f"Rewriting query: '{original_query}'")
            
            # Identify violation patterns
            violations = self.identify_violations(original_query, policy_violations)
            
            # Suggest strategy
            strategy = self.suggest_rewrite_strategy(violations)
            
            # Format requirements for prompt
            violations_text = "; ".join(policy_violations) if policy_violations else "General compliance issues"
            requirements_text = "; ".join(compliance_requirements) if compliance_requirements else "HIPAA, GDPR, CCPA compliance"
            
            # Add suggested modifications if provided
            if suggested_modifications:
                requirements_text += f"; Suggested: {suggested_modifications}"
            
            # Generate rewritten query
            prompt = self.rewrite_prompt.format(
                original_query=original_query,
                violations=violations_text,
                requirements=requirements_text
            )
            
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                required_fields = [
                    "rewritten_query", "rewrite_strategy", "changes_made",
                    "compliance_rationale", "data_utility_preserved"
                ]
                
                for field in required_fields:
                    if field not in result:
                        result[field] = f"Not specified for {field}"
                
                # Ensure confidence score is valid
                if "confidence_score" not in result or not isinstance(result["confidence_score"], (int, float)):
                    result["confidence_score"] = 0.8
                
                result["confidence_score"] = max(0.0, min(1.0, result["confidence_score"]))
                
                # Add metadata
                result.update({
                    "success": True,
                    "original_query": original_query,
                    "violations_identified": violations,
                    "recommended_strategy": strategy,
                    "model_used": self.model
                })
                
                logger.info(f"Query rewritten successfully. Strategy: {result['rewrite_strategy']}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse rewriter response as JSON: {e}")
                
                # Fallback: extract rewritten query from response
                lines = response.content.split('\n')
                rewritten_query = None
                
                for line in lines:
                    if line.strip().startswith('"rewritten_query"'):
                        # Try to extract the query
                        try:
                            rewritten_query = line.split(':', 1)[1].strip().strip('"').strip(',')
                        except:
                            pass
                
                if not rewritten_query:
                    rewritten_query = f"Please provide aggregated statistics instead of: {original_query}"
                
                return {
                    "success": True,
                    "original_query": original_query,
                    "rewritten_query": rewritten_query,
                    "rewrite_strategy": strategy,
                    "changes_made": ["Automated compliance rewrite"],
                    "compliance_rationale": "Query rewritten to ensure compliance",
                    "data_utility_preserved": "Analytical intent maintained through aggregation",
                    "confidence_score": 0.6,
                    "violations_identified": violations,
                    "parsing_error": str(e)
                }
                
        except Exception as e:
            logger.error(f"Failed to rewrite query: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_query": original_query,
                "rewritten_query": None
            }
    
    def validate_rewrite(self, original_query: str, rewritten_query: str) -> Dict[str, Any]:
        """
        Validate that the rewritten query is actually more compliant.
        
        Args:
            original_query: Original query
            rewritten_query: Rewritten query
            
        Returns:
            Validation results
        """
        validation = {
            "is_improved": False,
            "improvements": [],
            "remaining_concerns": [],
            "confidence": 0.0
        }
        
        original_lower = original_query.lower()
        rewritten_lower = rewritten_query.lower()
        
        # Check for PII removal
        pii_terms = ["name", "ssn", "address", "phone", "email"]
        for term in pii_terms:
            if term in original_lower and term not in rewritten_lower:
                validation["improvements"].append(f"Removed {term} reference")
        
        # Check for aggregation addition
        agg_terms = ["count", "average", "total", "statistics", "distribution", "summary"]
        if not any(term in original_lower for term in agg_terms) and any(term in rewritten_lower for term in agg_terms):
            validation["improvements"].append("Added aggregation")
        
        # Check for individual record requests
        individual_terms = ["show me", "list", "give me specific"]
        if any(term in original_lower for term in individual_terms) and not any(term in rewritten_lower for term in individual_terms):
            validation["improvements"].append("Removed individual record request")
        
        # Calculate confidence based on improvements
        validation["confidence"] = min(1.0, len(validation["improvements"]) * 0.3)
        validation["is_improved"] = len(validation["improvements"]) > 0
        
        return validation
    
    def get_rewrite_suggestions(self, query_type: str) -> List[str]:
        """
        Get general rewrite suggestions for common query types.
        
        Args:
            query_type: Type of query (e.g., 'patient_lookup', 'demographics', 'clinical')
            
        Returns:
            List of rewrite suggestions
        """
        suggestions = {
            "patient_lookup": [
                "Convert to aggregated patient statistics",
                "Use demographic summaries instead of individual records",
                "Focus on population-level insights"
            ],
            "demographics": [
                "Use age ranges instead of specific ages",
                "Aggregate by geographic regions instead of specific addresses",
                "Group by categories rather than individual values"
            ],
            "clinical": [
                "Focus on condition prevalence rather than individual cases",
                "Use treatment outcome statistics",
                "Analyze trends rather than specific patient journeys"
            ],
            "default": [
                "Add aggregation to prevent individual identification",
                "Remove personally identifiable information",
                "Focus on statistical summaries"
            ]
        }
        
        return suggestions.get(query_type, suggestions["default"])


def main():
    """Test Query Rewriter functionality."""
    try:
        # Initialize Query Rewriter
        rewriter = QueryRewriter()
        
        # Test queries that need rewriting
        test_cases = [
            {
                "query": "Show me John Doe's medical records",
                "violations": ["Request for individual patient records", "Contains patient name"],
                "requirements": ["HIPAA compliance", "Remove PII"]
            },
            {
                "query": "List all patients with diabetes and their addresses",
                "violations": ["Request for PII", "Individual patient data"],
                "requirements": ["Aggregate data only", "No individual identification"]
            },
            {
                "query": "What medications is patient ID 12345 taking?",
                "violations": ["Individual patient lookup", "Specific patient identifier"],
                "requirements": ["Statistical analysis only"]
            }
        ]
        
        print("🔄 Testing Query Rewriter")
        print("=" * 60)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\nTest Case {i}:")
            print(f"Original: {test_case['query']}")
            print(f"Violations: {', '.join(test_case['violations'])}")
            print("-" * 40)
            
            result = rewriter.rewrite_query(
                test_case["query"],
                test_case["violations"],
                test_case["requirements"]
            )
            
            if result["success"]:
                print(f"✅ Rewritten: {result['rewritten_query']}")
                print(f"📋 Strategy: {result['rewrite_strategy']}")
                print(f"🔧 Changes: {', '.join(result['changes_made'])}")
                print(f"📊 Confidence: {result['confidence_score']:.2f}")
                print(f"💡 Rationale: {result['compliance_rationale']}")
                
                # Validate the rewrite
                validation = rewriter.validate_rewrite(test_case["query"], result["rewritten_query"])
                if validation["is_improved"]:
                    print(f"✅ Validation: Improved ({', '.join(validation['improvements'])})")
                else:
                    print("⚠️  Validation: May need further refinement")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    main()
