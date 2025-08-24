#!/usr/bin/env python3
"""
Build and initialize the RAG system for policy documents.

This script sets up the complete RAG pipeline:
1. Parses policy documents (GDPR, HIPAA, CCPA)
2. Creates content-aware chunks
3. Generates embeddings
4. Stores in Qdrant vector database
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from g_sia.agents.policy_agent import PolicyAgent
from g_sia.core.qdrant_vector_store import QdrantPolicyVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_rag_system(
    policy_docs_dir: str = "policy_corpus/output",
    collection_name: str = "policy_documents",
    qdrant_url: str = "http://localhost:6333",
    clear_existing: bool = False
):
    """
    Build the complete RAG system.
    
    Args:
        policy_docs_dir: Directory containing policy documents
        collection_name: Qdrant collection name
        qdrant_url: Qdrant server URL
        clear_existing: Whether to clear existing data
    """
    print("🚀 Building G-SIA Policy RAG System")
    print("=" * 50)
    
    try:
        # Initialize policy agent
        print("📋 Initializing Policy Agent...")
        agent = PolicyAgent(
            collection_name=collection_name,
            qdrant_url=qdrant_url
        )
        
        # Check if Qdrant is accessible
        try:
            vector_store_info = agent.get_vector_store_info()
            print(f"✅ Connected to Qdrant collection: {collection_name}")
        except Exception as e:
            print(f"❌ Cannot connect to Qdrant: {e}")
            print("Please ensure Qdrant is running:")
            print("  Docker: docker run -p 6333:6333 qdrant/qdrant")
            print("  Local: Download from https://qdrant.tech/")
            return False
        
        # Initialize vector store with policy documents
        print(f"📚 Processing policy documents from: {policy_docs_dir}")
        print("This may take several minutes depending on document size...")
        
        result = agent.initialize_vector_store(
            policy_documents_dir=policy_docs_dir,
            clear_existing=clear_existing
        )
        
        print("\n🎉 RAG System Built Successfully!")
        print("=" * 50)
        print(f"📊 Processing Summary:")
        print(f"  • Documents processed: {result.get('documents_count', 0)}")
        print(f"  • Sections extracted: {result.get('sections_count', 0)}")
        print(f"  • Chunks created: {result.get('chunks_count', 0)}")
        
        # Test the system
        print("\n🧪 Testing RAG System...")
        test_queries = [
            "What are the key principles of GDPR?",
            "HIPAA privacy rule requirements",
            "Data subject rights under privacy regulations"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\nTest {i}: {query}")
            try:
                verdict = agent.get_policy_verdict(query)
                print(f"  ✅ Verdict: {verdict['verdict']} (Confidence: {verdict['confidence_score']:.2f})")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        # Show vector store statistics
        vector_info = agent.get_vector_store_info()
        print(f"\n📈 Vector Store Statistics:")
        print(f"  • Collection: {vector_info.get('name', collection_name)}")
        print(f"  • Total points: {vector_info.get('points_count', 0):,}")
        print(f"  • Indexed vectors: {vector_info.get('indexed_vectors_count', 0):,}")
        print(f"  • Status: {vector_info.get('status', 'unknown')}")
        
        print(f"\n✨ RAG system is ready for Phase 3 development!")
        return True
    
    except Exception as e:
        logger.error(f"Error building RAG system: {e}")
        print(f"\n❌ System Error: {e}")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build G-SIA Policy RAG System")
    parser.add_argument(
        "--policy-docs", 
        default="policy_corpus/output",
        help="Directory containing policy documents"
    )
    parser.add_argument(
        "--collection", 
        default="policy_documents",
        help="Qdrant collection name"
    )
    parser.add_argument(
        "--qdrant-url", 
        default="http://localhost:6333",
        help="Qdrant server URL"
    )
    parser.add_argument(
        "--clear", 
        action="store_true",
        help="Clear existing vector data"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if policy documents exist
    policy_dir = Path(args.policy_docs)
    if not policy_dir.exists():
        print(f"❌ Policy documents directory not found: {policy_dir}")
        print("Please ensure the policy documents are in the correct location.")
        sys.exit(1)
    
    # Check for required environment variables
    required_env_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file or environment.")
        sys.exit(1)
    
    # Run the build process
    success = build_rag_system(
        policy_docs_dir=args.policy_docs,
        collection_name=args.collection,
        qdrant_url=args.qdrant_url,
        clear_existing=args.clear
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
