from src.prompt_builder import build_prompt

"""
Test the prompt builder.

This script verifies that the prompt builder can:
- Include the user's question in the prompt
- Include retrieved climate technology context in the prompt
- Handle an empty context list
"""

def test_build_prompt_includes_question():
    question = "What renewable energy technologies are mentioned?"
    context_chunks = [
        "Solar Power includes photovoltaic cell efficiency improvements.",
        "Wind Energy includes offshore wind turbine designs.",
    ]

    prompt = build_prompt(question, context_chunks)

    assert question in prompt
    


def test_build_prompt_includes_context_chunks():
    question = "What renewable energy technologies are mentioned?"
    context_chunks = [
        "Solar Power includes photovoltaic cell efficiency improvements.",
        "Wind Energy includes offshore wind turbine designs.",
    ]

    prompt = build_prompt(question, context_chunks)

    assert context_chunks[0] in prompt
    assert context_chunks[1] in prompt
    assert "\n".join(context_chunks) in prompt


def test_build_prompt_with_empty_context():
    question = "What renewable energy technologies are mentioned?"

    prompt = build_prompt(question, [])

    assert isinstance(prompt, str)
    assert question in prompt