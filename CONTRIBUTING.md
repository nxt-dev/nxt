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

## The faster comp engine in a checkout

nxt composites graphs with a compiled module written in Rust, in
`native/`, and falls back to its Python code wherever the module isn't
there (see the README). Releases carry the module, but git doesn't: it is
built, not committed. So a checkout of nxt, and anything that runs nxt from
one, uses the slower Python code until you build the module once.
Everything works either way, with the same results.

### Setting it up

1. Install the tools Rust needs to link on your OS:
   - **Windows:** the Microsoft C++ build tools. The Rust installer offers
     to install them through Visual Studio Community; accept it, or install
     [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
     yourself with "Desktop development with C++". If you already have
     Visual Studio with C++, that is enough.
   - **macOS:** `xcode-select --install`.
   - **Linux:** a C compiler and linker, such as `build-essential` on
     Debian and Ubuntu, or `gcc` on Fedora and Rocky.
2. Install Rust from [rustup.rs](https://rustup.rs) with the defaults,
   then open a new terminal so `cargo` is on your `PATH`.
3. Build the module, from the root of the nxt checkout, with any Python
   3.10 or newer:
   ```
   python native/build.py
   ```
   It writes `nxt/_bin/<platform>/_nxt_native.pyd` on Windows, or
   `_nxt_native.so` on macOS and Linux. Git ignores that folder.
4. Check that it is used. `nxt --version` (or `python -m nxt.cli --version`)
   ends with `Comp native`. `Comp python` is followed by the reason it
   isn't.

One build serves every Python from 3.10 up on that OS, so the same build
works in the editor, in Maya, Unreal and Blender, and in headless runs,
whenever they import nxt from this checkout, through an editable install
or `PYTHONPATH`.

### Keeping it up to date

Run `python native/build.py` again after pulling changes to `native/`. A
build from before a change to what the module gives back has an older
version number, and nxt quietly uses the Python code instead until you
rebuild; `nxt --version` then says `Comp python (the native build is
another version)`. If Maya or Unreal has the old module loaded, the build
moves it aside, and the new one is used the next time the host starts.

### Changing it

- Each function in `native/src` has a Python twin in nxt, and both must
  give the same result, down to which strings are the same object: nxt
  compares some strings with `is`. A change to one is a change to both.
- When `native/src` changes what it gives back, raise `VERSION` in
  `native/src/lib.rs` and `NATIVE_VERSION` in `nxt/comp_plan.py`, so an
  older build left in place is not used.
- `nxt/test/test_native.py`, `test_tokens.py` and `test_comp_engines.py`
  compare the module with the Python code. They are skipped where there is
  no build, so build before running them.
- From `perf/`, `python deep_parity.py native --random 200` composites
  graphs with both engines and compares everything the comp leaves behind,
  and `python runtime_parity.py --random 50` checks runs. Run both after
  changing the comp, in Python or in Rust.
- `python native/build_all.py` builds every platform this machine can: all
  four on macOS, all but macOS on Windows and Linux. It installs the tools
  it needs into `~/.cache/nxt_native` the first time. CI builds and tests
  all four for every release, so you only need it to try another OS.

To compare against the Python code while working, set
`NXT_COMP_ENGINE=python` for compositing, or `NXT_NO_NATIVE=1` for
everything the module does.

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
