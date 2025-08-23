#!/usr/bin/env python3
"""
Fast PDF to Markdown conversion using PyPDF2 text extraction.
Since all our PDFs have extractable text, this will be instant!
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import PyPDF2
import re
from typing import List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FastPDFToMarkdown:
    """Fast PDF to Markdown converter using text extraction."""
    
    def clean_text(self, text: str) -> str:
        """Clean and format extracted text."""
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces
        
        # Fix common PDF extraction issues
        text = text.replace('\x00', '')  # Remove null bytes
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Add spaces between words
        
        # Basic markdown formatting for headers (simple heuristic)
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Detect potential headers (all caps, short lines)
            if (len(line) < 100 and 
                line.isupper() and 
                not any(char.isdigit() for char in line[:10])):
                formatted_lines.append(f'## {line.title()}')
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF file."""
        
        logger.info(f"📄 Extracting text from {pdf_path.name}...")
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                total_pages = len(reader.pages)
                logger.info(f"📊 Processing {total_pages} pages...")
                
                all_text = []
                
                for i, page in enumerate(reader.pages, 1):
                    logger.info(f"   Processing page {i}/{total_pages}...")
                    
                    text = page.extract_text()
                    if text.strip():
                        # Add page separator for multi-page documents
                        if i > 1:
                            all_text.append(f"\n\n---\n*Page {i}*\n\n")
                        all_text.append(text)
                
                raw_text = ''.join(all_text)
                logger.info(f"✅ Extracted {len(raw_text)} characters")
                
                return raw_text
                
        except Exception as e:
            logger.error(f"❌ Failed to extract text from {pdf_path.name}: {e}")
            return f"<!-- Error extracting text: {str(e)} -->"
    
    def convert_pdf_to_markdown(self, pdf_path: Path, output_path: Path) -> bool:
        """Convert PDF to markdown file."""
        
        logger.info(f"🔄 Converting {pdf_path.name} to markdown...")
        
        try:
            # Extract text
            raw_text = self.extract_pdf_text(pdf_path)
            
            if not raw_text.strip():
                logger.warning(f"⚠️ No text extracted from {pdf_path.name}")
                return False
            
            # Clean and format text
            logger.info("🧹 Cleaning and formatting text...")
            clean_text = self.clean_text(raw_text)
            
            # Create markdown content
            markdown_content = []
            markdown_content.append(f"# {pdf_path.stem}")
            markdown_content.append(f"*Source: {pdf_path.name}*")
            markdown_content.append(f"*Extracted using PyPDF2*")
            markdown_content.append("")
            markdown_content.append(clean_text)
            
            full_markdown = "\n".join(markdown_content)
            
            # Write to file
            logger.info(f"💾 Writing to {output_path}...")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_markdown)
            
            logger.info(f"✅ Successfully converted {pdf_path.name}")
            logger.info(f"📊 Output: {len(full_markdown)} characters")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to convert {pdf_path.name}: {e}")
            return False

def main():
    """Main function."""
    
    parser = argparse.ArgumentParser(
        description="Fast PDF to Markdown conversion using text extraction"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="policy_corpus",
        help="Directory containing PDF files"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="markdown_output",
        help="Directory to save markdown files"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process single PDF file"
    )
    
    args = parser.parse_args()
    
    # Setup paths
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Initialize converter
    converter = FastPDFToMarkdown()
    
    logger.info("🚀 FAST PDF TO MARKDOWN CONVERSION")
    logger.info("Using PyPDF2 text extraction (instant processing!)")
    logger.info("=" * 50)
    
    if args.file:
        # Process single file
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            return 1
        
        output_path = output_dir / f"{pdf_path.stem}.md"
        success = converter.convert_pdf_to_markdown(pdf_path, output_path)
        
        if success:
            logger.info("🎉 Single file conversion completed!")
        else:
            logger.error("❌ Single file conversion failed!")
            return 1
    
    else:
        # Process directory
        if not input_dir.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return 1
        
        pdf_files = list(input_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {input_dir}")
            return 0
        
        logger.info(f"📁 Found {len(pdf_files)} PDF files")
        
        # Process each PDF
        successful = 0
        failed = 0
        
        for pdf_path in pdf_files:
            output_path = output_dir / f"{pdf_path.stem}.md"
            
            if converter.convert_pdf_to_markdown(pdf_path, output_path):
                successful += 1
            else:
                failed += 1
        
        # Summary
        logger.info("=" * 50)
        logger.info("📊 CONVERSION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total PDFs: {len(pdf_files)}")
        logger.info(f"✅ Successful: {successful}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"📁 Output directory: {output_dir}")
        
        if successful > 0:
            logger.info("🎉 Fast conversion completed!")
        
        return 1 if failed > 0 else 0

if __name__ == "__main__":
    exit(main())

