"""
Qdrant vector store integration for policy document retrieval.

This module provides a high-performance vector store implementation using Qdrant
with optimized indexing, metadata filtering, and retrieval capabilities.
"""

import os
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
from dataclasses import asdict

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from langchain_openai import OpenAIEmbeddings

from .content_aware_chunker import ContentChunk
from .document_parser import DocumentSection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QdrantPolicyVectorStore:
    """
    High-performance vector store for policy documents using Qdrant.
    """
    
    def __init__(
        self,
        collection_name: str = "policy_documents",
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-ada-002",
        vector_size: int = 1536,
        distance_metric: str = "cosine"
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            collection_name: Name of the Qdrant collection
            qdrant_url: Qdrant server URL
            qdrant_api_key: API key for Qdrant Cloud (optional)
            embedding_model: OpenAI embedding model to use
            vector_size: Size of the embedding vectors
            distance_metric: Distance metric for similarity search
        """
        self.collection_name = collection_name
        self.vector_size = vector_size
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # Distance metric mapping
        distance_mapping = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot": Distance.DOT
        }
        self.distance_metric = distance_mapping.get(distance_metric, Distance.COSINE)
        
        # Initialize collection
        self._setup_collection()
    
    def _setup_collection(self):
        """Set up Qdrant collection with proper configuration."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_exists = any(
                collection.name == self.collection_name 
                for collection in collections.collections
            )
            
            if collection_exists:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return
            
            # Create collection with basic configuration
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=self.distance_metric,
                )
            )
            
            # Create payload indexes for efficient filtering
            payload_indexes = [
                ("document_type", models.PayloadSchemaType.KEYWORD),
                ("section_type", models.PayloadSchemaType.KEYWORD),
                ("section_id", models.PayloadSchemaType.KEYWORD),
                ("parent_section", models.PayloadSchemaType.KEYWORD),
                ("chunk_type", models.PayloadSchemaType.KEYWORD),
                ("word_count", models.PayloadSchemaType.INTEGER),
                ("estimated_tokens", models.PayloadSchemaType.INTEGER),
            ]
            
            for field_name, field_type in payload_indexes:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )
                    logger.debug(f"Created index for field: {field_name}")
                except Exception as e:
                    logger.warning(f"Could not create index for {field_name}: {e}")
            
            logger.info(f"Created collection '{self.collection_name}' with optimized settings")
            
        except Exception as e:
            logger.error(f"Error setting up collection: {e}")
            raise
    
    def _prepare_chunk_payload(self, chunk: ContentChunk) -> Dict[str, Any]:
        """
        Prepare chunk metadata as Qdrant payload.
        
        Args:
            chunk: Content chunk to prepare
            
        Returns:
            Payload dictionary for Qdrant
        """
        payload = {
            # Chunk information
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "chunk_type": chunk.chunk_type,
            "chunk_index": chunk.chunk_index,
            "word_count": chunk.word_count,
            
            # Section information
            "section_type": chunk.source_section.section_type,
            "section_id": chunk.source_section.section_id,
            "section_title": chunk.source_section.title or "",
            "parent_section": chunk.source_section.parent_section or "",
            
            # Context information
            "overlap_with_previous": chunk.overlap_with_previous,
            "overlap_with_next": chunk.overlap_with_next,
            
            # Document metadata
            **chunk.metadata
        }
        
        # Ensure all values are JSON serializable
        for key, value in payload.items():
            if value is None:
                payload[key] = ""
            elif isinstance(value, (int, float, str, bool, list, dict)):
                continue
            else:
                payload[key] = str(value)
        
        return payload
    
    def add_chunks(self, chunks: List[ContentChunk], batch_size: int = 100) -> bool:
        """
        Add chunks to the vector store.
        
        Args:
            chunks: List of content chunks to add
            batch_size: Number of chunks to process in each batch
            
        Returns:
            Success status
        """
        try:
            logger.info(f"Adding {len(chunks)} chunks to vector store")
            
            # Process chunks in batches
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                
                # Prepare batch content for embedding
                batch_content = []
                for chunk in batch_chunks:
                    # Use the chunk content with context for embedding
                    content = chunk.content
                    if chunk.source_section.title:
                        content = f"{chunk.source_section.title}\n\n{content}"
                    batch_content.append(content)
                
                # Generate embeddings for the batch
                logger.debug(f"Generating embeddings for batch {i//batch_size + 1}")
                embeddings = self.embeddings.embed_documents(batch_content)
                
                # Prepare points for Qdrant
                points = []
                for j, (chunk, embedding) in enumerate(zip(batch_chunks, embeddings)):
                    point_id = str(uuid.uuid4())
                    payload = self._prepare_chunk_payload(chunk)
                    
                    point = PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                    points.append(point)
                
                # Upload batch to Qdrant
                operation_info = self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                
                logger.debug(f"Uploaded batch {i//batch_size + 1}: {operation_info}")
            
            logger.info(f"Successfully added {len(chunks)} chunks to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error adding chunks to vector store: {e}")
            return False
    
    def search_similar(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks based on query.
        
        Args:
            query: Search query
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional metadata filters
            include_metadata: Whether to include chunk metadata
            
        Returns:
            List of search results with scores and metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Prepare search filters
            search_filter = None
            if filter_conditions:
                conditions = []
                for field, value in filter_conditions.items():
                    if isinstance(value, list):
                        # Handle list values (OR condition)
                        for v in value:
                            conditions.append(
                                FieldCondition(key=field, match=MatchValue(value=v))
                            )
                    else:
                        conditions.append(
                            FieldCondition(key=field, match=MatchValue(value=value))
                        )
                
                if conditions:
                    search_filter = Filter(should=conditions) if len(conditions) > 1 else Filter(must=[conditions[0]])
            
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=include_metadata,
                with_vectors=False
            )
            
            # Format results
            results = []
            for result in search_results:
                result_dict = {
                    "score": result.score,
                    "content": result.payload.get("content", "") if result.payload else "",
                }
                
                if include_metadata and result.payload:
                    result_dict["metadata"] = {
                        key: value for key, value in result.payload.items()
                        if key != "content"
                    }
                
                results.append(result_dict)
            
            logger.debug(f"Found {len(results)} similar chunks for query")
            return results
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {e}")
            return []
    
    def search_by_document_type(
        self,
        query: str,
        document_type: str,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific document type.
        
        Args:
            query: Search query
            document_type: Document type to filter by (e.g., 'gdpr', 'hipaa')
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results
        """
        return self.search_similar(
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions={"document_type": document_type}
        )
    
    def search_by_section_type(
        self,
        query: str,
        section_type: str,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific section type.
        
        Args:
            query: Search query
            section_type: Section type to filter by (e.g., 'recital', 'article', 'section')
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results
        """
        return self.search_similar(
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions={"section_type": section_type}
        )
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.
        
        Returns:
            Collection information dictionary
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "status": str(info.status) if hasattr(info, 'status') else 'active',
                "vectors_count": getattr(info, 'vectors_count', 0),
                "indexed_vectors_count": getattr(info, 'indexed_vectors_count', 0),
                "points_count": getattr(info, 'points_count', 0),
                "segments_count": getattr(info, 'segments_count', 0),
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {
                "name": self.collection_name,
                "status": "unknown",
                "vectors_count": 0,
                "indexed_vectors_count": 0,
                "points_count": 0,
                "segments_count": 0,
            }
    
    def clear_collection(self) -> bool:
        """
        Clear all points from the collection.
        
        Returns:
            Success status
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="chunk_id",
                                match=models.MatchAny(any=["*"])
                            )
                        ]
                    )
                )
            )
            logger.info(f"Cleared collection '{self.collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            return False
    
    def delete_collection(self) -> bool:
        """
        Delete the entire collection.
        
        Returns:
            Success status
        """
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection '{self.collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False


def main():
    """Example usage of Qdrant vector store."""
    from .document_parser import PolicyDocumentParser, DocumentType
    from .content_aware_chunker import ContentAwareChunker
    
    # Initialize components
    parser = PolicyDocumentParser()
    chunker = ContentAwareChunker(target_chunk_size=600, overlap_size=100)
    vector_store = QdrantPolicyVectorStore(collection_name="demo_policy_docs")
    
    # Process a small sample for demo
    gdpr_path = "policy_corpus/output/GDPR/GDPR.md"
    if Path(gdpr_path).exists():
        logger.info("Processing sample GDPR sections...")
        
        # Parse and chunk a few sections for demo
        sections = parser.parse_document(gdpr_path, DocumentType.GDPR)[:5]  # First 5 sections only
        chunks = chunker.chunk_document_sections(sections)
        
        print(f"Demo: Processing {len(chunks)} chunks")
        
        # Add to vector store
        success = vector_store.add_chunks(chunks)
        if success:
            print("✅ Successfully added chunks to vector store")
            
            # Test search
            results = vector_store.search_similar("data protection rights", limit=3)
            print(f"Found {len(results)} similar chunks:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. Score: {result['score']:.3f}")
                print(f"     Content: {result['content'][:100]}...")
            
            # Show collection info
            info = vector_store.get_collection_info()
            print(f"\nCollection info: {info}")
        else:
            print("❌ Failed to add chunks to vector store")


if __name__ == "__main__":
    main()
