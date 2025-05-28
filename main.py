import os
import sys
from PyQt5.QtWidgets import QApplication
from main_gui import MainGUI


def create_directories():
    directories = [
        'input_files',
        'output_files',
        'results',
        'analysis_templates',
        'structure_templates',
        'structure_database'
    ]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
    # Create config.txt if it doesn't exist
    if not os.path.exists('config.txt'):
        open('config.txt', 'w').close()

if __name__ == '__main__':
    create_directories()
    app = QApplication(sys.argv)
    main_window = MainGUI()
    main_window.show()
    sys.exit(app.exec_())