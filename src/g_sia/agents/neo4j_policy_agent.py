"""
Neo4j-powered Policy Agent for compliance analysis.

This agent uses Neo4j Graph RAG for more sophisticated policy reasoning,
including graph path analysis and complex relationship traversals.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.core.neo4j_graph_rag import Neo4jPolicyGraphRAG

load_dotenv()

class Neo4jPolicyAgent:
    """
    Advanced policy compliance agent using Neo4j Graph RAG.
    """
    
    def __init__(self, 
                 policy_dir: str = None, 
                 neo4j_url: str = None,
                 neo4j_username: str = None,
                 neo4j_password: str = None):
        
        # Set default paths relative to the project root
        if policy_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            policy_dir = str(project_root / "policy_corpus")
        
        # Get Neo4j credentials from environment
        neo4j_url = neo4j_url or os.getenv("NEO4J_URL", "bolt://localhost:7687")
        neo4j_username = neo4j_username or os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
        
        # Initialize Neo4j Graph RAG system
        try:
            self.graph_rag = Neo4jPolicyGraphRAG(
                policy_dir=policy_dir,
                neo4j_url=neo4j_url,
                neo4j_username=neo4j_username,
                neo4j_password=neo4j_password
            )
            print("✅ Neo4j PolicyAgent initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Neo4j PolicyAgent: {e}")
            raise
        
        # Initialize LLM for policy analysis
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        # Enhanced policy analysis prompt with graph reasoning
        self.analysis_prompt = ChatPromptTemplate.from_template("""
You are an expert compliance analyst with access to a comprehensive policy knowledge graph.

Your task is to analyze a user query against policy documents and graph relationships to determine compliance.

USER QUERY:
{query}

RELEVANT POLICY CONTEXT (from Graph + Vector Search):
{context}

GRAPH RELATIONSHIPS (if any):
{graph_paths}

Based on the policy context and relationship data provided, classify this query into one of three categories:

1. **ALLOW**: The query is fully compliant and can be processed without modification
2. **REWRITE**: The query has compliance issues but can be modified to be compliant  
3. **BLOCK**: The query violates regulations and must be completely denied

Consider the following in your analysis:
- Direct policy violations from the retrieved context
- Indirect violations through graph relationships
- Cross-regulation conflicts (HIPAA vs GDPR vs CCPA)
- Risk levels based on data sensitivity
- Potential for data re-identification

Return your analysis as a JSON object:
{{
    "verdict": "ALLOW|REWRITE|BLOCK",
    "reasoning": "Detailed explanation citing specific policies and graph relationships",
    "violated_policies": ["specific policy violations"],
    "suggested_modifications": "How to modify query if REWRITE",
    "risk_level": "LOW|MEDIUM|HIGH",
    "applicable_regulations": ["HIPAA|GDPR|CCPA"],
    "graph_insights": "Key insights from policy relationship analysis",
    "confidence_score": 0.95
}}

