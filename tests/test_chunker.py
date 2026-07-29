from src.chunker import chunk_text

"""
Test the text chunker.

This script verifies that the text chunker can:

- Split text into chunks
- Preserve remaining text
- Handle edge cases
"""
def test_chunk_text_basic():
    lines = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G"
    ]
    result = chunk_text(lines)
    assert result == [
        "A B C D E",
        "F G"
    ]

def test_chunk_text_lessthan1():
    lines = [
        "A",
        "B",
        "C"
    ]
    result = chunk_text(lines)
    assert result == [
        "A B C"
    ]
    
def test_chunk_text_1chunk():
    lines = [
    "A",
    "B",
    "C",
    "D",
    "E"
    ]
    result = chunk_text(lines)
    assert result == [
        "A B C D E"
    ]
    
def test_chunk_text_empty():
    lines = []
    result = chunk_text(lines)
    assert result == []