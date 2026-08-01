from pathlib import Path
from bs4 import BeautifulSoup

def shakespeare_loader(file_path: str):
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
        if speech.find("i") is None:
            speaker_tag = speech.find_previous("b")
            thisdic = {
                "speaker":speaker_tag.get_text(),
                "speech": speech.get_text(),
                "work": work,
                "act": act,
                "scene": scene}
            result.append(thisdic)
    return result