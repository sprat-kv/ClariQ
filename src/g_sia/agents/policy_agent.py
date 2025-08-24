"""
Policy compliance agent using Qdrant-based RAG system.

This module implements a sophisticated policy agent that analyzes user queries
against GDPR, HIPAA, and other compliance documents using content-aware retrieval.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.core.qdrant_vector_store import QdrantPolicyVectorStore
from g_sia.core.document_parser import PolicyDocumentParser, DocumentType
from g_sia.core.content_aware_chunker import ContentAwareChunker

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolicyAgent:
    """
    Advanced policy compliance agent using Qdrant vector store for retrieval.
    """
    
    def __init__(
        self,
        collection_name: str = "policy_documents",
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.0
    ):
        """
        Initialize the policy agent.
        
        Args:
            collection_name: Qdrant collection name
            qdrant_url: Qdrant server URL
            qdrant_api_key: API key for Qdrant Cloud (optional)
            model: OpenAI model to use
            temperature: LLM temperature setting
        """
        self.collection_name = collection_name
        
        # Initialize vector store
        self.vector_store = QdrantPolicyVectorStore(
            collection_name=collection_name,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key
        )
        
        # Initialize document processing components
        self.document_parser = PolicyDocumentParser()
        self.chunker = ContentAwareChunker(
            target_chunk_size=800,
            max_chunk_size=1200,
            overlap_size=100
        )
        
        # Initialize LLM
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
        # Policy analysis prompt
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

Consider these key factors in your analysis:
- Does the query request personally identifiable information (PII)?
- Are there legitimate business or healthcare reasons for the request?
- Can the query be answered with aggregated or de-identified data?
- Does the query comply with minimum necessary standards?
- Are there specific consent or authorization requirements?

Return your analysis as a JSON object with the following structure:
{{
    "verdict": "ALLOW|REWRITE|BLOCK",
    "reasoning": "Detailed explanation of your decision, citing specific policies and sections",
    "violated_policies": ["list of specific policy violations with section references"],
    "suggested_modifications": "If REWRITE, suggest how to modify the query to be compliant",
    "risk_level": "LOW|MEDIUM|HIGH",
    "applicable_regulations": ["HIPAA|GDPR|CCPA sections that apply"],
    "compliance_requirements": ["specific requirements that must be met"],
    "confidence_score": 0.95
}}

Be thorough in your analysis and always err on the side of caution when it comes to data privacy and patient protection.
""")
    
    def initialize_vector_store(
        self,
        policy_documents_dir: str = "policy_corpus/output",
        clear_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Initialize the vector store with policy documents.
        
        Args:
            policy_documents_dir: Directory containing policy documents
            clear_existing: Whether to clear existing data
            
        Returns:
            Processing results dictionary
        """
        policy_dir = Path(policy_documents_dir)
        if not policy_dir.exists():
            raise ValueError(f"Policy documents directory not found: {policy_dir}")
        
        # Find policy document files
        policy_files = []
        for doc_dir in policy_dir.iterdir():
            if doc_dir.is_dir():
                md_files = list(doc_dir.glob("*.md"))
                policy_files.extend([str(f) for f in md_files])
        
        if not policy_files:
            raise ValueError(f"No policy documents found in {policy_dir}")
        
        logger.info(f"Found {len(policy_files)} policy documents to process")
        
        # Clear existing data if requested
        if clear_existing:
            logger.info("Clearing existing vector store...")
            self.vector_store.clear_collection()
        
        # Process documents
        all_chunks = []
        total_sections = 0
        
        for file_path in policy_files:
            logger.info(f"Processing {Path(file_path).name}...")
            
            # Parse document
            sections = self.document_parser.parse_document(file_path)
            if sections:
                total_sections += len(sections)
                
                # Create chunks
                chunks = self.chunker.chunk_document_sections(sections)
                all_chunks.extend(chunks)
                
                logger.info(f"  → {len(sections)} sections, {len(chunks)} chunks")
            else:
                logger.warning(f"  → No sections extracted from {file_path}")
        
        if not all_chunks:
            raise ValueError("No chunks created from any documents")
        
        # Add chunks to vector store
        logger.info(f"Storing {len(all_chunks)} chunks in vector store...")
        success = self.vector_store.add_chunks(all_chunks)
        
        if not success:
            raise ValueError("Failed to add chunks to vector store")
        
        result = {
            "success": True,
            "documents_count": len(policy_files),
            "sections_count": total_sections,
            "chunks_count": len(all_chunks),
            "file_paths": policy_files
        }
        
        logger.info(f"Successfully processed {len(all_chunks)} chunks from {len(policy_files)} documents")
        return result
    
    def is_ready(self) -> bool:
        """
        Check if the policy agent is ready for queries.
        
        Returns:
            True if vector store is populated and ready
        """
        try:
            collection_info = self.vector_store.get_collection_info()
            return collection_info.get("points_count", 0) > 0
        except Exception as e:
            logger.error(f"Error checking readiness: {e}")
            return False
    
    def retrieve_relevant_policies(
        self,
        query: str,
        limit: int = 8,
        score_threshold: float = 0.7,
        document_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant policy documents for a query.
        
        Args:
            query: User query
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            document_types: Optional filter by document types
            
        Returns:
            List of relevant policy chunks
        """
        try:
            # Prepare filter conditions
            filter_conditions = {}
            if document_types:
                filter_conditions["document_type"] = document_types
            
            # Search for relevant policies
            results = self.vector_store.search_similar(
                query=query,
                limit=limit,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions if filter_conditions else None
            )
            
            logger.debug(f"Retrieved {len(results)} relevant policy chunks")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving policies: {e}")
            return []
    
    def get_policy_verdict(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze a user query against policy documents and return compliance verdict.
        
        Args:
            query: User query to analyze
            **kwargs: Additional parameters for retrieval
            
        Returns:
            Compliance verdict with detailed analysis
        """
        logger.info(f"Analyzing query: '{query}'")
        
        try:
            # Check if agent is ready
            if not self.is_ready():
                return {
                    "verdict": "BLOCK",
                    "reasoning": "Policy agent not initialized. Please initialize with policy documents first.",
                    "violated_policies": [],
                    "suggested_modifications": "",
                    "risk_level": "HIGH",
                    "applicable_regulations": [],
                    "compliance_requirements": [],
                    "confidence_score": 1.0
                }
            
            # Retrieve relevant policy information
            logger.debug("Retrieving relevant policy information...")
            relevant_docs = self.retrieve_relevant_policies(query, **kwargs)
            
            if not relevant_docs:
                logger.warning("No relevant policy documents found")
                return {
                    "verdict": "BLOCK",
                    "reasoning": "Unable to determine compliance due to lack of relevant policy context",
                    "violated_policies": [],
                    "suggested_modifications": "",
                    "risk_level": "HIGH",
                    "applicable_regulations": [],
                    "compliance_requirements": [],
                    "confidence_score": 0.5
                }
            
            # Format context for LLM analysis
            context_parts = []
            for i, doc in enumerate(relevant_docs):
                metadata = doc.get('metadata', {})
                
                # Create source information
                source_info = []
                if metadata.get('document_type'):
                    source_info.append(metadata['document_type'].upper())
                if metadata.get('section_type') and metadata.get('section_id'):
                    source_info.append(f"{metadata['section_type']} {metadata['section_id']}")
                if metadata.get('section_title'):
                    source_info.append(metadata['section_title'])
                
                source_str = " | ".join(source_info) if source_info else f"Document {i+1}"
                
                context_parts.append(
                    f"[{source_str}] (Relevance: {doc.get('score', 0):.3f})\n"
                    f"{doc.get('content', '')}\n"
                )
            
            context = "\n" + "="*80 + "\n".join(context_parts)
            
            # Analyze with LLM
            logger.debug("Performing compliance analysis...")
            prompt = self.analysis_prompt.format(query=query, context=context)
            response = self.llm.invoke(prompt)
            
            # Parse and validate response
            try:
                result = json.loads(response.content)
                
                # Validate and set defaults for required fields
                defaults = {
                    "verdict": "BLOCK",
                    "reasoning": "Unknown",
                    "violated_policies": [],
                    "suggested_modifications": "",
                    "risk_level": "HIGH",
                    "applicable_regulations": [],
                    "compliance_requirements": [],
                    "confidence_score": 0.5
                }
                
                for field, default_value in defaults.items():
                    if field not in result:
                        result[field] = default_value
                
                # Validate verdict
                if result["verdict"] not in ["ALLOW", "REWRITE", "BLOCK"]:
                    result["verdict"] = "BLOCK"
                    result["reasoning"] = f"Invalid verdict format. Defaulting to BLOCK for safety."
                
                # Ensure confidence score is valid
                try:
                    confidence = float(result["confidence_score"])
                    result["confidence_score"] = max(0.0, min(1.0, confidence))
                except (ValueError, TypeError):
                    result["confidence_score"] = 0.5
                
                logger.info(f"Analysis complete. Verdict: {result['verdict']} (Confidence: {result['confidence_score']:.2f})")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing LLM response: {e}")
                return {
                    "verdict": "BLOCK",
                    "reasoning": f"Error in policy analysis response parsing: {str(e)}",
                    "violated_policies": [],
                    "suggested_modifications": "",
                    "risk_level": "HIGH",
                    "applicable_regulations": [],
                    "compliance_requirements": [],
                    "confidence_score": 0.0
                }
        
        except Exception as e:
            logger.error(f"Error in policy analysis: {e}")
            return {
                "verdict": "BLOCK",
                "reasoning": f"System error during policy analysis: {str(e)}",
                "violated_policies": [],
                "suggested_modifications": "",
                "risk_level": "HIGH",
                "applicable_regulations": [],
                "compliance_requirements": [],
                "confidence_score": 0.0
            }
    
    def analyze_query_by_regulation(
        self,
        query: str,
        regulation: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze query against a specific regulation.
        
        Args:
            query: User query
            regulation: Regulation to check against ('gdpr', 'hipaa', 'ccpa')
            limit: Number of relevant chunks to retrieve
            
        Returns:
            Regulation-specific analysis
        """
        return self.get_policy_verdict(
            query,
            document_types=[regulation.lower()],
            limit=limit
        )
    
    def get_vector_store_info(self) -> Dict[str, Any]:
        """Get information about the underlying vector store."""
        return self.vector_store.get_collection_info()


# Global instance for backward compatibility
_policy_agent = None

def get_policy_verdict(query: str) -> Dict[str, Any]:
    """
    Legacy function wrapper for backward compatibility.
    
    Args:
        query: User query to analyze
        
    Returns:
        Policy verdict dictionary
    """
    global _policy_agent
    
    if _policy_agent is None:
        _policy_agent = PolicyAgent()
    
    return _policy_agent.get_policy_verdict(query)


def main():
    """Example usage of the policy agent."""
    # Initialize policy agent
    agent = PolicyAgent(collection_name="demo_policy_agent")
    
    # Initialize vector store (this would normally be done once)
    print("Initializing vector store with policy documents...")
    try:
        result = agent.initialize_vector_store(clear_existing=True)
        
        print("✅ Vector store initialized successfully!")
        print(f"📊 Processing Summary:")
        print(f"  • Documents processed: {result['documents_count']}")
        print(f"  • Sections extracted: {result['sections_count']}")
        print(f"  • Chunks created: {result['chunks_count']}")
        
        # Test queries
        test_queries = [
            "How many patients have diabetes?",
            "Show me the social security number for patient John Doe",
            "What are the average treatment costs by condition?",
            "Can I access patient email addresses for marketing purposes?"
        ]
        
        for query in test_queries:
            print(f"\n" + "="*60)
            print(f"Query: {query}")
            print("-"*60)
            
            verdict = agent.get_policy_verdict(query)
            
            print(f"Verdict: {verdict['verdict']}")
            print(f"Risk Level: {verdict['risk_level']}")
            print(f"Confidence: {verdict['confidence_score']:.2f}")
            print(f"Reasoning: {verdict['reasoning']}")
            
            if verdict['suggested_modifications']:
                print(f"Suggested Modifications: {verdict['suggested_modifications']}")
    
    except Exception as e:
        print(f"❌ Initialization failed: {e}")


if __name__ == "__main__":
    main()