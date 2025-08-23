
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.core.graph_rag import PolicyGraphRAG

load_dotenv()

class PolicyAgent:
    """
    Policy compliance agent that uses Graph RAG to analyze queries.
    """
    
    def __init__(self, policy_dir: str = None, data_dir: str = None):
        # Set default paths relative to the project root
        if policy_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            policy_dir = str(project_root / "policy_corpus")
        
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            data_dir = str(project_root / "data")
        
        # Initialize Graph RAG system
        self.graph_rag = PolicyGraphRAG(policy_dir=policy_dir, data_dir=data_dir)
        
        # Try to load existing graph data
        if not self.graph_rag.load_graph_data():
            print("Warning: No pre-built Graph RAG data found. Please run 'embed_policies.py' first.")
        
        # Initialize LLM for policy analysis
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        # Define the policy analysis prompt
        self.analysis_prompt = ChatPromptTemplate.from_template("""
You are a compliance expert specializing in healthcare data regulations (HIPAA), privacy laws (GDPR), and consumer protection (CCPA).

Your task is to analyze a user query against relevant policy documents and determine compliance.

USER QUERY:
{query}

RELEVANT POLICY CONTEXT:
{context}

Based on the policy context provided, classify this query into one of three categories:

1. **ALLOW**: The query is fully compliant and can be processed without modification
2. **REWRITE**: The query has compliance issues but can be modified to be compliant
3. **BLOCK**: The query violates regulations and must be completely denied

Return your analysis as a JSON object with the following structure:
{{
    "verdict": "ALLOW|REWRITE|BLOCK",
    "reasoning": "Detailed explanation of your decision, citing specific policies",
    "violated_policies": ["list of specific policy violations if any"],
    "suggested_modifications": "If REWRITE, suggest how to modify the query to be compliant",
    "risk_level": "LOW|MEDIUM|HIGH",
    "applicable_regulations": ["HIPAA|GDPR|CCPA that apply to this query"]
}}

Be thorough in your analysis and always err on the side of caution when it comes to data privacy and patient protection.
""")
    
    def get_policy_verdict(self, query: str) -> Dict[str, Any]:
        """
        Analyzes a user query against the policy corpus using Graph RAG.
        
        Args:
            query: The user's query to analyze
            
        Returns:
            Dictionary containing verdict, reasoning, and compliance details
    """
    print(f"Analyzing query: '{query}'")

        try:
            # Step 1: Retrieve relevant policy information using Graph RAG
            print("Retrieving relevant policy information...")
            relevant_docs = self.graph_rag.hybrid_retrieve(query, k=8)
            
            if not relevant_docs:
                print("Warning: No relevant policy documents found")
                return {
                    "verdict": "BLOCK",
                    "reasoning": "Unable to determine compliance due to lack of policy context",
                    "violated_policies": [],
                    "suggested_modifications": "",
                    "risk_level": "HIGH",
                    "applicable_regulations": []
                }
            
            # Step 2: Format context for LLM analysis
            context_parts = []
            for i, doc in enumerate(relevant_docs):
                source_info = ""
                if 'metadata' in doc and doc['metadata']:
                    policy_type = doc['metadata'].get('policy_type', 'Unknown')
                    source_info = f"[{policy_type}]"
                
                context_parts.append(f"Document {i+1} {source_info}:\n{doc['content']}\n")
            
            context = "\n---\n".join(context_parts)
            
            # Step 3: Analyze with LLM
            print("Performing compliance analysis...")
            prompt = self.analysis_prompt.format(query=query, context=context)
            response = self.llm.invoke(prompt)
            
            # Step 4: Parse the response
            try:
                result = json.loads(response.content)
                
                # Validate required fields
                required_fields = ["verdict", "reasoning", "violated_policies", "risk_level", "applicable_regulations"]
                for field in required_fields:
                    if field not in result:
                        result[field] = "Unknown"
                
                # Ensure verdict is valid
                if result["verdict"] not in ["ALLOW", "REWRITE", "BLOCK"]:
                    result["verdict"] = "BLOCK"
                    result["reasoning"] = f"Invalid verdict format. Original: {result.get('verdict', 'None')}"
                
                print(f"Analysis complete. Verdict: {result['verdict']}")
                return result
                
            except json.JSONDecodeError as e:
                print(f"Error parsing LLM response: {e}")
                return {
                    "verdict": "BLOCK",
                    "reasoning": f"Error in policy analysis: {str(e)}",
                    "violated_policies": [],
                    "suggested_modifications": "",
                    "risk_level": "HIGH",
                    "applicable_regulations": []
                }
        
        except Exception as e:
            print(f"Error in policy analysis: {e}")
            return {
                "verdict": "BLOCK",
                "reasoning": f"System error during policy analysis: {str(e)}",
                "violated_policies": [],
                "suggested_modifications": "",
                "risk_level": "HIGH",
                "applicable_regulations": []
            }

# Global instance for backward compatibility
_policy_agent = None

def get_policy_verdict(query: str) -> dict:
    """
    Legacy function wrapper for backward compatibility.
    """
    global _policy_agent
    
    if _policy_agent is None:
        _policy_agent = PolicyAgent()
    
    return _policy_agent.get_policy_verdict(query)


if __name__ == '__main__':
    # Example of how this function would be called
    test_query_1 = "How many patients have diabetes?"
    verdict_1 = get_policy_verdict(test_query_1)
    
    test_query_2 = "Show me the social security number for patient Jane Doe."
    verdict_2 = get_policy_verdict(test_query_2)
    # Expected verdict for query 2 would be "BLOCK" in the final implementation.
