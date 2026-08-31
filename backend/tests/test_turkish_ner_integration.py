import pytest

from backend.app.services.turkish_ner import (
    detect_named_entities,
    get_ner_pipeline,
)

# Real, non-mocked integration tests for the Turkish NER model path
# (audit finding B4: the normal suite never exercises the actual
# Hugging Face model -- every other NER-dependent test monkeypatches
# detect_named_entities). These do not.
#
# Excluded from the default fast run:
#   python -m pytest -m "not slow"
# Run explicitly to exercise the real model:
#   python -m pytest -m slow
#
# The first invocation may download model weights from the Hugging
# Face Hub over the network (akdeniz27/bert-base-turkish-cased-ner, no
# pinned revision -- see turkish_ner.MODEL_NAME). Once downloaded, the
# weights are cached under the Hugging Face cache directory (typically
# ~/.cache/huggingface on Linux/macOS, %USERPROFILE%\.cache\huggingface
# on Windows) and later runs can work fully offline.


@pytest.mark.slow
def test_get_ner_pipeline_loads_the_real_pipeline():
    """Real tokenizer + model load, not mocked. Failing here means the
    model/tokenizer couldn't be loaded (network unavailable and not yet
    cached, or an incompatible transformers/torch version) -- not a
    detection-logic problem.
    """
    ner_pipeline = get_ner_pipeline()

    assert callable(ner_pipeline)


@pytest.mark.slow
def test_detect_named_entities_finds_person_in_simple_sentence():
    """Real pipeline inference on a simple, unambiguous Turkish
    sentence, run through the full detect_named_entities mapping (raw
    model output -> merged entities -> PrivacyLens PERSON/LOCATION/
    ORGANIZATION finding dicts).

    Deliberately one robust assertion (at least one PERSON finding) --
    not asserting on exact confidence values or the model's full token
    output, since those can shift slightly across transformers/torch
    versions without the integration actually being broken.
    """
    text = "Ahmet Yılmaz İstanbul'da çalışıyor."

    findings = detect_named_entities(text)

    assert any(
        finding["type"] == "PERSON" for finding in findings
    )
