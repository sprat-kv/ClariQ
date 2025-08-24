"""
Smart document parser for policy documents.

This module implements NLP-based parsing to extract structured content from
GDPR and HIPAA documents while preserving their hierarchical structure.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

import spacy
from spacy.lang.en import English

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    CCPA = "ccpa"


@dataclass
class DocumentSection:
    """Represents a structured section of a policy document."""
    content: str
    section_type: str  # e.g., 'recital', 'article', 'section', 'title'
    section_id: str    # e.g., '1', '160.101', 'I'
    title: str = ""
    parent_section: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PolicyDocumentParser:
    """
    Advanced parser for policy documents that preserves hierarchical structure.
    """
    
    def __init__(self):
        """Initialize the parser with NLP capabilities."""
        try:
            # Try to load the full English model
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback to basic English tokenizer
            logger.warning("en_core_web_sm not found, using basic tokenizer")
            self.nlp = English()
            self.nlp.add_pipe('sentencizer')
        
        # Document-specific patterns
        self.gdpr_patterns = self._init_gdpr_patterns()
        self.hipaa_patterns = self._init_hipaa_patterns()
    
    def _init_gdpr_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize GDPR-specific regex patterns."""
        return {
            'recital': re.compile(r'^\s*-\s*\((\d+)\)\s*(.*?)(?=^\s*-\s*\(\d+\)|^CHAPTER|^Article|\Z)', re.MULTILINE | re.DOTALL),
            'chapter': re.compile(r'^CHAPTER\s+([IVXLCDM]+)\s*(.*)$', re.MULTILINE),
            'article': re.compile(r'^Article\s+(\d+)\s*(.*)$', re.MULTILINE),
            'section': re.compile(r'^(\d+)\.\s*(.*)$', re.MULTILINE),
        }
    
    def _init_hipaa_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize HIPAA-specific regex patterns."""
        return {
            'part': re.compile(r'^PART\s+(\d+)[—\-]\s*(.*)$', re.MULTILINE),
            'subpart': re.compile(r'^SUBPART\s+([A-Z])[—\-]\s*(.*)$', re.MULTILINE),
            'section': re.compile(r'^§\s*(\d+\.\d+)\s+(.*)$', re.MULTILINE),
            'title': re.compile(r'^TITLE\s+([IVXLCDM]+)[—\-]\s*(.*)$', re.MULTILINE),
        }
    
    def detect_document_type(self, content: str) -> DocumentType:
        """
        Automatically detect the document type based on content patterns.
        
        Args:
            content: Raw document content
            
        Returns:
            Detected document type
        """
        content_lower = content.lower()
        
        # Check for GDPR indicators
        gdpr_indicators = ['general data protection regulation', 'gdpr', 'recital', 'whereas:']
        if any(indicator in content_lower for indicator in gdpr_indicators):
            return DocumentType.GDPR
        
        # Check for HIPAA indicators
        hipaa_indicators = ['hipaa', 'health insurance portability', 'administrative simplification']
        if any(indicator in content_lower for indicator in hipaa_indicators):
            return DocumentType.HIPAA
        
        # Check for CCPA indicators
        ccpa_indicators = ['california consumer privacy act', 'ccpa']
        if any(indicator in content_lower for indicator in ccpa_indicators):
            return DocumentType.CCPA
        
        # Default to GDPR if uncertain
        logger.warning("Could not detect document type, defaulting to GDPR")
        return DocumentType.GDPR
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Remove OCR artifacts
        text = re.sub(r'[^\w\s\-\(\)\[\].,;:!?\'\"\/\\]', ' ', text)
        
        # Clean up common OCR errors
        text = re.sub(r'\b\d+\|\s*', '', text)  # Remove line numbers like "123| "
        
        return text.strip()
    
    def extract_gdpr_sections(self, content: str) -> List[DocumentSection]:
        """
        Extract structured sections from GDPR document.
        
        Args:
            content: GDPR document content
            
        Returns:
            List of structured document sections
        """
        sections = []
        current_chapter = None
        
        # Extract recitals first
        recital_matches = self.gdpr_patterns['recital'].findall(content)
        for recital_num, recital_content in recital_matches:
            section = DocumentSection(
                content=self.clean_text(recital_content),
                section_type='recital',
                section_id=recital_num,
                title=f"Recital {recital_num}",
                metadata={
                    'document_type': 'gdpr',
                    'recital_number': int(recital_num),
                    'section_length': len(recital_content.split())
                }
            )
            sections.append(section)
        
        # Extract chapters and articles
        lines = content.split('\n')
        current_section_content = []
        current_section_info = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for chapter
            chapter_match = self.gdpr_patterns['chapter'].match(line)
            if chapter_match:
                # Save previous section if exists
                if current_section_info and current_section_content:
                    sections.append(self._create_section_from_content(
                        current_section_content, current_section_info, 'gdpr'
                    ))
                
                current_chapter = chapter_match.group(1)
                current_section_info = {
                    'type': 'chapter',
                    'id': current_chapter,
                    'title': chapter_match.group(2).strip(),
                    'parent': None
                }
                current_section_content = [line]
                continue
            
            # Check for article
            article_match = self.gdpr_patterns['article'].match(line)
            if article_match:
                # Save previous section if exists
                if current_section_info and current_section_content:
                    sections.append(self._create_section_from_content(
                        current_section_content, current_section_info, 'gdpr'
                    ))
                
                current_section_info = {
                    'type': 'article',
                    'id': article_match.group(1),
                    'title': article_match.group(2).strip(),
                    'parent': current_chapter
                }
                current_section_content = [line]
                continue
            
            # Add to current section content
            if current_section_info:
                current_section_content.append(line)
        
        # Add final section
        if current_section_info and current_section_content:
            sections.append(self._create_section_from_content(
                current_section_content, current_section_info, 'gdpr'
            ))
        
        return sections
    
    def extract_hipaa_sections(self, content: str) -> List[DocumentSection]:
        """
        Extract structured sections from HIPAA document.
        
        Args:
            content: HIPAA document content
            
        Returns:
            List of structured document sections
        """
        sections = []
        current_part = None
        current_subpart = None
        
        lines = content.split('\n')
        current_section_content = []
        current_section_info = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for part
            part_match = self.hipaa_patterns['part'].match(line)
            if part_match:
                # Save previous section if exists
                if current_section_info and current_section_content:
                    sections.append(self._create_section_from_content(
                        current_section_content, current_section_info, 'hipaa'
                    ))
                
                current_part = part_match.group(1)
                current_section_info = {
                    'type': 'part',
                    'id': current_part,
                    'title': part_match.group(2).strip(),
                    'parent': None
                }
                current_section_content = [line]
                continue
            
            # Check for subpart
            subpart_match = self.hipaa_patterns['subpart'].match(line)
            if subpart_match:
                # Save previous section if exists
                if current_section_info and current_section_content:
                    sections.append(self._create_section_from_content(
                        current_section_content, current_section_info, 'hipaa'
                    ))
                
                current_subpart = subpart_match.group(1)
                current_section_info = {
                    'type': 'subpart',
                    'id': current_subpart,
                    'title': subpart_match.group(2).strip(),
                    'parent': current_part
                }
                current_section_content = [line]
                continue
            
            # Check for section
            section_match = self.hipaa_patterns['section'].match(line)
            if section_match:
                # Save previous section if exists
                if current_section_info and current_section_content:
                    sections.append(self._create_section_from_content(
                        current_section_content, current_section_info, 'hipaa'
                    ))
                
                current_section_info = {
                    'type': 'section',
                    'id': section_match.group(1),
                    'title': section_match.group(2).strip(),
                    'parent': f"{current_part}.{current_subpart}" if current_part and current_subpart else current_part
                }
                current_section_content = [line]
                continue
            
            # Add to current section content
            if current_section_info:
                current_section_content.append(line)
        
        # Add final section
        if current_section_info and current_section_content:
            sections.append(self._create_section_from_content(
                current_section_content, current_section_info, 'hipaa'
            ))
        
        return sections
    
    def _create_section_from_content(self, content_lines: List[str], section_info: Dict[str, Any], doc_type: str) -> DocumentSection:
        """
        Create a DocumentSection from content lines and section info.
        
        Args:
            content_lines: List of content lines
            section_info: Section metadata
            doc_type: Document type ('gdpr' or 'hipaa')
            
        Returns:
            DocumentSection object
        """
        content = '\n'.join(content_lines)
        cleaned_content = self.clean_text(content)
        
        # Calculate content metrics
        word_count = len(cleaned_content.split())
        sentence_count = len(list(self.nlp(cleaned_content).sents))
        
        metadata = {
            'document_type': doc_type,
            'word_count': word_count,
            'sentence_count': sentence_count,
            'section_length': len(cleaned_content)
        }
        
        # Add document-specific metadata
        if doc_type == 'gdpr':
            metadata['regulation'] = 'EU 2016/679'
        elif doc_type == 'hipaa':
            metadata['regulation'] = '45 CFR Parts 160, 162, and 164'
        
        return DocumentSection(
            content=cleaned_content,
            section_type=section_info['type'],
            section_id=section_info['id'],
            title=section_info['title'],
            parent_section=section_info.get('parent'),
            metadata=metadata
        )
    
    def parse_document(self, file_path: str, doc_type: Optional[DocumentType] = None) -> List[DocumentSection]:
        """
        Parse a policy document and extract structured sections.
        
        Args:
            file_path: Path to the document file
            doc_type: Optional document type (auto-detected if not provided)
            
        Returns:
            List of structured document sections
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []
        
        # Auto-detect document type if not provided
        if doc_type is None:
            doc_type = self.detect_document_type(content)
        
        logger.info(f"Parsing document as {doc_type.value.upper()}")
        
        # Parse based on document type
        if doc_type == DocumentType.GDPR:
            sections = self.extract_gdpr_sections(content)
        elif doc_type == DocumentType.HIPAA:
            sections = self.extract_hipaa_sections(content)
        else:
            logger.warning(f"Document type {doc_type} not fully implemented, using GDPR parser")
            sections = self.extract_gdpr_sections(content)
        
        logger.info(f"Extracted {len(sections)} sections from document")
        return sections


def main():
    """Example usage of the document parser."""
    parser = PolicyDocumentParser()
    
    # Parse GDPR document
    gdpr_path = "policy_corpus/output/GDPR/GDPR.md"
    if Path(gdpr_path).exists():
        gdpr_sections = parser.parse_document(gdpr_path, DocumentType.GDPR)
        print(f"GDPR sections extracted: {len(gdpr_sections)}")
        
        # Show sample section
        if gdpr_sections:
            sample = gdpr_sections[0]
            print(f"\nSample section:")
            print(f"Type: {sample.section_type}")
            print(f"ID: {sample.section_id}")
            print(f"Title: {sample.title}")
            print(f"Content preview: {sample.content[:200]}...")
    
    # Parse HIPAA document
    hipaa_path = "policy_corpus/output/hipaa-simplification-201303/hipaa-simplification-201303.md"
    if Path(hipaa_path).exists():
        hipaa_sections = parser.parse_document(hipaa_path, DocumentType.HIPAA)
        print(f"\nHIPAA sections extracted: {len(hipaa_sections)}")


if __name__ == "__main__":
    main()
