#include "lib_no5.h"
#include <algorithm>
#include <cstddef>
#include <cstring>
#include <exception>
#include <iterator>
#include <map>

#include <filesystem>
#include <iostream>
#include <queue>
#include <sstream>

#include <optional>
#include <regex>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include <fstream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

namespace no5_path {

std::string get_parent_path(const std::string &node_path) {
  if (node_path == WORLD) {
    return std::string();
  }
  auto sep_idx = node_path.rfind(NODE_SEP);
  // If the node seperator is unfound or the first character, then it's
  // parent is the world.
  if ((sep_idx == std::string::npos) | (sep_idx == 0)) {
    return WORLD;
  }
  return node_path.substr(0, sep_idx);
}

int get_path_depth(const std::string &path) {
  if (path == WORLD) {
    return 0;
  }
  int path_len = path.length();
  int depth = 0;
  for (int i = 0; i < path_len; i++) {
    if (path[i] == WORLD[0]) {
      depth++;
    }
  }
  return depth;
}

std::string trim_to_depth(const std::string &path, const int trim_depth) {
  if (trim_depth == 0) {
    return WORLD;
  }
  int given_depth = get_path_depth(path);
  if (given_depth <= trim_depth) {
    return path;
  }
  // Trim id is the string index of the slash _not_ to keep.
  // As in, trim to everything before this.
  int trim_id = 0;
  for (int i = 0; i < trim_depth; i++) {
    trim_id = path.find(NODE_SEP, trim_id + 1);
  }
  return path.substr(0, trim_id);
}

std::string expand_relative_node_path(const std::string &relative_path,
                                      const std::string &start_path) {
  if (relative_path.length() == 0) {
    return relative_path;
  }
  if (relative_path == WORLD) {
    return relative_path;
  }
  if (relative_path.substr(0, 1) == WORLD) {
    return relative_path;
  }
  auto current_path = start_path;

  std::istringstream to_split(relative_path);
  for (std::string directive; std::getline(to_split, directive, '/');) {
    if (directive == "..") {
      current_path = get_parent_path(current_path);
      continue;
    }
    if (directive == ".") {
      continue;
    }
    if (directive == "") {
      continue;
    }
    current_path = current_path + NODE_SEP + directive;
  }

  return current_path;
}
} // namespace no5_path

SourceLayer::SourceLayer(const std::string &file_path) {
  std::ifstream f(file_path);
  // std::cerr << "Loading " << file_path << std::endl;
  json data = json::parse(f);
  // std::cerr << "Parsed" << std::endl;
  real_path = file_path;
  if (data.contains("meta_data")) {
    auto metadata = data["meta_data"];
    if (metadata.contains("positions")) {
      // std::cerr << "loading positions" << std::endl;
      positions = metadata["positions"];
    }
    if (metadata.contains("collapse")) {
      collapse = metadata["collapse"];
    }
  }
  if (data.contains("alias")) {
    alias = data["alias"];
  }
  if (data.contains("references")) {
    references = data["references"];
  }
  if (data.contains("color")) {
    color = data["color"];
  }
  if (!data.contains("nodes")) {
    return;
  }
  auto nodes = data["nodes"];
  for (json::iterator it = nodes.begin(); it != nodes.end(); ++it) {
    std::optional<std::string> instance;
    std::optional<bool> start_point;
    std::optional<std::string> execute_in;
    std::optional<bool> enabled;
    std::optional<std::vector<std::string>> child_order;
    std::optional<std::vector<std::string>> code;
    std::optional<std::string> comment;
    std::optional<std::map<std::string, std::string>> user_attrs;

    // std::cerr << "Parsing " << it.key() << std::endl;
    auto node_data = it.value();
    if (node_data.contains("attrs")) {
      user_attrs = std::map<std::string, std::string>();
      auto save_attrs = node_data["attrs"];
      for (json::iterator at_it = save_attrs.begin(); at_it != save_attrs.end();
           ++at_it) {
        if (at_it.value().contains("value")) {
          user_attrs.value().insert({at_it.key(), at_it.value()["value"]});
        } else {
          user_attrs.value().insert({at_it.key(), ""});
        }
      }
    }
    /*
    if (node_data.contains("comment")) {
        comment = node_data["comment"];
    }
    */
    if (node_data.contains("enabled")) {
      enabled = node_data["enabled"];
    }
    if (node_data.contains("instance")) {
      instance = node_data["instance"];
    }
    if (node_data.contains("execute_in")) {
      execute_in = node_data["execute_in"];
    }
    if (node_data.contains("child_order")) {
      child_order = node_data["child_order"].template get<std::vector<std::string>>();
    }
    if (node_data.contains("start_point")) {
      start_point = node_data["start_point"];
    }
    if (node_data.contains("code")) {
      code = node_data["code"].template get<std::vector<std::string>>();
    }
    add_node(it.key(), instance, start_point, execute_in, enabled, child_order,
             code, comment, user_attrs);
  }
}

