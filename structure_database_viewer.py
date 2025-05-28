from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLineEdit,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QMessageBox
)

from PyQt5.QtCore import Qt

import os
import re


def parse_structure_variables(file_path):
    """Parse variable names and values from a .str file."""
    variables = {}
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
    except FileNotFoundError:
        return variables

    # Variables defined as name value
    for name, value in re.findall(r'!?(\b\w+_\w+\b)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)', content):
        variables[name] = value

    # Functions and variables inside parentheses
    for func_name, params in re.findall(r'([A-Za-z0-9_]+)\(([^\)]*)\)', content):
        variables.setdefault(func_name, params.strip())
        for token in params.split(','):
            token = token.strip()
            m = re.match(r'([A-Za-z0-9_]+)\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)?', token)
            if m and '_' in m.group(1):
                name = m.group(1)
                if name not in variables:
                    variables[name] = m.group(2)
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

    # Regex to match the variable and its numeric value
    pattern = re.compile(
        r'(?P<var>!?\b' + re.escape(variable) + r'\b)\s*(?:=)?\s*'
        r'(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)')

    match = pattern.search(original_line)
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

    def __init__(self, database_directory, parent=None):
        super().__init__(parent)
        self.database_directory = database_directory
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
            (var, val) for var, val in variables.items()
            if filter_text in var.lower()
        ]

        self.updating_table = True
        self.variable_table.setRowCount(len(filtered_items))
        for row, (var, val) in enumerate(sorted(filtered_items)):
            var_item = QTableWidgetItem(var)
            if val is None:
                val = ''
            item = QTableWidgetItem(str(val))
            item.setFlags(item.flags() | Qt.ItemIsEditable)

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
        self.structures.setdefault(structure_name, {})[var_name] = new_value
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
                self.structures.setdefault(structure_name, {})[var] = val

        self.pending_changes.clear()
        self.save_button.setEnabled(False)
        self.display_variables(self.structure_list.currentItem(), None)

