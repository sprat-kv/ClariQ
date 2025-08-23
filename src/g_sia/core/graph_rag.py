"""
Graph RAG implementation for policy documents.

This module implements a hybrid Graph RAG system that:
1. Extracts entities and relationships from policy documents
2. Builds a knowledge graph of compliance rules
3. Combines graph traversal with vector similarity for retrieval
"""

import os
import json
import pickle
from typing import List, Dict, Any, Tuple
from pathlib import Path

import PyPDF2
import networkx as nx
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate
import faiss


class PolicyGraphRAG:
    """
    Graph RAG system for policy compliance analysis.
    """
    
    def __init__(self, policy_dir: str, data_dir: str = "./data"):
        self.policy_dir = Path(policy_dir)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.knowledge_graph = nx.DiGraph()
        self.embeddings_model = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        # Storage paths
        self.graph_path = self.data_dir / "policy_graph.json"
        self.vector_index_path = self.data_dir / "policy_vectors.faiss"
        self.documents_path = self.data_dir / "policy_documents.pkl"
        
        # Document chunks and embeddings
        self.document_chunks = []
        self.vector_index = None
        
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
        
        for file_path in self.policy_dir.glob("*"):
            if file_path.suffix.lower() == '.pdf':
                print(f"Loading PDF: {file_path.name}")
                text = self.extract_text_from_pdf(file_path)
                if text.strip():
                    doc = Document(
                        page_content=text,
                        metadata={
                            "source": str(file_path),
                            "policy_type": self._infer_policy_type(file_path.name)
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
                                "policy_type": self._infer_policy_type(file_path.name)
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
    
    def extract_entities_and_relationships(self, documents: List[Document]) -> None:
        """Extract entities and relationships from documents to build knowledge graph."""
        
        entity_extraction_prompt = ChatPromptTemplate.from_template("""
        You are a legal compliance expert. Extract key entities and relationships from this policy text.
        
        For each policy text, identify:
        1. ENTITIES: Regulations, requirements, data types, rights, penalties, exceptions
        2. RELATIONSHIPS: How entities connect (requires, prohibits, allows, applies_to, etc.)
        
        Policy Text:
        {text}
        
        Return a JSON structure with:
        {{
            "entities": [
                {{"name": "entity_name", "type": "regulation|requirement|data_type|right|penalty|exception", "description": "brief_description"}}
            ],
            "relationships": [
                {{"source": "entity1", "target": "entity2", "relationship": "requires|prohibits|allows|applies_to", "description": "relationship_description"}}
            ]
        }}
        """)
        
        for doc in documents:
            # Split document into manageable chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000,
                chunk_overlap=200
            )
            chunks = text_splitter.split_documents([doc])
            
            policy_type = doc.metadata.get('policy_type', 'UNKNOWN')
            
            for i, chunk in enumerate(chunks):
                try:
                    # Extract entities and relationships using LLM
                    prompt = entity_extraction_prompt.format(text=chunk.page_content)
                    response = self.llm.invoke(prompt)
                    
                    # Parse JSON response
                    try:
                        data = json.loads(response.content)
                    except json.JSONDecodeError:
                        print(f"Failed to parse JSON for chunk {i} in {doc.metadata['source']}")
                        continue
                    
                    # Add entities to graph
                    for entity in data.get('entities', []):
                        node_id = f"{policy_type}_{entity['name']}"
                        self.knowledge_graph.add_node(
                            node_id,
                            name=entity['name'],
                            type=entity['type'],
                            description=entity.get('description', ''),
                            policy_type=policy_type,
                            source_chunk=i
                        )
                    
                    # Add relationships to graph
                    for rel in data.get('relationships', []):
                        source_id = f"{policy_type}_{rel['source']}"
                        target_id = f"{policy_type}_{rel['target']}"
                        
                        if source_id in self.knowledge_graph and target_id in self.knowledge_graph:
                            self.knowledge_graph.add_edge(
                                source_id,
                                target_id,
                                relationship=rel['relationship'],
                                description=rel.get('description', '')
                            )
                
                except Exception as e:
                    print(f"Error processing chunk {i} in {doc.metadata['source']}: {e}")
                    continue
        
        print(f"Built knowledge graph with {self.knowledge_graph.number_of_nodes()} nodes and {self.knowledge_graph.number_of_edges()} edges")
    
    def build_vector_index(self, documents: List[Document]) -> None:
        """Build FAISS vector index for semantic similarity search."""
        
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        all_chunks = []
        for doc in documents:
            chunks = text_splitter.split_documents([doc])
            all_chunks.extend(chunks)
        
        self.document_chunks = all_chunks
        
        # Generate embeddings
        print(f"Generating embeddings for {len(all_chunks)} chunks...")
        texts = [chunk.page_content for chunk in all_chunks]
        embeddings = self.embeddings_model.embed_documents(texts)
        
        # Create FAISS index
        dimension = len(embeddings[0])
        self.vector_index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        
        # Normalize embeddings for cosine similarity
        embeddings_array = np.array(embeddings).astype('float32')
        faiss.normalize_L2(embeddings_array)
        
        self.vector_index.add(embeddings_array)
        
        print(f"Built vector index with {self.vector_index.ntotal} vectors")
    
    def graph_traversal_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search knowledge graph for relevant nodes based on query."""
        
        # Simple keyword-based graph search (can be enhanced with embeddings)
        query_terms = query.lower().split()
        relevant_nodes = []
        
        for node_id, node_data in self.knowledge_graph.nodes(data=True):
            # Check if query terms appear in node attributes
            node_text = f"{node_data.get('name', '')} {node_data.get('description', '')}".lower()
            
            score = 0
            for term in query_terms:
                if term in node_text:
                    score += 1
            
            if score > 0:
                # Get connected nodes for context
                neighbors = list(self.knowledge_graph.neighbors(node_id))
                
                relevant_nodes.append({
                    'node_id': node_id,
                    'node_data': node_data,
                    'neighbors': neighbors,
                    'score': score
                })
        
        # Sort by relevance score
        relevant_nodes.sort(key=lambda x: x['score'], reverse=True)
        
        return relevant_nodes[:k]
    
    def vector_similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """Search vector index for semantically similar chunks."""
        
        if self.vector_index is None:
            return []
        
        # Generate query embedding
        query_embedding = self.embeddings_model.embed_query(query)
        query_vector = np.array([query_embedding]).astype('float32')
        faiss.normalize_L2(query_vector)
        
        # Search vector index
        scores, indices = self.vector_index.search(query_vector, k)
        
        # Return relevant documents
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.document_chunks):
                doc = self.document_chunks[idx]
                doc.metadata['similarity_score'] = float(scores[0][i])
                results.append(doc)
        
        return results
    
    def hybrid_retrieve(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining graph traversal and vector similarity.
        """
        
        # Get results from both methods
        graph_results = self.graph_traversal_search(query, k=k//2)
        vector_results = self.vector_similarity_search(query, k=k//2)
        
        # Combine results
        combined_results = []
        
        # Add graph results
        for result in graph_results:
            combined_results.append({
                'type': 'graph',
                'content': f"Entity: {result['node_data'].get('name', '')}\n"
                          f"Description: {result['node_data'].get('description', '')}\n"
                          f"Policy: {result['node_data'].get('policy_type', '')}",
                'metadata': result['node_data'],
                'score': result['score']
            })
        
        # Add vector results
        for result in vector_results:
            combined_results.append({
                'type': 'vector',
                'content': result.page_content,
                'metadata': result.metadata,
                'score': result.metadata.get('similarity_score', 0)
            })
        
        # Sort by score (descending)
        combined_results.sort(key=lambda x: x['score'], reverse=True)
        
        return combined_results
    
    def save_graph_data(self) -> None:
        """Save knowledge graph and vector index to disk."""
        
        # Save knowledge graph
        graph_data = {
            'nodes': dict(self.knowledge_graph.nodes(data=True)),
            'edges': list(self.knowledge_graph.edges(data=True))
        }
        
        with open(self.graph_path, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        # Save vector index
        if self.vector_index is not None:
            faiss.write_index(self.vector_index, str(self.vector_index_path))
        
        # Save document chunks
        with open(self.documents_path, 'wb') as f:
            pickle.dump(self.document_chunks, f)
        
        print(f"Saved graph data to {self.data_dir}")
    
    def load_graph_data(self) -> bool:
        """Load knowledge graph and vector index from disk."""
        
        try:
            # Load knowledge graph
            if self.graph_path.exists():
                with open(self.graph_path, 'r') as f:
                    graph_data = json.load(f)
                
                self.knowledge_graph = nx.DiGraph()
                
                # Add nodes
                for node_id, node_attrs in graph_data['nodes'].items():
                    self.knowledge_graph.add_node(node_id, **node_attrs)
                
                # Add edges
                for source, target, edge_attrs in graph_data['edges']:
                    self.knowledge_graph.add_edge(source, target, **edge_attrs)
            
            # Load vector index
            if self.vector_index_path.exists():
                self.vector_index = faiss.read_index(str(self.vector_index_path))
            
            # Load document chunks
            if self.documents_path.exists():
                with open(self.documents_path, 'rb') as f:
                    self.document_chunks = pickle.load(f)
            
            print(f"Loaded graph data from {self.data_dir}")
            return True
            
        except Exception as e:
            print(f"Error loading graph data: {e}")
            return False
    
    def build_complete_system(self, rebuild: bool = False) -> None:
        """Build the complete Graph RAG system."""
        
        # Try to load existing data first
        if not rebuild and self.load_graph_data():
            print("Loaded existing Graph RAG system")
            return
        
        print("Building Graph RAG system from scratch...")
        
        # Load policy documents
        documents = self.load_policy_documents()
        
        if not documents:
            print("No policy documents found!")
            return
        
        # Extract entities and build knowledge graph
        print("Extracting entities and relationships...")
        self.extract_entities_and_relationships(documents)
        
        # Build vector index
        print("Building vector index...")
        self.build_vector_index(documents)
        
        # Save everything
        self.save_graph_data()
        
        print("Graph RAG system built successfully!")


if __name__ == "__main__":
    # Example usage
    graph_rag = PolicyGraphRAG(
        policy_dir="../../policy_corpus",
        data_dir="../../data"
    )
    
    # Build the system
    graph_rag.build_complete_system(rebuild=True)
    
    # Test retrieval
    test_query = "What are the requirements for patient data access?"
    results = graph_rag.hybrid_retrieve(test_query, k=5)
    
    print(f"\nResults for query: '{test_query}'")
    for i, result in enumerate(results):
        print(f"\n{i+1}. Type: {result['type']}, Score: {result['score']:.3f}")
        print(f"Content: {result['content'][:200]}...")