std::string* SourceLayer::get_user_attr_val(const std::string &node_path,
                                            const std::string &attr_name) {
  auto spec_search = node_data_by_path.find(node_path);
  if (spec_search == node_data_by_path.end())
    return nullptr;
  if (!spec_search->second.user_attrs.has_value()) {
    return nullptr;
  }
  auto user_attrs = spec_search->second.user_attrs.value();
  auto attr_search = user_attrs.find(attr_name);
  if (attr_search == user_attrs.end())
    return nullptr;
  return &node_data_by_path[node_path].user_attrs.value()[attr_name];
}

void SourceLayer::add_node(
    const std::string &node_path, std::optional<std::string> instance,

    std::optional<bool> start_point, std::optional<std::string> execute_in,
    std::optional<bool> enabled,
    std::optional<std::vector<std::string>> child_order,

    std::optional<std::vector<std::string>> code,
    std::optional<std::string> comment,
    std::optional<std::map<std::string, std::string>> user_attrs

) {
  SourceNode new_spec;

  new_spec.instance = instance;

  new_spec.start_point = start_point;
  new_spec.execute_in = execute_in;
  new_spec.enabled = enabled;
  new_spec.child_order = child_order;

  new_spec.code = code;
  new_spec.comment = comment;
  new_spec.user_attrs = user_attrs;

  node_data_by_path[node_path] = new_spec;
}

void SourceLayer::set_collapse(const std::string &node_path, bool to_collapse) {
  collapse[node_path] = to_collapse;
}

/*
"layer" means attr value directly on the node path.
✔️ user_attrs - layer, parent, and inst
  ^ It's actually more complicated, read CompLayer::get_user_attr_val
parent comp is unique to user attrs(and enabled)

✔️ enabled - layer, inst, parent # inst is stronger than parent for enabled.

✔️ start_point - layer only
✔️ instance - layer only*
    * proxy instances ☠️

✔️ child_order - layer and inst
✔️ code - layer and inst
comment - layer and inst
✔️ execute_in - layer and inst

*/

