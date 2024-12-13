from Qt import QtCore, QtWidgets, QtGui

from collections import namedtuple, defaultdict
import os

from nxt_editor.commands import *
from nxt import DATA_STATE
from nxt_editor.stage_model import UnsavedLayerSet
from nxt_editor import colors
from no5 import no5_tokens



class No5Model(QtCore.QObject):
    destroy_cmd_port = QtCore.Signal(None)
    update_cache_dict = QtCore.Signal(dict)
    about_to_rename = QtCore.Signal()
    about_to_execute = QtCore.Signal(bool)
    executing_changed = QtCore.Signal(bool)
    build_changed = QtCore.Signal(tuple)  # new build list
    build_idx_changed = QtCore.Signal(int)
    build_paused_changed = QtCore.Signal(bool)
    processing = QtCore.Signal(bool)
    data_state_changed = QtCore.Signal(bool)
    implicit_connections_changed = QtCore.Signal(bool)
    layer_color_changed = QtCore.Signal(object)
    comp_layer_changed = QtCore.Signal(object)
    disp_layer_changed = QtCore.Signal(str)  # New display layer path
    target_layer_changed = QtCore.Signal(object)
    layer_mute_changed = QtCore.Signal(tuple)  # Layer paths whose mute changed
    layer_solo_changed = QtCore.Signal(tuple)  # Layer paths whose solo changed
    layer_alias_changed = QtCore.Signal(str)  # Layer path whose alias changed
    layer_lock_changed = QtCore.Signal(str)  # Layer path whose locked changed
    layer_removed = QtCore.Signal(str)  # Layer path who was removed
    layer_added = QtCore.Signal(str)  # Layer path who was added
    layer_saved = QtCore.Signal(str)  # Layer path that was just saved
    nodes_changed = QtCore.Signal(tuple)
    attrs_changed = QtCore.Signal(tuple)
    node_added = QtCore.Signal(str)
    node_deleted = QtCore.Signal(str)
    node_moved = QtCore.Signal(str, list)
    selection_changed = QtCore.Signal(tuple)  # new selection
    node_focus_changed = QtCore.Signal(str)
    node_name_changed = QtCore.Signal(str, str)  # old node path, new node path
    node_parent_changed = QtCore.Signal(str, str)  # old node path, new node path
    starts_changed = QtCore.Signal(tuple)  # new start point paths
    breaks_changed = QtCore.Signal(tuple)  # new break point paths
    skips_changed = QtCore.Signal(tuple)  # new skip point paths
    collapse_changed = QtCore.Signal(tuple)  # node paths where changed
    frame_items = QtCore.Signal(tuple)
    server_log = QtCore.Signal(str)
    request_ding = QtCore.Signal()

    def __init__(self, comp, parent=None):
        super(No5Model, self).__init__(parent=parent)
        self.init_comp = comp
        self.comp = comp

        self.display_layer = self.comp.layers[0].real_path

        # Compat
        self.effected_layers = UnsavedLayerSet()
        self.undo_stack = QtWidgets.QUndoStack(self)
        self.comp_layer = namedtuple("CompLayer", ["real_path", "failure"])
        self.comp_layer.failure = False
        self.top_layer = namedtuple("TopLayer", ["real_path"])
        self.top_layer.real_path = self.comp.layers[0].real_path
        self.stage = type("Stage", (), {})
        self.stage._sub_layers = []
        self.target_layer = None
        self.executing = False
        self.build_paused = False
        self.last_built_idx = -1
        self.selection = []
        self.uid = id(self)
        self._data_state = DATA_STATE.RESOLVED
        self._node_focus = None
        self._fake_collapse = {}

    def get_descendants(self, node_path, layer=None, include_implied=False):
        return self.comp.get_descendants(node_path)

    def node_exists(self, node_path, layer=None):
        if not node_path:
            return False
        return self.comp.node_exists(node_path)

    def has_children(self, node_path, layer=None):
        if not self.node_exists(node_path, layer):
            return False
        return bool(self.get_children(node_path))

    def get_is_node_breakpoint(self, node_path, layer=None):
        return False

    def get_is_node_start(self, node_path, layer=None):
        return node_path == "/init"

    def is_top_node(self, node_path):
        if node_path == "/":
            return False
        return node_path.count("/") == 1

    def get_node_sibling_paths(self, node_path, layer=None):
        return []

    def get_node_attr_source(self, node_path, attr_name, layer):
        return '', ''

    def get_node_comment(self, node_path, layer=None):
        return None

    def get_node_child_order(self, node_path, layer=None):
        return self.comp.get_children(node_path)

    def get_start_nodes(self, layer=None):
        return self.comp.get_starts()

    def get_exec_order(self, start_path, layer=None):
        return self.comp.get_exec_order(start_path)

    def is_build_setup(self):
        return True

    def execute_nodes(self, node_paths, rt_layer=None, safe_exec=True):
        exec_globals = {"STAGE": type("STAGE", (), {})}
        self.last_built_idx = -1
        start = self.last_built_idx+1
        stop = len(node_paths)
        for i in range(start, stop):
            node_path = node_paths[i]
            code = self.get_node_code_string(node_path, data_state=DATA_STATE.RESOLVED)
            try:
                exec(code, exec_globals)
            except Exception:
                print(node_path)
                raise
            self.last_built_idx = i
            QtCore.QCoreApplication.processEvents()

    def get_descendant_colors(self, base_path):
        return ["#ffffff"]

    def get_node_attr_color(self, node_path, attr_name, layer):
        return '#5633BB'

    def is_node_skippoint(self, node_path, layer_path=None):
        return False

    def get_node_pos(self, node_path):
        return self.init_comp.get_position(node_path)

    def get_node_is_proxy(self, node_path):
        return False

    def get_node_locked(self, node_path, local=False, layer_opinion=True):
        return False

    def toggle_node_collapse(self, node_paths, recursive_down=False,
                             recursive_up=False, layer_path=None):
        for path in node_paths:
            self.init_comp.layers[0].set_collapse(path, not self.get_node_collapse(path))
        self.collapse_changed.emit(list(node_paths))

    def get_node_collapse(self, node_path, layer=None):
        return self.init_comp.get_collapsed(node_path)

    def get_collapsed_ancestor(self, node_path):
        return self.init_comp.has_collapsed_ancestor(node_path)

    def get_node_enabled(self, node_path, layer=None, allow_none=False):
        return self.comp.get_node_enabled(node_path)

    def node_is_implied(self, node_path, layer=None):
        return False

    def node_is_instance_child(self, node_path, layer=None,
                               include_real_children=False):
        return False

    def get_node_error(self, node_path, layer=None):
        return []

    def get_unsaved_changes(self, layers=(), deep_check=False):
        return []

    def get_node_instance(self, node_path, layer=None):
        return None

    def get_node_instance_path(self, node_path, layer=None, expand=True):
        return ""

    def get_attr_display_state(self, node_path):
        return 0

    def get_children(self, node_path, layer=None, ordered=False,
                     include_implied=False):
        return self.comp.get_children(node_path)

    def get_node_exec_in(self, node_path, layer=None):
        return self.comp.get_exec_in(node_path)

    def get_node_code_external_sources(self, node_path, layer=None):
        return []

    def get_layer_locked(self, layer_path):
        return False

    def get_layer_alias(self, layer_path):
        for layer in self.comp.layers:
            if layer.real_path == layer_path:
                return layer.alias
        return os.path.splitext(os.path.basename(layer_path))[0]

    def get_is_layer_muted(self, layer):
        return False

    def get_is_layer_soloed(self, layer):
        return False

    def get_layer_color(self, layer, local=False):
        if layer == self.comp_layer:
            layer = self.comp.real_path
        if layer == self.target_layer:
            layer = self.comp.real_path
        if layer == self.top_layer:
            layer = self.comp.real_path
        return self.init_comp.get_layer_color(layer)

    def get_layer_colors(self, layer_list):
        return [self.get_layer_color(layer) for layer in layer_list]

    def get_node_color(self, node_path, layer=None):
        if not layer:
            layers = self.get_layers_with_opinion(node_path)
            if not layers:
                return "#787878"
            layer = layers[0]
        return self.get_layer_color(layer)

    def get_layers_with_opinion(self, node_path, attr_name=None):
        if not node_path:
            return []
        return self.comp.get_source_layers(node_path)

    def get_node_code_string(self, node_path, data_state=DATA_STATE.RAW,
                             layer=None):
        lines = self.comp.get_node_code_lines(node_path, data_state == DATA_STATE.RESOLVED);
        return "\n".join(lines)

    def get_node_code_source(self, node_path):
        return None

    def node_has_code(self, node_path, layer=None):
        return bool(self.get_node_code_string(node_path))

    def is_selected(self, path):
        return path in self.selection

    def set_selection(self, paths):
        if paths == self.selection:
            return
        cmd = SetSelection(paths, self)
        self.undo_stack.push(cmd)
        # Bad code
        self.node_focus = self.selection[-1]

    def get_selected_nodes(self, allow_world=False):
        return self.selection

    def set_display_layer(self, layer_path):
        self.processing.emit(True)
        if layer_path != self.top_layer.real_path:
            new_comp = self.init_comp.get_slice(layer_path)
            self.comp = new_comp
        else:
            self.comp = self.init_comp
        self.display_layer = layer_path
        self.comp_layer_changed.emit(())
        self.disp_layer_changed.emit(layer_path)
        self.processing.emit(False)

    @property
    def data_state(self):
        return self._data_state

    @data_state.setter
    def data_state(self, value):
        self._data_state = value
        self.data_state_changed.emit(value)

    @property
    def node_focus(self):
        return self._node_focus

    @node_focus.setter
    def node_focus(self, focus_path):
        if focus_path == self._node_focus:
            return
        self._node_focus = focus_path
        self.node_focus_changed.emit(focus_path)

