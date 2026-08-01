from pypdf import PdfReader

def load_document(file_path) -> list[str]:
    """
    Document Loader
    Support:
    - TXT
    - PDF

    Args: file_path: the file path.
    Output: A list of text lines.
    """
    if file_path.lower().endswith(".txt"):
        with open(file_path, encoding="utf-8") as f:
            lines = f.read().split("\n")
            result = [line.strip() for line in lines if line.strip() != ""]
            return result
    elif file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        result = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                lines = text.split("\n")
            result.extend(line.strip() for line in lines if line.strip() != "")
        return result
    else:
        raise ValueError("Unsupported file format")
