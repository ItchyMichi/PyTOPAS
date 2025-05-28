from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLineEdit,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QMessageBox
)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from file_handling import update_structure_files

import os
import re


def parse_structure_variables(file_path):
    """Parse variable names and values from a .str file.

    Returns a mapping ``{name: {"value": value, "commented": bool}}``.
    """
    variables = {}
    var_re = re.compile(r"!?(\b\w+_\w+\b)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")
    func_re = re.compile(r"([A-Za-z0-9_]+)\(([^\)]*)\)")
    token_re = re.compile(r"([A-Za-z0-9_]+)\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)?")

    try:
        with open(file_path, 'r', errors='ignore') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return variables

    for line in lines:
        stripped = line.lstrip()
        commented = stripped.startswith("'")

        for name, value in var_re.findall(line):
            info = variables.get(name, {"value": value, "commented": commented})
            info["value"] = value
            info["commented"] = info.get("commented", False) or commented
            variables[name] = info

        for func_name, params in func_re.findall(line):
            info = variables.get(func_name, {"value": params.strip(), "commented": commented})
            info["value"] = params.strip()
            info["commented"] = info.get("commented", False) or commented
            variables[func_name] = info
            for token in params.split(','):
                token = token.strip()
                m = token_re.match(token)
                if m and '_' in m.group(1):
                    name = m.group(1)
                    val = m.group(2)
                    sub_info = variables.get(name, {"value": val, "commented": commented})
                    if val is not None:
                        sub_info["value"] = val
                    sub_info["commented"] = sub_info.get("commented", False) or commented
                    variables[name] = sub_info

    return variables



def update_variable_in_file(file_path, variable, new_value):
    """Update a variable's value within a structure file.

    Returns a tuple ``(success, message)`` where ``success`` is ``True`` if
    the value was updated, otherwise ``False``.  ``message`` contains an
    error description when ``success`` is ``False``.
    """

    try:
        with open(file_path, 'r', errors='ignore') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, f"File not found: {file_path}"

    # Find all lines containing the variable as a whole word
    occ_indices = [i for i, line in enumerate(lines)
                   if re.search(r'\b' + re.escape(variable) + r'\b', line)]

    if not occ_indices:
        return False, f"Variable '{variable}' not found"
    if len(occ_indices) > 1:
        return False, f"Multiple occurrences of '{variable}' found"

    idx = occ_indices[0]
    original_line = lines[idx]

    # Regex to match a simple numeric assignment (var = value)
    pattern = re.compile(
        r'(?P<var>!?\b' + re.escape(variable) + r'\b)\s*(?:=)?\s*'
        r'(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)')

    match = pattern.search(original_line)

    # If not a simple assignment, try a function style call e.g. VAR(1,2,3)
    if not match:
        func_pattern = re.compile(
            r'(?P<var>\b' + re.escape(variable) + r'\b)\s*\((?P<value>[^)]*)\)')
        match = func_pattern.search(original_line)
        if not match:
            return False, f"Could not parse value for '{variable}'"

    start, end = match.span('value')
    new_line = original_line[:start] + str(new_value) + original_line[end:]
    lines[idx] = new_line

    try:
        with open(file_path, 'w') as f:
            f.writelines(lines)
    except OSError as exc:
        return False, str(exc)

    return True, None



