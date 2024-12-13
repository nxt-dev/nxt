# Building
`pip install .`

**Getting a build environment**  
`conda env create -f dev_env.yml` (This does not provide a compiler, just python, kinda useless)
You provide:
1. python
2. compiler
3. cmake  
Then, CMakeLists.txt takes care of the rest.

## Commands
`~/Projects/nxt/other_n| cmake -B build/cache && cmake --build build/cache && cmake --install build/cache`  
`~/Projects/nxt/other_n| g++ -I include src/dump.cpp src/lib_no5.cpp -o build/bin/dumper && ./build/bin/dumper test/pile.nxt`  
`~/Projects/nxt/other_n| make -C src && ./build/bin/editor`  
`(no5) ~/Projects/nxt/other_n| pip install . && python test/differ.py test/pile.nxt`  
`valgrind --tool=callgrind --callgrind-out-file=thistime.profile ./build/bin/dumper test/pile.nxt`  

editor and dump both require:  
- https://github.com/nlohmann/json at `include/nlohmann/json.hpp`

editor requires:  
- https://github.com/glfw/glfw at `vendor/glfw`
- https://github.com/ocornut/imgui at `vendor/imgui`

**Builds for your current python version, into your current directory**  
`python -m pip wheel . --no-deps`  

**What's in the wheels**  
The contents of the wheels are what is installed by cmake when the `NO5_PY` component
is enabled in the build. That means the compiled `no5` python bindings to `lib_no5`, plus the additional python scripts in `nxt2no5`
