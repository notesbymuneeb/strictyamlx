from strictyamlx import DMap, Control, Case
from strictyaml import Map, Str, Int, Seq, load
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
    assert "unexpected key not in schema 'value'" in str(excinfo.value)


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


def test_control_nested_dmap_deep_child_gets_parent_raw_and_partial_ctrl():
    observed = []

    deep_schema = DMap(
        control=Control(Map({"kind": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl, parents=None: (
                    observed.append(
                        {
                            "has_two_parents": bool(parents and len(parents) >= 2),
                            "root_ctrl": parents[-2]["ctrl"] if parents and len(parents) >= 2 else "missing",
                            "root_raw_selector": (
                                parents[-2]["raw"]["meta"]["selector"]
                                if parents and len(parents) >= 2
                                else "missing"
                            ),
                            "inner_ctrl_selector": (
                                parents[-1]["ctrl"]["selector"]
                                if parents and len(parents) >= 1 and parents[-1]["ctrl"] is not None
                                else "missing"
                            ),
                        }
                    )
                    or ctrl["kind"] == "leaf"
                ),
                schema=Map({"value": Int()}),
            )
        ],
    )

    control_inner = DMap(
        control=Control(Map({"selector": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["selector"] == "inner",
                schema=Map(
                    {
                        "mode": Str(),
                        "deep": deep_schema,
                    }
                ),
            )
        ],
    )

    schema = DMap(
        control=Control(Map({"meta": control_inner})),
        blocks=[
            Case(
                when=lambda raw, ctrl: observed.append(ctrl["meta"]["mode"]) or ctrl["meta"]["mode"] == "X",
                schema=Map({"meta": control_inner, "payload": Int()}),
            )
        ],
    )

    yaml_data = """
    meta:
      selector: inner
      mode: X
      deep:
        kind: leaf
        value: 7
    payload: 1
    """

    parsed = load(yaml_data, schema)
    assert parsed["payload"] == 1
    assert observed[0] == {
        "has_two_parents": True,
        "root_ctrl": None,
        "root_raw_selector": "inner",
        "inner_ctrl_selector": "inner",
    }
    assert observed[1] == "X"

    serialized = schema.to_yaml(
        {
            "meta": {
                "selector": "inner",
                "mode": "X",
                "deep": {"kind": "leaf", "value": 7},
            },
            "payload": 1,
        }
    )
    assert serialized["meta"]["selector"] == "inner"


def test_when_raw_is_local_node_in_sequence_items():
    schema = Map(
        {
            "constraints": Map(
                {
                    "hard": Seq(
                        DMap(
                            control=Control(Map({"name": Str(), "when": Str()})),
                            blocks=[
                                Case(
                                    when=lambda raw, ctrl: "forbid" in raw,
                                    schema=Map({"forbid": Str()}),
                                ),
                                Case(
                                    when=lambda raw, ctrl: "require" in raw,
                                    schema=Map({"require": Str()}),
                                ),
                            ],
                        )
                    )
                }
            )
        }
    )

    yaml_data = """
    constraints:
      hard:
        - name: test
          when: test
          forbid: test
        - name: test
          when: test
          require: test
    """

    parsed = load(yaml_data, schema)
    assert parsed["constraints"]["hard"][0]["forbid"] == "test"
    assert parsed["constraints"]["hard"][1]["require"] == "test"

