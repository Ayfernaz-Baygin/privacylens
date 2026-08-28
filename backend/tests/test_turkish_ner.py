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