"""
Neo4j-powered Graph RAG implementation for policy documents.

This module implements an advanced Graph RAG system using Neo4j that:
1. Stores policy entities and relationships in a Neo4j graph database
2. Leverages Cypher queries for complex graph traversals
3. Combines graph-based retrieval with vector similarity search
4. Provides explainable compliance reasoning through graph paths
"""

import os
import json
import pickle
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

import PyPDF2
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate
from langchain_neo4j import Neo4jGraph, Neo4jVector
from neo4j import GraphDatabase
import faiss


class Neo4jPolicyGraphRAG:
    """
    Advanced Graph RAG system using Neo4j for policy compliance analysis.
    """
    
    def __init__(self, 
                 policy_dir: str, 
                 neo4j_url: str = "bolt://localhost:7687",
                 neo4j_username: str = "neo4j",
                 neo4j_password: str = "password",
                 data_dir: str = "./data"):
        
        self.policy_dir = Path(policy_dir)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Neo4j connection parameters
        self.neo4j_url = neo4j_url
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password
        
        # Initialize Neo4j graph
        try:
            self.graph = Neo4jGraph(
                url=neo4j_url,
                username=neo4j_username,
                password=neo4j_password
            )
            print(f"✅ Connected to Neo4j at {neo4j_url}")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            print("Make sure Neo4j is running and credentials are correct")
            raise
        
        # Initialize embeddings and LLM
        self.embeddings_model = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        # Neo4j Vector store for hybrid retrieval
        self.vector_store = None
        
        # Storage paths
        self.documents_path = self.data_dir / "neo4j_policy_documents.pkl"
        self.document_chunks = []
    
    def clear_graph(self):
        """Clear all nodes and relationships from Neo4j graph."""
        print("Clearing existing graph data...")
        self.graph.query("MATCH (n) DETACH DELETE n")
        print("Graph cleared.")
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text content from PDF file."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}")
            return ""
    
    def load_policy_documents(self) -> List[Document]:
        """Load all policy documents from the policy directory."""
        documents = []
        
        # First, check for markdown files (processed OCR output)
        markdown_dir = self.policy_dir.parent / "markdown_output"
        
        if markdown_dir.exists():
            print(f"Loading processed markdown files from: {markdown_dir}")
            for file_path in markdown_dir.glob("*.md"):
                print(f"Loading Markdown: {file_path.name}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    if text.strip():
                        doc = Document(
                            page_content=text,
                            metadata={
                                "source": str(file_path),
                                "policy_type": self._infer_policy_type(file_path.name),
                                "filename": file_path.name,
                                "content_type": "markdown_ocr"
                            }
                        )
                        documents.append(doc)
        
        # Fallback: load from policy_corpus directory
        for file_path in self.policy_dir.glob("*"):
            if file_path.suffix.lower() == '.pdf':
                print(f"⚠️ Found PDF: {file_path.name} - Consider converting to markdown first")
                # Skip PDFs if we have markdown files, or process with OCR
                if not markdown_dir.exists() or len(list(markdown_dir.glob("*.md"))) == 0:
                    print(f"Loading PDF: {file_path.name}")
                    text = self.extract_text_from_pdf(file_path)
                    if text.strip():
                        doc = Document(
                            page_content=text,
                            metadata={
                                "source": str(file_path),
                                "policy_type": self._infer_policy_type(file_path.name),
                                "filename": file_path.name,
                                "content_type": "pdf_direct"
                            }
                        )
                        documents.append(doc)
            elif file_path.suffix.lower() == '.md':
                print(f"Loading Markdown: {file_path.name}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    if text.strip():
                        doc = Document(
                            page_content=text,
                            metadata={
                                "source": str(file_path),
                                "policy_type": self._infer_policy_type(file_path.name),
                                "filename": file_path.name,
                                "content_type": "markdown_direct"
                            }
                        )
                        documents.append(doc)
        
        print(f"Loaded {len(documents)} policy documents")
        return documents
    
    def _infer_policy_type(self, filename: str) -> str:
        """Infer policy type from filename."""
        filename_lower = filename.lower()
        if 'hipaa' in filename_lower:
            return 'HIPAA'
        elif 'gdpr' in filename_lower:
            return 'GDPR'
        elif 'ccpa' in filename_lower or 'california' in filename_lower:
            return 'CCPA'
        else:
            return 'UNKNOWN'
    
    def setup_graph_schema(self):
        """Set up Neo4j graph schema with constraints and indexes."""
        print("Setting up Neo4j graph schema...")
        
        # Create constraints for unique nodes
        constraints = [
            "CREATE CONSTRAINT policy_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT policy_regulation_id IF NOT EXISTS FOR (r:Regulation) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT policy_requirement_id IF NOT EXISTS FOR (req:Requirement) REQUIRE req.id IS UNIQUE",
            "CREATE CONSTRAINT policy_document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE"
        ]
        
        for constraint in constraints:
            try:
                self.graph.query(constraint)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Warning: Could not create constraint: {e}")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX regulation_policy_type_idx IF NOT EXISTS FOR (r:Regulation) ON (r.policy_type)"
        ]
        
        for index in indexes:
            try:
                self.graph.query(index)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Warning: Could not create index: {e}")
        
        print("Graph schema setup complete.")
    
    def extract_and_store_entities(self, documents: List[Document]) -> None:
        """Extract entities and relationships from documents and store in Neo4j."""
        
        entity_extraction_prompt = ChatPromptTemplate.from_template("""
        You are a legal compliance expert. Extract key entities and relationships from this policy text.
        
        For each policy text, identify:
        1. ENTITIES: Regulations, requirements, data types, rights, penalties, exceptions
        2. RELATIONSHIPS: How entities connect (requires, prohibits, allows, applies_to, etc.)
        
        Policy Text:
        {text}
        
        Policy Type: {policy_type}
        
        Return a JSON structure with:
        {{
            "entities": [
                {{
                    "name": "entity_name",
                    "type": "regulation|requirement|data_type|right|penalty|exception|concept",
                    "description": "brief_description",
                    "importance": "high|medium|low"
                }}
            ],
            "relationships": [
                {{
                    "source": "entity1",
                    "target": "entity2", 
                    "relationship": "REQUIRES|PROHIBITS|ALLOWS|APPLIES_TO|DEFINES|GOVERNS",
                    "description": "relationship_description",
                    "strength": 0.8
                }}
            ]
        }}
        
        Focus on compliance-relevant entities and their regulatory relationships.
        """)
        
        for doc in documents:
            # Split document into manageable chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000,
                chunk_overlap=200
            )
            chunks = text_splitter.split_documents([doc])
            
            policy_type = doc.metadata.get('policy_type', 'UNKNOWN')
            filename = doc.metadata.get('filename', 'unknown')
            
            # Create document node
            doc_id = f"doc_{filename.replace('.', '_').replace(' ', '_')}"
            self.graph.query("""
                MERGE (d:Document {id: $doc_id})
                SET d.filename = $filename,
                    d.policy_type = $policy_type,
                    d.source = $source
            """, {
                "doc_id": doc_id,
                "filename": filename,
                "policy_type": policy_type,
                "source": doc.metadata.get('source', '')
            })
            
            for i, chunk in enumerate(chunks):
                try:
                    # Extract entities and relationships using LLM
                    prompt = entity_extraction_prompt.format(
                        text=chunk.page_content,
                        policy_type=policy_type
                    )
                    response = self.llm.invoke(prompt)
                    
                    # Parse JSON response
                    try:
                        data = json.loads(response.content)
                    except json.JSONDecodeError:
                        print(f"Failed to parse JSON for chunk {i} in {filename}")
                        continue
                    
                    # Store entities in Neo4j
                    for entity in data.get('entities', []):
                        entity_id = f"{policy_type}_{entity['name'].replace(' ', '_')}"
                        
                        # Create entity node
                        self.graph.query("""
                            MERGE (e:Entity {id: $entity_id})
                            SET e.name = $name,
                                e.type = $type,
                                e.description = $description,
                                e.policy_type = $policy_type,
                                e.importance = $importance,
                                e.chunk_index = $chunk_index
                            
                            WITH e
                            MATCH (d:Document {id: $doc_id})
                            MERGE (d)-[:CONTAINS]->(e)
                        """, {
                            "entity_id": entity_id,
                            "name": entity['name'],
                            "type": entity['type'],
                            "description": entity.get('description', ''),
                            "policy_type": policy_type,
                            "importance": entity.get('importance', 'medium'),
                            "chunk_index": i,
                            "doc_id": doc_id
                        })
                    
                    # Store relationships in Neo4j
                    for rel in data.get('relationships', []):
                        source_id = f"{policy_type}_{rel['source'].replace(' ', '_')}"
                        target_id = f"{policy_type}_{rel['target'].replace(' ', '_')}"
                        
                        # Create relationship
                        self.graph.query(f"""
                            MATCH (s:Entity {{id: $source_id}})
                            MATCH (t:Entity {{id: $target_id}})
                            MERGE (s)-[r:{rel['relationship']}]->(t)
                            SET r.description = $description,
                                r.strength = $strength
                        """, {
                            "source_id": source_id,
                            "target_id": target_id,
                            "description": rel.get('description', ''),
                            "strength": rel.get('strength', 0.5)
                        })
                
                except Exception as e:
                    print(f"Error processing chunk {i} in {filename}: {e}")
                    continue
        
        # Get graph statistics
        result = self.graph.query("MATCH (n) RETURN count(n) as node_count")
        node_count = result[0]['node_count'] if result else 0
        
        result = self.graph.query("MATCH ()-[r]->() RETURN count(r) as rel_count")
        rel_count = result[0]['rel_count'] if result else 0
        
        print(f"✅ Built Neo4j knowledge graph with {node_count} nodes and {rel_count} relationships")
    
    def setup_vector_store(self, documents: List[Document]) -> None:
        """Set up Neo4j vector store for hybrid retrieval."""
        print("Setting up Neo4j vector store...")
        
        # Split documents into chunks for vector storage
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        all_chunks = []
        for doc in documents:
            chunks = text_splitter.split_documents([doc])
            all_chunks.extend(chunks)
        
        self.document_chunks = all_chunks
        
        try:
            # Create Neo4j vector store
            self.vector_store = Neo4jVector.from_documents(
                documents=all_chunks,
                embedding=self.embeddings_model,
                url=self.neo4j_url,
                username=self.neo4j_username,
                password=self.neo4j_password,
                index_name="policy_vector_index"
            )
            print(f"✅ Created Neo4j vector store with {len(all_chunks)} chunks")
            
        except Exception as e:
            print(f"❌ Error creating vector store: {e}")
            # Fallback to FAISS if Neo4j vector fails
            print("Falling back to FAISS vector store...")
            self._setup_faiss_fallback(all_chunks)
    
    def _setup_faiss_fallback(self, chunks: List[Document]) -> None:
        """Setup FAISS as fallback vector store."""
        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embeddings_model.embed_documents(texts)
        
        dimension = len(embeddings[0])
        self.faiss_index = faiss.IndexFlatIP(dimension)
        
        embeddings_array = np.array(embeddings).astype('float32')
        faiss.normalize_L2(embeddings_array)
        self.faiss_index.add(embeddings_array)
        
        print(f"✅ FAISS fallback vector store created with {len(chunks)} chunks")
    
    def graph_cypher_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search Neo4j graph using Cypher queries based on the user query."""
        
        # Generate Cypher query based on user intent
        cypher_generation_prompt = ChatPromptTemplate.from_template("""
        You are a Neo4j Cypher expert. Generate a Cypher query to find relevant policy entities for this user query.
        
        User Query: {query}
        
        Graph Schema:
        - Nodes: Entity (name, type, description, policy_type, importance)
        - Nodes: Document (filename, policy_type)
        - Relationships: CONTAINS, REQUIRES, PROHIBITS, ALLOWS, APPLIES_TO, DEFINES, GOVERNS
        
        Generate a Cypher query that finds the most relevant entities and their relationships.
        Focus on entities related to the user's query intent.
        
        Return only the Cypher query, no explanation:
        """)
        
        try:
            # Generate Cypher query
            prompt = cypher_generation_prompt.format(query=query)
            response = self.llm.invoke(prompt)
            cypher_query = response.content.strip()
            
            # Clean up the query
            if cypher_query.startswith("```"):
                cypher_query = cypher_query.split("```")[1].strip()
            if cypher_query.startswith("cypher"):
                cypher_query = cypher_query[6:].strip()
            
            print(f"Generated Cypher: {cypher_query}")
            
            # Execute Cypher query
            results = self.graph.query(cypher_query)
            
            # Format results
            formatted_results = []
            for result in results[:k]:
                formatted_results.append({
                    'type': 'graph',
                    'content': str(result),
                    'metadata': result,
                    'score': 1.0  # Cypher results are considered highly relevant
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in Cypher search: {e}")
            # Fallback to simple text-based node search
            return self._fallback_graph_search(query, k)
    
    def _fallback_graph_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Fallback graph search using simple text matching."""
        query_terms = query.lower().split()
        
        # Search for entities with matching names or descriptions
        cypher = """
        MATCH (e:Entity)
        WHERE any(term IN $terms WHERE 
            toLower(e.name) CONTAINS term OR 
            toLower(e.description) CONTAINS term
        )
        RETURN e.name as name, e.type as type, e.description as description, 
               e.policy_type as policy_type, e.importance as importance
        LIMIT $limit
        """
        
        results = self.graph.query(cypher, {"terms": query_terms, "limit": k})
        
        formatted_results = []
        for result in results:
            content = f"Entity: {result['name']}\nType: {result['type']}\nDescription: {result['description']}\nPolicy: {result['policy_type']}"
            formatted_results.append({
                'type': 'graph',
                'content': content,
                'metadata': dict(result),
                'score': 0.8
            })
        
        return formatted_results
    
    def vector_similarity_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search vector store for semantically similar chunks."""
        
        try:
            if self.vector_store:
                # Use Neo4j vector store
                results = self.vector_store.similarity_search_with_score(query, k=k)
                
                formatted_results = []
                for doc, score in results:
                    formatted_results.append({
                        'type': 'vector',
                        'content': doc.page_content,
                        'metadata': doc.metadata,
                        'score': float(score)
                    })
                
                return formatted_results
            
            elif hasattr(self, 'faiss_index'):
                # Use FAISS fallback
                query_embedding = self.embeddings_model.embed_query(query)
                query_vector = np.array([query_embedding]).astype('float32')
                faiss.normalize_L2(query_vector)
                
                scores, indices = self.faiss_index.search(query_vector, k)
                
                formatted_results = []
                for i, idx in enumerate(indices[0]):
                    if idx < len(self.document_chunks):
                        doc = self.document_chunks[idx]
                        formatted_results.append({
                            'type': 'vector',
                            'content': doc.page_content,
                            'metadata': doc.metadata,
                            'score': float(scores[0][i])
                        })
                
                return formatted_results
            
            else:
                print("No vector store available")
                return []
                
        except Exception as e:
            print(f"Error in vector search: {e}")
            return []
    
    def hybrid_retrieve(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining Neo4j graph traversal and vector similarity.
        """
        
        # Get results from both methods
        graph_results = self.graph_cypher_search(query, k=k//2)
        vector_results = self.vector_similarity_search(query, k=k//2)
        
        # Combine and rank results
        all_results = graph_results + vector_results
        
        # Sort by score (descending)
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        return all_results[:k]
    
    def get_policy_paths(self, entity1: str, entity2: str) -> List[Dict[str, Any]]:
        """Find paths between two policy entities in the graph."""
        
        cypher = """
        MATCH path = shortestPath((e1:Entity)-[*..5]-(e2:Entity))
        WHERE toLower(e1.name) CONTAINS toLower($entity1) 
          AND toLower(e2.name) CONTAINS toLower($entity2)
        RETURN path, length(path) as path_length
        ORDER BY path_length
        LIMIT 5
        """
        
        try:
            results = self.graph.query(cypher, {"entity1": entity1, "entity2": entity2})
            return [{"path": result["path"], "length": result["path_length"]} for result in results]
        except Exception as e:
            print(f"Error finding policy paths: {e}")
            return []
    
    def build_complete_system(self, rebuild: bool = False) -> None:
        """Build the complete Neo4j Graph RAG system."""
        
        if rebuild:
            self.clear_graph()
        
        print("Building Neo4j Graph RAG system...")
        
        # Setup graph schema
        self.setup_graph_schema()
        
        # Load policy documents
        documents = self.load_policy_documents()
        
        if not documents:
            print("No policy documents found!")
            return
        
        # Extract entities and build knowledge graph
        print("Extracting entities and relationships...")
        self.extract_and_store_entities(documents)
        
        # Setup vector store
        print("Setting up vector store...")
        self.setup_vector_store(documents)
        
        # Save document chunks
        with open(self.documents_path, 'wb') as f:
            pickle.dump(self.document_chunks, f)
        
        print("✅ Neo4j Graph RAG system built successfully!")
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the Neo4j graph."""
        
        stats = {}
        
        # Node counts by type
        result = self.graph.query("MATCH (n) RETURN labels(n) as labels, count(n) as count")
        stats['nodes_by_type'] = {str(r['labels']): r['count'] for r in result}
        
        # Relationship counts by type
        result = self.graph.query("MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count")
        stats['relationships_by_type'] = {r['rel_type']: r['count'] for r in result}
        
        # Policy type distribution
        result = self.graph.query("MATCH (e:Entity) RETURN e.policy_type as policy, count(e) as count")
        stats['entities_by_policy'] = {r['policy']: r['count'] for r in result}
        
        return stats


if __name__ == "__main__":
    # Example usage
    neo4j_graph_rag = Neo4jPolicyGraphRAG(
        policy_dir="../../policy_corpus",
        neo4j_url="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="password"
    )
    
    # Build the system
    neo4j_graph_rag.build_complete_system(rebuild=True)
    
    # Test retrieval
    test_query = "What are the requirements for patient data access?"
    results = neo4j_graph_rag.hybrid_retrieve(test_query, k=5)
    
    print(f"\nResults for query: '{test_query}'")
    for i, result in enumerate(results):
        print(f"\n{i+1}. Type: {result['type']}, Score: {result['score']:.3f}")
        print(f"Content: {result['content'][:200]}...")
    
    # Show graph statistics
    stats = neo4j_graph_rag.get_graph_stats()
    print(f"\nGraph Statistics: {stats}")
