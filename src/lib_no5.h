#pragma once

#include <algorithm>
#include <iostream>
#include <map>

#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

struct SourceNode {

  std::optional<std::string> instance;

  std::optional<bool> start_point;
  std::optional<std::string> execute_in;
  std::optional<bool> enabled;
  std::optional<std::vector<std::string>> child_order;

  std::optional<std::vector<std::string>> code;
  std::optional<std::string> comment;
  // TODO user attrs have comments...
  std::optional<std::map<std::string, std::string>> user_attrs;
};

static std::string default_color("#5633BB");

namespace no5_path {

static std::string WORLD = "/";
static std::string NODE_SEP = "/";

std::string get_parent_path(const std::string &node_path);

int get_path_depth(const std::string &path);

std::string trim_to_depth(const std::string &path, const int trim_depth);

std::string expand_relative_node_path(const std::string &relative_path,
                                      const std::string &start_path);
} // namespace no5_path

class SourceLayer {
public:
  std::string alias;
  std::string real_path;
  std::string color;
  std::vector<std::string> references;
  std::map<std::string, SourceNode> node_data_by_path;

  std::map<std::string, std::vector<float>> positions;
  std::map<std::string, bool> collapse;

  SourceLayer(const std::string &file_path);

  std::string* get_user_attr_val(const std::string &node_path,
                                 const std::string &attr_name);

  void add_node(const std::string &node_path,
                std::optional<std::string> instance,

                std::optional<bool> start_point,
                std::optional<std::string> execute_in,
                std::optional<bool> enabled,
                std::optional<std::vector<std::string>> child_order,

                std::optional<std::vector<std::string>> code,
                std::optional<std::string> comment,
                std::optional<std::map<std::string, std::string>> user_attrs

  );

  void set_collapse(const std::string &node_path, bool to_collapse);
};

struct CompNode {
  std::string path;
  std::string name;

  bool implied = true;

  std::vector<SourceLayer *> source_layers;

  CompNode * parent = nullptr;
  std::vector<CompNode *> children;

  CompNode * execute_in = nullptr;
  CompNode * execute_out = nullptr;

  CompNode * instance = nullptr;
  std::vector<CompNode *> instance_targets;

  bool built_children = false;

  std::vector<CompNode *> all_ancestors();
};

class CompGraph {

public:
  std::string real_path;
  CompGraph(const std::string &file_path);
  std::vector<SourceLayer> layers;

  CompGraph get_slice(const std::string &new_top);

  std::vector<std::string *> get_exec_order(const std::string &start_path);
  std::string* get_exec_in(std::string& node_path);
  std::vector<std::string> get_node_code_lines(std::string &node_path,
                                               const bool resolved = true);
  std::vector<std::string> get_code_lines(std::string &start_path,
                                          const bool resolved = true);
  std::vector<std::string *> get_starts();
  std::string* get_user_attr_val(const std::string &node_path,
                                 const std::string &attr_name);
  bool node_exists(const std::string& node_path);
  bool has_collapsed_ancestor(const std::string& node_path);
  bool get_node_enabled(const std::string &node_path);
  std::vector<std::string *> get_descendants(const std::string &parent_path);
  std::vector<std::string *> get_children(const std::string &parent_path);
  std::vector<float> get_position(const std::string &node_path);
  bool get_collapsed(const std::string &node_path);

  std::string* get_layer_color(const std::string& layer_path);
  std::vector<std::string *> get_source_layers(const std::string& node_path);

  std::map<std::string, std::string> get_node_attrs(const std::string& node_path);
private:
  CompGraph() {};
  void MakeCompNodes();

  std::map<std::string, CompNode> comp_nodes;

  CompNode* FindOrCreateImplied(const std::string &node_path);
  CompNode* FindOrCreateImplied(const std::string &parent_path, const std::string &node_name);
  CompNode* _CreateImplied(const std::string &node_path, const std::string &parent_path, const std::string &node_name);
  std::vector<std::string> get_child_order(CompNode &node);
  bool get_enabled(const CompNode &node);
  void sort_children(CompNode &node);
  void walk_execution(CompNode *from, std::vector<std::string *> *order);

  void _CompChildren(CompNode &parent);


  std::string* get_layered_user_attr_val(const std::string &node_path,
                                         const std::string &attr_name);

};

namespace no5_tokens {

std::string resolve(const std::string &val, const std::string &node_path,
                    CompGraph &comp);

std::string _resolve_token(const std::string &token,
                           const std::string &node_path, CompGraph &comp);

std::string _resolve_attr_token(const std::string &token,
                                const std::string &node_path, CompGraph &comp);

}; // namespace no5_tokens
