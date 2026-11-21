<div align="center">

[![Unittests](https://github.com/squarebit-studios/nxt/actions/workflows/unittests.yml/badge.svg?branch=dev)](https://github.com/squarebit-studios/nxt/actions/workflows/unittests.yml?query=branch%3Adev)
[![Rez Release](https://github.com/squarebit-studios/nxt/actions/workflows/rez_release.yml/badge.svg?branch=release)](https://github.com/squarebit-studios/nxt/actions/workflows/rez_release.yml)

[![Version](https://img.shields.io/badge/version-0.22.0-green?logo=rocket&logoColor=green)](https://github.com/squarebit-studios/nxt/releases/latest)
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

**This repo is the nxt core, it does not come with a UI. If you're looking for the UI, please see [the nxt editor](https://github.com/squarebit-studios/nxt_editor).**
This package is designed for headless execution of graphs in a render farm or other headless environment.  
Only clone this repo if you're contributing to the NXT codebase.

<br>

#### Requirements

- Python [3.10](https://www.python.org/downloads/release/python-3100/) to [3.13](https://www.python.org/downloads/release/python-3130/)
- We strongly recommend using a Python [virtual environment](https://docs.python.org/3/library/venv.html)

*[Requirements for contributors](CONTRIBUTING.md#python-environment)*  

### NXT Python Core

Our releases are hosted on [PyPi](https://pypi.org/project/nxt-core/).

> **This is the Square Bit fork.** It is distributed internally as the
> `nxt_core` rez package, not from PyPI. Use the rez package inside the
> studio; it is tested against the python versions our hosts use.

**Install:**  
`pip install nxt-core`

**Execute Graph:**  

```python
import nxt
nxt.execute_graph('path/to/graph.nxt')
```

**Update:**  
`pip install -U nxt-core`

**Native speedups:**  
Releases carry a compiled module for Windows, macOS and Linux that makes
some of nxt's work faster. nxt gives the same results without it, so it
runs anywhere, and `NXT_NO_NATIVE=1` turns it off. In a checkout, build it
for your machine with [Rust](https://rustup.rs) installed:
`python native/build.py`

`NXT_COMP_ENGINE=native` composites graphs with the native module, two to
three times faster on big graphs, leaving exactly what the usual way does.
It is off by default while it is tried out. A comp it can't do, it hands
back to the usual way.

<br>

## Special Thanks

[Sunrise Productions](https://sunriseproductions.tv/) | [School of Visual Art and Design](https://www.southern.edu/visualartanddesign/)

