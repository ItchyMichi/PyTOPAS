# template_editor.py

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QInputDialog, QMenu, QAction, QApplication, QDialog,
    QComboBox, QLineEdit, QTextEdit, QFrame, QGroupBox, QCheckBox, QWidget, QSizePolicy,
    QRadioButton, QButtonGroup  # Added QRadioButton and QButtonGroup
)
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import QTimer, QPropertyAnimation, QEasingCurve, pyqtSlot

import networkx as nx
import json
import os
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

class TemplateEditor(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flowchart Editor")
        self.setGeometry(100, 100, 1000, 700)
        self.focusWidget()

        # Initialize variables
        self.G = nx.DiGraph()
        self.pos = {}
        self.canvas_plot = None
        self.node_counter = 0
        self.flowchart = {}
        self.flowchart_file = None


        self.init_ui()

    def init_ui(self):
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        # Top Buttons
        top_frame = QHBoxLayout()

        new_button = QPushButton("New")
        new_button.clicked.connect(self.new_flowchart)
        top_frame.addWidget(new_button)

        load_button = QPushButton("Load")
        load_button.clicked.connect(self.load_flowchart)
        top_frame.addWidget(load_button)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_flowchart)
        top_frame.addWidget(save_button)

        add_node_button = QPushButton("Add Node")
        add_node_button.clicked.connect(self.add_node)
        top_frame.addWidget(add_node_button)

        main_layout.addLayout(top_frame)

        # Canvas Frame
        self.canvas_frame = QFrame()
        self.canvas_frame.setLayout(QVBoxLayout())
        main_layout.addWidget(self.canvas_frame)

        central_widget.setLayout(main_layout)

        # Initialize the flowchart diagram
        self.update_flowchart_diagram()

    def update_flowchart_diagram(self):
        # Clear the canvas
        for i in reversed(range(self.canvas_frame.layout().count())):
            widget = self.canvas_frame.layout().takeAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        if not self.flowchart:
            return

        steps = self.flowchart.get("nodes", [])
        connections = self.flowchart.get("connections", [])
        loops = self.flowchart.get("loops", [])

        self.G.clear()

        # Add nodes to the graph
        for node in steps:
            node_id = node['id']
            self.G.add_node(node_id, **node)

        # Add edges to the graph
        for conn in connections:
            self.G.add_edge(conn['from'], conn['to'])

        # Assign layers to nodes
        layers = self.assign_layers(self.G)

        # Group nodes by layers
        from collections import defaultdict
        layer_nodes = defaultdict(list)
        for node, layer in layers.items():
            layer_nodes[layer].append(node)

        # Position nodes
        self.pos = {}
        layer_height = 3  # Vertical spacing between layers
        node_width = 3  # Horizontal spacing between nodes

        for layer in sorted(layer_nodes.keys()):
            nodes_in_layer = layer_nodes[layer]
            num_nodes = len(nodes_in_layer)
            # Center nodes in this layer
            x_start = -((num_nodes - 1) * node_width) / 2
            y = -layer * layer_height  # Negative because y increases downward
            for i, node in enumerate(nodes_in_layer):
                x = x_start + i * node_width
                self.pos[node] = (x, y)

        # Create a matplotlib figure
        fig = Figure(figsize=(10, 8), dpi=100)
        ax = fig.add_subplot(111)

        # Draw nodes
        self.draw_nodes(self.G, self.pos, ax)

        # Draw edges
        self.draw_edges(self.G, self.pos, ax, loops)

        # Enable grid
        ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray', alpha=0.3)
        ax.axis('off')  # Hide axes

        # Embed the figure into the PyQt5 canvas
        self.canvas_plot = FigureCanvas(fig)
        self.canvas_plot.draw()
        self.canvas_frame.layout().addWidget(self.canvas_plot)

        # Add the navigation toolbar
        toolbar = NavigationToolbar2QT(self.canvas_plot, self)
        self.canvas_frame.layout().addWidget(toolbar)

        # Connect events
        self.canvas_plot.mpl_connect('button_press_event', self.on_plot_click)

    def draw_nodes(self, G, pos, ax):
        node_labels = {node: G.nodes[node].get('label', node) for node in G.nodes()}
        node_task_types = [G.nodes[node].get('task_type', 'Task') for node in G.nodes()]
        # Define colors for different task types
        task_type_colors = {
            'Crystallite Size': 'lightblue',
            'RWP': 'orange',
            'Cleanup': 'green',
            'Compare': 'yellow',
            'Task': 'grey'  # Default color
        }
        node_colors = [task_type_colors.get(task_type, 'grey') for task_type in node_task_types]
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=2000, ax=ax)
        nx.draw_networkx_labels(G, pos, node_labels, font_size=10, ax=ax)

    def draw_edges(self, G, pos, ax, loops):
        # Collect loop edges
        loop_edges = set()
        for loop_nodes in loops:
            for i in range(len(loop_nodes)):
                from_node = loop_nodes[i]
                to_node = loop_nodes[(i + 1) % len(loop_nodes)]
                loop_edges.add((from_node, to_node))

        for edge in G.edges():
            from_node, to_node = edge
            x1, y1 = pos[from_node]
            x2, y2 = pos[to_node]
            if edge in loop_edges:
                # Edge is part of a loop, draw curved arrow
                rad = 0.3  # Adjust curvature as needed
                ax.annotate(
                    "",
                    xy=(x2, y2), xycoords='data',
                    xytext=(x1, y1), textcoords='data',
                    arrowprops=dict(
                        arrowstyle="->", color="black",
                        shrinkA=15, shrinkB=15,
                        patchA=None, patchB=None,
                        connectionstyle=f"arc3,rad={rad}",
                    ),
                )
            else:
                # Draw straight arrow
                ax.annotate(
                    "",
                    xy=(x2, y2), xycoords='data',
                    xytext=(x1, y1), textcoords='data',
                    arrowprops=dict(
                        arrowstyle="->", color="black",
                        shrinkA=15, shrinkB=15,
                        patchA=None, patchB=None,
                        connectionstyle="arc3,rad=0.0",
                    ),
                )
        # Collect edge labels
        edge_labels = {}
        for edge in G.edges(data=True):
            from_node, to_node, data = edge
            label = ''
            if 'condition' in data and data['condition']:
                label += f"Cond: {data['condition']}\n"
            if 'priority' in data and data['priority']:
                label += f"Pri: {data['priority']}\n"
            if 'info_passed' in data and data['info_passed']:
                label += f"Info: {data['info_passed']}"
            if label:
                edge_labels[(from_node, to_node)] = label.strip()

        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8, ax=ax)

    def assign_layers(self, G):
        layers = {}
        visited = set()

        def dfs(node, current_layer):
            if node in layers:
                return
            layers[node] = current_layer
            for succ in G.successors(node):
                dfs(succ, current_layer + 1)

        # Start DFS from nodes with no predecessors
        for node in G.nodes():
            if G.in_degree(node) == 0:
                dfs(node, 0)

        # For nodes not reached by DFS (e.g., in cycles), assign layer
        for node in G.nodes():
            if node not in layers:
                layers[node] = 0  # Assign to layer 0 or adjust as needed

        return layers

    # Function to handle plot clicks
    def on_plot_click(self, event):
        x_click = event.xdata
        y_click = event.ydata
        if x_click is None or y_click is None:
            return

        # Find the closest node within a threshold distance
        closest_node = None
        min_distance = float('inf')
        threshold = 0.1  # Adjust based on your graph's scale
        for node, (x, y) in self.pos.items():
            distance = (x - x_click) ** 2 + (y - y_click) ** 2
            if distance < min_distance:
                min_distance = distance
                closest_node = node

        if min_distance > threshold:
            return  # Click was not close enough to a node

        if closest_node:
            if event.button == 1 and event.dblclick:
                # Left double-click
                self.open_node_customization_dialog(closest_node)
            elif event.button == 3:
                # Right-click
                self.show_context_menu(closest_node)

    def open_node_customization_dialog(self, node_id):
        node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == node_id), None)
        if node:
            dialog = NodeCustomizationDialog(self, node, self.flowchart, self.G)
            if dialog.exec_():
                self.update_flowchart_diagram()

    # Function to show context menu
    def show_context_menu(self, node_id):
        menu = QMenu()
        edit_action = QAction("Edit Node", self)
        edit_action.triggered.connect(lambda: self.edit_node(node_id))
        menu.addAction(edit_action)

        delete_action = QAction("Delete Node", self)
        delete_action.triggered.connect(lambda: self.delete_node(node_id))
        menu.addAction(delete_action)

        add_conn_action = QAction("Add Connection", self)
        add_conn_action.triggered.connect(lambda: self.add_connection(node_id))
        menu.addAction(add_conn_action)

        add_and_connect_action = QAction("Add and Connect Node", self)
        add_and_connect_action.triggered.connect(lambda: self.add_and_connect_node(node_id))
        menu.addAction(add_and_connect_action)

        add_loop_action = QAction("Add Loop", self)
        add_loop_action.triggered.connect(lambda: self.add_loop(node_id))
        menu.addAction(add_loop_action)

        delete_conn_action = QAction("Delete Connection", self)
        delete_conn_action.triggered.connect(lambda: self.delete_connection(node_id))
        menu.addAction(delete_conn_action)

        cursor = QCursor.pos()
        menu.exec_(cursor)

    def add_loop(self, from_node_id):
        dialog = AddLoopDialog(self)
        if dialog.exec_():
            nodes_info = dialog.result  # List of tuples: (node_label, task_type)
            new_node_ids = []
            # Create new nodes for the loop
            for label, task_type in nodes_info:
                self.node_counter += 1
                node_id = f"node_{self.node_counter}"
                node = {
                    'id': node_id,
                    'label': label,
                    'task_type': task_type,
                    'parameters': {}
                }
                self.flowchart.setdefault('nodes', []).append(node)
                new_node_ids.append(node_id)
            # Connect the first loop node to the rest to form a loop
            for i in range(len(new_node_ids)):
                from_id = new_node_ids[i]
                to_id = new_node_ids[(i + 1) % len(new_node_ids)]
                connection = {
                    'from': from_id,
                    'to': to_id
                }
                self.flowchart.setdefault('connections', []).append(connection)
            # Connect the original node to the first node in the loop
            connection = {
                'from': from_node_id,
                'to': new_node_ids[0]
            }
            self.flowchart.setdefault('connections', []).append(connection)
            # Store the loop nodes in flowchart
            self.flowchart.setdefault('loops', []).append(new_node_ids)

            # Update the diagram
            self.update_flowchart_diagram()

    def add_and_connect_node(self, from_node_id):
        dialog = AddNodeDialog(self)
        if dialog.exec_():
            node_label, task_type = dialog.result
            self.node_counter += 1
            node_id = f"node_{self.node_counter}"
            node = {
                'id': node_id,
                'label': node_label,
                'task_type': task_type,
                'parameters': {}
            }
            self.flowchart.setdefault('nodes', []).append(node)
            # Add connection from the original node to the new node
            connection = {
                'from': from_node_id,
                'to': node_id
            }
            self.flowchart.setdefault('connections', []).append(connection)
            self.update_flowchart_diagram()

    # Function to add a new node
    def add_node(self):
        dialog = AddNodeDialog(self)
        if dialog.exec_():
            node_label, task_type = dialog.result
            self.node_counter += 1
            node_id = f"node_{self.node_counter}"
            node = {
                'id': node_id,
                'label': node_label,
                'task_type': task_type,
                'parameters': {}
            }
            self.flowchart.setdefault('nodes', []).append(node)
            self.update_flowchart_diagram()

    # Function to edit a node
    def edit_node(self, node_id):
        node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == node_id), None)
        if node:
            new_label, ok = QInputDialog.getText(self, "Edit Node", "Enter new label:", text=node['label'])
            if ok and new_label:
                node['label'] = new_label
                self.update_flowchart_diagram()

    # Function to delete a node
    def delete_node(self, node_id):
        confirm = QMessageBox.question(self, "Delete Node", "Are you sure you want to delete this node?")
        if confirm == QMessageBox.Yes:
            self.flowchart['nodes'] = [n for n in self.flowchart.get('nodes', []) if n['id'] != node_id]
            # Remove associated connections
            self.flowchart['connections'] = [
                c for c in self.flowchart.get('connections', [])
                if c['from'] != node_id and c['to'] != node_id
            ]
            self.update_flowchart_diagram()

    # Function to add a connection
    def add_connection(self, from_node_id):
        node_labels = {n['id']: n['label'] for n in self.flowchart.get('nodes', []) if n['id'] != from_node_id}
        if not node_labels:
            QMessageBox.information(self, "Add Connection", "No other nodes to connect to.")
            return

        items = list(node_labels.values())
        item, ok = QInputDialog.getItem(self, "Select Node to Connect To", "Select node to connect to:", items, 0, False)
        if ok and item:
            to_node_id = next((nid for nid, lbl in node_labels.items() if lbl == item), None)
            if to_node_id:
                # Add the connection
                connection = {
                    'from': from_node_id,
                    'to': to_node_id,
                    'condition': '',  # Initialize as empty
                    'priority': '',  # Initialize as empty
                    'info_passed': ''  # Initialize as empty
                }
                self.flowchart.setdefault('connections', []).append(connection)
                self.update_flowchart_diagram()
            else:
                QMessageBox.warning(self, "Error", "Node not found.")

    # Function to delete a connection
    def delete_connection(self, from_node_id):
        connections = [
            c for c in self.flowchart.get('connections', [])
            if c['from'] == from_node_id
        ]
        if not connections:
            QMessageBox.information(self, "Delete Connection", "No outgoing connections from this node.")
            return
        dest_labels = {c['to']: self.G.nodes[c['to']]['label'] for c in connections}
        items = list(dest_labels.values())
        to_node_label, ok = QInputDialog.getItem(self, "Delete Connection", f"Delete connection from '{self.G.nodes[from_node_id]['label']}' to which node?", items, 0, False)
        if ok and to_node_label:
            to_node_id = next((nid for nid, lbl in dest_labels.items() if lbl == to_node_label), None)
            if to_node_id:
                self.flowchart['connections'] = [
                    c for c in self.flowchart.get('connections', [])
                    if not (c['from'] == from_node_id and c['to'] == to_node_id)
                ]
                self.update_flowchart_diagram()
            else:
                QMessageBox.warning(self, "Error", "Connection not found.")

    # Function to create a new flowchart
    def new_flowchart(self):
        confirm = QMessageBox.question(self, "New Flowchart", "Are you sure you want to create a new flowchart?")
        if confirm == QMessageBox.Yes:
            self.flowchart = {}
            self.node_counter = 0
            self.flowchart_file = None
            self.update_flowchart_diagram()

    # Function to save the flowchart
    def save_flowchart(self):
        if not self.flowchart_file:
            self.flowchart_file, _ = QFileDialog.getSaveFileName(self, "Save Flowchart", "", "JSON Files (*.json)")
            if not self.flowchart_file:
                return
        with open(self.flowchart_file, 'w') as f:
            json.dump(self.flowchart, f, indent=4)
        QMessageBox.information(self, "Save Flowchart", "Flowchart saved successfully.")

    # Function to load a flowchart
    def load_flowchart(self):
        flowchart_file_path, _ = QFileDialog.getOpenFileName(self, "Load Flowchart", "", "JSON Files (*.json)")
        if flowchart_file_path:
            with open(flowchart_file_path, 'r') as f:
                self.flowchart = json.load(f)
            node_ids = [int(n['id'].split('_')[1]) for n in self.flowchart.get('nodes', [])]
            self.node_counter = max(node_ids, default=0)
            self.flowchart_file = flowchart_file_path
            self.update_flowchart_diagram()

