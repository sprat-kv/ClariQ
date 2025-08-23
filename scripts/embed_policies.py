
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from g_sia.core.graph_rag import PolicyGraphRAG

load_dotenv()

def embed_and_store_policies():
    """
    Build Graph RAG system for policy documents.
    
    This implementation uses a hybrid approach:
    1. Extract entities and relationships from policy PDFs to build a knowledge graph
    2. Create vector embeddings for semantic similarity search
    3. Combine graph traversal with vector search for comprehensive retrieval
    """
    print("Starting Graph RAG policy embedding process...")
    
    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    policy_dir = project_root / "policy_corpus"
    data_dir = project_root / "data"
    
    # Check if policy directory exists
    if not policy_dir.exists():
        print(f"Error: Directory '{policy_dir}' not found.")
        return
    
    # Check if we have any policy files
    policy_files = list(policy_dir.glob("*.pdf")) + list(policy_dir.glob("*.md"))
    if not policy_files:
        print(f"Error: No policy files found in '{policy_dir}'")
        return
    
    print(f"Found {len(policy_files)} policy files:")
    for file in policy_files:
        print(f"  - {file.name}")
    
    try:
        # Initialize Graph RAG system
        print("\nInitializing Graph RAG system...")
        graph_rag = PolicyGraphRAG(
            policy_dir=str(policy_dir),
            data_dir=str(data_dir)
        )
        
        # Build the complete system
        print("Building Graph RAG system...")
        graph_rag.build_complete_system(rebuild=True)
        
        # Test the system
        print("\nTesting the Graph RAG system...")
        test_queries = [
            "What are the requirements for patient data access?",
            "How should personal data be protected?",
            "What are the penalties for data breaches?"
        ]
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            results = graph_rag.hybrid_retrieve(query, k=3)
            
            if results:
                print(f"Found {len(results)} relevant results:")
                for i, result in enumerate(results[:2]):  # Show top 2
                    print(f"  {i+1}. [{result['type']}] Score: {result['score']:.3f}")
                    content_preview = result['content'][:150].replace('\n', ' ')
                    print(f"     {content_preview}...")
            else:
                print("  No results found.")
        
        print("\n✅ Graph RAG system built successfully!")
        print(f"📊 Knowledge Graph: {graph_rag.knowledge_graph.number_of_nodes()} nodes, {graph_rag.knowledge_graph.number_of_edges()} edges")
        print(f"🔍 Vector Index: {graph_rag.vector_index.ntotal if graph_rag.vector_index else 0} embeddings")
        print(f"📁 Data saved to: {data_dir}")
        
    except Exception as e:
        print(f"❌ Error building Graph RAG system: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    embed_and_store_policies()
