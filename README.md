# strictyamlx
An extension of StrictYAML that adds more expressive schema tools for validation.

## Installation
```bash
pip install strictyamlx
```

## Features

### DMap (Dynamic Map)
`DMap` allows you to validate YAML where the schema of a map depends on the value of one or more of its keys.
It evaluates a "control" schema first, and uses its values to determine which `Case` schema applies. The final parsed object safely merges the validated control and case values.

Case matching rules:
- At most one `Case` can evaluate to `True`.
- Zero matching `Case` blocks is allowed; in that scenario, `DMap` validates with control + active overlays only.

```python
from strictyamlx import Map, Str, Int, load, Control, Case, DMap

# Control schema evaluates the "action" key to route the document
ctrl = Control(Map({"action": Str()}))

# Blocks conditionally apply a schema based on the evaluated control value
blocks = [
    Case(
        when=lambda raw, ctrl: ctrl["action"] == "message", 
        schema=Map({"text": Str()})
    ),
    Case(
        when=lambda raw, ctrl: ctrl["action"] == "transfer", 
        schema=Map({"amount": Int(), "to": Str()})
    ),
]

# Create the schema 
schema = DMap(ctrl, blocks)

# Validation merges the control ("action") and case schema values ("text")
yaml_str = """
action: message
text: Hello!
"""
doc = load(yaml_str, schema)
assert doc.data == {"action": "message", "text": "Hello!"}
```

#### Using `source` in Control
Sometimes the values needed to determine the schema aren't placed at the root of the document, but nested inside another key (like "metadata"). You can use `source` to define where the `Control` values should be drawn from:

```python
from strictyamlx import Map, Str, Int, load, Control, Case, DMap

# Evaluates the control values from the `meta` key
ctrl = Control(Map({"type": Str()}), source="meta")

blocks = [
    Case(
        when=lambda raw, ctrl: ctrl["type"] == "number", 
        schema=Map({"value": Int()})
    )
]

schema = DMap(ctrl, blocks)

yaml_str = """
meta:
  type: number
value: 42
"""
doc = load(yaml_str, schema)
assert doc.data == {"meta": {"type": "number"}, "value": 42}
```

#### Constraints
You can append constraints to `Case` blocks or globally on the `DMap`. Constraints are callables that validate the incoming data.

```python
Case(
    when=lambda raw, ctrl: ctrl["action"] == "transfer",
    schema=Map({"amount": Int(), "from": Str(), "to": Str()}),
    constraints=[
        lambda raw, ctrl, validated: validated["amount"] > 0,
        lambda raw, ctrl, validated: validated["from"] != validated["to"]
    ]
)
```

Constraint callbacks can use:
- `constraint(raw, ctrl, validated)` — no parent context
- `constraint(raw, ctrl, validated, parents=None)` — parent-aware

When `parents` is provided to constraints, each item is a dictionary with:
- `raw`: ancestor raw document
- `ctrl`: ancestor control projection
- `val`: ancestor validated value

Constraints are evaluated after schema validation, so parent `val` is available for nested `DMap` constraints.

#### Nesting DMaps
DMaps can nested to create complex state graphs. A `Case` block can even have another `DMap` as its schema!

```python
from strictyamlx import Map, Str, Int, Control, Case, DMap

inner_schema = DMap(
    Control(Map({"subkind": Str()})),
    [
        Case(when=lambda raw, ctrl: ctrl["subkind"] == "V1", schema=Map({"v1": Int()})),
        Case(when=lambda raw, ctrl: ctrl["subkind"] == "V2", schema=Map({"v2": Str()})),
    ]
)

schema = DMap(
    Control(Map({"kind": Str()})),
    [
        Case(when=lambda raw, ctrl: ctrl["kind"] == "complex", schema=inner_schema),
        Case(when=lambda raw, ctrl: ctrl["kind"] == "simple", schema=Map({"value": Str()})),
    ]
)
```

#### Parent context in nested `when`
Nested `when` clauses can inspect ancestor context with an optional `parents` argument:

```python
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
                            # Access parent control from the immediate parent.
                            when=lambda raw, ctrl, parents=None: (
                                parents
                                and parents[-1]["ctrl"]["type"] == "parent"
                                and ctrl["subtype"] == "V1"
                            ),
                            schema=Map({"v1": Int()}),
                        )
                    ],
                )
            }),
        )
    ],
)
```

For `when`, each `parents` item contains:
- `raw`
- `ctrl`

#### Parent context in nested constraints
Nested constraints can also read ancestor validated values:

