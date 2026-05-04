"""Tests for document_parser.py — file-based parsing with temp files."""

import csv
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from document_parser import (
    _json_to_text,
    _xml_walk,
    parse_any,
    parse_csv,
    parse_json,
    parse_md,
    parse_xml,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_temp(content, suffix, mode="w", encoding="utf-8"):
    """Write content to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(
        mode=mode, suffix=suffix, delete=False, encoding=encoding if mode == "w" else None
    )
    f.write(content)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# _json_to_text tests
# ---------------------------------------------------------------------------
class TestJsonToText:
    def test_flat_dict(self):
        result = _json_to_text({"name": "Alice", "age": 30})
        assert "name: Alice" in result
        assert "age: 30" in result

    def test_nested_dict(self):
        result = _json_to_text({"user": {"name": "Bob"}})
        assert "user.name: Bob" in result

    def test_array(self):
        result = _json_to_text(["a", "b", "c"])
        assert "[0]: a" in result
        assert "[2]: c" in result

    def test_nested_array_in_dict(self):
        result = _json_to_text({"items": [1, 2, 3]})
        assert "items[0]: 1" in result

    def test_empty_dict(self):
        assert _json_to_text({}) == ""

    def test_empty_list(self):
        assert _json_to_text([]) == ""

    def test_scalar(self):
        assert "42" in _json_to_text(42)

    def test_none_value(self):
        result = _json_to_text({"key": None})
        assert "key: None" in result


# ---------------------------------------------------------------------------
# parse_json tests
# ---------------------------------------------------------------------------
class TestParseJson:
    def test_valid_json_file(self):
        path = _write_temp('{"skill": "Python", "level": 5}', ".json")
        try:
            result = parse_json(path)
            assert "skill: Python" in result
            assert "level: 5" in result
        finally:
            os.unlink(path)

    def test_malformed_json(self):
        path = _write_temp("{broken", ".json")
        try:
            result = parse_json(path)
            assert "[JSON parse error" in result
        finally:
            os.unlink(path)

    def test_empty_json_file(self):
        path = _write_temp("", ".json")
        try:
            result = parse_json(path)
            assert "[JSON parse error" in result
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# XML parsing tests
# ---------------------------------------------------------------------------
class TestParseXml:
    def test_simple_xml(self):
        xml_str = "<root><item>Hello</item><item>World</item></root>"
        path = _write_temp(xml_str, ".xml")
        try:
            result = parse_xml(path)
            assert "item: Hello" in result
            assert "item: World" in result
        finally:
            os.unlink(path)

    def test_xml_with_attributes(self):
        xml_str = '<root><skill name="Python" level="expert"/></root>'
        path = _write_temp(xml_str, ".xml")
        try:
            result = parse_xml(path)
            assert "name=Python" in result
        finally:
            os.unlink(path)

    def test_namespaced_xml(self):
        xml_str = '<ns:root xmlns:ns="http://example.com"><ns:item>Data</ns:item></ns:root>'
        path = _write_temp(xml_str, ".xml")
        try:
            result = parse_xml(path)
            assert "item: Data" in result  # namespace stripped
        finally:
            os.unlink(path)

    def test_malformed_xml(self):
        path = _write_temp("<broken><no_close>", ".xml")
        try:
            result = parse_xml(path)
            assert "[XML parse error" in result
        finally:
            os.unlink(path)


class TestXmlWalk:
    def test_extracts_text(self):
        root = ET.fromstring("<item>Hello</item>")
        lines = []
        _xml_walk(root, lines)
        assert any("Hello" in line for line in lines)

    def test_extracts_attributes(self):
        root = ET.fromstring('<item key="value"/>')
        lines = []
        _xml_walk(root, lines)
        assert any("key=value" in line for line in lines)


# ---------------------------------------------------------------------------
# parse_csv tests
# ---------------------------------------------------------------------------
class TestParseCsv:
    def test_simple_csv(self):
        path = _write_temp("name,age\nAlice,30\nBob,25\n", ".csv")
        try:
            result = parse_csv(path)
            assert "name | age" in result
            assert "Alice | 30" in result
        finally:
            os.unlink(path)

    def test_skips_empty_rows(self):
        path = _write_temp("a,b\n,,\nc,d\n", ".csv")
        try:
            result = parse_csv(path)
            lines = [l for l in result.split("\n") if l.strip()]
            assert len(lines) == 2  # header + data row, empty row skipped
        finally:
            os.unlink(path)

    def test_empty_csv(self):
        path = _write_temp("", ".csv")
        try:
            result = parse_csv(path)
            assert result == ""
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# parse_md tests
# ---------------------------------------------------------------------------
class TestParseMd:
    def test_reads_markdown_as_is(self):
        md = "# Title\n\nSome **bold** text.\n- Item 1\n- Item 2"
        path = _write_temp(md, ".md")
        try:
            result = parse_md(path)
            assert result == md
        finally:
            os.unlink(path)

    def test_empty_file(self):
        path = _write_temp("", ".md")
        try:
            assert parse_md(path) == ""
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# parse_any routing tests
# ---------------------------------------------------------------------------
class TestParseAny:
    def test_routes_json(self):
        path = _write_temp('{"key": "val"}', ".json")
        try:
            result = parse_any(path)
            assert "key: val" in result
        finally:
            os.unlink(path)

    def test_routes_xml(self):
        path = _write_temp("<root><item>data</item></root>", ".xml")
        try:
            result = parse_any(path)
            assert "data" in result
        finally:
            os.unlink(path)

    def test_routes_csv(self):
        path = _write_temp("a,b\n1,2\n", ".csv")
        try:
            result = parse_any(path)
            assert "1" in result
        finally:
            os.unlink(path)

    def test_routes_md(self):
        path = _write_temp("# Hello", ".md")
        try:
            result = parse_any(path)
            assert "# Hello" in result
        finally:
            os.unlink(path)

    def test_txt_falls_back(self):
        path = _write_temp("Plain text content", ".txt")
        try:
            result = parse_any(path)
            assert "Plain text content" in result
        finally:
            os.unlink(path)

    def test_unknown_extension_reads_text(self):
        path = _write_temp("Some content", ".xyz")
        try:
            result = parse_any(path)
            assert "Some content" in result
        finally:
            os.unlink(path)
