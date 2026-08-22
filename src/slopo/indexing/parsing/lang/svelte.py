import tree_sitter_javascript
import tree_sitter_svelte
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Range

from slopo.indexing.parsing.base import CodeUnit, hash_body

_LANGUAGE = Language(tree_sitter_svelte.language())
_PARSER = Parser(_LANGUAGE)

# A .svelte file is markup with embedded script. The Svelte grammar leaves the
# contents of a <script> element as one opaque `raw_text` token, so the script
# is re-parsed with the JS/TS grammar restricted to that byte range. Parsing the
# original source through `included_ranges` (rather than a slice) keeps every
# line, column and byte offset absolute, so units carry .svelte line numbers.
_JS_PARSER = Parser(Language(tree_sitter_javascript.language()))
_TS_PARSER = Parser(Language(tree_sitter_typescript.language_typescript()))

_TS_LANGS = {"ts", "typescript"}

_COMMENT_TYPES = {"comment"}

_UNIT_TYPES = {
    "function_declaration",
    "generator_function_declaration",
    "method_definition",
    "arrow_function",
    "function_expression",
}


def parse(source: bytes) -> list[CodeUnit]:
    tree = _PARSER.parse(source)
    units: list[CodeUnit] = []
    for script in _script_elements(tree.root_node):
        raw_text = next(
            (c for c in script.children if c.type == "raw_text"),
            None,
        )
        if raw_text is None:  # <script src="..."> or an empty block
            continue
        parser = _TS_PARSER if _is_typescript(script) else _JS_PARSER
        parser.included_ranges = [
            Range(
                start_byte=raw_text.start_byte,
                end_byte=raw_text.end_byte,
                start_point=raw_text.start_point,
                end_point=raw_text.end_point,
            )
        ]
        _collect_units(parser.parse(source).root_node, source, units)
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


def _collect_units(node: Node, source: bytes, units: list[CodeUnit]) -> None:
    if node.type in _UNIT_TYPES:
        body = _body_without_comments(node, source)
        units.append(
            CodeUnit(
                name=_unit_name(node),
                body=body,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                body_node_count=_count_body_nodes(node),
                body_hash=hash_body(body),
            )
        )
    for child in node.children:
        _collect_units(child, source, units)


def _unit_name(node: Node) -> str:
    # Declarations and methods carry their own name. Arrow and function
    # expressions are anonymous, so the name comes from what they are bound to.
    name_node = node.child_by_field_name("name")
    if name_node is None and node.type in {"arrow_function", "function_expression"}:
        name_node = _binding_name_node(node)
    return name_node.text.decode() if (name_node and name_node.text) else "<unknown>"


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "variable_declarator":  # const f = () => ...
        return parent.child_by_field_name("name")
    if parent.type == "pair":  # { f: () => ... }
        return parent.child_by_field_name("key")
    if parent.type == "assignment_expression":  # x.f = () => ...
        left = parent.child_by_field_name("left")
        if left is not None and left.type == "member_expression":
            return left.child_by_field_name("property")
        return left
    return None


def _body_without_comments(unit: Node, source: bytes) -> str:
    comment_spans: list[tuple[int, int]] = []
    _collect_comment_spans(unit, comment_spans)

    pieces: list[bytes] = []
    cursor = unit.start_byte
    for start, end in sorted(comment_spans):
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor : unit.end_byte])
    return b"".join(pieces).decode()


def _collect_comment_spans(node: Node, spans: list[tuple[int, int]]) -> None:
    if node.type in _COMMENT_TYPES:
        spans.append((node.start_byte, node.end_byte))
        return
    for child in node.children:
        _collect_comment_spans(child, spans)


def _count_body_nodes(unit: Node) -> int:
    body = unit.child_by_field_name("body")
    if body is None:
        return 0
    return _count_named_nodes(body)


def _count_named_nodes(node: Node) -> int:
    count = 1 if node.is_named else 0
    for child in node.children:
        count += _count_named_nodes(child)
    return count