```python
def child_constraint(raw, ctrl, val, parents=None):
    if not parents:
        return False
    parent_val = parents[-1]["val"]
    return parent_val["type"] == "parent" and val["value"] > 0

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
                            when=lambda raw, ctrl: ctrl["subtype"] == "child_type",
                            schema=Map({"value": Int()}),
                            constraints=[child_constraint],
                        )
                    ],
                )
            }),
        )
    ],
)
```

### Overlay Blocks
`Overlay` blocks allow you to conditionally apply schema fragments on top of your base `Case` schema. Unlike `Case` blocks (where only one can match), multiple `Overlay` blocks can be active at the same time.

Overlays are useful for features like debug flags, optional configurations (like TLS or metrics), or environment-specific settings that should only appear when certain conditions are met.

**Precedence:** `Case` > `Overlay` (in order) > `Control`. This means fields in the `Case` schema override overlays, and overlays override the control schema.

```python
from strictyamlx import Map, Str, Int, Bool, Enum, Optional, Seq, load, Control, Case, DMap, Overlay

schema = DMap(
    control=Control(
        validator=Enum(["simple", "advanced"]),
        source=("meta", "mode"),
    ),
    blocks=[
        # Base Case 1: Simple Mode
        Case(
            when=lambda raw, ctrl: ctrl == "simple",
            schema=Map({
                "meta": Map({"mode": Enum(["simple"])}),
                "service": Map({"name": Str(), "port": Int()}),
            }),
        ),
        # Base Case 2: Advanced Mode
        Case(
            when=lambda raw, ctrl: ctrl == "advanced",
            schema=Map({
                "meta": Map({"mode": Enum(["advanced"])}),
                "service": Map({"name": Str(), "ports": Seq(Int())}),
                Optional("workers"): Int(),
            }),
        ),
        # Overlay: Debug (applied if 'debug' is true)
        Overlay(
            when=lambda raw, ctrl: raw.get("debug") is True,
            schema=Map({
                Optional("debug"): Bool(),
                Optional("log_level"): Enum(["debug", "info", "warn", "error"]),
            }),
        ),
        # Overlay: TLS (applied if 'tls' key exists)
        Overlay(
            when=lambda raw, ctrl: "tls" in raw,
            schema=Map({
                "tls": Map({
                    "enabled": Bool(),
                    Optional("cert_file"): Str(),
                    Optional("key_file"): Str(),
                })
            }),
        ),
    ],
)

# Example 1: Simple mode with Debug overlay
yaml_simple_debug = """
meta:
  mode: simple
service:
  name: api
  port: 8080
debug: true
log_level: debug
"""
doc = load(yaml_simple_debug, schema)
assert doc.data["log_level"] == "debug"

# Example 2: Advanced mode with TLS overlay
yaml_advanced_tls = """
meta:
  mode: advanced
service:
  name: api
  ports: [8080, 8081]
workers: 4
tls:
  enabled: true
  cert_file: /etc/certs/server.crt
"""
doc = load(yaml_advanced_tls, schema)
assert doc.data["tls"]["enabled"] is True
```

### ForwardRef
`ForwardRef` defines recursive or mutually dependent schemas, letting you use a schema component before it is fully defined.

```python
from strictyamlx import Map, Str, Optional, Seq, load, ForwardRef

# 1. Create the reference
tree = ForwardRef()

# 2. Define the schema recursively and assign it using .set()
tree.set(Map({"name": Str(), Optional("children"): Seq(tree)}))

# 3. Validation handles recursive resolution automatically
yaml_str = """
name: root
children:
  - name: child
    children:
      - name: grandchild
"""
doc = load(yaml_str, tree)
```

#### DMaps with ForwardRef
You can use a `ForwardRef` inside `DMap` case schemas to build recursive dynamic behavior:

```python
from strictyamlx import Map, Str, Int, Optional, load, Control, Case, DMap, ForwardRef

ref = ForwardRef()

schema = DMap(
    Control(Map({"type": Str()})),
    [
        Case(
            when=lambda raw, ctrl: ctrl["type"] == "node", 
            schema=Map({"value": Int(), Optional("child"): ref})
        ),
        Case(
            when=lambda raw, ctrl: ctrl["type"] == "leaf", 
            schema=Map({"value": Int()})
        ),
    ]
)

# Reference points to the DMap itself
ref.set(schema)

yaml_str = """
type: node
value: 1
child:
  type: leaf
  value: 2
"""
doc = load(yaml_str, schema)
```
