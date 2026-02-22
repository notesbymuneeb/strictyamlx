import pytest
from strictyaml.exceptions import YAMLSerializationError, YAMLValidationError

from strictyamlx import (
    Bool,
    Case,
    Control,
    DMap,
    Enum,
    Int,
    Map,
    Optional,
    Overlay,
    Seq,
    Str,
    as_document,
    load,
)


def test_dmap_overlays_with_case_routing():
    schema = DMap(
        control=Control(
            validator=Enum(["simple", "advanced"]),
            source=("meta", "mode"),
        ),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl == "simple",
                schema=Map(
                    {
                        "meta": Map({"mode": Enum(["simple"])}),
                        "service": Map({"name": Str(), "port": Int()}),
                    }
                ),
            ),
            Case(
                when=lambda raw, ctrl: ctrl == "advanced",
                schema=Map(
                    {
                        "meta": Map({"mode": Enum(["advanced"])}),
                        "service": Map({"name": Str(), "ports": Seq(Int())}),
                        Optional("workers"): Int(),
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: ("debug" in raw and raw["debug"] is True),
                schema=Map(
                    {
                        Optional("debug"): Bool(),
                        Optional("log_level"): Enum(["debug", "info", "warn", "error"]),
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: "tls" in raw,
                schema=Map(
                    {
                        "tls": Map(
                            {
                                "enabled": Bool(),
                                Optional("cert_file"): Str(),
                                Optional("key_file"): Str(),
                            }
                        )
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: "metrics" in raw,
                schema=Map(
                    {
                        "metrics": Map(
                            {
                                "enabled": Bool(),
                                Optional("path"): Str(),
                            }
                        )
                    }
                ),
            ),
        ],
    )

    yaml_simple_base = """
meta:
  mode: simple
service:
  name: api
  port: 8080
"""

    yaml_simple_debug = """
meta:
  mode: simple
service:
  name: api
  port: 8080
debug: true
log_level: debug
"""

    yaml_advanced_base = """
meta:
  mode: advanced
service:
  name: api
  ports:
    - 8080
    - 8081
workers: 4
"""

    yaml_advanced_tls_metrics = """
meta:
  mode: advanced
service:
  name: api
  ports:
    - 8080
workers: 2
tls:
  enabled: true
  cert_file: /etc/certs/server.crt
  key_file: /etc/certs/server.key
metrics:
  enabled: true
  path: /metrics
"""

    doc1 = load(yaml_simple_base, schema)
    doc2 = load(yaml_simple_debug, schema)
    doc3 = load(yaml_advanced_base, schema)
    doc4 = load(yaml_advanced_tls_metrics, schema)

    assert doc1.data == {
        "meta": {"mode": "simple"},
        "service": {"name": "api", "port": 8080},
    }
    assert doc2.data == {
        "meta": {"mode": "simple"},
        "service": {"name": "api", "port": 8080},
        "debug": True,
        "log_level": "debug",
    }
    assert doc3.data == {
        "meta": {"mode": "advanced"},
        "service": {"name": "api", "ports": [8080, 8081]},
        "workers": 4,
    }
    assert doc4.data == {
        "meta": {"mode": "advanced"},
        "service": {"name": "api", "ports": [8080]},
        "workers": 2,
        "tls": {
            "enabled": True,
            "cert_file": "/etc/certs/server.crt",
            "key_file": "/etc/certs/server.key",
        },
        "metrics": {"enabled": True, "path": "/metrics"},
    }


def test_dmap_overlay_and_case_are_authoritative_over_control():
    schema = DMap(
        control=Control(
            validator=Map(
                {
                    "meta": Map({"mode": Str()}),
                    "service": Map({"name": Str()}),
                    Optional("debug"): Bool(),
                }
            )
        ),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["meta"]["mode"] == "simple",
                schema=Map(
                    {
                        "meta": Map({"mode": Enum(["simple"])}),
                        "service": Map({"name": Enum(["api"])}),
                    }
                ),
            ),
            Overlay(
                when=lambda raw, ctrl: "debug" in raw,
                schema=Map({Optional("debug"): Bool()}),
            ),
        ],
    )

    doc = load(
        """
meta:
  mode: simple
service:
  name: api
debug: true
""",
        schema,
    )
    assert doc.data == {
        "meta": {"mode": "simple"},
        "service": {"name": "api"},
        "debug": True,
    }


def test_dmap_overlay_constraints_are_enforced():
    schema = DMap(
        control=Control(Map({"mode": Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["mode"] == "dev",
                schema=Map({"mode": Enum(["dev"])}),
            ),
            Overlay(
                when=lambda raw, ctrl: "debug" in raw,
                schema=Map({Optional("debug"): Bool(), Optional("log_level"): Str()}),
                constraints=[lambda raw, ctrl, val: (not val.get("debug")) or ("log_level" in val)],
            ),
        ],
    )

    with pytest.raises(YAMLValidationError, match="overlay constraints"):
        load(
            """
mode: dev
debug: true
""",
            schema,
        )

    doc = load(
        """
mode: dev
debug: true
log_level: debug
""",
        schema,
    )
    assert doc.data == {"mode": "dev", "debug": True, "log_level": "debug"}


def test_dmap_to_yaml_applies_matching_overlays():
    schema = DMap(
        control=Control(Map({"mode": Enum(["simple"])})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["mode"] == "simple",
                schema=Map({"mode": Enum(["simple"]), "service": Map({"port": Int()})}),
            ),
            Overlay(
                when=lambda raw, ctrl: "debug" in raw,
                schema=Map({Optional("debug"): Bool(), Optional("log_level"): Str()}),
            ),
        ],
    )

    doc = as_document(
        {"mode": "simple", "service": {"port": 8080}, "debug": True, "log_level": "debug"},
        schema,
    )
    yaml_str = doc.as_yaml()
    assert "debug: yes" in yaml_str
    assert "log_level: debug" in yaml_str


def test_dmap_to_yaml_raises_on_multiple_true_cases():
    schema = DMap(
        control=Control(Map({"kind": Str()})),
        blocks=[
            Case(when=lambda raw, ctrl: True, schema=Map({"kind": Str()})),
            Case(when=lambda raw, ctrl: True, schema=Map({"kind": Str()})),
        ],
    )

    with pytest.raises(YAMLSerializationError, match="Multiple DMap cases"):
        as_document({"kind": "x"}, schema)
