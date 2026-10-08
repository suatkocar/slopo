import tree_sitter_svelte
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, to_utf8
from slopo.indexing.parsing.lang import javascript, typescript

_LANGUAGE = Language(tree_sitter_svelte.language())
_PARSER = Parser(_LANGUAGE)
_TS_LANGS = {"ts", "typescript"}


def parse(source: bytes) -> list[CodeUnit]:
    source = to_utf8(source)
    tree = _PARSER.parse(source)
    units: list[CodeUnit] = []
    for script in _script_elements(tree.root_node):
        raw_text = next(
            (child for child in script.children if child.type == "raw_text"),
            None,
        )
        if raw_text is None:
            continue
        # Reuse the upstream JS/TS extraction, including comment stripping and
        # nested blocks. Translate script-relative lines back to the component.
        parser = typescript.parse if _is_typescript(script) else javascript.parse
        script_units = parser(source[raw_text.start_byte : raw_text.end_byte])
        for unit in script_units:
            unit.start_line += raw_text.start_point[0]
            unit.end_line += raw_text.start_point[0]
        units.extend(script_units)
    return units


def _script_elements(node: Node) -> list[Node]:
    # Instance and module scripts are siblings at the top level, but a <script>
    # can also sit inside <svelte:head> or similar, so recurse.
    if node.type == "script_element":
        return [node]
    return [s for child in node.children for s in _script_elements(child)]


def _is_typescript(script: Node) -> bool:
    start_tag = next((c for c in script.children if c.type == "start_tag"), None)
    if start_tag is None:
        return False
    for attribute in start_tag.children:
        if attribute.type != "attribute":
            continue
        name = attribute.child_by_field_name("name") or next(
            (c for c in attribute.children if c.type == "attribute_name"), None
        )
        if name is None or name.text is None or name.text.decode() != "lang":
            continue
        value = next(
            (
                v
                for c in attribute.children
                if c.type in {"quoted_attribute_value", "attribute_value"}
                for v in ([c] if c.type == "attribute_value" else c.children)
                if v.type == "attribute_value"
            ),
            None,
        )
        if value is not None and value.text is not None:
            return value.text.decode().strip().lower() in _TS_LANGS
    return False
