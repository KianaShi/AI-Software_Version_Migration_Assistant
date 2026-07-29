from src.document_loader import load_document;

"""
Test the document loader.

This script verifies that the document loader can:
- Load TXT documents
- Load PDF documents
- Return a unified list[str] output
"""
print("TXT Test")
print(load_document("data/sample.txt"))

print("\nPDF Test")
print(load_document("data/sample.pdf"))