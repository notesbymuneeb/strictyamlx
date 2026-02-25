from strictyamlx import (
    Any,
    Bool,
    Case,
    Control,
    DMap,
    Float,
    Int,
    KeyedChoiceMap,
    Map,
    MapPattern,
    Seq,
    Str,
    load,
)


def test_predicate_mappattern_with_nested_dmap_cases():
    predicate_schema = MapPattern(
        Str(),
        DMap(
            control=Control(Any()),
            blocks=[
                Case(
                    when=(lambda raw, ctrl: "eq" in raw),
                    schema=Map({"eq": Str() | Bool()}),
                ),
                Case(
                    when=(lambda raw, ctrl: "in" in raw),
                    schema=Map({"in": Seq(Str())}),
                ),
                Case(
                    when=(lambda raw, ctrl: "not_in" in raw),
                    schema=Map({"not_in": Seq(Str())}),
                ),
                Case(
                    when=(lambda raw, ctrl: "gt" in raw),
                    schema=Map({"gt": Int() | Float()}),
                ),
                Case(
                    when=(lambda raw, ctrl: "gte" in raw),
                    schema=Map({"gte": Int() | Float()}),
                ),
                Case(
                    when=(lambda raw, ctrl: "lt" in raw),
                    schema=Map({"lt": Int() | Float()}),
                ),
                Case(
                    when=(lambda raw, ctrl: "lte" in raw),
                    schema=Map({"lte": Int() | Float()}),
                ),
                Case(
                    when=(lambda raw, ctrl: "range" in raw),
                    schema=Map({"range": Map({"min": Int() | Float(), "max": Int() | Float()})}),
                ),
                Case(
                    when=(lambda raw, ctrl: "contains" in raw),
                    schema=Map({"contains": Str()}),
                ),
                Case(
                    when=(lambda raw, ctrl: "contains_any" in raw),
                    schema=Map({"contains_any": Seq(Str())}),
                ),
                Case(
                    when=(lambda raw, ctrl: "contains_all" in raw),
                    schema=Map({"contains_all": Seq(Str())}),
                ),
                Case(
                    when=(lambda raw, ctrl: "subset_of" in raw),
                    schema=Map({"subset_of": Seq(Str())}),
                ),
                Case(
                    when=(lambda raw, ctrl: "intersects" in raw),
                    schema=Map({"intersects": Seq(Str())}),
                ),
                Case(
                    when=(lambda raw, ctrl: "size" in raw),
                    schema=Map({"size": Map({"min": Int(), "max": Int()})}),
                ),
            ],
        ),
    )

    schema = Map(
        {
            "constraints": Map(
                {
                    "hard": Seq(
                        DMap(
                            control=Control(Map({"name": Str(), "when": predicate_schema})),
                            blocks=[
                                Case(
                                    when=(lambda raw, ctrl: "forbid" in raw),
                                    schema=Map({"forbid": predicate_schema}),
                                ),
                                Case(
                                    when=(lambda raw, ctrl: "require" in raw),
                                    schema=Map({"require": predicate_schema}),
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
    - name: "German requests cannot be angry"
      when:
        language:
          eq: de
      forbid:
        request_style:
          eq: angry
"""

    doc = load(yaml_data, schema)
    assert doc["constraints"]["hard"][0]["when"]["language"]["eq"] == "de"
    assert doc["constraints"]["hard"][0]["forbid"]["request_style"]["eq"] == "angry"


def test_predicate_mappattern_with_keyed_choice_map_value():
    predicate_value = KeyedChoiceMap(
        choices=[
            ("eq", Str() | Bool()),
            ("in", Seq(Str())),
            ("not_in", Seq(Str())),
            ("gt", Int() | Float()),
            ("gte", Int() | Float()),
            ("lt", Int() | Float()),
            ("lte", Int() | Float()),
            ("range", Map({"min": Int() | Float(), "max": Int() | Float()})),
        ],
    )
    predicate_schema = MapPattern(Str(), predicate_value)

    schema = Map(
        {
            "constraints": Map(
                {
                    "hard": Seq(
                        DMap(
                            control=Control(Map({"name": Str(), "when": predicate_schema})),
                            blocks=[
                                Case(
                                    when=(lambda raw, ctrl: "forbid" in raw),
                                    schema=Map({"forbid": predicate_schema}),
                                ),
                                Case(
                                    when=(lambda raw, ctrl: "require" in raw),
                                    schema=Map({"require": predicate_schema}),
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
    - name: "German requests cannot be angry"
      when:
        language:
          eq: de
      forbid:
        request_style:
          eq: angry
"""

    doc = load(yaml_data, schema)
    assert doc["constraints"]["hard"][0]["when"]["language"]["eq"] == "de"
    assert doc["constraints"]["hard"][0]["forbid"]["request_style"]["eq"] == "angry"
