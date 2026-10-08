from pathlib import Path

import pytest

from slopo.indexing.parsing.lang import svelte
from slopo.indexing.parsing.registry import get_parser
from slopo.indexing.scan_filter import ScanFilter
from slopo.indexing.scanner import parse_file, scan_directory
from slopo.result.report.markdown.shared import lang_tag

FIXTURES = Path(__file__).parent / "fixtures"


def test_scans_and_parses_tsx_jsx_and_svelte(tmp_path: Path):
    sources = {
        "Increment.tsx": "function increment({ a }: { a: number }) { return <span>{a + 1}</span>; }",
        "Increment.jsx": "function increment({ a }) { return <span>{a + 1}</span>; }",
        "Increment.svelte": "<script>function increment(a) { return a + 1; }</script>",
    }
    for name, source in sources.items():
        (tmp_path / name).write_text(source)
    scan_filter = ScanFilter.create(exclude=[], include_extensions=[])

    assert set(scan_directory(tmp_path, scan_filter)) == set(sources)
    for name in sources:
        units = parse_file(tmp_path / name)
        assert len(units) == 1
        assert "increment" in (units[0].context or "")
        assert "a + 1" in units[0].body


@pytest.mark.parametrize(
    "fixture, second_context, second_body",
    [
        ("javascript/Component.jsx", "Card", '<div className="card">'),
        ("typescript/Component.tsx", "Farewell", "Goodbye"),
    ],
)
def test_component_fixtures_keep_both_declarations(
    fixture: str, second_context: str, second_body: str
):
    path = FIXTURES / fixture
    units = get_parser(path)(path.read_bytes())

    assert len(units) == 2
    assert "Greeting" in (units[0].context or "")
    assert second_context in (units[1].context or "")
    assert "Hello" in units[0].body
    assert second_body in units[1].body


def test_tsx_generic_arrow_keeps_type_parameters_and_template():
    path = FIXTURES / "typescript/GenericArrow.tsx"
    units = get_parser(path)(path.read_bytes())

    assert len(units) == 2
    assert units[0].context == "identity = <T,>(x: T): T =>"
    assert units[0].body == "x"
    assert units[0].start_line == 1
    assert units[1].kind == "block"
    assert units[1].context == "List = <T,>({ items }: { items: T[] }) =>"
    assert "<ul>" in units[1].body
    assert "<li>{items.length}</li>" in units[1].body
    assert units[1].start_line == 4
    assert units[1].end_line == 8


@pytest.mark.parametrize("lang", ['lang="ts"', "lang='typescript'", "lang=ts"])
def test_svelte_scripts_keep_typescript_context_and_absolute_lines(lang: str):
    source = (
        "<h1>Markup before scripts</h1>\n"
        '<script context="module">\n'
        "  function shared(x) { return x * 2; }\n"
        "</script>\n"
        f"<script {lang}>\n"
        "  // A comment before the function.\n"
        "  const scale = (x: number): number => {\n"
        "    // A comment in the body.\n"
        "    return shared(x);\n"
        "  };\n"
        "</script>\n"
        "<style>h1 { color: red; }</style>\n"
    ).encode()

    units = svelte.parse(source)

    assert len(units) == 2
    assert units[0].context == "function shared(x)"
    assert units[0].start_line == 3
    assert units[0].end_line == 3
    assert units[1].context == "scale = (x: number): number =>"
    assert units[1].start_line == 7
    assert units[1].end_line == 10
    assert units[1].body == "{\n\n  return shared(x);\n}"
    assert all(unit.kind == "function" for unit in units)


def test_svelte_reuses_upstream_block_extraction_and_comment_handling():
    source = b"""<script>
function valid(items) {
  for (const item of items) {
    // Keep original line positions.
    if (item.active) {
      save(item);
    }
  }
}
</script>"""

    units = svelte.parse(source)

    assert [unit.kind for unit in units] == ["function", "block", "block"]
    assert [unit.start_line for unit in units] == [2, 3, 5]
    assert [unit.end_line for unit in units] == [9, 8, 7]
    assert all("Keep original" not in unit.body for unit in units)


def test_svelte_skips_empty_external_and_markup_only_components():
    assert (
        svelte.parse(
            b'<script></script><script src="shared.js"></script><h1>Hello</h1>'
        )
        == []
    )


def test_svelte_handles_invalid_utf8_before_and_inside_script():
    units = svelte.parse(
        b'<p>\xff</p>\n<script>function text() { return "\xff"; }</script>'
    )

    assert len(units) == 1
    assert units[0].body == '{ return "\ufffd"; }'
    assert units[0].start_line == 2


@pytest.mark.parametrize("extension", ["tsx", "jsx", "svelte"])
def test_fork_report_language_tags(extension: str):
    assert lang_tag(f"Component.{extension}") == extension
