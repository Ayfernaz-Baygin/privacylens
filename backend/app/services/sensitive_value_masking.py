import re


WORD_BASED_TYPES = {
    "PERSON",
    "LOCATION",
    "ORGANIZATION",
}

IDENTIFIER_TYPES = {
    "PHONE",
    "IBAN",
    "CARD_NUMBER",
}

EMAIL_LOCAL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+")
EMAIL_DOMAIN_LABEL_PATTERN = re.compile(r"[A-Za-z0-9-]+")


def _mask_short_part(part: str) -> str:
    if len(part) <= 2:
        return "*" * len(part)

    return part[0] + "*" * (len(part) - 2) + part[-1]


def _mask_words(value: str) -> str:
    return re.sub(r"\S+", lambda match: _mask_short_part(match.group()), value)


def _mask_alphanumeric(
    value: str,
    preserve_outer: bool,
) -> str:
    meaningful_indexes = [
        index
        for index, character in enumerate(value)
        if character.isalnum()
    ]

    visible_indexes = set()

    if preserve_outer and len(meaningful_indexes) >= 2:
        visible_indexes = {
            meaningful_indexes[0],
            meaningful_indexes[-1],
        }

    return "".join(
        (
            character
            if not character.isalnum() or index in visible_indexes
            else "*"
        )
        for index, character in enumerate(value)
    )


def _is_valid_email_structure(value: str) -> bool:
    if value.count("@") != 1:
        return False

    local_part, domain = value.split("@")
    domain_labels = domain.split(".")

    if (
        not EMAIL_LOCAL_PATTERN.fullmatch(local_part)
        or len(domain_labels) < 2
        or any(not label for label in domain_labels)
    ):
        return False

    return all(
        EMAIL_DOMAIN_LABEL_PATTERN.fullmatch(label)
        and not label.startswith("-")
        and not label.endswith("-")
        for label in domain_labels
    )


def _mask_email(value: str) -> str:
    if not _is_valid_email_structure(value):
        return "*" * len(value)

    local_part, domain = value.split("@")
    domain_labels = domain.split(".")
    masked_domain_labels = [
        _mask_short_part(label)
        for label in domain_labels[:-1]
    ]
    masked_domain_labels.append(domain_labels[-1])

    return (
        _mask_short_part(local_part)
        + "@"
        + ".".join(masked_domain_labels)
    )


def mask_sensitive_value(value: str, finding_type: str) -> str:
    """Return a deterministic, format-independent display mask."""
    if finding_type == "TCKN":
        return "*" * len(value)

    if finding_type in WORD_BASED_TYPES:
        return _mask_words(value)

    if finding_type in IDENTIFIER_TYPES:
        return _mask_alphanumeric(value, preserve_outer=True)

    if finding_type == "EMAIL":
        return _mask_email(value)

    return _mask_alphanumeric(value, preserve_outer=False)
