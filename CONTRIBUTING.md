# Contributing to nxt

Instruction snippets for getting started contributing to nxt and its sub-components.

## Basic Tools

- Install git. ([Git - Downloads](https://git-scm.com/downloads))

- If you don't already have an IDE we suggest installing one of the following:

  - [Pycharm community](https://www.jetbrains.com/pycharm/download/)

  - [Visual Studio Code](https://code.visualstudio.com/download)

- Clone the nxt repository:

  - Find link on GitHub main page 'Clone'
  - From PyCharm
    - Paste the link in Pycharm VCS > Git > Clone
  - From git command line (git bash if you're on Windows)
    - `git clone <clone link>`

## Python Environment
The nxt environment is specified via `nxt_env.yml` to be used by a conda environment.  
Conda is best installed via [miniconda](https://docs.conda.io/en/latest/miniconda.html). We reccomend **not** adding conda python to your system path and **not** making it your system python.

- Windows

  - Launch the **Anaconda Prompt** and install dependencies:
    `conda env create -f PATH_TO_NXT_CLONE/nxt/nxt_env.yml`

- Linux/Mac

  - From the terminal run:
     `conda env create -f PATH_TO_NXT_CLONE/nxt/nxt_env.yml`

- Setting IDE interpeter

  - PyCharm:

    - If haven't done so already, open the nxt clone as a project.
    - Go to Settings > Project: nxt > Python Interpeter
    - Click the gear icon > Add
    - Select Conda Environment > Exsisting Environment
    - Make sure the Interpeter path points to the Python interpeter executable in your newly created conda `nxt` env.
    - Click OK and then Apply

  - vscode:

    - Run the command `Python: Select Interpreter`
    - Select the python that was created as part of your miniconda environment.

## Launching

- PyCharm:

  - Run > Edit Configurations...

  - Add New Configuration (`+` Icon at the top left) > Python

  - Change the drop down `Srcript Path` to `Module name`

  - In the `Module name:` field enter `nxt.cli`, it should autocomplete for you.

  - In the `Parameters:`  field enter `ui`, this tells the cli to open the visual application.

  - Make sure the `Python interpeter:` is correctly set to the conda env you setup in the [setup](#setup) steps.

- vscode

  - Add a launch configuration.

  - A template launch config:
    ```json
    {
    "name": "nxt",
    "type": "python",
    "request": "launch",
    "module": "nxt.cli",
    "args": ["ui"],
    "console": "integratedTerminal",
    "cwd": "${workspaceFolder}",
    "justMyCode": true
    }
      ```

## The native module

`native/` holds the Rust module behind the faster comp engine, see the
README. Each function has a Python twin in nxt that must give the same
result, down to which objects are the same. A change to one is a change to
both.

- `python native/build.py` builds it for your machine into
  `nxt/_bin/<platform>/`, which git ignores. It needs [Rust](https://rustup.rs).
- `python native/build_all.py` builds every platform this machine can:
  all four on macOS, all but macOS on Windows and Linux. It installs the
  tools it needs into `~/.cache/nxt_native` the first time.
- When `native/src` changes what it gives back, raise `VERSION` in
  `native/src/lib.rs` and `NATIVE_VERSION` in `nxt/comp_plan.py`, so an
  older build left in place is not used.
- `nxt/test/test_native.py`, `test_tokens.py` and `test_comp_engines.py`
  compare it with the Python code. They are skipped where there is no build.

## Dependencies

- Python 2.7
- [Qt.py](https://github.com/mottosso/Qt.py)
- PySide2 5.6

## Changelog syntax
We follow a special syntax in our commits in order to indicate messages that should be included in our automatically generated changelog(see `/GenerateChangelog` in `build/ReleaseBot.nxt`). We have 5 different levels of messages indicated by starting a line with an indicator string, followed by a space, and then your message. The 5 indicator strings are:
* `!`
* `+`
* `-`
* `*`
* `...`

 Listed below are examples. Because the line following the message is formatted into markdown, markdown syntax can be used within the commit message to improve rendering in the changelog.

`! Something critical was changed`  
`+ I added something`  
`- removed some things`  
`* Something was changed`  
`... this is an unimportant note`  
