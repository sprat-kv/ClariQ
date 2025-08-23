#!/usr/bin/env python3
"""
Neo4j Graph RAG Setup Script

This script sets up the complete Neo4j-powered Graph RAG system for policy compliance.

Usage:
    python scripts/setup_neo4j_system.py [--rebuild]
"""

import sys
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from g_sia.core.neo4j_graph_rag import Neo4jPolicyGraphRAG

# Load environment variables
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Setup Neo4j Graph RAG system")
    parser.add_argument("--rebuild", action="store_true", 
                       help="Rebuild the system from scratch (clears existing data)")
    parser.add_argument("--neo4j-url", default=os.getenv("NEO4J_URL", "bolt://localhost:7687"),
                       help="Neo4j connection URL")
    parser.add_argument("--neo4j-username", default=os.getenv("NEO4J_USERNAME", "neo4j"),
                       help="Neo4j username")
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "password"),
                       help="Neo4j password")
    
    args = parser.parse_args()
    
    print("🚀 Setting up Neo4j Graph RAG System")
    print("=" * 50)
    
    # Debug: Show loaded environment variables
    print("🔧 Environment Configuration:")
    print(f"  NEO4J_URL: {args.neo4j_url}")
    print(f"  NEO4J_USERNAME: {args.neo4j_username}")
    print(f"  NEO4J_PASSWORD: {'*' * len(args.neo4j_password) if args.neo4j_password else 'Not set'}")
    print(f"  OPENAI_API_KEY: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
    print()
    
    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    policy_dir = project_root / "policy_corpus"
    
    # Check if policy directory exists
    if not policy_dir.exists():
        print(f"❌ Error: Policy directory '{policy_dir}' not found.")
        return 1
    
    # Check if we have any policy files
    policy_files = list(policy_dir.glob("*.pdf"))
    if not policy_files:
        print(f"❌ Error: No policy files found in '{policy_dir}'")
        return 1
    
    print(f"📁 Found {len(policy_files)} policy files:")
    for file in policy_files:
        print(f"  - {file.name}")
    
    try:
        # Initialize Neo4j Graph RAG system
        print(f"\n🔗 Connecting to Neo4j at {args.neo4j_url}...")
        graph_rag = Neo4jPolicyGraphRAG(
            policy_dir=str(policy_dir),
            neo4j_url=args.neo4j_url,
            neo4j_username=args.neo4j_username,
            neo4j_password=args.neo4j_password
        )
        
        # Build the complete system
        print("🏗️ Building Neo4j Graph RAG system...")
        graph_rag.build_complete_system(rebuild=args.rebuild)
        
        # Get and display statistics
        print("\n📊 System Statistics:")
        stats = graph_rag.get_graph_stats()
        
        print(f"  Nodes by type: {stats.get('nodes_by_type', {})}")
        print(f"  Relationships by type: {stats.get('relationships_by_type', {})}")
        print(f"  Entities by policy: {stats.get('entities_by_policy', {})}")
        
        # Test the system
        print("\n🧪 Testing the system...")
        test_queries = [
            "What are the requirements for patient data access?",
            "How should personal information be protected?",
            "What are the penalties for data breaches?"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{i}. Testing: {query}")
            results = graph_rag.hybrid_retrieve(query, k=3)
            
            if results:
                print(f"   ✅ Found {len(results)} results:")
                for j, result in enumerate(results[:2]):
                    print(f"     {j+1}. [{result['type']}] Score: {result['score']:.3f}")
                    content_preview = result['content'][:100].replace('\n', ' ')
                    print(f"        {content_preview}...")
            else:
                print("   ⚠️ No results found")
        
        print("\n🎉 Neo4j Graph RAG system setup completed successfully!")
        print("\n📋 Next steps:")
        print("  1. Run 'python test_neo4j_system.py' to test the PolicyAgent")
        print("  2. Use the Neo4jPolicyAgent in your application")
        print("  3. Access Neo4j Browser at http://localhost:7474 to explore the graph")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error setting up Neo4j Graph RAG system: {e}")
        print("\n🔧 Troubleshooting:")
        print("  1. Make sure Neo4j is running (neo4j start)")
        print("  2. Check your Neo4j credentials")
        print("  3. Verify OpenAI API key is set in .env file")
        print("  4. Ensure policy PDF files are in policy_corpus/ directory")
        
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
