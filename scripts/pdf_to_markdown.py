#!/usr/bin/env python3
"""
PDF to Markdown Conversion Script using Nanonets OCR

This script converts PDF files to structured markdown using the state-of-the-art
Nanonets OCR model from Hugging Face. It processes each PDF page and generates
clean markdown files suitable for RAG system ingestion.

Usage:
    python scripts/pdf_to_markdown.py [--input-dir INPUT] [--output-dir OUTPUT] [--gpu]
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional
import logging
from PIL import Image
import torch
from pdf2image import convert_from_path
from transformers import AutoTokenizer, AutoProcessor, AutoModelForImageTextToText

# Set transformers verbosity for detailed logging
os.environ["TRANSFORMERS_VERBOSITY"] = "info"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NanonetsOCRConverter:
    """
    PDF to Markdown converter using Nanonets OCR model.
    """
    
    def __init__(self, use_gpu: bool = True):
        """
        Initialize the Nanonets OCR model.
        
        Args:
            use_gpu: Whether to use GPU acceleration if available
        """
        logger.info("🔧 DEBUG: Starting NanonetsOCRConverter initialization...")
        
        self.model_path = "nanonets/Nanonets-OCR-s"
        logger.info(f"🔧 DEBUG: Model path set to: {self.model_path}")
        
        self.device = self._setup_device(use_gpu)
        logger.info(f"🔧 DEBUG: Device setup complete: {self.device}")
        
        logger.info(f"Loading Nanonets OCR model on {self.device}...")
        
        try:
            logger.info("🔧 DEBUG: Starting model download/load...")
            # Load model components
            self.model = AutoModelForImageTextToText.from_pretrained(
                self.model_path,
                torch_dtype="auto",
                device_map="auto" if self.device != "cpu" else None,
                trust_remote_code=True
            )
            logger.info("🔧 DEBUG: Model loaded from pretrained")
            
            if self.device != "cpu":
                logger.info(f"🔧 DEBUG: Moving model to {self.device}...")
                self.model = self.model.to(self.device)
                logger.info("🔧 DEBUG: Model moved to device")
            
            logger.info("🔧 DEBUG: Setting model to eval mode...")
            self.model.eval()
            logger.info("🔧 DEBUG: Model set to eval mode")
            
            logger.info("🔧 DEBUG: Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            logger.info("🔧 DEBUG: Tokenizer loaded")
            
            logger.info("🔧 DEBUG: Loading processor...")
            self.processor = AutoProcessor.from_pretrained(self.model_path)
            logger.info("🔧 DEBUG: Processor loaded")
            
            logger.info("✅ Nanonets OCR model loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load Nanonets OCR model: {e}")
            raise
    
    def _setup_device(self, use_gpu: bool) -> str:
        """Setup computation device."""
        if use_gpu and torch.cuda.is_available():
            device = "cuda"
            logger.info(f"🚀 Using GPU: {torch.cuda.get_device_name()}")
        else:
            device = "cpu"
            if use_gpu:
                logger.warning("⚠️ GPU requested but not available, using CPU")
            else:
                logger.info("💻 Using CPU")
        
        return device
    
    def pdf_to_images(self, pdf_path: Path, max_pages: int = None) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images.
        
        Args:
            pdf_path: Path to the PDF file
            max_pages: Maximum number of pages to process (None for all pages)
            
        Returns:
            List of PIL Images, one per page
        """
        logger.info(f"🔧 DEBUG: Starting PDF to images conversion for: {pdf_path.name}")
        logger.info(f"🔧 DEBUG: Max pages requested: {max_pages}")
        
        try:
            logger.info("🔧 DEBUG: Calling convert_from_path...")
            # Convert PDF to images (150 DPI for faster processing while maintaining readability)
            images = convert_from_path(
                pdf_path,
                dpi=150,  # Further reduced for faster processing
                fmt='RGB',
                first_page=1,
                last_page=max_pages if max_pages else None
            )
            logger.info(f"🔧 DEBUG: convert_from_path completed, got {len(images)} images")
            
            # Resize images if they're too large (optimize for OCR speed)
            logger.info("🔧 DEBUG: Starting image optimization...")
            optimized_images = []
            for i, img in enumerate(images):
                logger.info(f"🔧 DEBUG: Processing image {i+1}/{len(images)}, size: {img.width}x{img.height}")
                # Resize if width > 1500 pixels (keeps good quality but reduces processing time)
                if img.width > 1500:
                    logger.info(f"🔧 DEBUG: Resizing image {i+1} from {img.width}x{img.height}")
                    ratio = 1500 / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((1500, new_height), Image.Resampling.LANCZOS)
                    logger.info(f"🔧 DEBUG: Resized to {img.width}x{img.height}")
                optimized_images.append(img)
            
            logger.info(f"🔧 DEBUG: Image optimization complete")
            logger.info(f"✅ Converted and optimized {len(optimized_images)} pages to images")
            return optimized_images
            
        except Exception as e:
            logger.error(f"❌ Failed to convert PDF to images: {e}")
            raise
    
    def ocr_image_to_markdown(self, image: Image.Image, page_num: int = 1) -> str:
        """
        Convert a single image to markdown using Nanonets OCR.
        
        Args:
            image: PIL Image to process
            page_num: Page number for logging
            
        Returns:
            Markdown text extracted from the image
        """
        logger.info(f"🔧 DEBUG: Starting OCR processing for page {page_num}")
        logger.info(f"🔧 DEBUG: Image size: {image.width}x{image.height}")
        
        # OCR prompt optimized for policy documents
        prompt = """Extract the text from the above document as if you were reading it naturally. 
        Return the tables in markdown format. Return the equations in LaTeX representation. 
        If there is an image in the document and image caption is not present, add a small description 
        of the image inside the <img></img> tag; otherwise, add the image caption inside <img></img>. 
        Watermarks should be wrapped in brackets. Ex: <watermark>OFFICIAL COPY</watermark>. 
        Page numbers should be wrapped in brackets. Ex: <page_number>14</page_number>. 
        Prefer using ☐ and ☑ for check boxes. Focus on preserving the structure and hierarchy of 
        legal and policy documents."""
        
        try:
            logger.info(f"🔧 DEBUG: Preparing messages for page {page_num}...")
            # Prepare messages for the model
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in document OCR and formatting."},
                {"role": "user", "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ]},
            ]
            logger.info(f"🔧 DEBUG: Messages prepared for page {page_num}")
            
            logger.info(f"🔧 DEBUG: Applying chat template for page {page_num}...")
            # Apply chat template
            text = self.processor.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            logger.info(f"🔧 DEBUG: Chat template applied for page {page_num}, text length: {len(text)}")
            
            logger.info(f"🔧 DEBUG: Processing inputs for page {page_num}...")
            # Process inputs
            inputs = self.processor(
                text=[text], 
                images=[image], 
                padding=True, 
                return_tensors="pt"
            )
            logger.info(f"🔧 DEBUG: Inputs processed for page {page_num}")
            logger.info(f"🔧 DEBUG: Input tensor shapes: {[(k, v.shape if hasattr(v, 'shape') else type(v)) for k, v in inputs.items()]}")
            
            logger.info(f"🔧 DEBUG: Moving inputs to device {self.model.device} for page {page_num}...")
            inputs = inputs.to(self.model.device)
            logger.info(f"🔧 DEBUG: Inputs moved to device for page {page_num}")
            
            logger.info(f"🔧 DEBUG: Starting text generation for page {page_num}...")
            # Generate output with memory optimization
            with torch.no_grad():
                 # Clear cache before generation
                 if torch.cuda.is_available():
                     logger.info(f"🔧 DEBUG: Clearing CUDA cache for page {page_num}...")
                     torch.cuda.empty_cache()
                     logger.info(f"🔧 DEBUG: CUDA cache cleared for page {page_num}")
                 
                 logger.info(f"🔄 Generating text for page {page_num}...")
                 logger.info(f"🔧 DEBUG: About to call model.generate() for page {page_num}...")
                 
                 output_ids = self.model.generate(
                     **inputs,
                     max_new_tokens=2048,  # Further reduced for faster processing
                     do_sample=False,
                     pad_token_id=self.tokenizer.eos_token_id,
                     use_cache=True,
                     num_beams=1  # Use greedy decoding for speed
                 )
                 logger.info(f"🔧 DEBUG: model.generate() completed for page {page_num}")
                 logger.info(f"✅ Text generation complete for page {page_num}")
            
            logger.info(f"🔧 DEBUG: Starting output decoding for page {page_num}...")
            # Decode output
            generated_ids = [
                output_ids[len(input_ids):] 
                for input_ids, output_ids in zip(inputs.input_ids, output_ids)
            ]
            logger.info(f"🔧 DEBUG: Generated IDs extracted for page {page_num}")
            
            logger.info(f"🔧 DEBUG: Batch decoding for page {page_num}...")
            output_text = self.processor.batch_decode(
                generated_ids, 
                skip_special_tokens=True, 
                clean_up_tokenization_spaces=True
            )[0]
            logger.info(f"🔧 DEBUG: Batch decoding completed for page {page_num}, output length: {len(output_text)}")
            
            logger.info(f"✅ Successfully processed page {page_num}")
            return output_text.strip()
            
        except Exception as e:
            logger.error(f"❌ Failed to process page {page_num}: {e}")
            import traceback
            logger.error(f"🔧 DEBUG: Full traceback for page {page_num}: {traceback.format_exc()}")
            return f"<!-- OCR Error on page {page_num}: {str(e)} -->"
    
    def convert_pdf_to_markdown(self, pdf_path: Path, output_path: Path, max_pages: int = None) -> bool:
        """
        Convert entire PDF to markdown file.
        
        Args:
            pdf_path: Path to input PDF
            output_path: Path to output markdown file
            max_pages: Maximum number of pages to process (None for all pages)
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"🔧 DEBUG: Starting PDF to markdown conversion for {pdf_path.name}")
        logger.info(f"🔄 Converting {pdf_path.name} to markdown...")
        if max_pages:
            logger.info(f"📄 Processing first {max_pages} pages only")
        
        try:
            logger.info(f"🔧 DEBUG: Step 1 - Converting PDF to images...")
            # Convert PDF to images
            images = self.pdf_to_images(pdf_path, max_pages=max_pages)
            logger.info(f"🔧 DEBUG: Step 1 complete - Got {len(images)} images")
            
            logger.info(f"🔧 DEBUG: Step 2 - Setting up markdown content structure...")
            # Process each page
            markdown_content = []
            
            # Add document header
            markdown_content.append(f"# {pdf_path.stem}")
            markdown_content.append(f"*Source: {pdf_path.name}*")
            markdown_content.append(f"*Processed with Nanonets OCR*")
            markdown_content.append("")
            logger.info(f"🔧 DEBUG: Document header added to markdown content")
            
            logger.info(f"🔧 DEBUG: Step 3 - Starting OCR processing for {len(images)} pages...")
            for i, image in enumerate(images, 1):
                logger.info(f"🔧 DEBUG: === Processing page {i}/{len(images)} ===")
                logger.info(f"Processing page {i}/{len(images)}...")
                
                # Add page header for multi-page documents
                if len(images) > 1:
                    logger.info(f"🔧 DEBUG: Adding page header for page {i}")
                    markdown_content.append(f"## Page {i}")
                    markdown_content.append("")
                
                logger.info(f"🔧 DEBUG: About to start OCR for page {i}...")
                # OCR the page
                page_markdown = self.ocr_image_to_markdown(image, i)
                logger.info(f"🔧 DEBUG: OCR completed for page {i}, got {len(page_markdown)} characters")
                
                markdown_content.append(page_markdown)
                markdown_content.append("")  # Add spacing between pages
                logger.info(f"🔧 DEBUG: Page {i} content added to markdown")
            
            logger.info(f"🔧 DEBUG: Step 4 - Writing output file...")
            # Write to file
            full_markdown = "\n".join(markdown_content)
            logger.info(f"🔧 DEBUG: Full markdown assembled, total length: {len(full_markdown)} characters")
            
            logger.info(f"🔧 DEBUG: Writing to file: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_markdown)
            logger.info(f"🔧 DEBUG: File written successfully")
            
            logger.info(f"✅ Successfully converted {pdf_path.name} to {output_path.name}")
            logger.info(f"📊 Output size: {len(full_markdown)} characters")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to convert {pdf_path.name}: {e}")
            import traceback
            logger.error(f"🔧 DEBUG: Full traceback: {traceback.format_exc()}")
            return False


def main():
    """Main function to handle command line arguments and process PDFs."""
    parser = argparse.ArgumentParser(
        description="Convert PDFs to Markdown using Nanonets OCR"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="policy_corpus",
        help="Directory containing PDF files (default: policy_corpus)"
    )
    parser.add_argument(
        "--output-dir", 
        type=str,
        default="markdown_output",
        help="Directory to save markdown files (default: markdown_output)"
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Use GPU acceleration if available"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process a single PDF file instead of entire directory"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of pages to process per document (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Setup paths
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Initialize OCR converter
    try:
        converter = NanonetsOCRConverter(use_gpu=args.gpu)
    except Exception as e:
        logger.error(f"Failed to initialize OCR converter: {e}")
        return 1
    
    # Process files
    if args.file:
        # Process single file
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            return 1
        
        output_path = output_dir / f"{pdf_path.stem}.md"
        success = converter.convert_pdf_to_markdown(pdf_path, output_path, max_pages=args.max_pages)
        
        if success:
            logger.info("🎉 Single file conversion completed successfully!")
        else:
            logger.error("❌ Single file conversion failed!")
            return 1
    
    else:
        # Process entire directory
        if not input_dir.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return 1
        
        # Find all PDF files
        pdf_files = list(input_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {input_dir}")
            return 0
        
        logger.info(f"📁 Found {len(pdf_files)} PDF files to process")
        
        # Process each PDF
        successful = 0
        failed = 0
        
        for pdf_path in pdf_files:
            output_path = output_dir / f"{pdf_path.stem}.md"
            
            if converter.convert_pdf_to_markdown(pdf_path, output_path, max_pages=args.max_pages):
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
        
        if failed > 0:
            logger.warning(f"⚠️ {failed} files failed to convert")
            return 1
        else:
            logger.info("🎉 All files converted successfully!")
    
    return 0


if __name__ == "__main__":
    exit(main())
