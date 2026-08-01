def chunk_text(lines: list[str], chunk_size: int = 5) -> list[str]:
    """
    Text Chunker
    Combine multiple lines into fixed-size chunks.
    
    Args: lines: A list of text lines.
          chunk_size: The number of lines in each chunk.
    Returns:
        A list of text chunks.
    """
    current_chunk = []
    result = []
    for line in lines:
        current_chunk.append(line)
        if len(current_chunk) == chunk_size:
            chunk = " ".join(current_chunk)
            result.append(chunk)
            current_chunk = []
    if current_chunk:
        chunk = " ".join(current_chunk)
        result.append(chunk)
    return result