namespace no5_tokens {

std::string resolve(const std::string &val, const std::string &node_path,
                    CompGraph &comp) {
  // std::cout << "Res " << node_path << " " << val << std::endl;
  // Finds tokens with no tokens inside of them
  // std::cerr << "R" << std::endl;
  static std::regex token_pattern(R"(\$\{([^${}]*)\})");
  std::smatch search_match;
  std::string result = val;
  while (regex_search(result, search_match, token_pattern)) {
    result = search_match.prefix().str() +
             _resolve_token(search_match[1], node_path, comp) +
             search_match.suffix().str();
  }
  return result;
}

std::string _resolve_token(const std::string &token,
                           const std::string &node_path, CompGraph &comp) {
  // std::cerr << "_r" << std::endl;
  // (?:(\w+)::([^}\n]+))
  // group1 is the token type
  // group2 is the content
  // std::cerr << token << std::endl;
  static std::regex type_and_content_pattern(R"((.+)::(.+))");
  std::smatch search_match;
  regex_search(token, search_match, type_and_content_pattern);
  // Unless regex finds a node path in the attr sub
  // std::cerr << "|" << search_match[1] << "|" << std::endl;
  if (search_match[1].length() == 0) {
    return _resolve_attr_token(token, node_path, comp);
  }
  std::string resolved_match = resolve(search_match[2], node_path, comp);
  if (search_match[1] == "file") {
    std::filesystem::path test_path =
        std::filesystem::path(comp.layers[0].real_path).parent_path() /
        std::filesystem::path(resolved_match);
    if (std::filesystem::exists(test_path)) {
      test_path = std::filesystem::canonical(test_path);
      return test_path.string();
    }
  }
  if (search_match[1] == "filelist") {
    std::stringstream outstream;
    outstream << "[";
    std::vector<std::string> out_list;
    for (SourceLayer &layer : comp.layers) {
      std::filesystem::path file_list_path =
          std::filesystem::path(layer.real_path).parent_path() /
          std::filesystem::path(resolved_match);
      if (std::filesystem::exists(file_list_path)) {
        file_list_path = std::filesystem::canonical(file_list_path);
        if (out_list.size() > 0) {
          outstream << ", ";
        }
        outstream << "'" << file_list_path.string() << "'";
        out_list.push_back(file_list_path.string());
      }
    }
    outstream << "]";
    return outstream.str();
  }
  return "";
}

std::string _resolve_attr_token(const std::string &token,
                                const std::string &node_path, CompGraph &comp) {
  // Assumes everything is an attr ref token, others don't exist :)
  static std::regex token_pattern(R"((?:(.*(?=\.))\.)?(.+))");

  std::smatch search_match;
  regex_search(token, search_match, token_pattern);

  // Assume a local node path
  std::string resolve_node_path = node_path;
  // Unless regex finds a node path in the attr sub
  if (search_match[1].length() > 0) {
    resolve_node_path =
        no5_path::expand_relative_node_path(search_match[1], node_path);
  }

  std::string * attr_val = comp.get_user_attr_val(resolve_node_path, search_match[2]);
  if (!attr_val) {
    return "";
  }
  // Recursive resolve must be done on the node we retrieved the value from
  // to allow resolving patterns resolved in contexts not the final node.
  return resolve(*attr_val, resolve_node_path, comp);
}
} // namespace no5_tokens


std::vector<CompNode *> CompNode::all_ancestors() {
  // TODO an iterator would save this allocation in most cases I think.
  std::vector<CompNode *> out_ancestors;
  CompNode * next_parent = parent;
  while (next_parent) {
    out_ancestors.push_back(next_parent);
    next_parent = next_parent->parent;
  }
  return out_ancestors;
}

CompGraph::CompGraph(const std::string &file_path) {
  real_path = file_path;
  std::vector<std::string> remaining_paths;
  remaining_paths.push_back(file_path);
  while (!remaining_paths.empty()) {
    auto next_path = remaining_paths.back();
    remaining_paths.pop_back();
    // std::cout << next_path << "\n";
    auto new_layer = SourceLayer(next_path);
    layers.push_back(new_layer);
    std::vector<std::string> real_refs;
    for (auto ref : new_layer.references) {
      auto real_ref = std::filesystem::canonical(
          std::filesystem::path(new_layer.real_path).parent_path() /
          std::filesystem::path(ref));
      real_refs.push_back(real_ref.string());
      remaining_paths.insert(remaining_paths.begin(), real_ref.string());
    }
    new_layer.references = real_refs;
  }
  MakeCompNodes();
}

CompGraph CompGraph::get_slice(const std::string &new_top) {
  CompGraph out_graph;
  out_graph.real_path = new_top;

  bool found_top = false;
  for (auto &layer: layers) {
    if (layer.real_path == new_top) {
      found_top = true;
    }
    if (found_top) {
      out_graph.layers.push_back(layer);
    }
  }
  out_graph.MakeCompNodes();
  return out_graph;
}

