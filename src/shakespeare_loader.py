from pathlib import Path
from bs4 import BeautifulSoup

def shakespeare_loader(file_path: str):
    """
    Load a Shakespeare HTML scene and extract speeches with metadata.

    This loader:
    - Parses a Shakespeare HTML file using BeautifulSoup.
    - Extracts each character's speech from <blockquote> elements.
    - Removes stage directions enclosed in <i> tags.
    - Preserves dialogue while attaching metadata including
      speaker, work, act, and scene.

    Args:
        file_path: Path to a Shakespeare HTML scene.

    Returns:
        A list of dictionaries. Each dictionary contains:
        - speaker: Character name.
        - speech: Dialogue text.
        - work: Play name.
        - act: Act number.
        - scene: Scene number.
    """
    path = Path(file_path)

    parts = path.stem.split(".")

    work = parts[0]
    act = int(parts[1])
    scene = int(parts[2])
    
    if file_path.lower().endswith(".html"):
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                soup = BeautifulSoup(content, "html.parser")
            
    speeches = soup.find_all("blockquote")
    result = []
    for speech in speeches:
        speaker_tag = speech.find_previous("b")
        if speaker_tag is None:
            continue
        
        for stage_direction in speech.find_all("i"):
            stage_direction.decompose()
            
        speech_text = speech.get_text(" ", strip=True)
        
        if not speech_text:
            continue
        
        if speech.find("i") is None:
            speaker_tag = speech.find_previous("b")
            thisdic = {
                "speaker":speaker_tag.get_text(),
                "speech": speech_text,
                "work": work,
                "act": act,
                "scene": scene}
            result.append(thisdic)
    return result