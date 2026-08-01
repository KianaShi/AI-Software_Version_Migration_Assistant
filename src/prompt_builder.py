

def build_prompt(question: str, context_chunks: list[str]) -> str:
    """
    Build a formatted prompt for the language model.

    Args:
        question: The user's question.
        context_chunks: A list of retrieved text chunks.

    Returns: A formatted prompt.
    """
    context = "\n".join(context_chunks)
    prompt = f"""
    Answer the question using only the provided context.
    If the answer cannot be found in the context, say that you do not have enough information.
    Context:
    {context}
    Question:
    {question}
    Answer:
    """
    return prompt