void CompGraph::MakeCompNodes() {
  // Create and link nodes, starting from top-most layer.
  // Manually loop over source nodes, creating comp nodes for each.
  // In most cases the parent shoudl already exist, if it doesn't, create an
  // implied node.
  std::queue<CompNode *> needs_proxies;
  // std::cerr << "Creating real & implied nodes." << std::endl;
  for (auto &layer : layers) {
    for (const auto &source_pair : layer.node_data_by_path) {
      CompNode *new_node = FindOrCreateImplied(source_pair.first);
      new_node->implied = false;
      new_node->source_layers.push_back(&layer);
      if (!new_node->execute_in && source_pair.second.execute_in.has_value()) {
        CompNode *exec_in = FindOrCreateImplied(source_pair.second.execute_in.value());
        new_node->execute_in = exec_in;
        exec_in->execute_out = new_node;
      }
      if (!new_node->instance && source_pair.second.instance.has_value()) {
        if (!source_pair.second.instance.value().empty()) {
          CompNode *instance = FindOrCreateImplied(no5_path::expand_relative_node_path(source_pair.second.instance.value(), new_node->path));
          new_node->instance = instance;
          instance->instance_targets.push_back(new_node);
          // new_node->needs_proxy_children = true;
          needs_proxies.push(new_node);
        }
      }
    }
  }
  // std::cerr << "Propegating proxy children." << std::endl;
  for (auto& [node_path, c_node] : comp_nodes) {
    _CompChildren(c_node);
  }
  // std::cerr << "Comped?" << std::endl;
}

CompNode *CompGraph::FindOrCreateImplied(const std::string &node_path) {
  if (auto search = comp_nodes.find(node_path); search != comp_nodes.end()) {
    return &search->second;
  } else {
    // (.*)\/([^\/]+)
    // Group 1 is parent path
    // Group 2 is node name
    static std::regex parent_and_name_pattern(R"((.*)\/([^\/]+))");
    std::smatch parent_and_name_match;
    std::regex_search(node_path, parent_and_name_match, parent_and_name_pattern);
    return _CreateImplied(node_path, parent_and_name_match[1], parent_and_name_match[2]);
  }
}

CompNode *CompGraph::FindOrCreateImplied(const std::string &parent_path, const std::string &node_name) {
  // If we put a map of name->children on a comp node, then we can search by parent path and node
  // name without requiring an alloc in the case where the node already exists.
  auto node_path(parent_path + no5_path::NODE_SEP + node_name);
  if (auto search = comp_nodes.find(node_path); search != comp_nodes.end()) {
    return &search->second;
  } else {
    return _CreateImplied(node_path, parent_path, node_name);
  }
}

CompNode *CompGraph::_CreateImplied(const std::string &node_path, const std::string &parent_path, const std::string &node_name) {
  CompNode &new_node = comp_nodes[node_path];
  new_node.path = node_path;
  new_node.name = node_name;
  new_node.implied = true;
  if (node_path != no5_path::WORLD) {
    CompNode * parent;
    if (!parent_path.empty()) {
      parent = FindOrCreateImplied(parent_path);
    } else {
      parent = FindOrCreateImplied(no5_path::WORLD);
    }
    new_node.parent = parent;
    parent->children.push_back(&new_node);
  }
  return &new_node;
}

void CompGraph::_CompChildren(CompNode &parent) {
  if (parent.built_children) { return; }
  std::vector<CompNode *> new_proxies;
  if (parent.instance) {
    if (!parent.instance->built_children) {
    }
    _CompChildren(*parent.instance);
    for (auto &inst_child: parent.instance->children) {
      CompNode *proxy_child = FindOrCreateImplied(parent.path, inst_child->name);
      if (!proxy_child->instance) {
        proxy_child->instance = inst_child;
        inst_child->instance_targets.push_back(proxy_child);
        proxy_child->implied = false;
        new_proxies.push_back(proxy_child);
      }
    }
  }
  sort_children(parent);
  parent.built_children = true;
  for (auto new_proxy: new_proxies) {
    _CompChildren(*new_proxy);
  }
}

