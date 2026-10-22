"""Optional structured-identifier masking, never advertised as full anonymization."""

import hashlib
import hmac
import re

IDENTIFIERS = {
    "name",
    "email",
    "address",
    "lei",
    "external_id",
    "sender",
    "receiver",
    "counterparty",
    "account_reference",
    "phone",
    "date_of_birth",
}
UNTOUCHED = {"chunk_id", "policy_id", "quote_id", "version", "source_url"}


def pseudonymize(value, key, scope):
    key = hmac.new(key, b"policylens:pseudonymization:v1", hashlib.sha256).digest()
    replacements = {}

    def alias(label, text):
        if label in {"name", "sender", "receiver", "counterparty"}:
            label = "entity"
        digest = hmac.new(
            key, (scope + ":" + label + ":" + text.casefold()).encode(), hashlib.sha256
        ).hexdigest()[:16]
        return "[" + label.upper() + "-" + digest + "]"

    def collect(node):
        if isinstance(node, dict):
            for label, child in node.items():
                if label in IDENTIFIERS and isinstance(child, str) and child.strip():
                    replacements[child] = alias(label, child)
                else:
                    collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    collect(value)
    pattern = (
        re.compile(
            "|".join(
                (r"(?<!\w)" if text[0].isalnum() else "")
                + re.escape(text)
                + (r"(?!\w)" if text[-1].isalnum() else "")
                for text in sorted(replacements, key=len, reverse=True)
            ),
            re.IGNORECASE,
        )
        if replacements
        else None
    )
    aliases = {text.casefold(): result for text, result in replacements.items()}

    def mask(node, label=""):
        if isinstance(node, dict):
            return {name: mask(child, name) for name, child in node.items()}
        if isinstance(node, list):
            return [mask(child, label) for child in node]
        if isinstance(node, str):
            if label in UNTOUCHED:
                return node
            if label == "notes":
                return "[PRIVATE NOTES OMITTED]" if node else ""
            if label in IDENTIFIERS and node:
                return alias(label, node)
            return (
                pattern.sub(lambda match: aliases[match.group().casefold()], node)
                if pattern
                else node
            )
        return node

    return mask(value)
