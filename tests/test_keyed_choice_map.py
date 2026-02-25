import pytest
from strictyaml.exceptions import YAMLSerializationError, YAMLValidationError
from strictyaml.yamllocation import YAMLChunk
from strictyaml.ruamel.comments import CommentedMap

from strictyamlx import (
    Case,
    Control,
    DMap,
    ForwardRef,
    Int,
    KeyedChoiceMap,
    Map,
    MapPattern,
    Seq,
    Str,
    as_document,
    load,
)


def test_keyed_choice_map_default_exactly_one():
    schema = KeyedChoiceMap(
        choices=[
            ("eq", Str()),
            ("in", Seq(Str())),
        ],
    )

    doc = load("eq: hello", schema)
    assert doc.data == {"eq": "hello"}

    with pytest.raises(YAMLValidationError, match="minimum of 1 choice key"):
        schema(YAMLChunk(CommentedMap({})))

    with pytest.raises(YAMLValidationError, match="maximum of 1 choice key"):
        load("eq: hello\nin:\n  - a\n  - b", schema)

    with pytest.raises(YAMLValidationError, match="unexpected key"):
        load("nope: 1", schema)


def test_keyed_choice_map_allow_zero_or_one():
    schema = KeyedChoiceMap(
        choices=[
            ("eq", Str()),
            ("in", Seq(Str())),
        ],
        minimum_keys=0,
        maximum_keys=1,
    )

    doc = schema(YAMLChunk(CommentedMap({})))
    assert doc.data == {}

    doc2 = load("in:\n  - a\n  - b", schema)
    assert doc2.data == {"in": ["a", "b"]}


def test_keyed_choice_map_nested_values():
    inner = KeyedChoiceMap(choices=[("eq", Str())])
    outer = KeyedChoiceMap(choices=[("when", inner)])

    doc = load("when:\n  eq: x", outer)
    assert doc.data == {"when": {"eq": "x"}}


def test_keyed_choice_map_forwardref_value_validator():
    ref = ForwardRef()
    schema = KeyedChoiceMap(choices=[("node", ref)])
    ref.set(Map({"x": Int()}))

    doc = load("node:\n  x: 1", schema)
    assert doc.data == {"node": {"x": 1}}


def test_keyed_choice_map_to_yaml_roundtrip_smoke():
    schema = KeyedChoiceMap(choices=[("eq", Str()), ("in", Seq(Str()))])
    doc = as_document({"eq": "hello"}, schema)
    yaml_str = doc.as_yaml()
    assert "eq: hello" in yaml_str

    with pytest.raises(YAMLSerializationError):
        as_document({}, schema)

    with pytest.raises(YAMLSerializationError):
        as_document({"eq": "x", "in": ["a"]}, schema)


def test_keyed_choice_map_in_dmap_case_merge_preserves_minmax():
    schema = DMap(
        control=Control(Map({"type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: True,
                schema=KeyedChoiceMap(choices=[("eq", Str()), ("in", Seq(Str()))]),
            )
        ],
    )

    ok = load("type: A\neq: hello", schema)
    assert ok.data == {"type": "A", "eq": "hello"}

    with pytest.raises(YAMLValidationError, match="minimum of 1 choice key"):
        load("type: A", schema)

    with pytest.raises(YAMLValidationError, match="maximum of 1 choice key"):
        load("type: A\neq: hello\nin:\n  - a", schema)


def test_map_pattern_value_is_keyed_choice_map():
    predicate_value = KeyedChoiceMap(
        choices=[
            ("eq", Str()),
            ("in", Seq(Str())),
        ],
    )
    schema = Map(
        {
            "when": MapPattern(Str(), predicate_value),
        }
    )

    doc = load(
        """
when:
  language:
    eq: de
""",
        schema,
    )
    assert doc.data["when"]["language"]["eq"] == "de"


def test_keyed_choice_map_used_inside_control_map():
    schema = DMap(
        control=Control(
            Map(
                {
                    "meta": KeyedChoiceMap(choices=[("eq", Str()), ("in", Seq(Str()))]),
                }
            )
        ),
        blocks=[
            Case(
                when=lambda raw, ctrl: True,
                schema=Map({"payload": Int()}),
            )
        ],
    )

    doc = load(
        """
meta:
  eq: hello
payload: 1
""",
        schema,
    )
    assert doc.data["meta"]["eq"] == "hello"
    assert doc.data["payload"] == 1

    rendered = as_document({"meta": {"eq": "hello"}, "payload": 1}, schema).as_yaml()
    assert "meta:" in rendered
    assert "eq: hello" in rendered
