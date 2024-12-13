#include <iostream>
#include <string>
#include <regex>
#include "lib_no5.h"

int main(int argc, char *argv[]) {
    if (argc < 2) {
        std::cerr << "Dump an entire exeuction path, or a single node." << std::endl << argv[0] << " /graph/to/dump.nxt [/optional/single/node]" << std::endl;
        return 1;  // Return an error code
    }
    // What about a second argument that's an optional single node?
    std::string loading(argv[1]);
    std::string node;
    if (argc >= 3) {
        node = argv[2];
    }
    auto comp = CompGraph(loading);
    std::cerr << "Loaded" << std::endl;
    if (node.empty()) {
        for (std::string &line: comp.get_code_lines(*comp.get_starts()[0])) {
            std::cout << line << std::endl;
        }
    } else {
        for (std::string& line: comp.get_node_code_lines(node)) {
            std::cout << line << std::endl;
        }
    }
    return 0;  // Return a success code
}