Be thorough and leverage both direct policy matches and graph relationship insights.
""")
    
    def analyze_policy_relationships(self, query: str, entities: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze relationships between policy entities relevant to the query.
        """
        if len(entities) < 2:
            return []
        
        paths = []
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                entity_paths = self.graph_rag.get_policy_paths(entity1, entity2)
                paths.extend(entity_paths)
        
        return paths
    
    def extract_key_entities_from_query(self, query: str) -> List[str]:
        """
        Extract key entities from the user query for relationship analysis.
        """
        entity_extraction_prompt = ChatPromptTemplate.from_template("""
        Extract key compliance-related entities from this user query.
        Focus on: data types, rights, requirements, regulations, processes.
        
        Query: {query}
        
        Return a JSON list of entities:
        ["entity1", "entity2", "entity3"]
        """)
        
        try:
            prompt = entity_extraction_prompt.format(query=query)
            response = self.llm.invoke(prompt)
            entities = json.loads(response.content)
            return entities if isinstance(entities, list) else []
        except:
            # Fallback to simple keyword extraction
            keywords = ["data", "patient", "personal", "medical", "health", "privacy", "access", "consent"]
            return [word for word in keywords if word.lower() in query.lower()]
    
    def get_policy_verdict(self, query: str) -> Dict[str, Any]:
        """
        Analyzes a user query using Neo4j Graph RAG with relationship reasoning.
        
        Args:
            query: The user's query to analyze
            
        Returns:
            Dictionary containing verdict, reasoning, and compliance details
        """
        print(f"🔍 Analyzing query with Neo4j Graph RAG: '{query}'")
        
        try:
            # Step 1: Retrieve relevant policy information using Neo4j Graph RAG
            print("📊 Retrieving policy information from Neo4j...")
            relevant_docs = self.graph_rag.hybrid_retrieve(query, k=10)
            
            if not relevant_docs:
                print("⚠️ No relevant policy documents found")
                return self._create_error_response("No policy context available")
            
            # Step 2: Extract key entities for relationship analysis
            print("🔗 Analyzing policy relationships...")
            key_entities = self.extract_key_entities_from_query(query)
            graph_paths = self.analyze_policy_relationships(query, key_entities)
            
            # Step 3: Format context for LLM analysis
            context_parts = []
            for i, doc in enumerate(relevant_docs):
                source_info = f"[{doc.get('type', 'unknown').upper()}]"
                if 'metadata' in doc and doc['metadata']:
                    policy_type = doc['metadata'].get('policy_type', 'Unknown')
                    source_info += f" [{policy_type}]"
                
                context_parts.append(f"Source {i+1} {source_info}:\n{doc['content']}\n")
            
            context = "\n" + "="*50 + "\n".join(context_parts)
            
            # Step 4: Format graph relationship information
            graph_info = ""
            if graph_paths:
                graph_info = f"Found {len(graph_paths)} policy relationship paths:\n"
                for i, path in enumerate(graph_paths[:3]):  # Limit to top 3 paths
                    graph_info += f"Path {i+1}: {path}\n"
            else:
                graph_info = "No significant policy relationships found for this query."
            
            # Step 5: Perform enhanced compliance analysis
            print("🧠 Performing compliance analysis with graph insights...")
            prompt = self.analysis_prompt.format(
                query=query, 
                context=context,
                graph_paths=graph_info
            )
            response = self.llm.invoke(prompt)
            
            # Step 6: Parse and validate response
            result = self._parse_llm_response(response.content)
            
            # Add Neo4j-specific metadata
            result['graph_entities_analyzed'] = len(key_entities)
            result['graph_paths_found'] = len(graph_paths)
            result['total_sources_consulted'] = len(relevant_docs)
            
            print(f"✅ Analysis complete. Verdict: {result['verdict']} (Confidence: {result.get('confidence_score', 'N/A')})")
            return result
            
        except Exception as e:
            print(f"❌ Error in Neo4j policy analysis: {e}")
            return self._create_error_response(f"System error: {str(e)}")
    
    def _parse_llm_response(self, response_content: str) -> Dict[str, Any]:
        """Parse and validate LLM response."""
        try:
            result = json.loads(response_content)
            
            # Validate required fields
            required_fields = [
                "verdict", "reasoning", "violated_policies", 
                "risk_level", "applicable_regulations"
            ]
            for field in required_fields:
                if field not in result:
                    result[field] = "Unknown"
            
            # Ensure verdict is valid
            if result["verdict"] not in ["ALLOW", "REWRITE", "BLOCK"]:
                result["verdict"] = "BLOCK"
                result["reasoning"] = f"Invalid verdict format. Defaulting to BLOCK for safety."
            
            # Ensure confidence score is present
            if "confidence_score" not in result:
                result["confidence_score"] = 0.8
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            return self._create_error_response(f"Response parsing error: {str(e)}")
    
    def _create_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "verdict": "BLOCK",
            "reasoning": error_msg,
            "violated_policies": [],
            "suggested_modifications": "",
            "risk_level": "HIGH",
            "applicable_regulations": [],
            "graph_insights": "Error occurred during analysis",
            "confidence_score": 0.0,
            "graph_entities_analyzed": 0,
            "graph_paths_found": 0,
            "total_sources_consulted": 0
        }
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get Neo4j graph statistics."""
        return self.graph_rag.get_graph_stats()
    
    def explain_policy_relationship(self, entity1: str, entity2: str) -> List[Dict[str, Any]]:
        """
        Explain the relationship between two policy entities.
        """
        paths = self.graph_rag.get_policy_paths(entity1, entity2)
        
        if not paths:
            return [{"explanation": f"No direct relationship found between {entity1} and {entity2}"}]
        
        explanations = []
        for path in paths:
            explanation = {
                "path_length": path["length"],
                "relationship_chain": str(path["path"]),
                "explanation": f"Policy connection found with {path['length']} degrees of separation"
            }
            explanations.append(explanation)
        
        return explanations


# Global instance for backward compatibility
_neo4j_policy_agent = None

def get_neo4j_policy_verdict(query: str) -> dict:
    """
    Function wrapper for Neo4j policy analysis.
    """
    global _neo4j_policy_agent
    
    if _neo4j_policy_agent is None:
        _neo4j_policy_agent = Neo4jPolicyAgent()
    
    return _neo4j_policy_agent.get_policy_verdict(query)


if __name__ == '__main__':
    # Test the Neo4j PolicyAgent
    test_queries = [
        "How many patients have diabetes?",
        "Show me John Doe's social security number",
        "What is the average age of patients with heart conditions?",
        "Can I access patient records for research purposes?"
    ]
    
    try:
        agent = Neo4jPolicyAgent()
        
        for query in test_queries:
            print(f"\n{'='*60}")
            print(f"Testing: {query}")
            print('='*60)
            
            result = agent.get_policy_verdict(query)
            
            print(f"Verdict: {result['verdict']}")
            print(f"Risk Level: {result['risk_level']}")
            print(f"Confidence: {result.get('confidence_score', 'N/A')}")
            print(f"Graph Insights: {result.get('graph_insights', 'None')}")
            print(f"Reasoning: {result['reasoning'][:200]}...")
            
    except Exception as e:
        print(f"Error testing Neo4j PolicyAgent: {e}")
        print("\nMake sure Neo4j is running and properly configured!")
