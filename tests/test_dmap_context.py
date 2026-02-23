from strictyamlx import DMap, Control, Case
from strictyaml import Map, Str, Int, load
import pytest

def test_nested_dmap_context_with_parent():
    def check_parent(raw, ctrl, parents=None):
        if parents:
            parent_ctrl = parents[-1]['ctrl']
            return parent_ctrl['type'] == 'parent'
        return False

    schema = DMap(
        control=Control(Map({"type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["type"] == "parent",
                schema=Map({
                    "child": DMap(
                        control=Control(Map({"subtype": Str()})),
                        blocks=[
                            Case(
                                when=check_parent,
                                schema=Map({"value": Int()})
                            )
                        ]
                    )
                })
            )
        ]
    )

    yaml_data = """
    type: parent
    child:
      subtype: child_type
      value: 10
    """

    data = load(yaml_data, schema)
    assert data['child']['value'] == 10

def test_nested_dmap_context_with_parent_fail():
    def check_parent(raw, ctrl, parents=None):
        if parents:
            parent_ctrl = parents[-1]['ctrl']
            return parent_ctrl['type'] == 'other' # Should fail
        return False

    schema = DMap(
        control=Control(Map({"type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["type"] == "parent",
                schema=Map({
                    "child": DMap(
                        control=Control(Map({"subtype": Str()})),
                        blocks=[
                            Case(
                                when=check_parent,
                                schema=Map({"value": Int()})
                            )
                        ]
                    )
                })
            )
        ]
    )

    yaml_data = """
    type: parent
    child:
      subtype: child_type
      value: 10
    """

    with pytest.raises(Exception) as excinfo:
        load(yaml_data, schema)
    assert "none of the cases were true" in str(excinfo.value)


def test_nested_constraint_has_access_to_parent_val():
    def child_constraint(raw, ctrl, val, parents=None):
        if not parents:
            return False
        parent_val = parents[-1]["val"]
        return parent_val["type"] == "parent"

    schema = DMap(
        control=Control(Map({"type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["type"] == "parent",
                schema=Map(
                    {
                        "child": DMap(
                            control=Control(Map({"subtype": Str()})),
                            blocks=[
                                Case(
                                    when=lambda raw, ctrl: ctrl["subtype"] == "child_type",
                                    schema=Map({"value": Int()}),
                                    constraints=[child_constraint],
                                )
                            ],
                        )
                    }
                ),
            )
        ],
    )

    yaml_data = """
    type: parent
    child:
      subtype: child_type
      value: 10
    """

    data = load(yaml_data, schema)
    assert data["child"]["value"] == 10


def test_nested_constraint_parent_val_failure():
    def child_constraint(raw, ctrl, val, parents=None):
        if not parents:
            return False
        parent_val = parents[-1]["val"]
        return parent_val["type"] == "other"

    schema = DMap(
        control=Control(Map({"type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["type"] == "parent",
                schema=Map(
                    {
                        "child": DMap(
                            control=Control(Map({"subtype": Str()})),
                            blocks=[
                                Case(
                                    when=lambda raw, ctrl: ctrl["subtype"] == "child_type",
                                    schema=Map({"value": Int()}),
                                    constraints=[child_constraint],
                                )
                            ],
                        )
                    }
                ),
            )
        ],
    )

    yaml_data = """
    type: parent
    child:
      subtype: child_type
      value: 10
    """

    with pytest.raises(Exception) as excinfo:
        load(yaml_data, schema)
    assert "when evaluating DMap case constraints" in str(excinfo.value)


def test_when_parent_payload_is_consistent_for_load_and_to_yaml():
    observed = []

    def check_parent_shape(raw, ctrl, parents=None):
        if not parents:
            return False
        observed.append(tuple(sorted(parents[-1].keys())))
        parent_ctrl = parents[-1]["ctrl"]
        return parent_ctrl["type"] == "parent"

    schema = DMap(
        control=Control(Map({"type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["type"] == "parent",
                schema=Map(
                    {
                        "child": DMap(
                            control=Control(Map({"subtype": Str()})),
                            blocks=[
                                Case(
                                    when=check_parent_shape,
                                    schema=Map({"value": Int()}),
                                )
                            ],
                        )
                    }
                ),
            )
        ],
    )

    yaml_data = """
    type: parent
    child:
      subtype: child_type
      value: 10
    """

    parsed = load(yaml_data, schema)
    assert parsed["child"]["value"] == 10

    serialized = schema.to_yaml(
        {
            "type": "parent",
            "child": {"subtype": "child_type", "value": 10},
        }
    )
    assert serialized is not None

    # First call comes from load(), second call from to_yaml().
    assert observed == [("ctrl", "raw"), ("ctrl", "raw")]
