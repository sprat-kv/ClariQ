"""
Content-aware chunking system for policy documents.

This module implements intelligent chunking that preserves document structure
while optimizing for semantic coherence and retrieval performance.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import spacy
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from .document_parser import DocumentSection, PolicyDocumentParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ContentChunk:
    """Represents a content-aware chunk with rich metadata."""
    content: str
    chunk_id: str
    source_section: DocumentSection
    chunk_type: str  # 'full_section', 'partial_section', 'cross_section'
    chunk_index: int  # Index within the source section
    word_count: int
    overlap_with_previous: str = ""
    overlap_with_next: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Ensure word count is accurate
        if self.word_count == 0:
            self.word_count = len(self.content.split())


class ContentAwareChunker:
    """
    Intelligent chunker that preserves document structure and optimizes for retrieval.
    """
    
    def __init__(
        self,
        target_chunk_size: int = 800,
        max_chunk_size: int = 1200,
        min_chunk_size: int = 200,
        overlap_size: int = 100,
        respect_sentence_boundaries: bool = True,
        respect_section_boundaries: bool = True
    ):
        """
        Initialize the content-aware chunker.
        
        Args:
            target_chunk_size: Preferred chunk size in tokens
            max_chunk_size: Maximum allowed chunk size
            min_chunk_size: Minimum chunk size (avoid very small chunks)
            overlap_size: Overlap size between chunks
            respect_sentence_boundaries: Whether to avoid breaking sentences
            respect_section_boundaries: Whether to avoid breaking sections
        """
        self.target_chunk_size = target_chunk_size
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size
        self.respect_sentence_boundaries = respect_sentence_boundaries
        self.respect_section_boundaries = respect_section_boundaries
        
        # Initialize NLP model for sentence detection
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("en_core_web_sm not found, using basic sentencizer")
            from spacy.lang.en import English
            self.nlp = English()
            self.nlp.add_pipe('sentencizer')
        
        # Initialize fallback text splitter
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=target_chunk_size,
            chunk_overlap=overlap_size,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True
        )
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count using word-based approximation.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        # Rough approximation: 1.3 tokens per word for English
        word_count = len(text.split())
        return int(word_count * 1.3)
    
    def split_by_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using spaCy.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        doc = self.nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    
    def create_overlap(self, previous_text: str, current_text: str, next_text: str = "") -> Tuple[str, str]:
        """
        Create intelligent overlap between chunks.
        
        Args:
            previous_text: Previous chunk text
            current_text: Current chunk text
            next_text: Next chunk text (if available)
            
        Returns:
            Tuple of (overlap_with_previous, overlap_with_next)
        """
        overlap_with_previous = ""
        overlap_with_next = ""
        
        if previous_text:
            # Take last few sentences from previous chunk
            prev_sentences = self.split_by_sentences(previous_text)
            if prev_sentences:
                # Take last 1-2 sentences for context
                overlap_sentences = prev_sentences[-2:] if len(prev_sentences) > 1 else prev_sentences[-1:]
                overlap_with_previous = " ".join(overlap_sentences)
                
                # Limit overlap size
                if self.estimate_token_count(overlap_with_previous) > self.overlap_size:
                    overlap_with_previous = overlap_sentences[-1]  # Just take the last sentence
        
        if next_text:
            # Take first few sentences from next chunk
            next_sentences = self.split_by_sentences(next_text)
            if next_sentences:
                # Take first 1-2 sentences for context
                overlap_sentences = next_sentences[:2] if len(next_sentences) > 1 else next_sentences[:1]
                overlap_with_next = " ".join(overlap_sentences)
                
                # Limit overlap size
                if self.estimate_token_count(overlap_with_next) > self.overlap_size:
                    overlap_with_next = next_sentences[0]  # Just take the first sentence
        
        return overlap_with_previous, overlap_with_next
    
    def chunk_section_intelligently(self, section: DocumentSection) -> List[ContentChunk]:
        """
        Intelligently chunk a single document section.
        
        Args:
            section: Document section to chunk
            
        Returns:
            List of content chunks
        """
        chunks = []
        content = section.content
        estimated_tokens = self.estimate_token_count(content)
        
        # If section is small enough, keep as single chunk
        if estimated_tokens <= self.target_chunk_size:
            chunk = ContentChunk(
                content=content,
                chunk_id=f"{section.section_id}_chunk_0",
                source_section=section,
                chunk_type="full_section",
                chunk_index=0,
                word_count=len(content.split()),
                metadata={
                    'section_type': section.section_type,
                    'section_id': section.section_id,
                    'section_title': section.title,
                    'parent_section': section.parent_section,
                    'estimated_tokens': estimated_tokens,
                    **section.metadata
                }
            )
            chunks.append(chunk)
            return chunks
        
        # For larger sections, split intelligently
        if self.respect_sentence_boundaries:
            sentences = self.split_by_sentences(content)
            current_chunk_sentences = []
            current_chunk_tokens = 0
            chunk_index = 0
            
            for sentence in sentences:
                sentence_tokens = self.estimate_token_count(sentence)
                
                # Check if adding this sentence would exceed target size
                if (current_chunk_tokens + sentence_tokens > self.target_chunk_size and 
                    current_chunk_sentences and 
                    current_chunk_tokens >= self.min_chunk_size):
                    
                    # Create chunk from current sentences
                    chunk_content = " ".join(current_chunk_sentences)
                    chunk = ContentChunk(
                        content=chunk_content,
                        chunk_id=f"{section.section_id}_chunk_{chunk_index}",
                        source_section=section,
                        chunk_type="partial_section",
                        chunk_index=chunk_index,
                        word_count=len(chunk_content.split()),
                        metadata={
                            'section_type': section.section_type,
                            'section_id': section.section_id,
                            'section_title': section.title,
                            'parent_section': section.parent_section,
                            'estimated_tokens': current_chunk_tokens,
                            'sentence_count': len(current_chunk_sentences),
                            **section.metadata
                        }
                    )
                    chunks.append(chunk)
                    
                    # Start new chunk with overlap
                    if self.overlap_size > 0 and len(current_chunk_sentences) > 1:
                        # Keep last sentence for overlap
                        overlap_sentence = current_chunk_sentences[-1]
                        current_chunk_sentences = [overlap_sentence, sentence]
                        current_chunk_tokens = self.estimate_token_count(overlap_sentence) + sentence_tokens
                    else:
                        current_chunk_sentences = [sentence]
                        current_chunk_tokens = sentence_tokens
                    
                    chunk_index += 1
                else:
                    current_chunk_sentences.append(sentence)
                    current_chunk_tokens += sentence_tokens
            
            # Add final chunk if there are remaining sentences
            if current_chunk_sentences:
                chunk_content = " ".join(current_chunk_sentences)
                chunk = ContentChunk(
                    content=chunk_content,
                    chunk_id=f"{section.section_id}_chunk_{chunk_index}",
                    source_section=section,
                    chunk_type="partial_section",
                    chunk_index=chunk_index,
                    word_count=len(chunk_content.split()),
                    metadata={
                        'section_type': section.section_type,
                        'section_id': section.section_id,
                        'section_title': section.title,
                        'parent_section': section.parent_section,
                        'estimated_tokens': current_chunk_tokens,
                        'sentence_count': len(current_chunk_sentences),
                        **section.metadata
                    }
                )
                chunks.append(chunk)
        
        else:
            # Fallback to character-based splitting
            text_chunks = self.fallback_splitter.split_text(content)
            for i, chunk_text in enumerate(text_chunks):
                chunk = ContentChunk(
                    content=chunk_text,
                    chunk_id=f"{section.section_id}_chunk_{i}",
                    source_section=section,
                    chunk_type="partial_section",
                    chunk_index=i,
                    word_count=len(chunk_text.split()),
                    metadata={
                        'section_type': section.section_type,
                        'section_id': section.section_id,
                        'section_title': section.title,
                        'parent_section': section.parent_section,
                        'estimated_tokens': self.estimate_token_count(chunk_text),
                        **section.metadata
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def add_cross_section_context(self, chunks: List[ContentChunk]) -> List[ContentChunk]:
        """
        Add cross-section context overlaps to chunks.
        
        Args:
            chunks: List of chunks to enhance with overlaps
            
        Returns:
            Enhanced chunks with overlap information
        """
        enhanced_chunks = []
        
        for i, chunk in enumerate(chunks):
            previous_chunk = chunks[i-1] if i > 0 else None
            next_chunk = chunks[i+1] if i < len(chunks) - 1 else None
            
            # Create overlaps
            overlap_prev, overlap_next = self.create_overlap(
                previous_chunk.content if previous_chunk else "",
                chunk.content,
                next_chunk.content if next_chunk else ""
            )
            
            # Create enhanced chunk
            enhanced_chunk = ContentChunk(
                content=chunk.content,
                chunk_id=chunk.chunk_id,
                source_section=chunk.source_section,
                chunk_type=chunk.chunk_type,
                chunk_index=chunk.chunk_index,
                word_count=chunk.word_count,
                overlap_with_previous=overlap_prev,
                overlap_with_next=overlap_next,
                metadata=chunk.metadata
            )
            
            enhanced_chunks.append(enhanced_chunk)
        
        return enhanced_chunks
    
    def chunk_document_sections(self, sections: List[DocumentSection]) -> List[ContentChunk]:
        """
        Chunk all sections of a document intelligently.
        
        Args:
            sections: List of document sections to chunk
            
        Returns:
            List of content-aware chunks
        """
        all_chunks = []
        
        logger.info(f"Chunking {len(sections)} document sections")
        
        for section in sections:
            section_chunks = self.chunk_section_intelligently(section)
            all_chunks.extend(section_chunks)
            
            logger.debug(f"Section {section.section_id}: {len(section_chunks)} chunks created")
        
        # Add cross-section context
        if self.overlap_size > 0:
            all_chunks = self.add_cross_section_context(all_chunks)
        
        logger.info(f"Total chunks created: {len(all_chunks)}")
        
        # Log chunk statistics
        total_words = sum(chunk.word_count for chunk in all_chunks)
        avg_words_per_chunk = total_words / len(all_chunks) if all_chunks else 0
        
        logger.info(f"Chunk statistics:")
        logger.info(f"  Total words: {total_words}")
        logger.info(f"  Average words per chunk: {avg_words_per_chunk:.1f}")
        logger.info(f"  Min words: {min(chunk.word_count for chunk in all_chunks) if all_chunks else 0}")
        logger.info(f"  Max words: {max(chunk.word_count for chunk in all_chunks) if all_chunks else 0}")
        
        return all_chunks
    
    def get_chunk_for_retrieval(self, chunk: ContentChunk, include_context: bool = True) -> str:
        """
        Get the full chunk content optimized for retrieval, including context if requested.
        
        Args:
            chunk: Content chunk
            include_context: Whether to include overlap context
            
        Returns:
            Retrieval-optimized chunk content
        """
        content_parts = []
        
        # Add section header for context
        if chunk.source_section.title:
            content_parts.append(f"[{chunk.source_section.section_type.upper()} {chunk.source_section.section_id}: {chunk.source_section.title}]")
        
        # Add previous context if available
        if include_context and chunk.overlap_with_previous:
            content_parts.append(f"...{chunk.overlap_with_previous}")
        
        # Add main content
        content_parts.append(chunk.content)
        
        # Add next context if available
        if include_context and chunk.overlap_with_next:
            content_parts.append(f"{chunk.overlap_with_next}...")
        
        return "\n\n".join(content_parts)


def main():
    """Example usage of the content-aware chunker."""
    from .document_parser import PolicyDocumentParser, DocumentType
    
    # Initialize components
    parser = PolicyDocumentParser()
    chunker = ContentAwareChunker(
        target_chunk_size=800,
        max_chunk_size=1200,
        overlap_size=100
    )
    
    # Parse and chunk GDPR document
    gdpr_path = "policy_corpus/output/GDPR/GDPR.md"
    if Path(gdpr_path).exists():
        logger.info("Processing GDPR document...")
        gdpr_sections = parser.parse_document(gdpr_path, DocumentType.GDPR)
        gdpr_chunks = chunker.chunk_document_sections(gdpr_sections)
        
        print(f"\nGDPR Processing Results:")
        print(f"  Sections: {len(gdpr_sections)}")
        print(f"  Chunks: {len(gdpr_chunks)}")
        
        # Show sample chunk
        if gdpr_chunks:
            sample = gdpr_chunks[0]
            print(f"\nSample chunk:")
            print(f"  ID: {sample.chunk_id}")
            print(f"  Type: {sample.chunk_type}")
            print(f"  Words: {sample.word_count}")
            print(f"  Content preview: {sample.content[:200]}...")
    
    # Parse and chunk HIPAA document
    hipaa_path = "policy_corpus/output/hipaa-simplification-201303/hipaa-simplification-201303.md"
    if Path(hipaa_path).exists():
        logger.info("Processing HIPAA document...")
        hipaa_sections = parser.parse_document(hipaa_path, DocumentType.HIPAA)
        hipaa_chunks = chunker.chunk_document_sections(hipaa_sections)
        
        print(f"\nHIPAA Processing Results:")
        print(f"  Sections: {len(hipaa_sections)}")
        print(f"  Chunks: {len(hipaa_chunks)}")


if __name__ == "__main__":
    main()
