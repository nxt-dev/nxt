import os
import time
from Qt import QtWidgets
from contextlib import contextmanager
import nxt_editor
from nxt_editor.main_window import MainWindow
from nxt_editor.stage_view import StageView
import no5
from .nxt_editor_compat import No5Model, No5LayerModel, No5NodeAttrsModel

def no5_it():
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        raise Exception('No qapp found! Is nxt open?')
    windows = qapp.topLevelWidgets()
    for win in windows:
        if isinstance(win, MainWindow):
            nxt_window = win
            break
    else:
        raise Exception('No nxt window found')

    nxt_editor.window = nxt_window

    from nxt_editor.actions import NxtAction
    try:
        no5_action = nxt_window.menu_bar.no5_action
    except AttributeError:
        no5_action = NxtAction(text="Open NO₅ Graph", parent=nxt_window)
        nxt_window.menu_bar.file_menu.insertAction(nxt_window.menu_bar.layer_actions.save_layer_action, no5_action)
    nxt_window.no5_tab = no5_tab
    no5_action.triggered.connect(nxt_window.no5_tab)
    nxt_window.open_files_tab_widget.currentChanged.connect(on_tab_change)
    nxt_window.open_files_tab_widget.tabCloseRequested.connect(on_tab_close)
    nxt_window.menu_bar.load_recent_menu.action_target = nxt_window.no5_tab
    print("hello from no5, we took over your recent files menu.")
    test_path = "/home/michael/Projects/nxt/other_n/test/pile.nxt"
    test_path = "/home/michael/Desktop/higher.nxt"
    no5_tab(test_path)


def no5_tab(chosen_path=None):
    if not chosen_path:
        chosen_path = QtWidgets.QFileDialog.getOpenFileName(
            filter="Graphs (*.nxt *.nxtb *.no5)"
        )[0]
    if not chosen_path:
        return
    nxt_editor.window.set_waiting_cursor(True)

    with timer("Loading no5"):
        comp = no5.CompGraph(chosen_path)

    nxt_editor.window.set_waiting_cursor(False)

    model = No5Model(comp)
    # model.processing.connect(self.set_waiting_cursor)
    # model.request_ding.connect(self.ding)
    # model.layer_alias_changed.connect(partial(self.update_tab_title, model))
    with timer("construct stage view"):
        view = StageView(model=model, parent=nxt_editor.window)
    tab_index = nxt_editor.window.open_files_tab_widget.count()
    with timer("add and change tab"):
        nxt_editor.window.open_files_tab_widget.addTab(
            view,
            os.path.splitext(os.path.basename(chosen_path))[0] + ".NO₅"
        )
        nxt_editor.window.open_files_tab_widget.setCurrentIndex(tab_index)
    with timer("code editor"):
        nxt_editor.window.code_editor.set_stage_model(model)
    with timer("build view"):
        nxt_editor.window.build_view.set_stage_model(model)
    with timer("layer manager"):
        nxt_editor.window.layer_manager.layer_tree.setModel(No5LayerModel(model))
    with timer("property editor"):
        new_model = No5NodeAttrsModel(model)
        nxt_editor.window.property_editor.model = new_model
        # The property editor's model never changes fyi
        nxt_editor.window.property_editor.proxy_model.setSourceModel(new_model)
        nxt_editor.window.property_editor.set_stage_model(model)


def on_tab_change(tab_index):
    view = nxt_editor.window.open_files_tab_widget.widget(tab_index)
    if not view:
        return
    if isinstance(view.model, No5Model):
        nxt_editor.window.code_editor.set_stage_model(view.model)
        nxt_editor.window.build_view.set_stage_model(view.model)
        nxt_editor.window.layer_manager.layer_tree.setModel(No5LayerModel(view.model))
        nxt_editor.window.property_editor.set_stage_model(view.model)


def on_tab_close(tab_index):
    view = nxt_editor.window.open_files_tab_widget.widget(tab_index)
    if not view:
        return
    if isinstance(view.model, No5Model):
        view.deleteLater()
        view.model.deleteLater()
        nxt_editor.window.open_files_tab_widget.removeTab(tab_index)
        nxt_editor.window.tab_changed.emit()


@contextmanager
def timer(name):
    t0 = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - t0
        print(f"{name} took {elapsed:.3f}")