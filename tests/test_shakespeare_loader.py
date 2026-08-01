from src.shakespeare_loader import shakespeare_loader

TEST_FILE = (
    r"C:\Users\kiana\Documents\GitHub\shakespeare"
    r"\hamlet\hamlet.3.1.html"
)

def test_shakespeare_loader_returns_speeches():
    result = shakespeare_loader(TEST_FILE)

    assert isinstance(result, list)
    assert len(result) > 0


def test_shakespeare_loader_extracts_metadata():
    result = shakespeare_loader(TEST_FILE)
    first_speech = result[0]

    assert first_speech["work"] == "hamlet"
    assert first_speech["act"] == 3
    assert first_speech["scene"] == 1


def test_shakespeare_loader_extracts_speaker_and_speech():
    result = shakespeare_loader(TEST_FILE)
    first_speech = result[0]

    assert "speaker" in first_speech
    assert "speech" in first_speech

    assert isinstance(first_speech["speaker"], str)
    assert isinstance(first_speech["speech"], str)

    assert first_speech["speaker"].strip() != ""
    assert first_speech["speech"].strip() != ""


def test_shakespeare_loader_extracts_expected_first_speaker():
    result = shakespeare_loader(TEST_FILE)
    first_speech = result[0]

    assert first_speech["speaker"] == "KING CLAUDIUS"


def test_shakespeare_loader_excludes_stage_directions():
    result = shakespeare_loader(TEST_FILE)

    speeches = [item["speech"] for item in result]

    assert not any(
        "Enter KING CLAUDIUS" in speech
        for speech in speeches
    )