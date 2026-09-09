import pandas as pd
import pytest

from nextphase.profilers.detect import detect_modality


def test_detects_tabular_dataframe():
    df = pd.DataFrame({"age": [30, 40]})
    assert detect_modality(df) == "tabular"


def test_detects_tabular_dict():
    assert detect_modality({"age": 30}) == "tabular"


def test_detects_text_string():
    assert detect_modality("hello world") == "text"


def test_detects_text_list_of_strings():
    assert detect_modality(["hello", "world"]) == "text"


def test_raises_on_unrecognized_type():
    with pytest.raises(ValueError, match="Could not auto-detect modality"):
        detect_modality(object())


def test_raises_on_empty_list():
    with pytest.raises(ValueError):
        detect_modality([])
