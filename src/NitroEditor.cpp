#include "NitroEditor.h"
#include "imgui.h"
#include "lib_no5.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <filesystem>

namespace NitroEditor {
    void RenderUI() {

        static ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings;

        // "Main Area = entire viewport,\nWork Area = entire viewport minus sections used by the main menu bars, task bars etc.\n\nEnable the main-menu bar in Examples menu to see the difference."
        // We demonstrate using the full viewport area or the work area (without menu-bars, task-bars etc.)
        // Based on your use case you may want one or the other.
        bool use_work_area = true;
        const ImGuiViewport* viewport = ImGui::GetMainViewport();
        ImGui::DockSpaceOverViewport(viewport);
        ImGui::SetNextWindowPos(use_work_area ? viewport->WorkPos : viewport->Pos);
        ImGui::SetNextWindowSize(use_work_area ? viewport->WorkSize : viewport->Size);

        static bool window_is_open;
        ImGui::Begin("Open Graphs", &window_is_open, flags);

        static char to_load[256] = "/home/michael/Projects/nxt/other_n/test/pile.nxt";


        // static std::stringstream text;
        // ImGui::InputTextMultiline("Graph code", text.str().data(), text.str().size(), ImVec2(-FLT_MIN, ImGui::GetTextLineHeight() * 69));
        // if (ImGui::Button("Load") && std::filesystem::exists(to_load)) {
        //     auto new_comp = CompGraph(std::string(to_load));
        //     std::string start("/init");
        //     for (auto line: new_comp.get_code_lines(start)) {
        //         text << line << "\n";
        //     }
        // }

        static std::vector<CompGraph> loaded_comps;
        static std::map<std::string, std::vector<std::string *>> exec_orders;
        static std::map<std::string, std::map<std::string, std::string>> raw_maps;
        static std::map<std::string, std::map<std::string, std::string>> resolved_maps;

        if (ImGui::Button("Load") && std::filesystem::exists(to_load)) {
            auto new_comp = CompGraph(std::string(to_load));
            loaded_comps.push_back(new_comp);
            std::string start("/init");
            auto exec_order = new_comp.get_exec_order(start);
            std::map<std::string, std::string> raw_code_map;
            std::map<std::string, std::string> resolved_code_map;
            for (auto next_node: exec_order){
                std::stringstream raw;
                std::stringstream resolved;
                for (auto raw_line:new_comp.get_node_code_lines(*next_node, false)) {
                    raw << raw_line << "\n";
                    resolved << no5_tokens::resolve(raw_line, *next_node, new_comp) << "\n";
                }
                raw_code_map[*next_node] = raw.str();
                resolved_code_map[*next_node] = resolved.str();
            }
            exec_orders[new_comp.layers[0].real_path] = exec_order;
            raw_maps[new_comp.layers[0].real_path] = raw_code_map;
            raw_maps[new_comp.layers[0].real_path] = raw_code_map;
            resolved_maps[new_comp.layers[0].real_path] = resolved_code_map;
        }
        ImGui::SameLine();
        ImGui::InputText("##", to_load, 256);

        for (auto comp: loaded_comps) {
            ImGui::Text(comp.layers[0].alias.c_str());

            std::vector<std::string> starts;
            std::string root("/init");
            starts.push_back(root);

            auto raw_code_map = raw_maps[comp.layers[0].real_path];
            auto resolved_code_map = resolved_maps[comp.layers[0].real_path];
            auto exec_order = exec_orders[comp.layers[0].real_path];

            std::filesystem::path raw_path = std::string(comp.layers[0].real_path);
            raw_path.replace_extension(".raw.no5.py");
            if (ImGui::Button("Save Raw")) {
                std::ofstream outputFile(raw_path);

                if (outputFile.is_open()) {
                    for (auto next_node: exec_order){
                        outputFile << raw_code_map[*next_node] << std::endl;
                    }
                    outputFile.close();
                    std::cerr << "Written to " << raw_path << std::endl;
                } else {
                    std::cout << "Unable to open the file." << std::endl;
                }

            }
            ImGui::SameLine();
            ImGui::Text(raw_path.c_str());


            std::filesystem::path resolved_path = std::string(comp.layers[0].real_path);
            resolved_path.replace_extension(".resolved.no5.py");
            if (ImGui::Button("Save Resolved")) {
                std::ofstream res_outputFile(resolved_path);

                if (res_outputFile.is_open()) {
                    for (auto next_node: exec_order){
                        res_outputFile << resolved_code_map[*next_node];
                    }
                    res_outputFile.close();
                    std::cerr << "Written to " << resolved_path << std::endl;
                } else {
                    std::cout << "Unable to open the file." << std::endl;
                }

            }
            ImGui::SameLine();
            ImGui::Text(resolved_path.c_str());


            if (ImGui::BeginTabBar("Doc Views"))
            {
                if (ImGui::BeginTabItem("Raw"))
                {
                    if (ImGui::BeginTable("Raw Doc", 2, ImGuiTableFlags_RowBg))
                    {
                        ImGui::TableSetupColumn("node_path", ImGuiTableColumnFlags_WidthFixed, 100.0f);
                        ImGui::TableSetupColumn("code", ImGuiTableColumnFlags_WidthStretch);
                        for (auto next_node: exec_order)
                        {
                            ImGui::TableNextRow();
                            ImGui::TableSetColumnIndex(0);
                            ImGui::Text(next_node->c_str());
                            ImGui::TableSetColumnIndex(1);
                            ImGui::Text(raw_code_map[*next_node].c_str());
                        }
                        ImGui::EndTable();
                    }
                    ImGui::EndTabItem();
                }
                if (ImGui::BeginTabItem("Resolved"))
                {
                    if (ImGui::BeginTable("Res Doc", 2, ImGuiTableFlags_RowBg))
                    {
                        ImGui::TableSetupColumn("node_path", ImGuiTableColumnFlags_WidthFixed, 100.0f);
                        ImGui::TableSetupColumn("code", ImGuiTableColumnFlags_WidthStretch);
                        for (auto next_node: exec_order)
                        {
                            ImGui::TableNextRow();
                            ImGui::TableSetColumnIndex(0);
                            ImGui::Text(next_node->c_str());
                            ImGui::TableSetColumnIndex(1);
                            ImGui::Text(resolved_code_map[*next_node].c_str());
                        }
                        ImGui::EndTable();
                    }
                    ImGui::EndTabItem();
                }
                ImGui::EndTabBar();
            }
        }
        /*
        static bool show_demo;
        if (ImGui::Button("Show Demo")) {
            show_demo = true;
        }
        if (show_demo) {
            ImGui::ShowDemoWindow();
        }
        Loop over keys/vals. new window for every key, with text of every line.
        ImGui::Begin(key);
        ImGui::End();
        */
        ImGui::End();
    }

}