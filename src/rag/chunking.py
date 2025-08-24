import re
import json
from typing import List, Dict, Any

def clean_text(text: str) -> str:
    """A helper function to clean up the text content of a chunk."""
    # Replace multiple newlines with a single one
    text = re.sub(r'\n\s*\n', '\n', text)
    # Remove leading/trailing whitespace
    return text.strip()

def chunk_hipaa(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses and chunks the HIPAA document with proper metadata.
    Chunks are based on sections (§).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = []
    current_part = ""
    current_subpart = ""

    # Split the document by sections (§)
    # The regex keeps the delimiter (§ xxx.xxx) as part of the next chunk
    sections = re.split(r'(§ \d+\.\d+)', text)
    if not sections:
        return []

    # The first element is the content before the first section, which we can analyze for initial PART/Subpart
    header = sections[0]
    part_match = re.search(r'PART (\d+)', header)
    if part_match:
        current_part = part_match.group(1)
    subpart_match = re.search(r'Subpart ([A-Z])', header)
    if subpart_match:
        current_subpart = subpart_match.group(1)

    # Process each section
    for i in range(1, len(sections), 2):
        section_title = sections[i].strip()
        content = sections[i+1]

        # Check if the content for this section contains new PART or Subpart declarations
        part_match = re.search(r'PART (\d+)', content)
        if part_match:
            current_part = part_match.group(1)

        subpart_match = re.search(r'Subpart ([A-Z])', content)
        if subpart_match:
            current_subpart = subpart_match.group(1)

        chunk_text = f"{section_title}\n{content}"
        
        metadata = {
            'source': 'HIPAA',
            'part': current_part,
            'subpart': current_subpart,
            'section': section_title.replace('§ ', ''),
        }
        chunks.append({'page_content': clean_text(chunk_text), 'metadata': metadata})
        
    print(f"HIPAA chunks created: {len(chunks)}")
    return chunks

def chunk_gdpr(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses and chunks the GDPR document into Recitals and Articles.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chunks = []
    current_text = ""
    current_metadata = {}
    in_recital = False
    in_article = False

    for line in lines:
        # Check for start of a new Recital
        recital_match = re.match(r'-\s*\((\d+)\)', line)
        if recital_match:
            if current_text: # Save the previous chunk
                chunks.append({'page_content': clean_text(current_text), 'metadata': current_metadata})

            in_recital = True
            in_article = False
            recital_number = recital_match.group(1)
            current_metadata = {'source': 'GDPR', 'type': 'recital', 'recital': recital_number}
            current_text = line
            continue

        # Check for start of a new Chapter/Article
        chapter_match = re.match(r'CHAPTER\s+([A-Z]+)', line)
        article_match = re.match(r'Article\s+(\d+)', line)
        
        if chapter_match or article_match:
            if current_text: # Save the previous chunk
                 chunks.append({'page_content': clean_text(current_text), 'metadata': current_metadata})

            in_recital = False
            in_article = True
            current_text = line

            if chapter_match:
                current_metadata = current_metadata.copy() # Carry over GDPR source
                current_metadata['chapter'] = chapter_match.group(1)
            if article_match:
                 current_metadata = current_metadata.copy()
                 current_metadata['type'] = 'article'
                 current_metadata['article'] = article_match.group(1)
            continue
            
        if in_recital or in_article:
            current_text += line

    # Add the last chunk
    if current_text:
        chunks.append({'page_content': clean_text(current_text), 'metadata': current_metadata})

    print(f"GDPR chunks created: {len(chunks)}")
    return chunks

def save_chunks_to_json(chunks: List[Dict[str, Any]], file_path: str):
    """Saves a list of chunks to a JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2)
    print(f"Successfully saved {len(chunks)} chunks to {file_path}")

if __name__ == '__main__':
    # Define file paths relative to the Compliance-Aware-AI-Chatbot directory
    hipaa_file = 'policy_corpus/output/hipaa-simplification-201303/hipaa-simplification-201303.md'
    gdpr_file = 'policy_corpus/output/GDPR/GDPR.md'
    output_json_file = 'rag/chunks.json'
    
    hipaa_chunks = chunk_hipaa(hipaa_file)
    gdpr_chunks = chunk_gdpr(gdpr_file)
    
    all_chunks = hipaa_chunks + gdpr_chunks
    
    if all_chunks:
        save_chunks_to_json(all_chunks, output_json_file)
        
        print("\n--- Sample Chunk ---")
        print(json.dumps(all_chunks[0], indent=2))
        print("--------------------")
    else:
        print("No chunks were created. Please check the parsing logic and file paths.")
