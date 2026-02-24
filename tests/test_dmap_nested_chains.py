from strictyamlx import Bool, Case, Control, DMap, Int, Map, Optional, Overlay, Str, as_document, load


def test_control_chain_nested_dmaps_parent_context_in_when_load_and_to_yaml():
    observed = []

    deep_control = DMap(
        control=Control(Map({"kind": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl, parents=None: (
                    observed.append(
                        {
                            "root_ctrl_is_none": parents[-2]["ctrl"] is None,
                            "root_raw_selector": parents[-2]["raw"]["meta"]["selector"],
                            "parent_selector": parents[-1]["ctrl"]["selector"],
                            "kind": ctrl["kind"],
                        }
                    )
                    or ctrl["kind"] == "leaf"
                ),
                schema=Map({"kind": Str(), "value": Int()}),
            )
        ],
    )

    control_inner = DMap(
        control=Control(Map({"selector": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["selector"] == "inner",
                schema=Map({"selector": Str(), "route": Str(), "deep": deep_control}),
            )
        ],
    )

    schema = DMap(
        control=Control(Map({"meta": control_inner})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["meta"]["route"] == "alpha",
                schema=Map({"meta": control_inner, "payload": Int()}),
            )
        ],
    )

    parsed = load(
        """
meta:
  selector: inner
  route: alpha
  deep:
    kind: leaf
    value: 7
payload: 1
""",
        schema,
    )
    assert parsed["payload"] == 1

    doc = as_document(
        {
            "meta": {
                "selector": "inner",
                "route": "alpha",
                "deep": {"kind": "leaf", "value": 7},
            },
            "payload": 1,
        },
        schema,
    )
    assert "payload: 1" in doc.as_yaml()

    assert len(observed) >= 2
    assert all(item["root_raw_selector"] == "inner" for item in observed)
    assert all(item["parent_selector"] == "inner" for item in observed)
    assert all(item["kind"] == "leaf" for item in observed)
    assert any(item["root_ctrl_is_none"] is True for item in observed)


def test_case_nested_dmap_receives_parent_ctrl_with_overlay_active():
    case_seen = []

    case_nested = DMap(
        control=Control(Map({"node_type": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl, parents=None: (
                    case_seen.append(parents[-1]["ctrl"]["mode"]) or True
                )
                and ctrl["node_type"] == "leaf",
                schema=Map({"node_type": Str(), "value": Int()}),
            )
        ],
    )

    schema = DMap(
        control=Control(Map({"mode": Str(), Optional("debug"): Bool()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["mode"] == "run",
                schema=Map(
                    {
                        "mode": Str(),
                        Optional("debug"): Bool(),
                        "node": case_nested,
                        Optional("trace_label"): Str(),
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: raw.get("debug") is True,
                schema=Map({Optional("trace_label"): Str()}),
            ),
        ],
    )

    parsed = load(
        """
mode: run
debug: true
node:
  node_type: leaf
  value: 5
trace_label: enabled
""",
        schema,
    )
    assert parsed["node"]["value"] == 5
    assert parsed["trace_label"] == "enabled"

    assert "run" in case_seen


def test_deep_constraint_in_control_chain_has_parent_vals():
    seen = []

    def deep_constraint(raw, ctrl, val, parents=None):
        seen.append(
            {
                "root_payload": parents[-2]["val"]["payload"],
                "inner_route": parents[-1]["val"]["route"],
                "deep_value": val["value"],
            }
        )
        return (
            parents[-2]["val"]["payload"] > 0
            and parents[-1]["val"]["route"] == "alpha"
            and val["value"] > 0
        )

    deep_control = DMap(
        control=Control(Map({"kind": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["kind"] == "leaf",
                schema=Map({"kind": Str(), "value": Int()}),
                constraints=[deep_constraint],
            )
        ],
    )

    control_inner = DMap(
        control=Control(Map({"selector": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["selector"] == "inner",
                schema=Map({"selector": Str(), "route": Str(), "deep": deep_control}),
            )
        ],
    )

    schema = DMap(
        control=Control(Map({"meta": control_inner})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["meta"]["route"] == "alpha",
                schema=Map({"meta": control_inner, "payload": Int()}),
            )
        ],
    )

    parsed = load(
        """
meta:
  selector: inner
  route: alpha
  deep:
    kind: leaf
    value: 9
payload: 4
""",
        schema,
    )
    assert parsed["meta"]["deep"]["value"] == 9
    assert len(seen) >= 1
    assert all(item == {"root_payload": 4, "inner_route": "alpha", "deep_value": 9} for item in seen)