class No5LayerModel(QtCore.QAbstractItemModel):
    ALIAS_COLUMN = 0
    DISPLAY_COLUMN = 1
    TARGET_COLUMN = 2
    MUTE_COLUMN = 3
    SOLO_COLUMN = 4
    LOCK_COLUMN = 5
    HAS_SELECTED_COLUMN = 6
    UNSAVED = 7


    FAKE_LAYERS = {
        "/foo":{"children":["/bar", "/baz"], "color":"#769b70"},
        "/bar": {"parent":"/foo", "color":"#464b70"},
        "/baz": {"parent":"/foo", "color":"#424b40"},
    }

    def __init__(self, no5_model):
        super(No5LayerModel, self).__init__()
        self.no5_model = no5_model
        self.layers = defaultdict(dict)
        self.top_layer_path = self.no5_model.top_layer.real_path
        for layer in self.no5_model.init_comp.layers:
            self.layers[layer.real_path]["color"] = layer.color
            self.layers[layer.real_path].setdefault("children", [])
            for child_path in layer.references:
                real_child_path = os.path.realpath(os.path.join(os.path.dirname(layer.real_path), child_path))
                self.layers[layer.real_path]["children"].append(real_child_path)
                self.layers[real_child_path]["parent"] = layer.real_path
        self.no5_model.disp_layer_changed.connect(self.reset)

    def reset(self):
        self.beginResetModel()
        self.endResetModel()

    def index(self, row, column, parent=None):
        """Returns a model index for the layer at the given row/column with
        given parent.
        Part of QAbstractItemModel
        """
        if not parent or not parent.isValid():
            return self.createIndex(row, column, self.top_layer_path)
        parent_path = parent.internalPointer()
        try:
            return self.createIndex(row, column, self.layers[parent_path].get("children", [])[row])
        except IndexError:
            return QtCore.QModelIndex()
        print('who gets here?')
        return QtCore.QModelIndex()

    def parent(self, child_index):
        """Returns model index that represents the parent of the layer at
        given `child_index`
        Part of QAbstractItemModel
        """
        if not child_index.isValid():
            return QtCore.QModelIndex()
        child_layer_path = child_index.internalPointer()
        try:
            parent_layer_path = self.layers[child_layer_path]["parent"]
        except KeyError:
            return QtCore.QModelIndex()
        try:
            grand_parent_path = self.layers[parent_layer_path]["parent"]
            parent_row = self.layers[grand_parent_path]["children"].index(parent_layer_path)
        except KeyError:
            parent_row = 0
        return self.createIndex(parent_row, 0, parent_layer_path)

    def rowCount(self, parent=None):
        """Returns count of rows(children) for the model, or parent specified
        by `parent`
        Part of QAbstractItemModel
        """
        if not parent or not parent.isValid():
            return 1
        if parent.column() > 0:
            return 0
        layer_path = parent.internalPointer()
        return len(self.layers[layer_path].get("children", []))

    def columnCount(self, parent=None):
        """Returns number of columns in the model.
        Part of QAbstractItemModel
        """
        return 6

    def data(self, index, role=None):
        """Returns the data continaed at given model index with given role.
        Part of QAbstractItemModel
        """
        layer_path = index.internalPointer()
        column = index.column()
        if role == QtCore.Qt.BackgroundRole:
            color_hex = self.no5_model.get_layer_color(layer_path, local=False)
            return QtGui.QBrush(QtGui.QColor(color_hex))
        if role == QtCore.Qt.DisplayRole:
            if column == self.ALIAS_COLUMN:
                return self.no5_model.get_layer_alias(layer_path)
            return
        is_disp = layer_path == self.no5_model.display_layer
        is_target = layer_path == self.no5_model.top_layer.real_path
        is_locked = self.no5_model.get_layer_locked(layer_path)
        is_muted = self.no5_model.get_is_layer_muted(layer_path)
        is_soloed = self.no5_model.get_is_layer_soloed(layer_path)
        if role == QtCore.Qt.EditRole:
            if column == self.ALIAS_COLUMN:
                return self.no5_model.get_layer_alias(layer_path)
            if column == self.TARGET_COLUMN:
                return is_target
            if column == self.DISPLAY_COLUMN:
                return is_disp
            if column == self.MUTE_COLUMN:
                return is_muted
            if column == self.SOLO_COLUMN:
                return is_soloed
            if column == self.LOCK_COLUMN:
                return is_locked
            if column == self.HAS_SELECTED_COLUMN:
                return False
            if column == self.UNSAVED:
                return False
            return
        if role == QtCore.Qt.CheckStateRole:
            if column == self.TARGET_COLUMN:
                return QtCore.Qt.Checked if is_target else QtCore.Qt.Unchecked
            if column == self.DISPLAY_COLUMN:
                return QtCore.Qt.Checked if is_disp else QtCore.Qt.Unchecked
            if column == self.MUTE_COLUMN:
                return QtCore.Qt.Checked if is_muted else QtCore.Qt.Unchecked
            if column == self.SOLO_COLUMN:
                return QtCore.Qt.Checked if is_soloed else QtCore.Qt.Unchecked
            if column == self.LOCK_COLUMN:
                return QtCore.Qt.Checked if is_locked else QtCore.Qt.Unchecked

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        """Allows editing of layers via qt model interface.
        """
        column = index.column()
        layer_path = index.internalPointer()
        if role != QtCore.Qt.CheckStateRole:
            return
        if column == self.DISPLAY_COLUMN:
            if not value:
                return False
            self.no5_model.set_display_layer(layer_path)
            return True

