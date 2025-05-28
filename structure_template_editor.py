# structure_template_editor.py

import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QListWidget, QListWidgetItem,
    QFileDialog, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt


class StructureTemplateEditor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Structure Template Editor")
        self.setGeometry(200, 200, 600, 400)  # Adjust size as needed

        # Paths
        self.database_directory = os.path.join(os.getcwd(), 'structure_database')
        self.template_name = ""  # Will store the currently loaded template name

        # Main vertical layout
        main_layout = QVBoxLayout()

        # Top row of buttons
        button_layout = QHBoxLayout()
        load_button = QPushButton("Load Template")
        save_button = QPushButton("Save Template")
        new_button = QPushButton("New Template")

        load_button.clicked.connect(self.load_template)
        save_button.clicked.connect(self.save_template)
        new_button.clicked.connect(self.new_template)

        button_layout.addWidget(load_button)
        button_layout.addWidget(save_button)
        button_layout.addWidget(new_button)
        button_layout.addStretch()  # Push buttons to the left if desired
        main_layout.addLayout(button_layout)

        # Middle section with two frames and arrow buttons
        middle_layout = QHBoxLayout()

        # Left frame with a QListWidget
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.StyledPanel)
        left_frame.setFrameShadow(QFrame.Raised)

        self.left_list = QListWidget()
        self.left_list.setSelectionMode(QListWidget.ExtendedSelection)  # Allow multi-selection
        self.populate_left_list()

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.left_list)
        left_frame.setLayout(left_layout)

        # Right frame with a QListWidget
        right_frame = QFrame()
        right_frame.setFrameShape(QFrame.StyledPanel)
        right_frame.setFrameShadow(QFrame.Raised)

        self.right_list = QListWidget()
        self.right_list.setSelectionMode(QListWidget.ExtendedSelection)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.right_list)
        right_frame.setLayout(right_layout)

        # Arrows layout (vertical)
        arrows_layout = QVBoxLayout()

        # Buttons for moving items
        self.move_right_button = QPushButton("-->")  # Move selected items from left to right
        self.move_left_button = QPushButton("<--")   # Move selected items from right to left

        self.move_right_button.clicked.connect(self.move_items_left_to_right)
        self.move_left_button.clicked.connect(self.move_items_right_to_left)

        arrows_layout.addStretch()
        arrows_layout.addWidget(self.move_right_button, alignment=Qt.AlignCenter)
        arrows_layout.addWidget(self.move_left_button, alignment=Qt.AlignCenter)
        arrows_layout.addStretch()

        # Add frames and arrows to the middle layout
        middle_layout.addWidget(left_frame, 1)
        middle_layout.addLayout(arrows_layout)
        middle_layout.addWidget(right_frame, 1)

        main_layout.addLayout(middle_layout)

        self.setLayout(main_layout)

    def populate_left_list(self):
        """Populate the left list with structures found in the structure_database directory."""
        self.left_list.clear()
        if os.path.exists(self.database_directory) and os.path.isdir(self.database_directory):
            structures = os.listdir(self.database_directory)
            # You may add filtering (e.g., only .str files)
            for structure in structures:
                if structure.endswith('.str'):  # Example filter
                    item = QListWidgetItem(structure)
                    self.left_list.addItem(item)
        else:
            # Directory doesn't exist or no files found
            pass

    def move_items_left_to_right(self):
        """Move selected items from the left list to the right list."""
        selected_items = self.left_list.selectedItems()
        for item in selected_items:
            self.right_list.addItem(item.text())
            self.left_list.takeItem(self.left_list.row(item))

    def move_items_right_to_left(self):
        """Move selected items from the right list to the left list."""
        selected_items = self.right_list.selectedItems()
        for item in selected_items:
            # Add the item text back to the left list only if it doesn't already exist there
            if not self.item_exists_in_list(self.left_list, item.text()):
                self.left_list.addItem(item.text())
            self.right_list.takeItem(self.right_list.row(item))

    def item_exists_in_list(self, list_widget, text):
        for i in range(list_widget.count()):
            if list_widget.item(i).text() == text:
                return True
        return False

    def load_template(self):
        """Load a template JSON file and populate the right list."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Load Template', '', 'JSON Files (*.json);;All Files (*)', options=options
        )

        if not file_path:
            return

        # Load the JSON file
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load template:\n{e}')
            return

        # Expecting "template_name" and "structures"
        template_name = data.get("template_name", "")
        structures = data.get("structures", [])

        if not isinstance(structures, list):
            QMessageBox.warning(self, 'Invalid Format', 'The "structures" field should be a list.')
            return

        # Clear the right list and add these structures
        self.right_list.clear()
        for s in structures:
            item = QListWidgetItem(s)
            self.right_list.addItem(item)

        self.template_name = template_name
        QMessageBox.information(self, 'Template Loaded', f'Template "{template_name}" loaded successfully.')

    def save_template(self):
        """Save the current template (right list items) into a JSON file."""
        # Prompt the user for a template name
        template_name, ok = QInputDialog.getText(self, 'Template Name', 'Enter template name:', text=self.template_name)
        if not ok or not template_name.strip():
            # User canceled or empty name
            return

        self.template_name = template_name.strip()

        # Collect structures from the right list
        structures = []
        for i in range(self.right_list.count()):
            structures.append(self.right_list.item(i).text())

        data = {
            "template_name": self.template_name,
            "structures": structures
        }

        # Save to JSON file
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Template', '', 'JSON Files (*.json);;All Files (*)', options=options
        )

        if not file_path:
            return

        # Ensure file extension is .json
        if not file_path.lower().endswith('.json'):
            file_path += '.json'

        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, 'Template Saved', f'Template saved to {file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save template:\n{e}')

    def new_template(self):
        """Start a new template (clear right list and reset template name)."""
        self.right_list.clear()
        self.template_name = ""
        QMessageBox.information(self, 'New Template', 'A new template has been started.')
