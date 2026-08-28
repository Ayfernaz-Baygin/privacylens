from functools import lru_cache

from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    pipeline,
)


MODEL_NAME = "akdeniz27/bert-base-turkish-cased-ner"


ENTITY_TYPE_MAP = {
    "PER": "PERSON",
    "LOC": "LOCATION",
    "ORG": "ORGANIZATION",
}


@lru_cache(maxsize=1)
def get_ner_pipeline():
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME
    )

    return pipeline(
        task="ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="first",
        device=-1,
    )


def merge_adjacent_entities(
    entities: list[dict],
    text: str,
) -> list[dict]:
    if not entities:
        return []

    merged = []

    for entity in entities:
        normalized_entity = {
            "entity_group": entity["entity_group"],
            "score": float(entity["score"]),
            "word": entity["word"],
            "start": int(entity["start"]),
            "end": int(entity["end"]),
        }

        if not merged:
            merged.append(normalized_entity)
            continue

        previous = merged[-1]

        same_type = (
            previous["entity_group"]
            == normalized_entity["entity_group"]
        )

        gap = text[
            previous["end"]:
            normalized_entity["start"]
        ]

        adjacent = gap.strip() == ""

        if same_type and adjacent:
            previous["end"] = normalized_entity["end"]

            previous["word"] = text[
                previous["start"]:
                previous["end"]
            ]

            previous["score"] = min(
                previous["score"],
                normalized_entity["score"],
            )

        else:
            merged.append(normalized_entity)

    return merged


def detect_named_entities(text: str) -> list[dict]:
    ner_pipeline = get_ner_pipeline()

    raw_entities = ner_pipeline(text)

    entities = merge_adjacent_entities(
        entities=raw_entities,
        text=text,
    )

    findings = []

    for entity in entities:
        entity_group = entity["entity_group"]

        normalized_type = ENTITY_TYPE_MAP.get(
            entity_group
        )

        if normalized_type is None:
            continue

        findings.append(
            {
                "type": normalized_type,
                "value": text[
                    entity["start"]:
                    entity["end"]
                ],
                "start": entity["start"],
                "end": entity["end"],
                "confidence": entity["score"],
                "source": "ner_model",
            }
        )

    return findings