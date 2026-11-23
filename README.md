<div align="center">

[![Release](https://github.com/nxt-dev/nxt/actions/workflows/release.yml/badge.svg?branch=release)](https://github.com/nxt-dev/nxt/actions/workflows/release.yml)
[![Unittests](https://github.com/nxt-dev/nxt/actions/workflows/unittests.yml/badge.svg?branch=dev)](https://github.com/nxt-dev/nxt/actions/workflows/unittests.yml?query=branch%3Adev)

[![Version](https://img.shields.io/badge/version-0.22.0-green?logo=rocket&logoColor=green)](https://github.com/nxt-dev/nxt/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)&nbsp;&nbsp;
![Linux](https://img.shields.io/badge/Linux-FCC624?style=flat&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/macOS-000000?style=flat&logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat)

![Python310](https://img.shields.io/badge/python-3.10-3776AB.svg?logo=python&logoColor=3776AB)
![Python311](https://img.shields.io/badge/python-3.11-3776AB.svg?logo=python&logoColor=3776AB)
![Python312](https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=3776AB)
![Python313](https://img.shields.io/badge/python-3.13-3776AB.svg?logo=python&logoColor=3776AB)

# NXT Python Core

</div>


**nxt** (**/ɛn·ɛks·ti/**) is a general purpose code compositor designed for rigging, scene assembly, and automation. (node execution tree)  
[Installation/Usage](#installationusage) | [Docs](https://nxt-dev.github.io/) | [Contributing](CONTRIBUTING.md) | [Licensing](LICENSE)

# Installation/Usage

**This repo is the nxt core, it does not come with a UI. If you're looking for the UI, please see [the nxt editor](https://github.com/nxt-dev/nxt_editor).**
This package is designed for headless execution of graphs in a render farm or other headless environment.  
Only clone this repo if you're contributing to the NXT codebase.

<br>

#### Requirements

- Python [3.10](https://www.python.org/downloads/release/python-3100/) to [3.13](https://www.python.org/downloads/release/python-3130/)
- We strongly recommend using a Python [virtual environment](https://docs.python.org/3/library/venv.html)

*[Requirements for contributors](CONTRIBUTING.md#python-environment)*  

### NXT Python Core

Our releases are hosted on [PyPi](https://pypi.org/project/nxt-core/).

**Install:**  
`pip install nxt-core`

**Execute Graph:**  

```python
import nxt
nxt.execute_graph('path/to/graph.nxt')
```

**Update:**  
`pip install -U nxt-core`

### The faster comp engine

nxt composites graphs with a compiled module written in Rust, two to three
times faster on big graphs, and finds tokens with it too. It leaves exactly
what nxt's Python code does, so it changes speed and nothing else. It is on
by default, and there is nothing to set up:

- `pip install nxt-core` and the Maya, Blender and Unreal zips carry it for
  Windows (x86_64), macOS (Intel and Apple silicon) and Linux (x86_64 and
  ARM64), for Python 3.10 to 3.13.
- An install from git builds it for your machine when
  [Rust](https://rustup.rs) is installed. Without Rust nxt installs and runs
  on its Python code.
- In a checkout, build it with `python native/build.py`, and again after
  pulling changes to `native/`.

`nxt --version` says which engine composites: `Comp native`, or
`Comp python` and why.

Wherever the module can't help, nxt uses its Python code instead, with the
same result:

- There is no build for the platform, it doesn't load, or it is from
  another version of nxt.
- It fails while working. nxt logs a warning once and uses the Python code
  for the rest of the session.
- A comp it doesn't do yet, such as a graph that has never been saved.

To turn it off, set `NXT_COMP_ENGINE=python` for compositing, or
`NXT_NO_NATIVE=1` for everything the module does.

<br>

## Special Thanks

[Sunrise Productions](https://sunriseproductions.tv/) | [School of Visual Art and Design](https://www.southern.edu/visualartanddesign/)