class AddNodeDialog(QDialog):
    def __init__(self, parent, title="Add Node"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result = None
        self.create_widgets()

    def create_widgets(self):
        layout = QVBoxLayout()

        label_label = QLabel("Node Label:")
        layout.addWidget(label_label)

        self.label_entry = QLineEdit()
        layout.addWidget(self.label_entry)

        task_type_label = QLabel("Task Type:")
        layout.addWidget(task_type_label)

        task_types = ["Crystallite Size", "RWP", "Cleanup", "Compare", "Start", "RWP Addition", "RWP Removal", "RWP Missing"]  # Extend as needed
        self.task_type_combobox = QComboBox()
        self.task_type_combobox.addItems(task_types)
        layout.addWidget(self.task_type_combobox)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.on_ok)
        layout.addWidget(ok_button)

        self.setLayout(layout)

    def on_ok(self):
        label = self.label_entry.text()
        task_type = self.task_type_combobox.currentText()
        if label:
            self.result = (label, task_type)
            self.accept()
        else:
            QMessageBox.warning(self, "Input Error", "Node label is required.")

class AddLoopDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add Loop")
        self.result = None
        self.node_entries = []
        self.create_widgets()

    def create_widgets(self):
        layout = QVBoxLayout()

        self.nodes_frame = QVBoxLayout()
        layout.addLayout(self.nodes_frame)

        # Add initial nodes
        for _ in range(2):
            self.add_node_entry()

        add_node_button = QPushButton("Add Node")
        add_node_button.clicked.connect(self.add_node_entry)
        layout.addWidget(add_node_button)

        submit_button = QPushButton("Submit")
        submit_button.clicked.connect(self.on_submit)
        layout.addWidget(submit_button)

        self.setLayout(layout)

    def add_node_entry(self):
        frame = QHBoxLayout()

        label_label = QLabel("Label:")
        frame.addWidget(label_label)

        label_entry = QLineEdit()
        frame.addWidget(label_entry)

        type_label = QLabel("Task Type:")
        frame.addWidget(type_label)

        task_types = ["Crystallite Size", "RWP", "Cleanup", "Compare", "Start", "RWP Addition", "RWP Removal", "RWP Missing" ]  # Extend as needed
        task_type_combobox = QComboBox()
        task_type_combobox.addItems(task_types)
        frame.addWidget(task_type_combobox)

        self.node_entries.append((label_entry, task_type_combobox))
        self.nodes_frame.addLayout(frame)

    def on_submit(self):
        nodes_info = []
        for label_entry, task_type_combobox in self.node_entries:
            label = label_entry.text()
            task_type = task_type_combobox.currentText()
            if not label:
                QMessageBox.warning(self, "Input Error", "All node labels are required.")
                return
            nodes_info.append((label, task_type))
        self.result = nodes_info
        self.accept()


