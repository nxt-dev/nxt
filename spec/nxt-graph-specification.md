# NXT Graph Specification
# Introduction
TODO: Add introduction
## Technical Terminology
TODO: Add technical terminology for terms like "instance" or "token".

# Concepts
## Core
TODO: Explain that new implementations of NXT core API must adhere to this specification, but are not required to implement the editor nor provide all the API features of our current implementation.
### Stage
### Runtime
## Editor
The editor is a separate package which consumes the core API; it provides a user interface for creating and manipulating graphs. The editor is **not** part of the core API and is **not** part of this specification.

## Nodes
```json
"/node_name": {
    "comment": "This is a node comment",
    "attrs": {},
    "code": [],
    "enabled": true
}
```
### Comments
### Code
### Enabled
### Skip

## Attributes
### User Attributes
### Internal Attributes
### Types

## Reference Layers
### Aliases
### Colors

## Paths
TODO: Explain paths and why `/` and `.` became the standard separators.
### Node Paths
### Attribute Paths
### Layer Paths
### Relative Pathing


## Node Tress
### Roots
### Children
### Child Order
TODO: Explain the 6 months of work that went into child order and why it matters.

## Instances
### Instance Paths

## Tokens
### Resolvers

## Composition Arcs
TODO: The specifics about composition of full graphs.
### Special Cases
#### Code
#### Instance Path

## Metadata
TODO: Explain metadata, and it's supplemental role in the NXT system.
### Positions

# NXT File Format Specification
## JSON
TODO: .nxt is _just_ JSON
# JSON Schema
TODO: Add JSON Schema. Is that doable for our data?
## NXT Graph
```json
{
    "version": "1.15",
    "alias": "My Graph",
    "color": "#FF0000",
    "mute": false,
    "solo": false,
    "meta_data": {},
    "nodes": {
        "/node_name": {
          "comment": "This is a node comment",
          "instance": "",
          "child_order": [],
          "attrs": {},
          "code": [],
          "enabled": true,
          "start_point": false,
          "execute_in": "/start_node"
        }
    }
}
```
### Versioning
We do not support patch versions in the NXT Graph file format. We only support major and minor versions. We strongly recommend implementing backwards compatibility for all minor versions. We do not require backwards compatibility for major versions, although we have build it out of necessity for our own use cases.
### Required Fields
* Version
### Optional Fields
* Alias
* Color
* Mute
* Solo
* References
* Metadata (meta_data)
* Nodes