class No5NodeAttrsModel(QtCore.QAbstractTableModel):
    COLUMNS = [
        "Name",
        "Value",
        "Type",
        "Source",
        "Locality",
        "Comment"
    ]
    NAME_COLUMN = COLUMNS.index("Name")
    VALUE_COLUMN = COLUMNS.index("Value")
    TYPE_COLUMN = COLUMNS.index("Type")
    SOURCE_COLUMN = COLUMNS.index("Source")
    LOCALITY_COLUMN = COLUMNS.index("Locality")
    COMMENT_COLUMN = COLUMNS.index("Comment")

    FAKE_ATTR_DATA = [
        ["attr2", "", "raw", "/top", "1.Local", ""],
        ["sleep_time", "2", "int", "/top", "1.Local", ""]
    ]

    def __init__(self, no5_model):
        super(No5NodeAttrsModel, self).__init__()
        self.no5_model = no5_model
        self.node_path = None
        self._data = []
        # self._data = self.FAKE_ATTR_DATA

    @property
    def stage_model(self):
        raise ValueError("Don't!")

    @stage_model.setter
    def stage_model(self, new):
        self.no5_model = new

    def set_represented_node(self, node_path=None):
        self.beginResetModel()
        self.node_path = node_path
        # Get data table formatted as above.
        self._data = []
        if node_path:
            for name, value in self.no5_model.comp.get_node_attrs(node_path).items():
                self._data.append([str(name), str(value), "fake", "fake", "fake", "fake"])
        self.endResetModel()

    def data(self, index, role=None):
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()
        cached_state = DATA_STATE.CACHED
        resolved_state = DATA_STATE.RESOLVED
        if role is None:
            return self._data[row][column]
        if role == QtCore.Qt.BackgroundRole and column == self.VALUE_COLUMN:
            if self.no5_model.data_state == DATA_STATE.CACHED:
                # Warning with red we don't have cached data.
                return QtGui.QBrush(color, QtCore.Qt.BDiagPattern)
        if role == QtCore.Qt.DisplayRole:
            if self.no5_model.data_state == DATA_STATE.CACHED:
                return
            if column != self.VALUE_COLUMN:
                return self._data[row][column]
            if self.no5_model.data_state == DATA_STATE.RAW:
                return self._data[row][column]
            return no5_tokens.resolve(self._data[row][column] or "", self.node_path, self.no5_model.comp)

        if role == QtCore.Qt.ToolTipRole:
            return str(dict(zip(self.COLUMNS, self._data[row])))

        if role == QtCore.Qt.ForegroundRole:
            color = self.no5_model.get_node_color(self._data[row][self.SOURCE_COLUMN])
            return QtGui.QColor(color)


    def flags(self, index):
        column = index.column()
        if column in (self.NAME_COLUMN, self.VALUE_COLUMN, self.COMMENT_COLUMN):
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable
        elif column == self.TYPE_COLUMN:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        elif column == self.SOURCE_COLUMN:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.NoItemFlags

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                return self.COLUMNS[section]

    def rowCount(self, parent):
        return len(self._data)

    def columnCount(self, parent):
        return len(self.COLUMNS)