std::vector<std::string *> CompGraph::get_starts() {
  std::vector<std::string *> out_starts;
  for (auto &root: comp_nodes[no5_path::WORLD].children) {
    bool is_start = false;
    for (auto &layer: layers) {
      if (auto search = layer.node_data_by_path.find(root->path);
        search != layer.node_data_by_path.end()) {
      if (search->second.start_point.has_value()) {
          if (search->second.start_point.value()) {
            out_starts.push_back(&root->path);
          }
          break;
        }
      }
    }
  }
  return out_starts;
}

std::vector<std::string *> CompGraph::get_exec_order(const std::string &start_path) {
  // std::cerr << "Start from: " << start_path << std::endl;
  CompNode * start_root;
  if (no5_path::get_path_depth(start_path) == 1) {
    start_root = &comp_nodes[start_path];
  } else {
    throw std::invalid_argument("I can only start with roots, not sorry.");
    start_root = &comp_nodes[no5_path::trim_to_depth(start_path, 1)];
  }

  std::vector<std::string *> out_order;
  out_order.push_back(&no5_path::WORLD);
  walk_execution(start_root, &out_order);
  return out_order;
}

bool CompGraph::node_exists(const std::string &node_path) {
  if (auto search = comp_nodes.find(node_path);
      search != comp_nodes.end()) {
    return true;
  }
  return false;
}

bool CompGraph::has_collapsed_ancestor(const std::string& node_path) {
  CompNode *target_node = &comp_nodes[node_path];
  auto ancestors = target_node->all_ancestors();
  // Iterate in reverse to check from root down.
  for (auto ancestor = ancestors.rbegin(); ancestor != ancestors.rend(); ++ancestor) {
    if (get_collapsed((*ancestor)->path)) {
      return true;
    }
  }
  return false;
}

std::vector<std::string *> CompGraph::get_descendants(const std::string &parent_path) {
  std::vector<std::string *> out_descendants;
  if (parent_path == no5_path::WORLD) {
    out_descendants.reserve(comp_nodes.size()); // Reserve space for performance
    for (auto& pair : comp_nodes) {
        out_descendants.push_back(const_cast<std::string*>(&pair.first));
    }
    return out_descendants;
  }
  for (auto *child: get_children(parent_path)) {
    out_descendants.push_back(child);
    for (auto *desc: get_descendants(*child)) {
      out_descendants.push_back(desc);
    }
  }
  return out_descendants;
}

std::vector<std::string *> CompGraph::get_children(const std::string &parent_path) {
  std::vector<std::string *> out_children;
  for (auto &child: comp_nodes[parent_path].children) {
    out_children.push_back(&child->path);
  }
  return out_children;
}

bool CompGraph::get_node_enabled(const std::string &node_path) {
  return get_enabled(comp_nodes[node_path]);
}

std::vector<float> CompGraph::get_position(const std::string &node_path) {
  for (auto &layer: layers) {
    if (auto search = layer.positions.find(node_path);
        search != layer.positions.end()) {
      return search->second;
    }
  }
  return std::vector<float>{0.0, 0.0};
}

bool CompGraph::get_collapsed(const std::string &node_path) {
  for (auto &layer: layers) {
    if (auto search = layer.collapse.find(node_path);
        search != layer.collapse.end()) {
      return search->second;
    }
  }
  return false;
}

bool CompGraph::get_enabled(const CompNode &node) {
  for (auto &layer: layers) {
    if (auto search = layer.node_data_by_path.find(node.path);
        search != layer.node_data_by_path.end()) {
      if (search->second.enabled.has_value()) {
        return search->second.enabled.value();
      }
    }
  }
  if (!node.instance) {return true;}
  return get_enabled(*node.instance);
}

