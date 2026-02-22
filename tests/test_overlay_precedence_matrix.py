from strictyamlx import Bool, Case, Control, DMap, Enum, Int, Map, Optional, Overlay, Str, load


def _schema_for_matrix_tests():
    return DMap(
        control=Control(
            Map(
                {
                    "kind": Str(),
                    "conflict": Str(),
                    "nested": Map({"winner": Str(), "control_only": Int()}),
                    Optional("ov1_on"): Bool(),
                    Optional("ov2_on"): Bool(),
                    Optional("ov1_only"): Int(),
                    Optional("ov2_only"): Int(),
                    Optional("case_only"): Int(),
                }
            )
        ),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["kind"] == "x",
                schema=Map(
                    {
                        "kind": Enum(["x"]),
                        "conflict": Enum(["case"]),
                        "nested": Map({"winner": Enum(["case"])}),
                        Optional("case_only"): Int(),
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: "ov1_on" in raw,
                schema=Map(
                    {
                        "conflict": Enum(["overlay1"]),
                        "nested": Map({"winner": Enum(["overlay1"])}),
                        Optional("ov1_only"): Int(),
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: "ov2_on" in raw,
                schema=Map(
                    {
                        "conflict": Enum(["overlay2"]),
                        "nested": Map({"winner": Enum(["overlay2"])}),
                        Optional("ov2_only"): Int(),
                    }
                ),
            ),
        ],
    )


def test_precedence_case_wins_over_overlay_and_control_on_shared_key():
    schema = _schema_for_matrix_tests()
    doc = load(
        """
kind: x
ov1_on: true
conflict: case
nested:
  winner: case
  control_only: 1
""",
        schema,
    )
    assert doc.data["conflict"] == "case"
    assert doc.data["nested"]["winner"] == "case"


def test_overlay_order_first_overlay_wins_when_case_missing_conflict_key():
    schema = DMap(
        control=Control(
            Map(
                {
                    "kind": Str(),
                    "conflict": Str(),
                    Optional("ov1_on"): Bool(),
                    Optional("ov2_on"): Bool(),
                }
            )
        ),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["kind"] == "x",
                schema=Map({"kind": Enum(["x"])}),
            ),
            Overlay(
                when=lambda raw, ctrl: "ov1_on" in raw,
                schema=Map({"conflict": Enum(["overlay1"])}),
            ),
            Overlay(
                when=lambda raw, ctrl: "ov2_on" in raw,
                schema=Map({"conflict": Enum(["overlay2"])}),
            ),
        ],
    )

    doc = load(
        """
kind: x
ov1_on: true
ov2_on: true
conflict: overlay1
""",
        schema,
    )
    assert doc.data["conflict"] == "overlay1"


def test_control_fills_missing_fields_not_defined_by_case_or_overlays():
    schema = _schema_for_matrix_tests()
    doc = load(
        """
kind: x
conflict: case
nested:
  winner: case
  control_only: 7
""",
        schema,
    )
    assert doc.data["nested"]["control_only"] == 7


def test_overlay_adds_optional_keys_when_active():
    schema = _schema_for_matrix_tests()
    doc = load(
        """
kind: x
ov1_on: true
conflict: case
nested:
  winner: case
  control_only: 9
ov1_only: 100
""",
        schema,
    )
    assert doc.data["ov1_only"] == 100
    assert "ov2_only" not in doc.data


def test_case_optional_keys_remain_allowed_with_active_overlays():
    schema = _schema_for_matrix_tests()
    doc = load(
        """
kind: x
ov1_on: true
ov2_on: true
conflict: case
nested:
  winner: case
  control_only: 2
case_only: 11
""",
        schema,
    )
    assert doc.data["case_only"] == 11
