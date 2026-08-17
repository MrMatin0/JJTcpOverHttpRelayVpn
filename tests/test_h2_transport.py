"""Regression tests for the HTTP/2 stream lifecycle."""

import ast
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "src" / "relay" / "h2_transport.py"


def test_stream_state_is_registered_before_headers_are_sent():
    """A fast peer must not be able to answer before dispatch state exists."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "_single_request"
    )
    registration = next(
        i for i, node in enumerate(method.body)
        if isinstance(node, ast.AsyncWith)
    )
    write_block = method.body[registration]
    names = [
        node for node in ast.walk(write_block)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "_streams"
            for target in node.targets
        )
    ]
    send_headers = next(
        node for node in ast.walk(write_block)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_headers"
    )
    assert names, "the stream must be inserted into _streams"
    assert max(n.lineno for n in names) < send_headers.lineno


def test_transport_has_explicit_h2_dependency_failure():
    source = SOURCE.read_text(encoding="utf-8")
    assert "HTTP/2 support requires the 'h2' package" in source