void CompGraph::walk_execution(CompNode *from, std::vector<std::string *> *order) {
  if (get_enabled(*from)) {
    // std::cerr << from->path << std::endl;
    order->push_back(&(from->path));
    for (auto &child : from->children) {
      walk_execution(child, order);
    }
  }
  if (from->execute_out) {
    walk_execution(from->execute_out, order);
  }
}

std::vector<std::string> CompGraph::get_child_order(CompNode &node) {
  for (auto &layer: layers) {
    if (auto search = layer.node_data_by_path.find(node.path);
        search != layer.node_data_by_path.end()) {
      if (search->second.child_order.has_value()) {
        return search->second.child_order.value();
      }
    }
  }
  if (!node.instance) {return std::vector<std::string>();}
  return get_child_order(*node.instance);
}

void CompGraph::sort_children(CompNode &node) {
  // Sort the children vector in place.
  auto child_order = get_child_order(node);
  while (!child_order.empty()) {
    // Loop over child order strings starting from LAST
    auto next_child = child_order.back();
    child_order.pop_back();
    for (auto i = 0; i < node.children.size(); i++) {
      if (node.children[i]->name == next_child) {
        // Move the found child to the first position.
        //The last loop iteration moves the first node into first place.
        std::rotate(node.children.begin(), node.children.begin() + i, node.children.begin() + i + 1);
        break;
      }
    }
  }
}

std::vector<std::string> CompGraph::get_node_code_lines(std::string &node_path, const bool resolved) {
  // std::cerr << "nc " << node_path << std::endl;
  std::vector<std::string> resolved_output;
  for (auto &layer: layers) {
    if (auto search = layer.node_data_by_path.find(node_path);
        search != layer.node_data_by_path.end()) {
      if (search->second.code.has_value()) {
        // std::cerr << "real ";
        if (!resolved) {
          return search->second.code.value();
        } else {
          // std::cerr << "resolve";
          for (auto &line: search->second.code.value()) {
            resolved_output.push_back(no5_tokens::resolve(line, node_path, *this));
          }
          return resolved_output;
        }
      }
    }
  }
  auto &comp_node = comp_nodes[node_path];
  if (!comp_node.instance) {
    return std::vector<std::string>();
  }
  // Once we have resolve, we have to get the raw lines from our instance,
  // then resolve it locally.
  // std::cerr << "inst ";
  if (!resolved) {
    return get_node_code_lines(comp_node.instance->path, false);
  } else {
    for (auto &line: get_node_code_lines(comp_node.instance->path, false)) {
      resolved_output.push_back(no5_tokens::resolve(line, node_path, *this));
    }
    return resolved_output;
  }
}

std::string* CompGraph::get_exec_in(std::string& node_path) {
  CompNode *target_node = &comp_nodes[node_path];
  if (target_node->execute_in) {
    return &target_node->execute_in->path;
  }
  return nullptr;
}

std::vector<std::string> CompGraph::get_code_lines(std::string &start_path, const bool resolved) {
  std::vector<std::string> out_order;
  for (std::string *exec_path: get_exec_order(start_path)) {
    // std::cerr << "Get " << *exec_path;
    auto code_lines = get_node_code_lines(*exec_path, resolved);
    // std::cerr << " Got" << std::endl;
    for (auto &line: code_lines) {
      out_order.push_back(line);
    }
  }
  return out_order;
}

