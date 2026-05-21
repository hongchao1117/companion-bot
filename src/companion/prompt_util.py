from __future__ import annotations


def safe_format(template: str, **kwargs: str) -> str:
    """format() that won't break if values contain { or }."""
    escaped = {k: v.replace("{", "{{").replace("}", "}}") for k, v in kwargs.items()}
    return template.format(**escaped)