import logging


class NodeCustomizationDialog(QDialog):
    def __init__(self, parent, node, flowchart, G):
        super().__init__(parent)
        self.setWindowTitle("Customize Node")
        self.node = node
        self.flowchart = flowchart
        self.G = G  # The graph
        self.result = None

        # Initialize logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG)

        self.create_widgets()

    def create_widgets(self):
        self.logger.debug("Creating widgets for NodeCustomizationDialog")
        layout = QVBoxLayout()

        # Node Label
        label_label = QLabel("Node Label:")
        layout.addWidget(label_label)

        self.label_entry = QLineEdit(self.node.get('label', ''))
        layout.addWidget(self.label_entry)

        # Task Type
        task_type_label = QLabel("Task Type:")
        layout.addWidget(task_type_label)

        task_types = ["Crystallite Size", "RWP", "Cleanup", "Compare", "Start", "RWP Addition", "RWP Removal", "RWP Missing"]  # Extend as needed
        self.task_type_combobox = QComboBox()
        self.task_type_combobox.addItems(task_types)
        index = self.task_type_combobox.findText(self.node.get('task_type', ''))
        if index >= 0:
            self.task_type_combobox.setCurrentIndex(index)
        self.task_type_combobox.currentIndexChanged.connect(self.on_task_type_selected)
        layout.addWidget(self.task_type_combobox)

        # Parameters Frame
        self.parameters_frame = QVBoxLayout()
        layout.addLayout(self.parameters_frame)

        # Initialize parameters based on the current task type
        self.create_parameters_widgets()

        # Incoming Connections Collapsible Frame
        self.incoming_collapsible = CollapsibleWidget("Incoming Connections")
        layout.addWidget(self.incoming_collapsible)
        self.incoming_connections_frame = self.incoming_collapsible.content_layout
        self.create_incoming_connections_widgets()

        # Outgoing Connections Collapsible Frame
        self.outgoing_collapsible = CollapsibleWidget("Outgoing Connections")
        layout.addWidget(self.outgoing_collapsible)
        self.outgoing_connections_frame = self.outgoing_collapsible.content_layout
        self.create_outgoing_connections_widgets()

        # Add a field for expected_deps
        expected_deps_label = QLabel("Minimum number of dependencies required (expected_deps):")
        layout.addWidget(expected_deps_label)

        self.expected_deps_entry = QLineEdit()
        # Default value is 1 if not specified
        current_expected_deps = str(self.node.get('expected_deps', 1))
        self.expected_deps_entry.setText(current_expected_deps)
        layout.addWidget(self.expected_deps_entry)


        # Save Button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.on_save)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def on_task_type_selected(self):
        # Update parameters widgets based on selected task type
        QTimer.singleShot(0, self.create_parameters_widgets)

    def create_parameters_widgets(self):
        task_type = self.task_type_combobox.currentText()
        parameters = self.node.get('parameters', {})

        # Clear existing widgets
        while self.parameters_frame.count():
            child = self.parameters_frame.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Reset widget references
        self.min_weight_entry = None
        self.max_weight_entry = None
        self.polynomial_entry = None
        #self.param1_entry = None
        #self.param2_entry = None
        self.min_crystallite_entry = None
        self.crystallite_step = None
        self.rwp_threshold_entry = None
        self.exclusion_variable_combobox = None
        self.exclusion_criteria_combobox = None
        self.list1_entry = None
        self.list2_entry = None
        self.structure_list_entry = None
        self.external_list_entry = None



        if task_type == 'Crystallite Size':
            # Parameters common to Crystallite Size and RWP
            min_weight_label = QLabel("Minimum Percentage Weight cuttoff:")
            self.parameters_frame.addWidget(min_weight_label)
            self.min_weight_entry = QLineEdit(parameters.get('min_weight', '0.1'))
            self.parameters_frame.addWidget(self.min_weight_entry)

            max_weight_label = QLabel("Maximum Percentage Weight tested:")
            self.parameters_frame.addWidget(max_weight_label)
            self.max_weight_entry = QLineEdit(parameters.get('max_weight', '4'))
            self.parameters_frame.addWidget(self.max_weight_entry)

            min_crystallite_label = QLabel("Min. Crystallite Size 1:")
            self.parameters_frame.addWidget(min_crystallite_label)
            self.min_crystallite_entry = QLineEdit(parameters.get('min_crystallite', '20'))
            self.parameters_frame.addWidget(self.min_crystallite_entry)

            crystallite_step_label = QLabel("Threshold Step Size:")
            self.parameters_frame.addWidget(crystallite_step_label)
            self.crystallite_step_entry = QLineEdit(parameters.get('crystallite_step', '30'))
            self.parameters_frame.addWidget(self.crystallite_step_entry)

            polynomial_label = QLabel("Polynomial:")
            self.parameters_frame.addWidget(polynomial_label)
            self.polynomial_entry = QLineEdit(parameters.get('polynomial', '5'))
            self.parameters_frame.addWidget(self.polynomial_entry)

            # Exclusion Variable
            exclusion_variable_label = QLabel("Exclusion Variable:")
            self.parameters_frame.addWidget(exclusion_variable_label)
            exclusion_variables = ['Crystallite Size']
            self.exclusion_variable_combobox = QComboBox()
            self.exclusion_variable_combobox.addItems(exclusion_variables)
            current_variable = parameters.get('exclusion_variable', exclusion_variables[0])
            self.exclusion_variable_combobox.setCurrentText(current_variable)
            self.parameters_frame.addWidget(self.exclusion_variable_combobox)

            # Exclusion Criteria
            exclusion_criteria_label = QLabel("Exclusion Criteria:")
            self.parameters_frame.addWidget(exclusion_criteria_label)
            exclusion_criteria = ['Worst', 'Failing', 'Worst Negative', 'Failing Z-Score', 'All Failing Except Best','Worst Combined', 'Failing Combined', 'Worst Negative Combined', 'Failing Z-Score Combined', 'All Failing Except Best Combined']
            self.exclusion_criteria_combobox = QComboBox()
            self.exclusion_criteria_combobox.addItems(exclusion_criteria)
            current_criteria = parameters.get('exclusion_criteria', exclusion_criteria[0])
            self.exclusion_criteria_combobox.setCurrentText(current_criteria)
            self.parameters_frame.addWidget(self.exclusion_criteria_combobox)

            # Confidence
            confidence_label = QLabel("Confidence (e.g., 0.95):")
            self.parameters_frame.addWidget(confidence_label)
            self.confidence_entry = QLineEdit(parameters.get('confidence', '0.5'))
            self.parameters_frame.addWidget(self.confidence_entry)

        elif task_type == 'RWP Addition':
            # Parameters common to Crystallite Size and RWP
            min_weight_label = QLabel("Minimum Percentage Weight:")
            self.parameters_frame.addWidget(min_weight_label)
            self.min_weight_entry = QLineEdit(parameters.get('min_weight', ''))
            self.parameters_frame.addWidget(self.min_weight_entry)

            max_weight_label = QLabel("Maximum Percentage Weight tested:")
            self.parameters_frame.addWidget(max_weight_label)
            self.max_weight_entry = QLineEdit(parameters.get('max_weight', ''))
            self.parameters_frame.addWidget(self.max_weight_entry)

            rwp_threshold_label = QLabel("RWP Threshold:")
            self.parameters_frame.addWidget(rwp_threshold_label)
            self.rwp_threshold_entry = QLineEdit(parameters.get('rwp_threshold', ''))
            self.parameters_frame.addWidget(self.rwp_threshold_entry)

            polynomial_label = QLabel("Polynomial:")
            self.parameters_frame.addWidget(polynomial_label)
            self.polynomial_entry = QLineEdit(parameters.get('polynomial', ''))
            self.parameters_frame.addWidget(self.polynomial_entry)

            # Exclusion Variable
            exclusion_variable_label = QLabel("Exclusion Variable:")
            self.parameters_frame.addWidget(exclusion_variable_label)
            exclusion_variables = ['delta RWP', 'RWP', 'Percentage weight scaled RWP']
            self.exclusion_variable_combobox = QComboBox()
            self.exclusion_variable_combobox.addItems(exclusion_variables)
            current_variable = parameters.get('exclusion_variable', exclusion_variables[0])
            self.exclusion_variable_combobox.setCurrentText(current_variable)
            self.parameters_frame.addWidget(self.exclusion_variable_combobox)

            # Exclusion Criteria
            exclusion_criteria_label = QLabel("Exclusion Criteria:")
            self.parameters_frame.addWidget(exclusion_criteria_label)
            exclusion_criteria = ['Worst', 'Failing', 'Worst Negative', 'Failing Z-Score', 'All Failing Except Best','Worst Combined', 'Failing Combined', 'Worst Negative Combined', 'Failing Z-Score Combined', 'All Failing Except Best Combined']
            self.exclusion_criteria_combobox = QComboBox()
            self.exclusion_criteria_combobox.addItems(exclusion_criteria)
            current_criteria = parameters.get('exclusion_criteria', exclusion_criteria[0])
            self.exclusion_criteria_combobox.setCurrentText(current_criteria)
            self.parameters_frame.addWidget(self.exclusion_criteria_combobox)

            # Confidence
            confidence_label = QLabel("Confidence (e.g., 0.95):")
            self.parameters_frame.addWidget(confidence_label)
            self.confidence_entry = QLineEdit(parameters.get('confidence', '0.95'))
            self.parameters_frame.addWidget(self.confidence_entry)

        elif task_type == 'RWP Missing':
            # Parameters common to Crystallite Size and RWP
            min_weight_label = QLabel("Minimum Percentage Weight:")
            self.parameters_frame.addWidget(min_weight_label)
            self.min_weight_entry = QLineEdit(parameters.get('min_weight', ''))
            self.parameters_frame.addWidget(self.min_weight_entry)

            max_weight_label = QLabel("Maximum Percentage Weight tested:")
            self.parameters_frame.addWidget(max_weight_label)
            self.max_weight_entry = QLineEdit(parameters.get('max_weight', ''))
            self.parameters_frame.addWidget(self.max_weight_entry)

            rwp_threshold_label = QLabel("RWP Threshold:")
            self.parameters_frame.addWidget(rwp_threshold_label)
            self.rwp_threshold_entry = QLineEdit(parameters.get('rwp_threshold', ''))
            self.parameters_frame.addWidget(self.rwp_threshold_entry)

            polynomial_label = QLabel("Polynomial:")
            self.parameters_frame.addWidget(polynomial_label)
            self.polynomial_entry = QLineEdit(parameters.get('polynomial', ''))
            self.parameters_frame.addWidget(self.polynomial_entry)

            # Exclusion Variable
            exclusion_variable_label = QLabel("Exclusion Variable:")
            self.parameters_frame.addWidget(exclusion_variable_label)
            exclusion_variables = ['delta RWP', 'RWP', 'Percentage weight scaled RWP']
            self.exclusion_variable_combobox = QComboBox()
            self.exclusion_variable_combobox.addItems(exclusion_variables)
            current_variable = parameters.get('exclusion_variable', exclusion_variables[0])
            self.exclusion_variable_combobox.setCurrentText(current_variable)
            self.parameters_frame.addWidget(self.exclusion_variable_combobox)

            # Exclusion Criteria
            exclusion_criteria_label = QLabel("Exclusion Criteria:")
            self.parameters_frame.addWidget(exclusion_criteria_label)
            exclusion_criteria = ['Worst', 'Failing', 'Worst Negative', 'Failing Z-Score', 'All Failing Except Best','Worst Combined', 'Failing Combined', 'Worst Negative Combined', 'Failing Z-Score Combined', 'All Failing Except Best Combined']
            self.exclusion_criteria_combobox = QComboBox()
            self.exclusion_criteria_combobox.addItems(exclusion_criteria)
            current_criteria = parameters.get('exclusion_criteria', exclusion_criteria[0])
            self.exclusion_criteria_combobox.setCurrentText(current_criteria)
            self.parameters_frame.addWidget(self.exclusion_criteria_combobox)

            # Confidence
            confidence_label = QLabel("Confidence (e.g., 0.95):")
            self.parameters_frame.addWidget(confidence_label)
            self.confidence_entry = QLineEdit(parameters.get('confidence', '0.95'))
            self.parameters_frame.addWidget(self.confidence_entry)

        elif task_type == 'RWP Removal':
            # Parameters common to Crystallite Size and RWP
            min_weight_label = QLabel("Minimum Percentage Weight:")
            self.parameters_frame.addWidget(min_weight_label)
            self.min_weight_entry = QLineEdit(parameters.get('min_weight', ''))
            self.parameters_frame.addWidget(self.min_weight_entry)

            max_weight_label = QLabel("Maximum Percentage Weight tested:")
            self.parameters_frame.addWidget(max_weight_label)
            self.max_weight_entry = QLineEdit(parameters.get('max_weight', ''))
            self.parameters_frame.addWidget(self.max_weight_entry)

            rwp_threshold_label = QLabel("RWP Threshold:")
            self.parameters_frame.addWidget(rwp_threshold_label)
            self.rwp_threshold_entry = QLineEdit(parameters.get('rwp_threshold', ''))
            self.parameters_frame.addWidget(self.rwp_threshold_entry)

            polynomial_label = QLabel("Polynomial:")
            self.parameters_frame.addWidget(polynomial_label)
            self.polynomial_entry = QLineEdit(parameters.get('polynomial', ''))
            self.parameters_frame.addWidget(self.polynomial_entry)

            # Exclusion Variable
            exclusion_variable_label = QLabel("Exclusion Variable:")
            self.parameters_frame.addWidget(exclusion_variable_label)
            exclusion_variables = ['delta RWP', 'RWP', 'Percentage weight scaled RWP']
            self.exclusion_variable_combobox = QComboBox()
            self.exclusion_variable_combobox.addItems(exclusion_variables)
            current_variable = parameters.get('exclusion_variable', exclusion_variables[0])
            self.exclusion_variable_combobox.setCurrentText(current_variable)
            self.parameters_frame.addWidget(self.exclusion_variable_combobox)

            # Exclusion Criteria
            exclusion_criteria_label = QLabel("Exclusion Criteria:")
            self.parameters_frame.addWidget(exclusion_criteria_label)
            exclusion_criteria = ['Worst', 'Failing', 'Worst Negative', 'Failing Z-Score', 'All Failing Except Best','Worst Combined', 'Failing Combined', 'Worst Negative Combined', 'Failing Z-Score Combined', 'All Failing Except Best Combined']
            self.exclusion_criteria_combobox = QComboBox()
            self.exclusion_criteria_combobox.addItems(exclusion_criteria)
            current_criteria = parameters.get('exclusion_criteria', exclusion_criteria[0])
            self.exclusion_criteria_combobox.setCurrentText(current_criteria)
            self.parameters_frame.addWidget(self.exclusion_criteria_combobox)

            # Confidence
            confidence_label = QLabel("Confidence (e.g., 0.95):")
            self.parameters_frame.addWidget(confidence_label)
            self.confidence_entry = QLineEdit(parameters.get('confidence', '0.95'))
            self.parameters_frame.addWidget(self.confidence_entry)

        elif task_type == 'Compare':
            # Parameters for Compare
            list1_label = QLabel("List 1:")
            self.parameters_frame.addWidget(list1_label)
            self.list1_entry = QLineEdit(parameters.get('list1', ''))
            self.parameters_frame.addWidget(self.list1_entry)

            list2_label = QLabel("List 2:")
            self.parameters_frame.addWidget(list2_label)
            self.list2_entry = QLineEdit(parameters.get('list2', ''))
            self.parameters_frame.addWidget(self.list2_entry)

            external_list_label = QLabel("External List:")
            self.parameters_frame.addWidget(external_list_label)
            self.external_list_entry = QLineEdit(parameters.get('external_list', ''))
            self.parameters_frame.addWidget(self.external_list_entry)

            # Exclusion Variable
            exclusion_variable_label = QLabel("Exclusion Variable:")
            self.parameters_frame.addWidget(exclusion_variable_label)
            exclusion_variables = ['length', 'contents']
            self.exclusion_variable_combobox = QComboBox()
            self.exclusion_variable_combobox.addItems(exclusion_variables)
            current_variable = parameters.get('exclusion_variable', exclusion_variables[0])
            self.exclusion_variable_combobox.setCurrentText(current_variable)
            self.parameters_frame.addWidget(self.exclusion_variable_combobox)

            # Exclusion Criteria
            exclusion_criteria_label = QLabel("Exclusion Criteria:")
            self.parameters_frame.addWidget(exclusion_criteria_label)
            exclusion_criteria = ['Longest', 'Shortest', 'Contains']
            self.exclusion_criteria_combobox = QComboBox()
            self.exclusion_criteria_combobox.addItems(exclusion_criteria)
            current_criteria = parameters.get('exclusion_criteria', exclusion_criteria[0])
            self.exclusion_criteria_combobox.setCurrentText(current_criteria)
            self.parameters_frame.addWidget(self.exclusion_criteria_combobox)

        if task_type == 'Start':
            # Load files from `structures_templates`
            structurelist1_label = QLabel("Structure List:")
            self.parameters_frame.addWidget(structurelist1_label)

            self.structurelist1_combobox = QComboBox()
            template_dir = os.path.join(os.getcwd(), 'structure_templates')
            if os.path.isdir(template_dir):
                files = [f for f in os.listdir(template_dir) if f.endswith('.json')]
                self.structurelist1_combobox.addItems(files)
            else:
                QMessageBox.warning(self, "Directory Not Found", f"{template_dir} does not exist.")

            # Handle current value
            current_file = parameters.get('structurelist1', '')
            if isinstance(current_file, dict):
                # Extract template name and match it to the file
                template_name = current_file.get('template_name', '').replace(' ', '_').lower() + '.json'
                if template_name in files:
                    self.structurelist1_combobox.setCurrentText(template_name)
            elif isinstance(current_file, str) and current_file in files:
                self.structurelist1_combobox.setCurrentText(current_file)

            self.parameters_frame.addWidget(self.structurelist1_combobox)

    def create_incoming_connections_widgets(self):
        incoming_edges = list(self.G.in_edges(self.node['id']))
        self.incoming_params_checkboxes = []

        # Use QHBoxLayout to stack frames left to right
        incoming_layout = QHBoxLayout()
        self.incoming_connections_frame.addLayout(incoming_layout)

        for edge in incoming_edges:
            from_node_id = edge[0]
            from_node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == from_node_id), None)
            if from_node:
                group_box = QGroupBox(f"From: {from_node['label']}")
                group_box.setCheckable(True)
                group_box.setChecked(True)
                group_box_layout = QVBoxLayout()

                # Parameters
                params_label = QLabel("Select information to pull:")
                group_box_layout.addWidget(params_label)

                # Available parameters (example list)
                available_params = [
                    'RWP', 'Crystallite Size', 'Specific Structure - RWP',
                    'Specific Structure - Percentage weight', 'Specific Structure - Crystallite Size',
                    'structures_list', 'valid_structures', 'invalid_structures', 'excluded_structure_list',
                    'Node Specific Output'
                ]

                for param in available_params:
                    checkbox = QCheckBox(param)
                    if 'incoming_params' in self.node:
                        checkbox.setChecked(param in self.node['incoming_params'].get(from_node_id, []))
                    else:
                        # Default behavior: if it's 'structures_list', check it by default
                        if param == 'structures_list':
                            checkbox.setChecked(True)

                    group_box_layout.addWidget(checkbox)
                    self.incoming_params_checkboxes.append((from_node_id, param, checkbox))

                group_box.setLayout(group_box_layout)
                incoming_layout.addWidget(group_box)




    def create_outgoing_connections_widgets(self):
        outgoing_edges = list(self.G.out_edges(self.node['id']))
        self.outgoing_connections_frames = []

        # Use QHBoxLayout to stack frames left to right
        outgoing_layout = QHBoxLayout()
        self.outgoing_connections_frame.addLayout(outgoing_layout)

        for edge in outgoing_edges:
            to_node_id = edge[1]
            to_node = next((n for n in self.flowchart['nodes'] if n['id'] == to_node_id), None)
            if to_node:
                conn = next((c for c in self.flowchart['connections']
                             if c['from'] == self.node['id'] and c['to'] == to_node_id), {})

                group_box = QGroupBox(f"To: {to_node['label']}")
                group_box.setCheckable(True)
                # Corrected line
                condition_exists = bool(conn.get('condition'))
                group_box.setChecked(condition_exists)
                group_box_layout = QVBoxLayout()

                # Condition Widgets
                condition_label = QLabel("Condition:")
                group_box_layout.addWidget(condition_label)
                conditions = ['List length (greater than equal to)','List length (less than equal to)', 'RWP gradient', 'Contains', 'Number of runs (greater than equal to)', 'Number of runs (less than equal to)', 'Finished']
                condition_combobox = QComboBox()
                condition_combobox.addItems(conditions)
                current_condition = conn.get('condition', conditions[0])
                condition_combobox.setCurrentText(current_condition)
                group_box_layout.addWidget(condition_combobox)

                # Parameters for Condition
                condition_param_label = QLabel("Condition Parameter:")
                group_box_layout.addWidget(condition_param_label)
                condition_param_entry = QLineEdit(conn.get('condition_param', ''))
                group_box_layout.addWidget(condition_param_entry)

                # Disable widgets if group box is unchecked
                condition_combobox.setEnabled(condition_exists)
                condition_param_entry.setEnabled(condition_exists)

                # Connect the group box toggled signal to enable/disable widgets
                group_box.toggled.connect(lambda checked, combo=condition_combobox, entry=condition_param_entry: self.toggle_condition_widgets(checked, combo, entry))

                # Store references
                self.outgoing_connections_frames.append({
                    'to_node_id': to_node_id,
                    'group_box': group_box,
                    'condition_combobox': condition_combobox,
                    'condition_param_entry': condition_param_entry,
                })

                group_box.setLayout(group_box_layout)
                outgoing_layout.addWidget(group_box)


    def toggle_condition_widgets(self, checked, condition_combobox, condition_param_entry):
        condition_combobox.setEnabled(checked)
        condition_param_entry.setEnabled(checked)

    def create_connections_widgets(self):
        # Display incoming and outgoing connections
        connections_label = QLabel("Connections:")
        self.connections_frame.addWidget(connections_label)

        # Get incoming and outgoing connections
        incoming_edges = list(self.G.in_edges(self.node['id']))
        outgoing_edges = list(self.G.out_edges(self.node['id']))

        # Incoming Connections
        incoming_label = QLabel("Incoming Connections:")
        self.connections_frame.addWidget(incoming_label)
        for edge in incoming_edges:
            from_node_id = edge[0]
            from_node = next((n for n in self.flowchart['nodes'] if n['id'] == from_node_id), None)
            if from_node:
                label = QLabel(f"From: {from_node['label']}")
                self.connections_frame.addWidget(label)

        # Outgoing Connections
        outgoing_label = QLabel("Outgoing Connections:")
        self.connections_frame.addWidget(outgoing_label)
        self.outgoing_connections_frames = []

        for edge in outgoing_edges:
            to_node_id = edge[1]
            to_node = next((n for n in self.flowchart['nodes'] if n['id'] == to_node_id), None)
            if to_node:
                conn = next((c for c in self.flowchart['connections'] if c['from'] == self.node['id'] and c['to'] == to_node_id), {})
                conn_layout = QHBoxLayout()
                label = QLabel(f"To: {to_node['label']}")
                conn_layout.addWidget(label)

                # Condition
                condition_label = QLabel("Condition:")
                conn_layout.addWidget(condition_label)
                condition_entry = QLineEdit(conn.get('condition', ''))
                conn_layout.addWidget(condition_entry)

                # Priority
                priority_label = QLabel("Priority:")
                conn_layout.addWidget(priority_label)
                priority_entry = QLineEdit(conn.get('priority', ''))
                conn_layout.addWidget(priority_entry)

                # Information Passed
                info_passed_label = QLabel("Info Passed:")
                conn_layout.addWidget(info_passed_label)
                info_passed_combobox = QComboBox()
                info_passed_combobox.addItems(["Structure List", "RWP", "Other"])
                index = info_passed_combobox.findText(conn.get('info_passed', ''))
                if index >= 0:
                    info_passed_combobox.setCurrentIndex(index)
                conn_layout.addWidget(info_passed_combobox)

                self.connections_frame.addLayout(conn_layout)
                self.outgoing_connections_frames.append({
                    'to_node_id': to_node_id,
                    'condition_entry': condition_entry,
                    'priority_entry': priority_entry,
                    'info_passed_combobox': info_passed_combobox
                })

    def on_save(self):
        self.logger.debug("Entering on_save")
        # Update node information
        self.node['label'] = self.label_entry.text()
        self.logger.debug(f"Node label set to: {self.node['label']}")
        self.node['task_type'] = self.task_type_combobox.currentText()
        self.logger.debug(f"Node task_type set to: {self.node['task_type']}")

        self.node['allow_partial_dependencies'] = self.node.get('allow_partial_dependencies', False)

        # Save expected_deps from the input field
        expected_deps_text = self.expected_deps_entry.text().strip()
        if expected_deps_text.isdigit():
            self.node['expected_deps'] = int(expected_deps_text)
        else:
            self.node['expected_deps'] = 1  # Default to 1 if invalid input

        self.logger.debug(f"Node updated with expected_deps: {self.node['expected_deps']}")

        # Update parameters based on task type
        task_type = self.node['task_type']
        parameters = {}
        if task_type == 'Crystallite Size':
            parameters['min_weight'] = self.min_weight_entry.text()
            parameters['max_weight'] = self.max_weight_entry.text()
            parameters['min_crystallite'] = self.min_crystallite_entry.text()
            parameters['crystallite_step'] = self.crystallite_step_entry.text()
            parameters['polynomial'] = self.polynomial_entry.text()
            parameters['exclusion_variable'] = self.exclusion_variable_combobox.currentText()
            parameters['exclusion_criteria'] = self.exclusion_criteria_combobox.currentText()
            parameters['confidence'] = self.confidence_entry.text() if self.confidence_entry else '0.50'
            self.node['parameters'] = parameters
            self.logger.debug(f"Node updated with parameters: {parameters}")
        elif task_type == 'RWP Addition':
            parameters['min_weight'] = self.min_weight_entry.text()
            parameters['max_weight'] = self.max_weight_entry.text()
            parameters['rwp_threshold'] = self.rwp_threshold_entry.text()
            parameters['polynomial'] = self.polynomial_entry.text()
            parameters['exclusion_variable'] = self.exclusion_variable_combobox.currentText()
            parameters['exclusion_criteria'] = self.exclusion_criteria_combobox.currentText()
            parameters['confidence'] = self.confidence_entry.text() if self.confidence_entry else '0.50'
            self.node['parameters'] = parameters
            self.logger.debug(f"Node updated with parameters: {parameters}")
        elif task_type == 'RWP Missing':
            parameters['min_weight'] = self.min_weight_entry.text()
            parameters['max_weight'] = self.max_weight_entry.text()
            parameters['rwp_threshold'] = self.rwp_threshold_entry.text()
            parameters['polynomial'] = self.polynomial_entry.text()
            parameters['exclusion_variable'] = self.exclusion_variable_combobox.currentText()
            parameters['exclusion_criteria'] = self.exclusion_criteria_combobox.currentText()
            parameters['confidence'] = self.confidence_entry.text() if self.confidence_entry else '0.50'
            self.node['parameters'] = parameters
            self.logger.debug(f"Node updated with parameters: {parameters}")
        elif task_type == 'RWP Removal':
            parameters['min_weight'] = self.min_weight_entry.text()
            parameters['max_weight'] = self.max_weight_entry.text()
            parameters['rwp_threshold'] = self.rwp_threshold_entry.text()
            parameters['polynomial'] = self.polynomial_entry.text()
            parameters['exclusion_variable'] = self.exclusion_variable_combobox.currentText()
            parameters['exclusion_criteria'] = self.exclusion_criteria_combobox.currentText()
            parameters['confidence'] = self.confidence_entry.text() if self.confidence_entry else '0.50'
            self.node['parameters'] = parameters
            self.logger.debug(f"Node updated with parameters: {parameters}")
        elif task_type == 'Compare':
            parameters['list1'] = self.list1_entry.text()
            parameters['list2'] = self.list2_entry.text()
            parameters['external_list'] = self.external_list_entry.text()
            parameters['exclusion_variable'] = self.exclusion_variable_combobox.currentText()
            parameters['exclusion_criteria'] = self.exclusion_criteria_combobox.currentText()
        elif task_type == 'Start':
            selected_file = self.structurelist1_combobox.currentText()
            template_dir = os.path.join(os.getcwd(), 'structure_templates')
            file_path = os.path.join(template_dir, selected_file)
            logging.info(f"Selected file: {selected_file}")
            logging.info("Start Type")

            if os.path.exists(file_path):
                with (open(file_path, 'r') as f):
                    try:
                        file_content = json.load(f)
                        parameters['structurelist1'] = file_content  # Append entire JSON structure
                        self.node['parameters'] = parameters
                        self.logger.debug(f"Node updated with parameters: {parameters}")
                        logging.info(f"Node updated with parameters: {parameters}")
                    except json.JSONDecodeError:
                        QMessageBox.warning(self, "Invalid JSON", f"{selected_file} is not a valid JSON file.")
            else:
                QMessageBox.warning(self, "File Not Found", f"{selected_file} not found in {template_dir}.")


        # Save incoming connections parameters
        incoming_params = {}
        for from_node_id, param, checkbox in self.incoming_params_checkboxes:
            if checkbox.isChecked():
                incoming_params.setdefault(from_node_id, []).append(param)
        self.node['incoming_params'] = incoming_params

        # Update outgoing connections
        self.logger.debug("Processing outgoing connections")
        for conn_frame in self.outgoing_connections_frames:
            to_node_id = conn_frame['to_node_id']
            group_box = conn_frame['group_box']
            is_checked = group_box.isChecked()
            self.logger.debug(f"Group box for connection to {to_node_id} is {'checked' if is_checked else 'unchecked'}")

            # Find the connection
            conn = next((c for c in self.flowchart['connections']
                         if c['from'] == self.node['id'] and c['to'] == to_node_id), None)
            if not conn:
                # Should not happen, but just in case
                conn = {
                    'from': self.node['id'],
                    'to': to_node_id
                }
                self.flowchart['connections'].append(conn)

            if is_checked:
                condition = conn_frame['condition_combobox'].currentText()
                condition_param = conn_frame['condition_param_entry'].text()
                self.logger.debug(f"Condition: {condition}, Condition Param: {condition_param}")
                conn['condition'] = condition
                conn['condition_param'] = condition_param
            else:
                # If unchecked, set condition to None
                conn['condition'] = None
                conn['condition_param'] = None
            self.logger.debug(f"Connection updated: {conn}")

        self.logger.debug("Exiting on_save")
        self.accept()


from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, pyqtSlot

class CollapsibleWidget(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet("QPushButton { text-align: left; }")

        self.content_area = QWidget()
        # Initially set the maximum height to 0 to start collapsed
        self.content_area.setMaximumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_area.setLayout(self.content_layout)

        # Animation for expanding/collapsing
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(150)
        self.toggle_animation.setEasingCurve(QEasingCurve.InOutQuart)

        # Set the layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        # Connect the toggle button
        self.toggle_button.toggled.connect(self.on_toggle)

        # Variable to store the content height
        self.content_height = 0

    @pyqtSlot(bool)
    def on_toggle(self, checked):
        if checked:
            # Expand
            # Update content height if it's not already set
            if not self.content_height:
                self.content_height = self.content_area.sizeHint().height()
            self.toggle_animation.stop()
            self.toggle_animation.setStartValue(self.content_area.maximumHeight())
            self.toggle_animation.setEndValue(self.content_height)
            self.toggle_animation.start()
        else:
            # Collapse
            self.toggle_animation.stop()
            self.toggle_animation.setStartValue(self.content_area.maximumHeight())
            self.toggle_animation.setEndValue(0)
            self.toggle_animation.start()