std::string* CompGraph::get_user_attr_val(const std::string &node_path, const std::string &attr_name) {
  // std::cerr << "l1" << std::endl;
  std::string* layered_value = get_layered_user_attr_val(node_path, attr_name);
  if (layered_value) {
    return layered_value;
  }
  CompNode *target_node = &comp_nodes[node_path];
  // std::cerr << "aa" << std::endl;
  for (CompNode *ancestor : target_node->all_ancestors()) {
    std::string* layered_value = get_layered_user_attr_val(ancestor->path, attr_name);
    if (layered_value) {
      return layered_value;
    }
  }
  // std::cerr << "i" << std::endl;
  if (target_node->instance) {
    std::string* inst_value = get_user_attr_val(target_node->instance->path, attr_name);
    if (inst_value) {
      return inst_value;
    }
  }
  for (CompNode *ancestor : target_node->all_ancestors()) {
    if (ancestor->instance) {
      std::string* inst_value = get_user_attr_val(ancestor->instance->path, attr_name);
      if (inst_value) {
        return inst_value;
      }
    }
  }
  return nullptr;
}

std::string* CompGraph::get_layered_user_attr_val(const std::string &node_path, const std::string &attr_name) {
  for (SourceLayer &layer : layers) {
    auto layer_val = layer.get_user_attr_val(node_path, attr_name);
    if (layer_val) { return layer_val; }
  }
  return nullptr;
}

std::string* CompGraph::get_layer_color(const std::string& layer_path) {
  for (auto &layer : layers) {
    if (layer.real_path == layer_path) {
      return &layer.color;
    }
  }
  return &default_color;
}

std::vector<std::string *> CompGraph::get_source_layers(const std::string& node_path) {
  std::vector<std::string *> out_paths;
  CompNode *target_node = &comp_nodes[node_path];
  for (auto *layer: target_node->source_layers) {
    out_paths.push_back(&layer->real_path);
  }
  return out_paths;
}

std::map<std::string, std::string> CompGraph::get_node_attrs(const std::string& node_path) {
  std::map<std::string, std::string> in_progress;
  CompNode *target_node = &comp_nodes[node_path];
  // This logic is like the reverse of get_user_attr value. We start from
  // Weakest to strongest since we cannnot rule out any attribute.
  auto ancestors = target_node->all_ancestors();
  for (auto ancestor = ancestors.rbegin(); ancestor != ancestors.rend(); ++ancestor) {
    if ((*ancestor)->instance) {
      for (auto &ancest_attr : get_node_attrs((*ancestor)->instance->path)) {
        in_progress[ancest_attr.first] = ancest_attr.second;
        // std::cout << ancest_attr.first << " ancest_inst= " << ancest_attr.second << std::endl;
      }
    }
  }
  if (target_node->instance) {
    for (auto &inst_attr : get_node_attrs(target_node->instance->path)) {
      in_progress[inst_attr.first] = inst_attr.second;
      // std::cout << inst_attr.first << " inst= " << inst_attr.second << std::endl;
    }
  }
  for (auto ancestor = ancestors.rbegin(); ancestor != ancestors.rend(); ++ancestor) {
    for (auto layer = layers.rbegin(); layer != layers.rend(); ++layer) {
        auto spec_search = (*layer).node_data_by_path.find((*ancestor)->path);
        if (spec_search == (*layer).node_data_by_path.end())
          continue;
        if (!spec_search->second.user_attrs.has_value()) {
          continue;
        }
        auto user_attrs = spec_search->second.user_attrs.value();
        for (auto attr = user_attrs.begin(); attr != user_attrs.end(); ++attr) {
          in_progress[attr->first] = attr->second;
          // std::cout << attr->first << " ancestor= " << attr->second << std::endl;
        }
    }
  }
  for (auto layer = layers.rbegin(); layer != layers.rend(); ++layer) {
    auto spec_search = (*layer).node_data_by_path.find(node_path);
    if (spec_search == (*layer).node_data_by_path.end())
      continue;
    if (!spec_search->second.user_attrs.has_value()) {
      continue;
    }
    auto user_attrs = spec_search->second.user_attrs.value();
    for (auto attr = user_attrs.begin(); attr != user_attrs.end(); ++attr) {
      in_progress[attr->first] = attr->second;
      // std::cout << attr->first << " local= " << attr->second << std::endl;
    }
  }
  return in_progress;
}
