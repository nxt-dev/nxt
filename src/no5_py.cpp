#include "lib_no5.h"

#include <pybind11/pybind11.h>
// For conversions between std::map and dict
#include <pybind11/stl.h>
namespace py = pybind11;

PYBIND11_MODULE(no5, m_comp) {
    py::class_<SourceLayer>(m_comp, "SourceLayer")
        .def_readonly("alias", &SourceLayer::alias)
        .def_readonly("real_path", &SourceLayer::real_path)
        .def_readonly("color", &SourceLayer::color)
        .def_readonly("references", &SourceLayer::references)
        .def(
            "set_collapse",
            &SourceLayer::set_collapse
        );
    py::class_<CompGraph>(m_comp, "CompGraph")
        .def(py::init<const std::string &>())
        .def_readonly("real_path", &CompGraph::real_path)
        .def_readonly("layers", &CompGraph::layers)
        .def(
            "get_slice",
            &CompGraph::get_slice
        )
        .def(
            "get_layer_color",
            &CompGraph::get_layer_color
        )
        .def(
            "get_source_layers",
            &CompGraph::get_source_layers
        )
        .def(
            "node_exists",
            &CompGraph::node_exists
        )
        .def(
            "has_collapsed_ancestor",
            &CompGraph::has_collapsed_ancestor
        )
        .def(
            "get_descendants",
            &CompGraph::get_descendants,
            py::arg("parent_path"),
            py::return_value_policy::copy
        )
        .def(
            "get_children",
            &CompGraph::get_children,
            py::arg("parent_path"),
            py::return_value_policy::copy
        )
        .def(
            "get_collapsed",
            &CompGraph::get_collapsed
        )
        .def(
            "get_position",
            &CompGraph::get_position,
            py::arg("node_path"),
            py::return_value_policy::copy
        )
        .def(
            "get_node_enabled",
            &CompGraph::get_node_enabled,
            py::arg("node_path"),
            py::return_value_policy::copy
        )
        .def(
            "get_starts",
            &CompGraph::get_starts
        )
        .def(
            "get_exec_in",
            &CompGraph::get_exec_in,
            py::arg("node_path")
        )
        .def(
            "get_exec_order",
            &CompGraph::get_exec_order,
            py::arg("start_path"),
            py::return_value_policy::copy
        )
        .def(
            "get_node_attrs",
            &CompGraph::get_node_attrs,
            py::arg("node_path")
        )
        .def(
            "get_node_code_lines",
            &CompGraph::get_node_code_lines,
            py::arg("node_path"),
            py::arg("resolved"),
            py::return_value_policy::copy
        );
    auto m_tokens = m_comp.def_submodule("no5_tokens");
    m_tokens.def(
        "resolve",
        &no5_tokens::resolve,
        py::arg("val"),
        py::arg("node_path"),
        py::arg("comp"),
        py::return_value_policy::copy
    );
}
