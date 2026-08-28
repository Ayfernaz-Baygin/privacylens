import json
import re
from collections import defaultdict
from pathlib import Path

from backend.app.services.turkish_ner import detect_named_entities


DATASET_PATH = Path(
    "backend/evaluation/ner_samples.json"
)

THRESHOLDS = (
    0.00,
    0.40,
    0.50,
    0.60,
    0.70,
    0.80,
    0.90,
)


def normalize_entity_value(value: str) -> str:
    value = value.strip()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    value = value.rstrip(
        ".,;:!?"
    )

    return value


def entity_key(entity: dict) -> tuple[str, str]:
    return (
        entity["type"],
        normalize_entity_value(
            entity["value"]
        ),
    )


def calculate_metrics(
    true_positive: int,
    false_positive: int,
    false_negative: int,
) -> dict:
    precision_denominator = (
        true_positive + false_positive
    )

    recall_denominator = (
        true_positive + false_negative
    )

    precision = (
        true_positive / precision_denominator
        if precision_denominator
        else 0.0
    )

    recall = (
        true_positive / recall_denominator
        if recall_denominator
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_threshold(
    samples: list[dict],
    threshold: float,
) -> dict:
    true_positive = 0
    false_positive = 0
    false_negative = 0

    for sample in samples:
        expected = {
            entity_key(entity)
            for entity in sample["entities"]
        }

        predictions = detect_named_entities(
            sample["text"]
        )

        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["confidence"] >= threshold
        ]

        predicted = {
            entity_key(entity)
            for entity in filtered_predictions
        }

        true_positive += len(
            expected & predicted
        )

        false_positive += len(
            predicted - expected
        )

        false_negative += len(
            expected - predicted
        )

    metrics = calculate_metrics(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
    )

    return {
        "threshold": threshold,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        **metrics,
    }


def print_error_analysis(
    samples: list[dict],
    threshold: float,
) -> None:
    print()
    print("=" * 74)
    print(
        f"ERROR ANALYSIS - THRESHOLD {threshold:.2f}"
    )
    print("=" * 74)

    errors_found = False

    for index, sample in enumerate(
        samples,
        start=1,
    ):
        expected = {
            entity_key(entity)
            for entity in sample["entities"]
        }

        predictions = detect_named_entities(
            sample["text"]
        )

        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["confidence"] >= threshold
        ]

        predicted = {
            entity_key(entity)
            for entity in filtered_predictions
        }

        false_positives = predicted - expected
        false_negatives = expected - predicted

        if not false_positives and not false_negatives:
            continue

        errors_found = True

        print()
        print(f"Sample {index}")
        print(f"Text: {sample['text']}")

        if false_positives:
            print("False Positives:")

            for entity_type, value in sorted(false_positives):
                prediction = next(
                    item
                    for item in filtered_predictions
                    if entity_key(item)
                    == (entity_type, value)
                )

                print(
                    f"  + {entity_type}: {value}"
                    f" | confidence="
                    f"{prediction['confidence']:.4f}"
                )

        if false_negatives:
            print("False Negatives:")

            for entity_type, value in sorted(false_negatives):
                print(
                    f"  - {entity_type}: {value}"
                )

    if not errors_found:
        print("No errors found.")


def evaluate_per_type(
    samples: list[dict],
    threshold: float,
) -> None:
    stats = defaultdict(
        lambda: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
        }
    )

    for sample in samples:
        expected = {
            entity_key(entity)
            for entity in sample["entities"]
        }

        predictions = detect_named_entities(
            sample["text"]
        )

        predicted = {
            entity_key(prediction)
            for prediction in predictions
            if prediction["confidence"] >= threshold
        }

        for entity in expected & predicted:
            stats[entity[0]]["tp"] += 1

        for entity in predicted - expected:
            stats[entity[0]]["fp"] += 1

        for entity in expected - predicted:
            stats[entity[0]]["fn"] += 1

    print()
    print("=" * 74)
    print("PER-ENTITY METRICS")
    print("=" * 74)

    print(
        f"{'Entity':<18}"
        f"{'Precision':<12}"
        f"{'Recall':<12}"
        f"{'F1':<12}"
        f"{'TP':<6}"
        f"{'FP':<6}"
        f"{'FN':<6}"
    )

    print("-" * 74)

    for entity_type in sorted(stats):
        values = stats[entity_type]

        metrics = calculate_metrics(
            true_positive=values["tp"],
            false_positive=values["fp"],
            false_negative=values["fn"],
        )

        print(
            f"{entity_type:<18}"
            f"{metrics['precision']:<12.4f}"
            f"{metrics['recall']:<12.4f}"
            f"{metrics['f1']:<12.4f}"
            f"{values['tp']:<6}"
            f"{values['fp']:<6}"
            f"{values['fn']:<6}"
        )


def evaluate() -> None:
    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        samples = json.load(file)

    print()
    print("=" * 74)
    print("NER CONFIDENCE THRESHOLD EVALUATION")
    print("=" * 74)

    print(
        f"{'Threshold':<12}"
        f"{'Precision':<12}"
        f"{'Recall':<12}"
        f"{'F1':<12}"
        f"{'TP':<8}"
        f"{'FP':<8}"
        f"{'FN':<8}"
    )

    print("-" * 74)

    results = []

    for threshold in THRESHOLDS:
        result = evaluate_threshold(
            samples=samples,
            threshold=threshold,
        )

        results.append(result)

        print(
            f"{result['threshold']:<12.2f}"
            f"{result['precision']:<12.4f}"
            f"{result['recall']:<12.4f}"
            f"{result['f1']:<12.4f}"
            f"{result['true_positive']:<8}"
            f"{result['false_positive']:<8}"
            f"{result['false_negative']:<8}"
        )

    best_f1 = max(
        result["f1"]
        for result in results
    )

    best_results = [
        result
        for result in results
        if result["f1"] == best_f1
    ]

    best_threshold = max(
        result["threshold"]
        for result in best_results
    )

    print()
    print("=" * 74)

    print(
        "Best threshold by F1:",
        f"{best_threshold:.2f}",
    )

    print(
        "Best F1:",
        f"{best_f1:.4f}",
    )

    print_error_analysis(
        samples=samples,
        threshold=best_threshold,
    )

    evaluate_per_type(
        samples=samples,
        threshold=best_threshold,
    )


if __name__ == "__main__":
    evaluate()