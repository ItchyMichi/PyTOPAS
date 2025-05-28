# main_gui.py

import os
import json
import logging
from collections import defaultdict
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QAction, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt
from template_editor import TemplateEditor
from structure_template_editor import StructureTemplateEditor
from structure_database_viewer import StructureDatabaseViewer
from tasks import CrystalliteSizeTask, StartTask, RWPAdditionTask, RWPRemovalTask, RWPTask, RWPMissingTask

from condition_tasks import ListLengthGreaterTask, ListLengthLessTask, RWPGradientTask, ContainsTask, NumberOfRunsGreaterTask, NumberOfRunsLessTask, FinishedTask

class MainGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Analysis Application')
        self.setGeometry(100, 100, 800, 600)
        self.selected_file = ''
        self.output_directory = ''
        self.selected_template = ''
        self.flowchart = None
        self.results_directory = ''  # Directory to store results
        self.index_file_path = ''  # Path to the index JSON file
        self.index_data = {}  # Dictionary to keep track of data locations

        # NEW: Staging dictionary for partial dependencies
        self.node_data_staging = {}  # (run_id, node_id) -> {'data':{}, 'received_deps':set(), 'expected_deps': int}

        # Mapping of task types to their corresponding classes
        self.task_classes = {
            'Crystallite Size': CrystalliteSizeTask,
            'Start': StartTask,
            'RWP Addition': RWPAdditionTask,
            'RWP Removal': RWPRemovalTask,
            'RWP': RWPTask,
            'RWP Missing': RWPMissingTask,
            # Add new task types here
        }

        self.condition_classes = {
            'List length (greater than equal to)': ListLengthGreaterTask,
            'List length (less than equal to)': ListLengthLessTask,
            'RWP gradient': RWPGradientTask,
            'Contains': ContainsTask,
            'Number of runs (greater than equal to)': NumberOfRunsGreaterTask,
            'Number of runs (less than equal to)': NumberOfRunsLessTask,
            'Finished': FinishedTask,
            # Add new task types here
        }

        # Initialize logger
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.init_ui()

    def init_ui(self):
        # Create Menu Bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')

        new_action = QAction('New Analysis', self)
        new_action.triggered.connect(self.new_analysis)
        file_menu.addAction(new_action)

        load_action = QAction('Load Job', self)
        load_action.triggered.connect(self.load_job)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Add Analysis Template Editor menu
        template_menu = menubar.addMenu('Analysis Template Editor')

        open_template_editor_action = QAction('Open Editor', self)
        open_template_editor_action.triggered.connect(self.open_template_editor)
        template_menu.addAction(open_template_editor_action)

        # Add Another Template Editor menu
        structure_template_menu = menubar.addMenu('Structure Template Editor')

        open_structure_template_editor_action = QAction('Open Structure Editor', self)
        open_structure_template_editor_action.triggered.connect(self.open_structure_template_editor)
        structure_template_menu.addAction(open_structure_template_editor_action)

        # Menu for viewing structure database
        view_menu = menubar.addMenu('Structure Database Viewer')
        open_structure_viewer_action = QAction('Open Viewer', self)
        open_structure_viewer_action.triggered.connect(self.open_structure_database_viewer)
        view_menu.addAction(open_structure_viewer_action)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel('No file selected')
        select_file_btn = QPushButton('Select File for Analysis')
        select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(select_file_btn)
        main_layout.addLayout(file_layout)

        # Output directory selection
        output_layout = QHBoxLayout()
        self.output_dir_label = QLabel('No output directory selected')
        select_output_dir_btn = QPushButton('Select Output Directory')
        select_output_dir_btn.clicked.connect(self.select_output_directory)
        output_layout.addWidget(self.output_dir_label)
        output_layout.addWidget(select_output_dir_btn)
        main_layout.addLayout(output_layout)

        # Analysis template selection
        template_layout = QHBoxLayout()
        self.template_label = QLabel('No template selected')
        select_template_btn = QPushButton('Select Analysis Template')
        select_template_btn.clicked.connect(self.select_template)
        template_layout.addWidget(self.template_label)
        template_layout.addWidget(select_template_btn)
        main_layout.addLayout(template_layout)

        # Job queue
        self.job_queue = QTreeWidget()
        self.job_queue.setHeaderLabels(['Job', 'Status'])
        main_layout.addWidget(self.job_queue)

        # Buttons for job queue management
        btn_layout = QHBoxLayout()
        start_analysis_btn = QPushButton('Start Analysis')
        start_analysis_btn.clicked.connect(self.start_analysis)
        clear_jobs_btn = QPushButton('Clear Job List')
        clear_jobs_btn.clicked.connect(self.clear_jobs)
        load_job_btn = QPushButton('Load Unfinished Job')
        load_job_btn.clicked.connect(self.load_job)

        btn_layout.addWidget(start_analysis_btn)
        btn_layout.addWidget(clear_jobs_btn)
        btn_layout.addWidget(load_job_btn)
        main_layout.addLayout(btn_layout)

        central_widget.setLayout(main_layout)

    def select_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select File for Analysis', '', 'All Files (*)',
                                                   options=options)
        if file_path:
            self.file_label.setText(os.path.basename(file_path))
            self.selected_file = file_path

    def open_template_editor(self):
        self.template_editor = TemplateEditor(self)
        self.template_editor.show()

    def open_structure_template_editor(self):
        self.structure_template_editor = StructureTemplateEditor(self)
        self.structure_template_editor.show()

    def open_structure_database_viewer(self):
        database_dir = os.path.join(os.getcwd(), 'structure_database')
        config_path = os.path.join(os.getcwd(), 'config.txt')
        self.structure_database_viewer = StructureDatabaseViewer(
            database_dir, self, config_path
        )
        self.structure_database_viewer.show()

    def select_output_directory(self):
        options = QFileDialog.Options()
        dir_path = QFileDialog.getExistingDirectory(self, 'Select Output Directory', '', options=options)
        if dir_path:
            self.output_dir_label.setText(os.path.basename(dir_path))
            self.output_directory = dir_path

    def select_template(self):
        options = QFileDialog.Options()
        initial_dir = os.path.join(os.getcwd(), 'analysis_templates')
        template_path, _ = QFileDialog.getOpenFileName(self, 'Select Analysis Template', initial_dir, 'All Files (*)',
                                                       options=options)
        if template_path:
            self.template_label.setText(os.path.basename(template_path))
            self.selected_template = template_path

    def start_analysis(self):
        if self.selected_file and self.output_directory and self.selected_template:
            # Load the analysis template (flowchart)
            try:
                with open(self.selected_template, 'r') as f:
                    self.flowchart = json.load(f)
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to load analysis template:\n{e}')
                return

            # Prepare results directory
            self.prepare_results_directory()

            # Start processing from the first node
            starting_node = self.get_starting_node()
            if starting_node:
                self.process_runs([{'run_id': 'run_1', 'node': starting_node, 'iteration': 1}])
                QMessageBox.information(self, 'Analysis', 'Analysis started.')
            else:
                QMessageBox.warning(self, 'Analysis', 'No starting node found in the flowchart.')
        else:
            QMessageBox.warning(self, 'Missing Information',
                                'Please select file, output directory, and analysis template.')

    def prepare_results_directory(self):
        # Create a unique results directory based on input file name and current time
        input_filename = os.path.splitext(os.path.basename(self.selected_file))[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_dir_name = f"{input_filename}_{timestamp}"
        self.results_directory = os.path.join(os.getcwd(), 'results', results_dir_name)
        os.makedirs(self.results_directory, exist_ok=True)

        # Initialize index file
        self.index_file_path = os.path.join(self.results_directory, 'index.json')
        self.index_data = {}  # Reset index data

    def get_starting_node(self):
        nodes = self.flowchart.get('nodes', [])
        # Assuming 'node_1' is the starting node
        starting_node = next((node for node in nodes if node['id'] == 'node_1'), None)
        return starting_node

    def process_runs(self, runs):
        run_queue = runs
        completed_runs = set()
        processed_nodes = set()
        waiting_runs = []

        while run_queue or waiting_runs:
            if run_queue:
                current_run = run_queue.pop(0)
            else:
                # Check waiting_runs for nodes that can now be processed
                current_run = None
                for i, waiting_run in enumerate(waiting_runs):
                    run_id = waiting_run['run_id']
                    node = waiting_run['node']
                    node_id = node['id']
                    incoming_params = node.get('incoming_params', {})
                    allow_partial_dependencies = node.get('allow_partial_dependencies', False)

                    dependencies_met = False
                    available_dependencies = []

                    if allow_partial_dependencies:
                        # Node can proceed if any dependency is met
                        for source_node_id in incoming_params.keys():
                            if (run_id, source_node_id) in processed_nodes:
                                available_dependencies.append(source_node_id)
                        if available_dependencies:
                            dependencies_met = True
                    else:
                        # Node requires all dependencies to be met
                        dependencies_met = True
                        for source_node_id in incoming_params.keys():
                            if (run_id, source_node_id) not in processed_nodes:
                                dependencies_met = False
                                break

                    if dependencies_met:
                        current_run = waiting_runs.pop(i)
                        break

                if current_run is None:
                    self.logger.error("No nodes can be processed due to unmet dependencies.")
                    break

            run_id = current_run['run_id']
            node = current_run['node']
            node_id = node['id']
            task_type = node.get('task_type')
            parameters = node.get('parameters', {})
            incoming_params = node.get('incoming_params', {})
            allow_partial_dependencies = node.get('allow_partial_dependencies', False)

            unique_execution_id = f"{run_id}_{node_id}"
            self.logger.info(f"Processing {unique_execution_id}")

            # If we have merged_data (from try_queue_node), use it directly
            required_data = current_run.get('merged_data', None)

            if required_data is None:
                # Fall back to old logic if merged_data not provided
                dependencies_met = False
                available_dependencies = []

                if allow_partial_dependencies:
                    # Node can proceed if any dependency is met
                    for source_node_id in incoming_params.keys():
                        if (run_id, source_node_id) in processed_nodes:
                            available_dependencies.append(source_node_id)
                    if available_dependencies:
                        dependencies_met = True
                else:
                    # Node requires all dependencies to be met
                    dependencies_met = True
                    for source_node_id in incoming_params.keys():
                        if (run_id, source_node_id) not in processed_nodes:
                            dependencies_met = False
                            break

                if not dependencies_met:
                    waiting_runs.append(current_run)
                    continue

                # Prepare incoming_params_to_use based on partial dependencies
                if allow_partial_dependencies:
                    incoming_params_to_use = {dep: incoming_params[dep] for dep in available_dependencies}
                else:
                    incoming_params_to_use = incoming_params

                # Retrieve and merge data from upstream nodes if no merged_data was provided
                required_data = {}
                for source_node_id, data_keys in incoming_params_to_use.items():
                    source_output = self.load_node_output(run_id, source_node_id)
                    if source_output:
                        for data_key in data_keys:
                            if data_key in required_data:
                                existing = required_data[data_key]
                                new_val = source_output.get(data_key)
                                required_data[data_key] = self.merge_values(existing, new_val)
                            else:
                                required_data[data_key] = source_output.get(data_key)
                    else:
                        self.logger.error(f"Required data from node {source_node_id} not available for node {node_id}")
                        return

            # Now run the task with required_data
            self.process_task(run_id, node_id, task_type, parameters, {}, node, required_data=required_data)
            processed_nodes.add((run_id, node_id))
            self.handle_outgoing_connections(run_id, node_id, processed_nodes, run_queue)

            if not run_queue and not waiting_runs:
                # If no next runs were added, and no outgoing connections were valid, finish the run
                completed_runs.add(run_id)

    def merge_values(self, existing, new_val):
        # If both are lists, extend them
        if isinstance(existing, list) and isinstance(new_val, list):
            existing.extend(new_val)
            return existing
        # If one is list and other not
        if isinstance(existing, list) and not isinstance(new_val, list):
            existing.append(new_val)
            return existing
        if not isinstance(existing, list) and isinstance(new_val, list):
            return [existing] + new_val
        # If neither are lists, put them both in a list
        if not isinstance(existing, list) and not isinstance(new_val, list):
            return [existing, new_val]

    def handle_outgoing_connections(self, run_id, node_id, processed_nodes, run_queue):
        # Get outgoing connections
        outgoing_connections = [
            conn for conn in self.flowchart.get('connections', [])
            if conn['from'] == node_id
        ]

        for conn in outgoing_connections:
            condition = conn.get('condition')
            condition_param = conn.get('condition_param')
            to_node_id = conn['to']
            logging.info(f"Processing connection from {node_id} to {to_node_id}")

            # Get the target node
            to_node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == to_node_id), None)
            if not to_node:
                continue
            logging.info(f"Found target node: {to_node_id}")
            to_node_parameters = to_node.get('parameters', {})

            # Check condition
            if self.check_condition(
                    condition=condition,
                    condition_param=condition_param,
                    run_id=run_id,
                    from_node_id=node_id,
                    to_node_id=to_node_id,
                    parameters=to_node_parameters
            ):
                logging.info(f"Condition met for connection from {node_id} to {to_node_id}")
                # Update downstream dependencies and try to queue node if ready
                self.update_downstream_dependencies(run_id, to_node_id, node_id, run_queue)

    def update_downstream_dependencies(self, run_id, to_node_id, from_node_id, run_queue):
        self.logger.info(f"update_downstream_dependencies called for {to_node_id} with dep {from_node_id}")
        try:
            # Retrieve the node definition
            to_node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == to_node_id), None)
            logging.info(f"Updating downstream dependencies for node: {to_node_id}")
            if not to_node:
                return

            expected_deps = to_node.get('expected_deps', 0)
            if expected_deps == 0:
                # If no expected dependencies, we can potentially queue immediately
                # But let's handle this in a separate method
                self.try_queue_node(run_id, to_node_id, run_queue)
                return

            # Initialize staging entry if not present
            staging_key = (run_id, to_node_id)
            if staging_key not in self.node_data_staging:
                self.node_data_staging[staging_key] = {
                    'data': {},
                    'received_deps': set(),
                    'expected_deps': expected_deps
                }

            # Mark the from_node_id as a received dependency
            self.node_data_staging[staging_key]['received_deps'].add(from_node_id)
            self.try_queue_node(run_id, to_node_id, run_queue)
        except Exception as e:
            self.logger.error(f"Error in update_downstream_dependencies: {e}", exc_info=True)

        # At this stage, we are only recording the arrival of a dependency.
        # We will handle the data merging and final check in the next step.

    def try_queue_node(self, run_id, to_node_id, run_queue):
        self.logger.info(f"Attempting to queue node {to_node_id}")
        try:
            staging_key = (run_id, to_node_id)
            self.logger.info(f"Attempting to queue node: {to_node_id} for run: {run_id}")
            if staging_key not in self.node_data_staging:
                # If we have no staging info, it might mean no deps required
                self.logger.info("No staging info found, checking if node expects zero dependencies.")
                to_node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == to_node_id), None)
                if to_node and to_node.get('expected_deps', 0) == 0:
                    # No dependencies means we can directly queue
                    self.logger.info(f"Node {to_node_id} has no dependencies, queueing directly.")
                    to_node_copy = dict(to_node)
                    run_queue.append({'run_id': run_id, 'node': to_node_copy})
                return

            staging_info = self.node_data_staging[staging_key]
            expected_deps = staging_info['expected_deps']
            received_count = len(staging_info['received_deps'])

            self.logger.info(f"For node {to_node_id}: expected_deps={expected_deps}, received_count={received_count}")
        except Exception as e:
            self.logger.error(f"Error in try_queue_node: {e}", exc_info=True)
            raise
        # Check if all expected dependencies have been received
        if received_count == expected_deps:
            to_node = next((n for n in self.flowchart.get('nodes', []) if n['id'] == to_node_id), None)
            if not to_node:
                self.logger.error(f"No node definition found for {to_node_id}. Cannot queue.")
                return

            incoming_params = to_node.get('incoming_params', {})
            merged_data = {}

            # Merge data from all upstream dependencies
            for from_node_id in staging_info['received_deps']:
                self.logger.info(f"Merging data from dependency {from_node_id} for node {to_node_id}")
                if from_node_id not in incoming_params:
                    self.logger.warning(
                        f"No incoming_params defined for dependency {from_node_id}. Skipping data merge.")
                    continue

                # Load output of the from_node_id
                source_output = self.load_node_output(run_id, from_node_id)
                if source_output is None:
                    self.logger.error(f"Source output for {from_node_id} is None. Cannot merge data.")
                    return  # Early return or consider skipping this dependency

                data_keys = incoming_params[from_node_id]
                self.logger.info(f"Expected data keys from {from_node_id}: {data_keys}")
                for data_key in data_keys:
                    try:
                        new_val = source_output.get(data_key)
                        if data_key in merged_data:
                            merged_data[data_key] = self.merge_values(merged_data[data_key], new_val)
                        else:
                            merged_data[data_key] = new_val
                    except Exception as e:
                        self.logger.error(f"Error merging data key '{data_key}' from {from_node_id}: {e}")
                        return

            to_node_copy = dict(to_node)
            self.logger.info(f"All dependencies met for {to_node_id}. Queuing with merged data: {merged_data.keys()}")
            run_queue.append({
                'run_id': run_id,
                'node': to_node_copy,
                'merged_data': merged_data
            })

            # Once queued, remove from staging to avoid re-queuing in the future
            del self.node_data_staging[staging_key]
        else:
            self.logger.info(f"Not all dependencies met for {to_node_id}. Waiting.")

    def process_task(self, run_id, node_id, task_type, parameters, incoming_params, node, required_data=None):
        # Get the task class
        task_class = self.task_classes.get(task_type)
        logging.info(f"Processing task: {task_type} for node {node_id}")
        if not task_class:
            self.logger.error(f"No task class found for task type: {task_type}")
            return

        # Read node_info to get the current iteration
        node_dir = os.path.join(self.results_directory, run_id, node_id)
        node_info_path = os.path.join(node_dir, 'node_info.json')
        if os.path.exists(node_info_path):
            with open(node_info_path, 'r') as f:
                node_info = json.load(f)
        else:
            node_info = {'iteration': 0}

        # Increment iteration
        node_info['iteration'] += 1
        iteration = node_info['iteration']

        # Save updated node_info
        os.makedirs(node_dir, exist_ok=True)
        with open(node_info_path, 'w') as f:
            json.dump(node_info, f, indent=4)

        if required_data is None:
            # If required_data not passed, run existing logic to get it if needed
            required_data = {}
            # In a scenario where all dependencies are required and we got here,
            # we already handled merging in process_runs if partial dependencies are allowed.
            # If partial dependencies are not allowed, just retrieve data as before.
            for source_node_id, data_keys in incoming_params.items():
                source_output = self.load_node_output(run_id, source_node_id)
                if source_output:
                    for data_key in data_keys:
                        if data_key in required_data:
                            existing = required_data[data_key]
                            new_val = source_output.get(data_key)
                            required_data[data_key] = self.merge_values(existing, new_val)
                        else:
                            required_data[data_key] = source_output.get(data_key)
                else:
                    self.logger.error(f"Required data from node {source_node_id} not available for node {node_id}")
                    return

        # Add input file paths and other required data
        required_data['input_file'] = self.selected_file
        required_data['input_directory'] = os.path.dirname(self.selected_file)
        required_data['output_directory'] = self.output_directory
        required_data['iteration'] = iteration

        logging.info(f"Required data for task: {required_data}")

        # Instantiate and run the task
        task = task_class(
            node_id=node_id,
            parameters=parameters,
            data=required_data,
            output_directory=self.output_directory
        )
        task.run()

        # Add iteration count to output data
        task.output_data['iteration'] = iteration

        # Save the output data
        self.save_node_output(run_id, node_id, iteration, task.output_data)

    def save_node_output(self, run_id, node_id, iteration, output_data):
        # Create directory for the run
        run_dir = os.path.join(self.results_directory, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # Create directory for the node
        node_dir = os.path.join(run_dir, node_id)
        os.makedirs(node_dir, exist_ok=True)

        # File path for the iteration
        file_name = f"{node_id}_iter_{iteration}.json"
        file_path = os.path.join(node_dir, file_name)

        # Save output data to JSON file
        with open(file_path, 'w') as f:
            json.dump(output_data, f, indent=4)

        # Update index data
        self.index_data.setdefault(run_id, {}).setdefault(node_id, {})[str(iteration)] = file_path

        # Save index data to index file
        with open(self.index_file_path, 'w') as f:
            json.dump(self.index_data, f, indent=4)

    def load_node_output(self, run_id, node_id, iteration=None):
        # Load index data if not already loaded
        if not self.index_data:
            if os.path.exists(self.index_file_path):
                with open(self.index_file_path, 'r') as f:
                    self.index_data = json.load(f)
            else:
                self.logger.error(f"Index file not found at {self.index_file_path}")
                return None

        # Get the iterations available for this node
        iterations = self.index_data.get(run_id, {}).get(node_id, {})
        if not iterations:
            self.logger.error(f"No data found for node {node_id} in run {run_id}")
            return None

        if iteration is None:
            # Get the latest iteration
            max_iteration = max(int(k) for k in iterations.keys())
            iteration = max_iteration
            file_path = iterations.get(str(iteration))
            self.logger.info(f"Loading data from iteration {iteration} for node {node_id}")
        else:
            file_path = iterations.get(str(iteration))
            if not file_path:
                self.logger.error(f"No data found for node {node_id} at iteration {iteration} in run {run_id}")
                return None

        # Load output data from JSON file
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                output_data = json.load(f)
            return output_data
        else:
            self.logger.error(f"Data file not found at {file_path}")
            return None

    def check_condition(self, condition, condition_param, run_id, from_node_id, to_node_id, parameters):
        logging.info(f"Checking condition: {condition} with parameter: {condition_param}")

        if not condition:
            # No condition means always proceed
            return True

        # Get the output data from the source node
        from_node_output = self.load_node_output(run_id, from_node_id)
        if from_node_output is None:
            self.logger.error(f"Cannot check condition because data from node {from_node_id} is missing")
            return False

        # Get the iteration count
        iteration = from_node_output.get('iteration', 0)

        # Implement actual condition checking logic
        self.logger.info(f"Checking condition: {condition} with parameter: {condition_param} at iteration {iteration}")

        # Retrieve all keys from the source node
        keys = self.get_all_keys_from_run(run_id, from_node_id, iteration)
        logging.info(f"Keys found in node {from_node_id} for run {run_id}: {keys}")
        if not keys:
            self.logger.error(f"No keys found in node {from_node_id} for run {run_id}")
            return False

        # Initialize the data dictionary
        data = {}

        # Iterate over each key and fetch its value
        for key in keys:
            value = self.get_data_from_run(run_id, from_node_id, iteration, key)
            if value is not None:
                data[key] = value
            else:
                self.logger.warning(f"Key '{key}' not found in node {from_node_id} output.")

        logging.info(f"Data dictionary: {data}")

        # Initialize condition_class using self.condition_classes
        condition_class = self.condition_classes.get(condition)

        if not condition_class:
            self.logger.error(f"No condition class found for condition type: {condition}")
            return False  # Ensure a boolean is returned

        self.logger.info(f"Condition class: {condition_class}")

        try:
            conditiontask = condition_class(
                node_id=to_node_id,  # Pass 'to_node_id' here
                parameters=parameters,
                data=data,  # Pass the assembled data dictionary
                output_directory=self.output_directory
            )
        except Exception as e:
            self.logger.error(f"Failed to instantiate condition class: {e}")
            return False

        try:
            return conditiontask.run(condition_param, iteration)
        except Exception as e:
            self.logger.error(f"Condition check failed: {e}")
            return False

    def clear_jobs(self):
        self.job_queue.clear()

    def load_job(self):
        # Placeholder for loading an unfinished job
        QMessageBox.information(self, 'Load Job', 'Function to load an unfinished job.')

    def new_analysis(self):
        # Placeholder for creating a new analysis
        QMessageBox.information(self, 'New Analysis', 'Function to start a new analysis.')

    def open_template_editor(self):
        self.template_editor = TemplateEditor(self)
        self.template_editor.show()

    def get_all_keys_from_run(self, run_id, node_id, iteration=None):
        """
        Retrieve all keys from a node's output data.

        :param run_id: ID of the run
        :param node_id: ID of the node
        :param iteration: Iteration number (optional). If None, fetches the latest iteration.
        :return: List of keys or empty list if data not found.
        """
        output_data = self.load_node_output(run_id, node_id, iteration)
        if output_data is not None:
            return list(output_data.keys())
        else:
            self.logger.error(f"Data not found for run {run_id}, node {node_id}, iteration {iteration}")
            return []

    # Additional method to retrieve specific information
    def get_data_from_run(self, run_id, node_id, iteration, key_name):
        """
        Retrieve specific information from a run by providing run_id, node_id, iteration, and key_name.

        :param run_id: ID of the run
        :param node_id: ID of the node
        :param iteration: Iteration number
        :param key_name: Key name of the data to retrieve
        :return: Value associated with key_name or None if not found
        """
        output_data = self.load_node_output(run_id, node_id, iteration)
        if output_data is not None:
            return output_data.get(key_name)
        else:
            self.logger.error(f"Data not found for run {run_id}, node {node_id}, iteration {iteration}")
            return None
