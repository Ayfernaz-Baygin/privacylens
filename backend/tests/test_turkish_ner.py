from backend.app.services import turkish_ner
from backend.app.services.turkish_ner import (
    merge_adjacent_entities,
)


def test_merge_adjacent_person_entities():
    text = "Ayşe Yılmaz İstanbul"

    entities = [
        {
            "entity_group": "PER",
            "score": 0.98,
            "word": "Ayşe",
            "start": 0,
            "end": 4,
        },
        {
            "entity_group": "PER",
            "score": 0.67,
            "word": "Yılmaz",
            "start": 5,
            "end": 11,
        },
        {
            "entity_group": "LOC",
            "score": 0.99,
            "word": "İstanbul",
            "start": 12,
            "end": 20,
        },
    ]

    merged = merge_adjacent_entities(
        entities=entities,
        text=text,
    )

    assert len(merged) == 2

    assert merged[0]["entity_group"] == "PER"
    assert merged[0]["word"] == "Ayşe Yılmaz"

    assert merged[1]["entity_group"] == "LOC"
    assert merged[1]["word"] == "İstanbul"


def test_get_ner_pipeline_uses_pinned_model_name_and_revision(
    monkeypatch,
):
    """No real model download: AutoTokenizer/AutoModelForTokenClassification
    .from_pretrained and pipeline(...) are all monkeypatched, so this
    only verifies what MODEL_NAME/MODEL_REVISION get passed to them --
    not that the real weights load.
    """
    tokenizer_calls = []
    model_calls = []
    fake_tokenizer = object()
    fake_model = object()

    def fake_tokenizer_from_pretrained(
        model_name, revision=None, **kwargs
    ):
        tokenizer_calls.append((model_name, revision))
        return fake_tokenizer

    def fake_model_from_pretrained(
        model_name, revision=None, **kwargs
    ):
        model_calls.append((model_name, revision))
        return fake_model

    pipeline_calls = []

    def fake_pipeline(**kwargs):
        pipeline_calls.append(kwargs)
        return "fake-pipeline"

    monkeypatch.setattr(
        turkish_ner.AutoTokenizer,
        "from_pretrained",
        fake_tokenizer_from_pretrained,
    )
    monkeypatch.setattr(
        turkish_ner.AutoModelForTokenClassification,
        "from_pretrained",
        fake_model_from_pretrained,
    )
    monkeypatch.setattr(
        turkish_ner, "pipeline", fake_pipeline
    )

    turkish_ner.get_ner_pipeline.cache_clear()

    try:
        result = turkish_ner.get_ner_pipeline()
    finally:
        turkish_ner.get_ner_pipeline.cache_clear()

    assert result == "fake-pipeline"

    assert tokenizer_calls == [
        (turkish_ner.MODEL_NAME, turkish_ner.MODEL_REVISION)
    ]
    assert model_calls == [
        (turkish_ner.MODEL_NAME, turkish_ner.MODEL_REVISION)
    ]

    # Pinning the revision must not change any other pipeline wiring.
    assert pipeline_calls == [
        {
            "task": "ner",
            "model": fake_model,
            "tokenizer": fake_tokenizer,
            "aggregation_strategy": "first",
            "device": -1,
        }
    ]