# NXT Python Core

**nxt** (**/ɛn·ɛks·ti/**) is a general purpose code compositor designed for rigging, scene assembly, and automation. (node execution tree)  
[Installation/Usage](#installationusage) | [Docs](https://nxt-dev.github.io/) | [Contributing](CONTRIBUTING.md) | [Licensing](LICENSE)

# Installation/Usage
**This repo is the nxt core, it does not come with a UI. If you're looking for the UI, please see [the nxt editor](https://github.com/nxt-dev/nxt_editor).**
This package is designed for headless execution of graphs in a render farm or other headless environment.  
Only clone this repo if you're contributing to the NXT codebase.

<br>

#### Requirements
- Python >= [2.7.*](https://www.python.org/download/releases/2.7) <= [3.7.*](https://www.python.org/download/releases/3.7)
- We strongly recommend using a Python [virtual environment](https://docs.python.org/3.7/tutorial/venv.html)

*[Requirements for contributors](CONTRIBUTING.md#python-environment)*  

### NXT Python Core
Our releases are hosted on [PyPi](https://pypi.org/project/nxt-editor/).

**Install:**  
`pip install nxt-core`

**Execute Graph:**  
```python
import nxt
nxt.execute_graph('path/to/graph.nxt')
```

**Update:**  
`pip install -U nxt-core`

<br>

## Special Thanks
[Sunrise Productions](https://sunriseproductions.tv/) | [School of Visual Art and Design](https://www.southern.edu/visualartanddesign/)

---

| Release | Dev |
| :---: | :---: |
| [![Build Status](https://travis-ci.com/nxt-dev/nxt.svg?token=rBRbAJTv2rq1c8WVEwGs&branch=release)](https://travis-ci.com/nxt-dev/nxt) | [![Build Status](https://travis-ci.com/nxt-dev/nxt.svg?token=rBRbAJTv2rq1c8WVEwGs&branch=dev)](https://travis-ci.com/nxt-dev/nxt) |