class StructureDatabaseViewer(QDialog):
    """Popup dialog to browse structures and inspect variables."""

    def __init__(self, database_directory, parent=None, config_path=None):
        super().__init__(parent)
        self.database_directory = database_directory
        if config_path is None:
            config_path = os.path.join(os.getcwd(), "config.txt")
        self.config_path = config_path
        self.setWindowTitle("Structure Database Viewer")
        self.setGeometry(200, 200, 800, 600)

        self.structures = {}
        self.filtered_structures = []

        self.updating_table = False
        self.pending_changes = {}

        self.init_ui()
        self.load_structures()
        self.populate_structure_list()

    def init_ui(self):
        layout = QVBoxLayout()

        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter by variable:")
        self.filter_edit = QLineEdit()
        self.filter_edit.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)


        var_filter_layout = QHBoxLayout()
        var_filter_label = QLabel("Filter variables:")
        self.var_filter_edit = QLineEdit()
        self.var_filter_edit.textChanged.connect(lambda: self.display_variables(self.structure_list.currentItem(), None))
        var_filter_layout.addWidget(var_filter_label)
        var_filter_layout.addWidget(self.var_filter_edit)
        layout.addLayout(var_filter_layout)

        lists_layout = QHBoxLayout()

        self.structure_list = QListWidget()
        self.structure_list.currentItemChanged.connect(self.display_variables)
        lists_layout.addWidget(self.structure_list)

        self.variable_table = QTableWidget()
        self.variable_table.setColumnCount(2)
        self.variable_table.setHorizontalHeaderLabels(["Variable", "Value"])

        self.variable_table.itemChanged.connect(self.variable_edited)

        lists_layout.addWidget(self.variable_table)

        layout.addLayout(lists_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = QPushButton("Save Changes")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_changes)
        button_layout.addWidget(self.save_button)

        self.update_button = QPushButton("Update Structures to Config Settings")
        self.update_button.clicked.connect(self.update_from_config)
        button_layout.addWidget(self.update_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_structures(self):
        if not os.path.isdir(self.database_directory):
            return
        for fname in sorted(os.listdir(self.database_directory)):
            if fname.endswith('.str'):
                fpath = os.path.join(self.database_directory, fname)
                self.structures[fname] = parse_structure_variables(fpath)
        self.filtered_structures = list(self.structures.keys())

    def populate_structure_list(self):
        self.structure_list.clear()
        for name in self.filtered_structures:
            self.structure_list.addItem(name)
        if self.structure_list.count() > 0:
            self.structure_list.setCurrentRow(0)

    def apply_filter(self):
        text = self.filter_edit.text().strip().lower()
        if not text:
            self.filtered_structures = list(self.structures.keys())
        else:
            self.filtered_structures = [
                name for name, vars_ in self.structures.items()
                if any(text in var.lower() for var in vars_.keys())
            ]
        self.populate_structure_list()

    def display_variables(self, current, previous):
        if not current:
            self.variable_table.setRowCount(0)
            return
        name = current.text()
        variables = self.structures.get(name, {})

        filter_text = self.var_filter_edit.text().strip().lower()
        filtered_items = [
            (var, info) for var, info in variables.items()
            if filter_text in var.lower()
        ]

        self.updating_table = True
        self.variable_table.setRowCount(len(filtered_items))
        for row, (var, info) in enumerate(sorted(filtered_items)):
            value = info.get("value")
            commented = info.get("commented", False)
            var_item = QTableWidgetItem(var)
            if value is None:
                value = ''
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() | Qt.ItemIsEditable)

            if commented:
                # Highlight commented variables in orange
                #orange color for commented variables
                color = QColor(255, 200, 200)
                var_item.setBackground(color)
                item.setBackground(color)

            if self.pending_changes.get(name, {}).get(var) is not None:
                bold_font = item.font()
                bold_font.setBold(True)
                item.setFont(bold_font)
                var_item.setFont(bold_font)

            self.variable_table.setItem(row, 0, var_item)
            self.variable_table.setItem(row, 1, item)
        self.variable_table.resizeColumnsToContents()
        self.updating_table = False

    def variable_edited(self, item):
        if self.updating_table or item.column() != 1:
            return

        variable_item = self.variable_table.item(item.row(), 0)
        if not variable_item:
            return

        var_name = variable_item.text()
        new_value = item.text()

        current_item = self.structure_list.currentItem()
        if not current_item:
            return
        structure_name = current_item.text()

        # Store edited value in memory
        info = self.structures.setdefault(structure_name, {}).get(var_name, {"value": new_value, "commented": False})
        info["value"] = new_value
        self.structures[structure_name][var_name] = info
        self.pending_changes.setdefault(structure_name, {})[var_name] = new_value

        # Mark edited cell bold
        bold_font = item.font()
        bold_font.setBold(True)
        item.setFont(bold_font)
        variable_item.setFont(bold_font)

        self.save_button.setEnabled(True)

    def save_changes(self):
        for structure_name, vars_ in self.pending_changes.items():
            file_path = os.path.join(self.database_directory, structure_name)
            for var, val in vars_.items():
                success, msg = update_variable_in_file(file_path, var, val)
                if not success:
                    QMessageBox.warning(self, "Save Error", msg)
                    return
                info = self.structures.setdefault(structure_name, {}).get(var, {"value": val, "commented": False})
                info["value"] = val
                self.structures[structure_name][var] = info

        self.pending_changes.clear()
        self.save_button.setEnabled(False)
        self.display_variables(self.structure_list.currentItem(), None)

    def update_from_config(self):
        try:
            update_structure_files(self.database_directory, self.config_path)
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", str(exc))
            return

        QMessageBox.information(
            self,
            "Update Complete",
            "Structures updated to configuration settings."
        )
        self.load_structures()
        self.populate_structure_list()

