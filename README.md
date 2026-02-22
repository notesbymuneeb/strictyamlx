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
You can use a `ForwardRef` inside `DMap` case schemas to easily build deep recursive dynamic behavior:

```python
from strictyamlx import Map, Str, Int, load, Control, Case, DMap, ForwardRef

ref = ForwardRef()

schema = DMap(
    Control(Map({"type": Str()})),
    [
        Case(
            when=lambda raw, ctrl: ctrl["type"] == "node", 
            schema=Map({"value": Int(), "child": ref})
        ),
        Case(
            when=lambda raw, ctrl: ctrl["type"] == "leaf", 
            schema=Map({"value": Int()})
        ),
    ]
)

# Reference points to the DMap itself, allowing infinite nesting!
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
