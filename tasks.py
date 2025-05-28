import os
import logging
import re
import shutil
import subprocess
from ast import parse
from concurrent.futures import ThreadPoolExecutor

from numpy.random import logistic

from file_handling import parse_config, get_structure_content_in_content, parse_crystallite_size, parse_percentage_weight
from exclusion_tasks import CrystalliteSizeExclusionTask, RWPExclusionTask

class BaseTask:
    def __init__(self, node_id, parameters, data, output_directory):
        self.node_id = node_id
        self.parameters = parameters  # Parameters defined in the node
        self.data = data              # Data from previous nodes
        self.output_directory = data.get('output_directory', output_directory)
        self.logger = logging.getLogger(f'Task_{self.node_id}')
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_directory = data.get('input_directory', os.getcwd())
        self.input_file = data.get('input_file')
        self.input_dir = os.path.join(self.script_dir, 'input_files')
        self.output_dir = os.path.join(self.script_dir, 'output_files')
        self.output_data = {}         # Output data to be saved
        self.root_dir = os.getcwd()

        self.exclusion_classes = {
            'Crystallite Size': CrystalliteSizeExclusionTask,
            'RWP': RWPExclusionTask,
            # Add new task types here
        }

    def clear_input_output_files(self):
        # Clear the input and output directories
        for dir_path in [self.input_dir, self.output_dir]:
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            else:
                os.makedirs(dir_path)

    def move_output_files(self):
        #move output files to output directory from input directory
        logging.info("Moving .out files to output directory")
        for file in os.listdir(self.input_dir):
            if file.endswith('.out'):
                logging.info(f"Moving file {file}")
                file_path = os.path.join(self.input_dir, file)
                logging.info(f"File path: {file_path}")
                if os.path.isfile(file_path):
                    logging.info(f"Moving file {file} to {self.output_dir}")
                    shutil.move(file_path, self.output_dir)
                    logging.info(f"File moved to {self.output_dir}")
                    #os.remove(file_path)

    def parse_output_crystallite_size(self, structures_list):
        self.logger.info("Parsing output files for Crystallite Size")

        output_files = [os.path.join(self.output_dir, f) for f in os.listdir(self.output_dir) if f.endswith('.out')]
        parsed_data = {}

        for output_file in output_files:
            # Read the content of the output file
            logging.info(f"Reading output file: {output_file}")
            with open(output_file, 'r') as f:
                content = f.read()
            for structure in structures_list:
                logging.info(f"Parsing structure: {structure}")
                #return a dictionary with the structure name as the key and the crystallite size as the value
                subcontent = get_structure_content_in_content(content, structure)
                crystallite_size = parse_crystallite_size(subcontent)
                logging.info(f"Crystallite size: {crystallite_size}")
                structure_name = os.path.splitext(os.path.basename(structure))[0]
                logging.info(f"Structure name: {structure_name}")
                parsed_data[structure_name] = crystallite_size
                logging.info(f"Parsed data: {parsed_data}")
        return parsed_data

    def parse_output_percentage_weight(self, structures_list):
        self.logger.info("Parsing output files for Crystallite Size")

        output_files = [os.path.join(self.output_dir, f) for f in os.listdir(self.output_dir) if f.endswith('.out')]
        parsed_data = {}

        for output_file in output_files:
            # Read the content of the output file
            logging.info(f"Reading output file: {output_file}")
            with open(output_file, 'r') as f:
                content = f.read()
            for structure in structures_list:
                logging.info(f"Parsing structure: {structure}")
                #return a dictionary with the structure name as the key and the crystallite size as the value
                subcontent = get_structure_content_in_content(content, structure)
                percentage_weight = parse_percentage_weight(subcontent)
                logging.info(f"Percentage weight: {percentage_weight}")
                structure_name = os.path.splitext(os.path.basename(structure))[0]
                logging.info(f"Structure name: {structure_name}")
                parsed_data[structure_name] = percentage_weight
                logging.info(f"Parsed data: {parsed_data}")
        return parsed_data

    def parse_output_RWP(self, structures_list, excluded_structure_list):
        """
        Parse RWP values for included and excluded structures.

        Returns:
            dict: A dictionary of the form:
                  {
                      "rwp_all": {"RWP": <float or None>},
                      "StructureName1": {"RWP": <float or None>},
                      "StructureName2": {"RWP": <float or None>},
                      ...
                  }
        """

        parsed_data_RWP = {}

        # 1. Parse the all_structures.out file
        all_structures_out_file = os.path.join(self.output_dir, "all_structures.out")
        if os.path.exists(all_structures_out_file):
            with open(all_structures_out_file, 'r') as out_file:
                all_content = out_file.read()
            # Extract RWP
            rwp_match = re.search(r'r_wp\s+([\d.]+)', all_content)
            if rwp_match:
                rwp_all = float(rwp_match.group(1))
                logging.info(f"RWP (all structures): {rwp_all}")
            else:
                logging.warning("RWP value not found in all_structures.out.")
                rwp_all = None
        else:
            logging.warning(f"all_structures.out file not found: {all_structures_out_file}")
            rwp_all = None

        # 2. Set rwp_all in parsed_data_RWP as a dict
        parsed_data_RWP["rwp_all"] = {"RWP": rwp_all}

        # Convert to sets
        excluded_set = {
            os.path.splitext(os.path.basename(s))[0] for s in excluded_structure_list
        }
        included_set = {
            os.path.splitext(os.path.basename(s))[0]
            for s in structures_list
            if os.path.splitext(os.path.basename(s))[0] not in excluded_set
        }

        # 3. For included structures, store {"RWP": rwp_all}
        for included_structure in included_set:
            parsed_data_RWP[included_structure] = {"RWP": rwp_all}

        # 4. For excluded structures, parse from all_structures_{excluded_structure}.out
        for excluded_structure in excluded_set:
            excluded_out_file = os.path.join(self.output_dir, f"all_structures_{excluded_structure}.out")

            if os.path.exists(excluded_out_file):
                with open(excluded_out_file, 'r') as out_file:
                    excluded_content = out_file.read()
                rwp_match = re.search(r'r_wp\s+([\d.]+)', excluded_content)
                if rwp_match:
                    rwp_excluded = float(rwp_match.group(1))
                    logging.info(f"RWP for excluded structure {excluded_structure}: {rwp_excluded}")
                    parsed_data_RWP[excluded_structure] = {"RWP": rwp_excluded}
                else:
                    logging.warning(f"RWP value not found in {excluded_out_file}.")
                    parsed_data_RWP[excluded_structure] = {"RWP": None}
            else:
                logging.warning(f"Excluded structure output file not found: {excluded_out_file}")
                parsed_data_RWP[excluded_structure] = {"RWP": None}

        return parsed_data_RWP

    def parse_output_RWP_negative(self, structures_list, excluded_structure_list):
        """
        Parse RWP values for included and excluded structures.

        Returns:
            dict: A dictionary of the form:
                  {
                      "rwp_all": {"RWP": <float or None>},
                      "StructureName1": {"RWP": <float or None>},
                      "StructureName2": {"RWP": <float or None>},
                      ...
                  }
        """

        parsed_data_RWP = {}

        # 1. Parse the all_structures.out file
        all_structures_out_file = os.path.join(self.output_dir, "all_structures.out")
        if os.path.exists(all_structures_out_file):
            with open(all_structures_out_file, 'r') as out_file:
                all_content = out_file.read()
            # Extract RWP
            rwp_match = re.search(r'r_wp\s+([\d.]+)', all_content)
            if rwp_match:
                rwp_all = float(rwp_match.group(1))
                logging.info(f"RWP (all structures): {rwp_all}")
            else:
                logging.warning("RWP value not found in all_structures.out.")
                rwp_all = None
        else:
            logging.warning(f"all_structures.out file not found: {all_structures_out_file}")
            rwp_all = None



        # 2. Set rwp_all in parsed_data_RWP as a dict
        parsed_data_RWP["rwp_all"] = {"RWP": rwp_all}

        # Convert to sets
        excluded_set = {
            os.path.splitext(os.path.basename(s))[0] for s in excluded_structure_list
        }
        included_set = {
            os.path.splitext(os.path.basename(s))[0]
            for s in structures_list
            if os.path.splitext(os.path.basename(s))[0] not in excluded_set
        }

        # 3. For included structures, store {"RWP": rwp_all}
        for included_structure in included_set:
            parsed_data_RWP[included_structure] = {"RWP": rwp_all}

        # 4. For excluded structures, parse from all_structures_{excluded_structure}.out
        for excluded_structure in excluded_set:
            excluded_out_file = os.path.join(self.output_dir, f"all_structures_{excluded_structure}.out")

            if os.path.exists(excluded_out_file):
                with open(excluded_out_file, 'r') as out_file:
                    excluded_content = out_file.read()
                rwp_match = re.search(r'r_wp\s+([\d.]+)', excluded_content)
                if rwp_match:
                    rwp_excluded = float(rwp_match.group(1))
                    logging.info(f"RWP for excluded structure {excluded_structure}: {rwp_excluded}")
                    parsed_data_RWP[excluded_structure] = {"RWP": rwp_excluded}
                else:
                    logging.warning(f"RWP value not found in {excluded_out_file}.")
                    parsed_data_RWP[excluded_structure] = {"RWP": None}
            else:
                logging.warning(f"Excluded structure output file not found: {excluded_out_file}")
                parsed_data_RWP[excluded_structure] = {"RWP": None}

        return parsed_data_RWP

    def parse_output_RWP_percentage_weight(self, structures_list, excluded_structure_list):
        """
        Parse percentage weights from output files.

        For included structures (those in structures_list but not in excluded_structure_list),
        parse from 'all_structures.out'.

        For excluded structures, parse from 'all_structures_{structure_name}.out'.
        """

        # Convert lists to sets for easier operations
        excluded_set = {os.path.splitext(os.path.basename(s))[0] for s in excluded_structure_list}
        included_set = {os.path.splitext(os.path.basename(s))[0] for s in structures_list if
                        os.path.splitext(os.path.basename(s))[0] not in excluded_set}

        parsed_data = {}

        # 1. Parse percentage weight for included structures from all_structures.out
        all_structures_out_file = os.path.join(self.output_dir, "all_structures.out")

        if not os.path.exists(all_structures_out_file):
            self.logger.warning(f"all_structures.out file not found: {all_structures_out_file}")
        else:
            self.logger.info("Parsing percentage weights from all_structures.out for included structures.")
            with open(all_structures_out_file, 'r') as f:
                all_content = f.read()

            for structure_name in included_set:
                # The original structure list might have ".str" so we reconstruct it if needed
                # But get_structure_content_in_content should just need the base name without extension
                full_structure_name = structure_name + '.str'

                subcontent = get_structure_content_in_content(all_content, full_structure_name)
                if subcontent:
                    percentage_weight = parse_percentage_weight(subcontent)
                    parsed_data[structure_name] = percentage_weight
                    self.logger.info(f"Parsed percentage weight for {structure_name}: {percentage_weight}")
                else:
                    self.logger.warning(f"Content for {structure_name} not found in all_structures.out.")
                    parsed_data[structure_name] = None

        # 2. Parse percentage weight for excluded structures from their respective all_structures_{excluded_structure}.out
        for excluded_structure in excluded_set:
            excluded_out_file = os.path.join(self.output_dir, f"all_structures_{excluded_structure}.out")
            if not os.path.exists(excluded_out_file):
                self.logger.warning(f"Output file for excluded structure not found: {excluded_out_file}")
                parsed_data[excluded_structure] = None
                continue

            self.logger.info(
                f"Parsing percentage weight for excluded structure {excluded_structure} from {excluded_out_file}.")
            with open(excluded_out_file, 'r') as f:
                excluded_content = f.read()

            # The excluded structure name with extension for subcontent parsing
            full_excluded_name = excluded_structure + '.str'
            subcontent = get_structure_content_in_content(excluded_content, full_excluded_name)

            if subcontent:
                percentage_weight = parse_percentage_weight(subcontent)
                parsed_data[excluded_structure] = percentage_weight
                self.logger.info(
                    f"Parsed percentage weight for excluded structure {excluded_structure}: {percentage_weight}")
            else:
                self.logger.warning(
                    f"Content for excluded structure {excluded_structure} not found in {excluded_out_file}.")
                parsed_data[excluded_structure] = None

        return parsed_data

    def parse_output_crystallite_size_with_exclusions(self, structures_list, excluded_structure_list):
        """
        Parse crystallite size values for included and excluded structures.

        For included structures (those in structures_list but not in excluded_structure_list),
        parse from 'all_structures.out'.

        For excluded structures, parse from 'all_structures_{structure_name}.out'.

        Returns:
            dict: A dictionary with structure_name (no extension) as keys and crystallite size values as floats.
        """
        self.logger.info("Parsing output files for Crystallite Size with exclusions logic.")

        # Convert to sets without extensions
        excluded_set = {os.path.splitext(os.path.basename(s))[0] for s in excluded_structure_list}
        included_set = {os.path.splitext(os.path.basename(s))[0] for s in structures_list if
                        os.path.splitext(os.path.basename(s))[0] not in excluded_set}

        parsed_data_crystallite = {}

        # 1. Parse crystallite from all_structures.out for included structures
        all_structures_out_file = os.path.join(self.output_dir, "all_structures.out")
        if os.path.exists(all_structures_out_file):
            with open(all_structures_out_file, 'r') as f:
                all_content = f.read()

            for included_structure in included_set:
                # Reconstruct full name with extension
                full_structure_name = included_structure + '.str'
                subcontent = get_structure_content_in_content(all_content, full_structure_name)
                if subcontent:
                    crystallite_size = parse_crystallite_size(subcontent)
                    parsed_data_crystallite[included_structure] = crystallite_size
                    self.logger.info(f"Crystallite size for included structure {included_structure}: {crystallite_size}")
                else:
                    self.logger.warning(f"No crystallite data found for included structure {included_structure} in all_structures.out.")
                    parsed_data_crystallite[included_structure] = None
        else:
            self.logger.warning(f"all_structures.out file not found at {all_structures_out_file}. No included structures will have crystallite values from this file.")

        # 2. Parse crystallite from individual all_structures_{excluded_structure}.out for excluded structures
        for excluded_structure in excluded_set:
            excluded_out_file = os.path.join(self.output_dir, f"all_structures_{excluded_structure}.out")
            if os.path.exists(excluded_out_file):
                with open(excluded_out_file, 'r') as f:
                    excluded_content = f.read()
                full_excluded_name = excluded_structure + '.str'
                subcontent = get_structure_content_in_content(excluded_content, full_excluded_name)
                if subcontent:
                    crystallite_size = parse_crystallite_size(subcontent)
                    parsed_data_crystallite[excluded_structure] = crystallite_size
                    self.logger.info(f"Crystallite size for excluded structure {excluded_structure}: {crystallite_size}")
                else:
                    self.logger.warning(f"No crystallite data found for excluded structure {excluded_structure} in {excluded_out_file}.")
                    parsed_data_crystallite[excluded_structure] = None
            else:
                self.logger.warning(f"{excluded_out_file} for excluded structure {excluded_structure} not found.")
                parsed_data_crystallite[excluded_structure] = None

        return parsed_data_crystallite


    def combine_parsed_data(self, **data_dicts):
        """
        Combine multiple parsed data dictionaries into a single dictionary.

        Each keyword argument is a data label and its corresponding dictionary.
        For example:
        combine_parsed_data(crystallite_size=parsed_data_crystallite_size, percentage_weight=parsed_data_percentage_weight)
        """
        combined_data = {}
        if not data_dicts:
            return combined_data

        # Get all structure names
        structure_names = set()
        for data_dict in data_dicts.values():
            structure_names.update(data_dict.keys())

        for structure_name in structure_names:
            combined_data[structure_name] = {}
            for data_label, data_dict in data_dicts.items():
                combined_data[structure_name][data_label] = data_dict.get(structure_name)
        return combined_data

    def run_topas_simulation(self, tc_executable, input_file, output_dir):
        # Build the command to execute TOPAS
        output_file_name = f"{os.path.basename(input_file)[:-4]}.out"
        output_file_path = os.path.join(output_dir, output_file_name)

        # TOPAS execution command
        cmd_command = f'"{tc_executable}" "{input_file}"'

        self.logger.info(f"Running command: {cmd_command}")

        try:
            # Execute the command and capture output
            result = subprocess.run(cmd_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.logger.info(f"Command output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with error: {e.stderr}")
            raise

    def run_simulation(self):
        self.logger.info("Running simulations")
        config_path = os.path.join(self.root_dir, 'config.txt')
        self.logger.info(f"Reading config file from {config_path}")
        if os.path.exists(config_path):
            self.logger.info(f"Config exists at {config_path}")
            try:
                # Use the parse_config function from filehandling.py
                config = parse_config(config_path)
                self.logger.info(f"Config: {config}")
            except Exception as e:
                self.logger.error(f"Error parsing config file: {e}")
                return  # Exit the method if parsing fails
        else:
            self.logger.warning(f"Config file not found at {config_path}. Using default TOPAS directory.")
            config = {}

        topas_dir = config.get('topas_dir', 'C:\\TOPAS5')
        tc_executable = os.path.join(topas_dir, 'tc.exe')
        self.logger.info(f"Using TOPAS executable: {tc_executable}")

        # Check if tc.exe exists
        if not os.path.exists(tc_executable):
            self.logger.error(f"TOPAS executable not found at {tc_executable}")
            return

        # Limit the number of parallel processes
        max_parallel_processes = 10

        # Use a ThreadPoolExecutor for parallel execution with a limit on concurrent processes
        input_files = [os.path.join(self.input_dir, f) for f in os.listdir(self.input_dir) if f.endswith('.inp')]
        with ThreadPoolExecutor(max_workers=max_parallel_processes) as executor:
            futures = []
            for input_file in input_files:
                future = executor.submit(self.run_topas_simulation, tc_executable, input_file, self.output_dir)
                futures.append(future)

            # Wait for all futures to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Simulation failed with error: {e}")
                    # Handle the exception as needed (e.g., continue or abort)

        self.logger.info("All simulations completed successfully.")

    def screen_data(self, parsed_data, task_type):
        """
        Screen parsed data using the appropriate exclusion task.
        """
        self.logger.info(f"Screening data {parsed_data}")
        self.logger.info(f"Screening data (Task Type: {task_type}): {parsed_data}")

        # 1) Identify the correct exclusion class based on self.parameters
        exclusion_task_class = self.exclusion_classes.get(
            self.parameters.get('exclusion_variable')
        )

        self.parameters["task_type"] = task_type

        # 2) Instantiate the exclusion task and pass task_type
        exclusion_task = exclusion_task_class(
            parameters=self.parameters
        )

        # 3) Run the exclusion logic
        data = exclusion_task.run(parsed_data)

        self.logger.info(f"Screened Data: {data}")
        self.logger.info(f"Valid structures: {data['valid_structures']}")
        self.logger.info(f"Invalid structures: {data['invalid_structures']}")

        # 4) Store results in self.output_data
        structure_result_names = [
            name for name in parsed_data.keys()
            if name not in [
                'valid_structures', 'invalid_structures',
                'structure_list', 'excluded_structure_list'
            ]
        ]

        self.output_data['results'] = {name: data[name] for name in structure_result_names}
        self.output_data['valid_structures'] = data['valid_structures']
        self.output_data['invalid_structures'] = data['invalid_structures']
        self.output_data['structures_list'] = data['structures_list']
        self.output_data['excluded_structure_list'] = data['excluded_structure_list']




    def create_all_structures_inp_file(self, structures_list, input_file_name, structures_dir):
        """
        Creates a single .inp file that includes the modified start.inp header and all the structures from structures_list.

        :param structures_list: List of structure file names.
        :param input_file_name: Name of the input file to be processed (e.g., 'all_structures.inp').
        :param structures_dir: Directory where structure files are located.
        """
        # Paths for start.inp and the new all_structures.inp
        original_start_inp_path = os.path.join(self.script_dir, 'start.inp')
        all_structures_inp_path = os.path.join(self.input_dir, 'all_structures.inp')

        # Copy start.inp to input directory and rename it to input_file_name (e.g., 'all_structures.inp')
        shutil.copy(original_start_inp_path, all_structures_inp_path)
        self.logger.info(f"Copied start.inp to {all_structures_inp_path}")

        # Verify that the copied file exists
        if not os.path.exists(all_structures_inp_path):
            self.logger.error(f"Template file {all_structures_inp_path} not found.")
            return

        # Read the copied start.inp file
        with open(all_structures_inp_path, 'r') as start_inp_file:
            start_inp_lines = start_inp_file.readlines()

        # Modify the first line with input file name
        input_file = self.data.get('input_file', 'default_input.xdd')
        start_inp_lines[0] = f'   xdd "{input_file}"\n'

        # Modify the line for polynomial number (assuming it's line index 3)
        polynomial_number = self.parameters.get('polynomial', '3')
        start_inp_lines[3] = f'   bkg @ {"0 " * int(polynomial_number)}\n'

        # Open the all_structures.inp file for writing (overwrite the existing content)
        with open(all_structures_inp_path, 'w') as inp_file:
            # Write the modified header
            inp_file.writelines(start_inp_lines)
            self.logger.info(f"Modified header in {all_structures_inp_path}")

            # Iterate over all structures and append their content
            for structure_name in structures_list:
                # Find the structure file
                structure_file_path = None
                for root, dirs, files in os.walk(structures_dir):
                    if structure_name in files:
                        structure_file_path = os.path.join(root, structure_name)
                        break

                if not structure_file_path:
                    self.logger.error(f"Structure file {structure_name} not found in {structures_dir}.")
                    continue  # Skip to the next structure

                # Read the structure file content
                with open(structure_file_path, 'r') as structure_file:
                    structure_content = structure_file.read()

                # Append the structure content to the input file
                inp_file.write(f"\n/*{structure_name}_START*/\n")
                inp_file.write(structure_content)
                inp_file.write(f"\n/*{structure_name}_END*/\n")
                self.logger.info(f"Appended structure {structure_name} to {input_file_name}")

class StartTask(BaseTask):
    def run(self):
        self.logger.info(f"Running Start Task for Node {self.node_id}")

        # Delete all files in input_files and output_files directories
        self.clear_input_output_files()

        # Get structures specified in the analysis template
        structures_list = []
        for key in self.parameters:
            if 'structures' in self.parameters[key]:
                structures_list.extend(self.parameters[key]['structures'])
        self.logger.info(f"Structures from parameters: {structures_list}")

        # Add the structures to output data under 'structures_list'
        self.output_data['structures_list'] = structures_list

        # The input_file, input_directory, and output_directory are already passed in self.data
        self.logger.info("Structures added to output data")

class CrystalliteSizeTask(BaseTask):
    def run(self):
        # Retrieve 'input_file' from 'self.data'
        input_file = self.data.get('input_file', 'default_input.xdd')
        self.logger.info(f"Running Crystallite Size Task for Node {self.node_id} on file {input_file}")

        # Retrieve 'structures_list' from 'self.data'
        structures_list = self.data.get('structures_list', [])
        valid_structures_list = self.data.get('valid_structures', [])
        invalid_structures_list = self.data.get('invalid_structures', [])
        excluded_structure_list = self.data.get('excluded_structure_list', [])

        logging.info(f"Valid structures: {valid_structures_list}")
        logging.info(f"Invalid structures: {invalid_structures_list}")
        logging.info(f"Structure list is: {structures_list}")

        if not structures_list:
            if valid_structures_list:
                structures_list = [structure + '.str' for structure in valid_structures_list]
            elif invalid_structures_list:
                structures_list = [structure + '.str' for structure in invalid_structures_list]
            else:
                structures_list = [structure + '.str' for structure in excluded_structure_list]


        if not structures_list:
            self.logger.error("No 'structures_list' found in input data")
            return

        # Prepare input files
        self.prepare_all_structures_input_file(structures_list, input_file)



        # Run simulations
        self.run_simulation()
        self.move_output_files()
        # Parse output files
        logging.info("Parsing output files")
        parsed_data_crystallite_size = self.parse_output_crystallite_size(structures_list)
        # append parse_output_percentage_weight to parsed_data
        parsed_data_percentage_weight = self.parse_output_percentage_weight(structures_list)
        combined_data = self.combine_parsed_data(
            crystallite_size=parsed_data_crystallite_size,
            percentage_weight=parsed_data_percentage_weight
        )
        logging.info(f"Combined data: {combined_data}")
        # Collate data
        self.screen_data(combined_data,task_type="CrystalliteSize" )
        self.clear_input_output_files()



    def prepare_all_structures_input_file(self, structures_list, input_file):
        self.logger.info("Preparing input files for Crystallite Size Task")

        # Ensure input directory exists
        os.makedirs(self.input_dir, exist_ok=True)

        # Path to the structures directory (assuming it's in the script directory)
        structures_dir = os.path.join(self.script_dir, 'structure_database')

        self.create_all_structures_inp_file(structures_list, input_file, structures_dir)

class RWPTask(BaseTask):
    def run(self):
        input_file = self.data.get('input_file', 'default_input.xdd')
        self.logger.info(f"Running RWP Basic Removal Task for Node {self.node_id} on file {input_file}")

        # Retrieve lists from self.data
        structures_list = self.data.get('structures_list', [])
        valid_structures_list = self.data.get('valid_structures', [])
        invalid_structures_list = self.data.get('invalid_structures', [])

        self.logger.info(f"Structures list: {structures_list}")

        # If structures_list is empty, try to populate from valid or invalid
        if not structures_list:
            if valid_structures_list:
                structures_list = [s + '.str' for s in valid_structures_list]
            elif invalid_structures_list:
                structures_list = [s + '.str' for s in invalid_structures_list]
            else:
                self.logger.error("No 'structures_list' found in input data")
                return

        # Prepare input files:
        #   - one all_structures.inp (with everything)
        #   - for each structure in structures_list, create a scenario excluding that one structure
        self.prepare_removal_RWP_input_file(structures_list, input_file)

        # Run simulations & move output files
        self.run_simulation()
        self.move_output_files()

        # Parsing stage
        self.logger.info("Parsing output files")

        # Parse RWP from baseline (all_structures.out) and each scenario (all_structures_<structure>.out)
        parsed_data_RWP = self.parse_output_RWP(structures_list)
        self.logger.info(f"RWP data: {parsed_data_RWP}")

        # Parse percentage weight
        parsed_data_RWP_percentage_weight = self.parse_output_RWP_percentage_weight(structures_list)

        # Parse crystallite size
        parsed_data_RWP_crystallite_size = self.parse_output_crystallite_size_with_exclusions(structures_list)

        # Combine parsed data
        combined_data = self.combine_parsed_data(
            RWP=parsed_data_RWP,
            percentage_weight=parsed_data_RWP_percentage_weight,
            crystallite_size=parsed_data_RWP_crystallite_size
        )
        self.logger.info(f"Combined data: {combined_data}")

        # Screen data if needed
        # The screen_data method expects the parsed data and the task type
        # as separate arguments. A typo here previously combined them into
        # one invalid argument causing a crash when running the RWP task.
        self.screen_data(combined_data, task_type="RWP")

        # Cleanup
        self.clear_input_output_files()

    def prepare_removal_RWP_input_file(self, structures_list, input_file):
        self.logger.info("Preparing input files for Removal RWP Task")

        # Ensure input directory exists
        os.makedirs(self.input_dir, exist_ok=True)

        structures_dir = os.path.join(self.script_dir, 'structure_database')

        # 1) Create the baseline input file (includes ALL structures)
        self.create_all_structures_inp_file(structures_list, input_file, structures_dir)

        # 2) For each structure in structures_list, create a scenario that excludes it
        self.create_all_structures_removal_inp_file(structures_list, input_file, structures_dir)

    def create_all_structures_removal_inp_file(self, structures_list, input_file, structures_dir):
        """
        For each structure in structures_list, produce an input file that excludes that single structure.
        """
        for structure in structures_list:
            structure_name = os.path.splitext(structure)[0]
            # Exclude exactly this structure from the scenario
            scenario_list = [s for s in structures_list if s != structure]

            self.logger.info(f"Creating scenario excluding: {structure_name}")
            self.create_all_structures_inp_file(scenario_list, input_file, structures_dir)

            # Rename the newly created file from all_structures.inp to all_structures_<structure_name>.inp
            old_path = os.path.join(self.input_dir, 'all_structures.inp')
            new_path = os.path.join(self.input_dir, f'all_structures_{structure_name}.inp')

            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                self.logger.info(f"Created {new_path} (excluded {structure_name})")
            else:
                self.logger.warning(f"Expected file {old_path} not found.")

    def create_all_structures_inp_file(self, structures_list, input_file, structures_dir):
        original_start_inp_path = os.path.join(self.script_dir, 'start.inp')
        output_inp_path = os.path.join(self.input_dir, 'all_structures.inp')

        if not os.path.exists(original_start_inp_path):
            self.logger.error(f"start.inp file not found at {original_start_inp_path}")
            return

        with open(original_start_inp_path, 'r') as f:
            start_inp_lines = f.readlines()

        # Optionally modify first line with the input_file
        # start_inp_lines[0] = f'   xdd "{input_file}"\n'

        with open(output_inp_path, 'w') as out_f:
            out_f.writelines(start_inp_lines)

            for structure in structures_list:
                structure_path = os.path.join(structures_dir, structure)
                if not os.path.exists(structure_path):
                    self.logger.warning(f"Structure {structure} not found in {structures_dir}")
                    continue

                out_f.write(f"\n/*{structure}_START*/\n")
                with open(structure_path, 'r') as sf:
                    out_f.write(sf.read())
                out_f.write(f"\n/*{structure}_END*/\n")

        self.logger.info(f"Created all_structures.inp with {len(structures_list)} structures.")

    # ------------------ Parsing Helper Methods ------------------

    def parse_output_RWP(self, structures_list):
        """
        Parse RWP from:
          1) all_structures.out  (baseline)
          2) all_structures_<structure_name>.out for each structure in structures_list
        """
        parsed_data_RWP = {}

        # 1. Baseline RWP
        all_out_file = os.path.join(self.output_dir, "all_structures.out")
        rwp_all = self.extract_rwp_from_file(all_out_file)
        parsed_data_RWP["all"] = rwp_all  # store under key "all" or "baseline"

        # 2. Per-structure scenario
        for structure in structures_list:
            struct_name_no_ext = os.path.splitext(structure)[0]
            out_file = os.path.join(self.output_dir, f"all_structures_{struct_name_no_ext}.out")
            rwp_value = self.extract_rwp_from_file(out_file)
            parsed_data_RWP[struct_name_no_ext] = rwp_value

        return parsed_data_RWP

    def extract_rwp_from_file(self, filepath):
        if not os.path.exists(filepath):
            self.logger.warning(f"{filepath} not found.")
            return None
        with open(filepath, 'r') as f:
            content = f.read()
        match = re.search(r'r_wp\s+([\d.]+)', content)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                self.logger.warning(f"Could not convert RWP to float in {filepath}")
                return None
        else:
            self.logger.warning(f"RWP value not found in {filepath}")
            return None

    def parse_output_RWP_percentage_weight(self, structures_list):
        """
        Parse percentage weights:
          - from 'all_structures.out' for the baseline
          - from 'all_structures_<structure>.out' for each exclusion scenario
        """
        parsed_data = {}

        # 1. Baseline parse from all_structures.out
        all_out_file = os.path.join(self.output_dir, "all_structures.out")
        if os.path.exists(all_out_file):
            with open(all_out_file, 'r') as f:
                all_content = f.read()

            # Store a dict of structure -> weight for baseline
            baseline_weights = {}
            for structure in structures_list:
                subcontent = get_structure_content_in_content(all_content, structure)
                if subcontent:
                    baseline_weights[structure] = parse_percentage_weight(subcontent)
                else:
                    baseline_weights[structure] = None

            parsed_data["all"] = baseline_weights
        else:
            self.logger.warning(f"{all_out_file} not found.")
            parsed_data["all"] = None

        # 2. Parse from all_structures_<structure>.out for each scenario
        for structure in structures_list:
            struct_name_no_ext = os.path.splitext(structure)[0]
            scenario_out_file = os.path.join(self.output_dir, f"all_structures_{struct_name_no_ext}.out")

            if not os.path.exists(scenario_out_file):
                self.logger.warning(f"{scenario_out_file} not found.")
                parsed_data[struct_name_no_ext] = None
                continue

            with open(scenario_out_file, 'r') as f:
                scenario_content = f.read()

            scenario_weights = {}
            # We can parse *all* structures from the scenario content if we want to
            # see which remain or get partial data. Here, we'll still attempt them all:
            for s in structures_list:
                subcontent = get_structure_content_in_content(scenario_content, s)
                scenario_weights[s] = parse_percentage_weight(subcontent) if subcontent else None

            parsed_data[struct_name_no_ext] = scenario_weights

        return parsed_data

    def parse_output_crystallite_size_with_exclusions(self, structures_list, excluded_structure_list):
        """
        Similar to percentage weight parsing, but here for crystallite size.
        """
        parsed_data_crystallite = {}

        excluded_set = {os.path.splitext(os.path.basename(s))[0] for s in excluded_structure_list}
        included_set = {os.path.splitext(os.path.basename(s))[0] for s in structures_list if
                        os.path.splitext(os.path.basename(s))[0] not in excluded_set}

        # Parse from all_structures.out for included structures
        all_out_file = os.path.join(self.output_dir, "all_structures.out")
        if os.path.exists(all_out_file):
            with open(all_out_file, 'r') as f:
                all_content = f.read()
            for included_structure in included_set:
                full_structure_name = included_structure + '.str'
                subcontent = get_structure_content_in_content(all_content, full_structure_name)
                if subcontent:
                    crystallite_size = parse_crystallite_size(subcontent)
                    parsed_data_crystallite[included_structure] = crystallite_size
                else:
                    parsed_data_crystallite[included_structure] = None
        else:
            self.logger.warning(f"{all_out_file} not found. No included crystallite data.")

        # Parse from all_structures_{excluded_structure}.out for excluded structures
        for excluded_structure in excluded_set:
            excluded_out_file = os.path.join(self.output_dir, f"all_structures_{excluded_structure}.out")
            if os.path.exists(excluded_out_file):
                with open(excluded_out_file, 'r') as f:
                    excluded_content = f.read()
                full_excluded_name = excluded_structure + '.str'
                subcontent = get_structure_content_in_content(excluded_content, full_excluded_name)
                if subcontent:
                    crystallite_size = parse_crystallite_size(subcontent)
                    parsed_data_crystallite[excluded_structure] = crystallite_size
                else:
                    parsed_data_crystallite[excluded_structure] = None
            else:
                self.logger.warning(f"{excluded_out_file} not found.")
                parsed_data_crystallite[excluded_structure] = None

        return parsed_data_crystallite

class RWPAdditionTask(BaseTask):
    def run(self):
        # Retrieve 'input_file' from 'self.data'
        input_file = self.data.get('input_file', 'default_input.xdd')
        self.logger.info(f"Running RWP Task for Node {self.node_id} on file {input_file}")

        # Retrieve 'structures_list' from 'self.data'
        structures_list = self.data.get('structures_list', [])
        valid_structures_list = self.data.get('valid_structures', [])
        invalid_structures_list = self.data.get('invalid_structures', [])
        excluded_structure_list = self.data.get('excluded_structure_list', [])

        logging.info(f"Valid structures: {valid_structures_list}")
        logging.info(f"Invalid structures: {invalid_structures_list}")
        logging.info(f"Excluded structures: {excluded_structure_list}")
        logging.info(f"Structure list is: {structures_list}")

        if not structures_list:
            if valid_structures_list:
                structures_list = [structure + '.str' for structure in valid_structures_list]
            elif invalid_structures_list:
                structures_list = [structure + '.str' for structure in invalid_structures_list]
            else:
                structures_list = [structure + '.str' for structure in excluded_structure_list]


        if not structures_list:
            self.logger.error("No 'structures_list' found in input data")
            return

        # Prepare input files
        self.prepare_RWP_input_file(structures_list, excluded_structure_list, input_file)


        # Run simulations
        self.run_simulation()
        self.move_output_files()
        # Parse output files
        logging.info("Parsing output files")
        parsed_data_RWP = self.parse_output_RWP(structures_list, excluded_structure_list)
        logging.info(f"RWP data: {parsed_data_RWP}")
        parsed_data_RWP_percentage_weight = self.parse_output_RWP_percentage_weight(structures_list, excluded_structure_list)
        parsed_data_RWP_crystallite_size = self.parse_output_crystallite_size_with_exclusions(structures_list, excluded_structure_list)


        combined_data = self.combine_parsed_data(
            RWP=parsed_data_RWP,
            percentage_weight=parsed_data_RWP_percentage_weight,
            crystallite_size=parsed_data_RWP_crystallite_size
        )

        logging.info(f"Combined data: {combined_data}")
        # Collate data
        self.screen_data(combined_data, task_type="RWPAddition")
        self.clear_input_output_files()


    def prepare_RWP_input_file(self, structures_list, excluded_structure_list, input_file):
        self.logger.info("Preparing input files for Addition RWP Task")

        # Ensure input directory exists
        os.makedirs(self.input_dir, exist_ok=True)

        # Path to the structures directory (assuming it's in the script directory)
        structures_dir = os.path.join(self.script_dir, 'structure_database')

        self.create_all_structures_addition_inp_file(structures_list, excluded_structure_list, input_file, structures_dir)
        self.create_all_structures_inp_file(structures_list, input_file, structures_dir)

    def create_all_structures_addition_inp_file(self, structures_list, excluded_structure_list, input_file, structures_dir):

        #for each excluded structure in the excluded_structure_list
        #add the structure to the structures_list
        for excluded_structure in excluded_structure_list:
            #get the structure name without the .str extension
            structure_name = os.path.splitext(excluded_structure)[0]
            #add the structure to the structures_list

            #append .str to each excluded_structure
            excluded_structure = excluded_structure+'.str'

            structures_list.append(excluded_structure)
            logging.info(f"Structure list: {structures_list} with excluded structure {excluded_structure}")
            #create the input file for the structure list
            self.create_all_structures_inp_file(structures_list, input_file, structures_dir)
            #rename the input file to the all_structures_{structure_name}.inp
            os.rename(os.path.join(self.input_dir, 'all_structures.inp'), os.path.join(self.input_dir, f'all_structures_{structure_name}.inp'))
            #remove the structure from the structures_list
            structures_list.remove(excluded_structure)
            logging.info(f"Structure list: {structures_list} without excluded structure {excluded_structure}")

class RWPMissingTask(BaseTask):
    def run(self):
        # Retrieve 'input_file' from 'self.data'
        input_file = self.data.get('input_file', 'default_input.xdd')
        self.logger.info(f"Running Crystallite Size Task for Node {self.node_id} on file {input_file}")

        # Retrieve 'structures_list' from 'self.data'
        structures_list = self.data.get('structures_list', [])
        valid_structures_list = self.data.get('valid_structures', [])
        invalid_structures_list = self.data.get('invalid_structures', [])
        excluded_structure_list = self.data.get('excluded_structure_list', [])

        logging.info(f"Valid structures: {valid_structures_list}")
        logging.info(f"Invalid structures: {invalid_structures_list}")
        logging.info(f"Structure list is: {structures_list}")

        if not structures_list:
            if valid_structures_list:
                structures_list = [structure + '.str' for structure in valid_structures_list]
            elif invalid_structures_list:
                structures_list = [structure + '.str' for structure in invalid_structures_list]
            else:
                structures_list = [structure + '.str' for structure in excluded_structure_list]

        if not structures_list:
            self.logger.error("No 'structures_list' found in input data")
            return

        # Prepare input files
        self.prepare_all_structures_input_file(structures_list, input_file)

        for structure in structures_list:
            logging.info(f"Adding Structure to excluded list: {structure}")
            structure_name = structure.removesuffix('.str')
            logging.info(f"Structure name: {structure_name}")
            excluded_structure_list.append(structure_name)

        # Run simulations
        self.run_simulation()
        self.move_output_files()
        # Parse output files
        logging.info("Parsing output files")
        parsed_data_RWP = self.parse_output_RWP_negative(structures_list, excluded_structure_list)
        logging.info(f"RWP data: {parsed_data_RWP}")

        for structure in structures_list:
            logging.info(f"Removing Structure to excluded list: {structure}")
            structure_name = structure.removesuffix('.str')
            logging.info(f"Structure name: {structure_name}")
            excluded_structure_list.remove(structure_name)

        parsed_data_RWP_percentage_weight = self.parse_output_RWP_percentage_weight(structures_list, excluded_structure_list)
        parsed_data_RWP_crystallite_size = self.parse_output_crystallite_size_with_exclusions(structures_list, excluded_structure_list)



        combined_data = self.combine_parsed_data(
            RWP=parsed_data_RWP,
            percentage_weight=parsed_data_RWP_percentage_weight,
            crystallite_size=parsed_data_RWP_crystallite_size
        )

        logging.info(f"Combined data: {combined_data}")
        # Collate data
        self.screen_data(combined_data,task_type="RWPMissing")
        self.clear_input_output_files()

    def prepare_all_structures_input_file(self, structures_list, input_file):
        self.logger.info("Preparing input files for Crystallite Size Task")

        # Ensure input directory exists
        os.makedirs(self.input_dir, exist_ok=True)

        # Path to the structures directory (assuming it's in the script directory)
        structures_dir = os.path.join(self.script_dir, 'structure_database')

        self.create_all_structures_inp_file(structures_list, input_file, structures_dir)
        self.create_all_structures_missing_inp_files(structures_list, structures_dir)



    def create_all_structures_missing_inp_files(self, structures_list, structures_dir):
        """
        For each structure in `structures_list`, create a file named
        'all_structures_{structure_name}.inp' that includes the modified
        'start.inp' header and all structures EXCEPT the current one.

        :param structures_list: List of structure file names.
        :param structures_dir: Directory where structure files are located.
        """
        original_start_inp_path = os.path.join(self.script_dir, 'start.inp')
        if not os.path.exists(original_start_inp_path):
            self.logger.error(f"Template file {original_start_inp_path} not found.")
            return

        # Read the original 'start.inp' file lines
        with open(original_start_inp_path, 'r') as start_inp_file:
            start_inp_lines = start_inp_file.readlines()

        # Modify the first line with your XDD input file name
        input_file = self.data.get('input_file', 'default_input.xdd')
        start_inp_lines[0] = f'   xdd "{input_file}"\n'

        # Modify the polynomial line (assuming it is line index 3 in 'start.inp')
        polynomial_number = self.parameters.get('polynomial', '3')
        start_inp_lines[3] = f'   bkg @ {"0 " * int(polynomial_number)}\n'

        # Load all structure contents into a dictionary {structure_name: file_content}
        structure_files_content = {}
        for structure_name in structures_list:
            structure_file_path = None
            # Search for the structure file
            for root, dirs, files in os.walk(structures_dir):
                if structure_name in files:
                    structure_file_path = os.path.join(root, structure_name)
                    break

            if not structure_file_path:
                self.logger.error(f"Structure file {structure_name} not found in {structures_dir}.")
                # You can skip or raise an exception; this code skips.
                continue

            with open(structure_file_path, 'r') as structure_file:
                structure_files_content[structure_name] = structure_file.read()

        # Create a separate file for each structure, omitting that structure
        for exclude_structure in structures_list:
            # If we never loaded it (file not found earlier), skip
            if exclude_structure not in structure_files_content:
                continue

            exclude_structure_name = os.path.splitext(exclude_structure)[0]

            # Destination file path
            out_file_name = f"all_structures_{exclude_structure_name}.inp"
            all_structures_inp_path = os.path.join(self.input_dir, out_file_name)

            # Write the modified 'start.inp' lines plus all structures except `exclude_structure`
            with open(all_structures_inp_path, 'w') as inp_file:
                # Write the modified header
                inp_file.writelines(start_inp_lines)

                # Write the content for every structure except the excluded one
                for structure_name, content in structure_files_content.items():
                    if structure_name == exclude_structure:
                        continue
                    inp_file.write(f"\n/*{structure_name}_START*/\n")
                    inp_file.write(content)
                    inp_file.write(f"\n/*{structure_name}_END*/\n")

            self.logger.info(
                f"Created {out_file_name} with all structures except '{exclude_structure}'."
            )


class RWPRemovalTask(BaseTask):
    def run(self):
        # Retrieve 'input_file' from 'self.data'
        input_file = self.data.get('input_file', 'default_input.xdd')
        self.logger.info(f"Running RWP Task for Node {self.node_id} on file {input_file}")

        # Retrieve 'structures_list' from 'self.data'
        structures_list = self.data.get('structures_list', [])
        valid_structures_list = self.data.get('valid_structures', [])
        invalid_structures_list = self.data.get('invalid_structures', [])
        excluded_structure_list = self.data.get('excluded_structure_list', [])

        logging.info(f"Valid structures: {valid_structures_list}")
        logging.info(f"Invalid structures: {invalid_structures_list}")
        logging.info(f"Excluded structures: {excluded_structure_list}")
        logging.info(f"Structure list is: {structures_list}")

        if not structures_list:
            if valid_structures_list:
                structures_list = [structure + '.str' for structure in valid_structures_list]
            elif invalid_structures_list:
                structures_list = [structure + '.str' for structure in invalid_structures_list]
            else:
                structures_list = [structure + '.str' for structure in excluded_structure_list]


        if not structures_list:
            self.logger.error("No 'structures_list' found in input data")
            return

        # Prepare input files
        self.prepare_removal_RWP_input_file(structures_list, excluded_structure_list, input_file)


        # Run simulations
        self.run_simulation()
        self.move_output_files()
        # Parse output files
        logging.info("Parsing output files")
        parsed_data_RWP = self.parse_output_RWP(structures_list, excluded_structure_list)
        logging.info(f"RWP data: {parsed_data_RWP}")
        parsed_data_RWP_percentage_weight = self.parse_output_RWP_percentage_weight(structures_list, excluded_structure_list)
        parsed_data_RWP_crystallite_size = self.parse_output_crystallite_size_with_exclusions(structures_list, excluded_structure_list)


        combined_data = self.combine_parsed_data(
            RWP=parsed_data_RWP,
            percentage_weight=parsed_data_RWP_percentage_weight,
            crystallite_size=parsed_data_RWP_crystallite_size
        )

        logging.info(f"Combined data: {combined_data}")
        # Collate data
        self.screen_data(combined_data, task_type="RWPRemoval")
        self.clear_input_output_files()


    def prepare_addition_RWP_input_file(self, structures_list, excluded_structure_list, input_file):
        self.logger.info("Preparing input files for Addition RWP Task")

        # Ensure input directory exists
        os.makedirs(self.input_dir, exist_ok=True)

        # Path to the structures directory (assuming it's in the script directory)
        structures_dir = os.path.join(self.script_dir, 'structure_database')

        self.create_all_structures_addition_inp_file(structures_list, excluded_structure_list, input_file, structures_dir)
        self.create_all_structures_inp_file(structures_list, input_file, structures_dir)

    def prepare_removal_RWP_input_file(self, structures_list, excluded_structure_list, input_file):
        self.logger.info("Preparing input files for Addition RWP Task")

        # Ensure input directory exists
        os.makedirs(self.input_dir, exist_ok=True)

        # Path to the structures directory (assuming it's in the script directory)
        structures_dir = os.path.join(self.script_dir, 'structure_database')

        self.create_all_structures_addition_inp_file(structures_list, excluded_structure_list, input_file,
                                                     structures_dir)
        self.create_all_structures_inp_file(structures_list, input_file, structures_dir)

    def create_all_structures_addition_inp_file(self, structures_list, excluded_structure_list, input_file, structures_dir):

        #for each excluded structure in the excluded_structure_list
        #add the structure to the structures_list
        for excluded_structure in excluded_structure_list:
            #get the structure name without the .str extension
            structure_name = os.path.splitext(excluded_structure)[0]
            #add the structure to the structures_list

            #append .str to each excluded_structure
            excluded_structure = excluded_structure+'.str'

            structures_list.append(excluded_structure)
            logging.info(f"Structure list: {structures_list} with excluded structure {excluded_structure}")
            #create the input file for the structure list
            self.create_all_structures_inp_file(structures_list, input_file, structures_dir)
            #rename the input file to the all_structures_{structure_name}.inp
            os.rename(os.path.join(self.input_dir, 'all_structures.inp'), os.path.join(self.input_dir, f'all_structures_{structure_name}.inp'))
            #remove the structure from the structures_list
            structures_list.remove(excluded_structure)
            logging.info(f"Structure list: {structures_list} without excluded structure {excluded_structure}")

    def create_all_structures_removal_inp_file(self, structures_list, excluded_structure_list, input_file, structures_dir):

        total_structures_list = [structure + '.str' for structure in excluded_structure_list] + structures_list

        #for each excluded structure in the excluded_structure_list
        #add the structure to the structures_list
        for excluded_structure in excluded_structure_list:
            #get the structure name without the .str extension
            structure_name = os.path.splitext(excluded_structure)[0]
            #add the structure to the structures_list

            #append .str to each excluded_structure
            excluded_structure = excluded_structure+'.str'

            total_structures_list.remove(excluded_structure)
            logging.info(f"Structure list: {total_structures_list} without excluded structure {excluded_structure}")
            #create the input file for the structure list
            self.create_all_structures_inp_file(total_structures_list, input_file, structures_dir)
            #rename the input file to the all_structures_{structure_name}.inp
            os.rename(os.path.join(self.input_dir, 'all_structures.inp'), os.path.join(self.input_dir, f'all_structures_{structure_name}.inp'))
            #remove the structure from the structures_list
            total_structures_list.append(excluded_structure)
            logging.info(f"Structure list: {structures_list} with excluded structure {excluded_structure}")

class CombineListsTask(BaseTask):
    def run(self):
        self.logger.info(f"Running Combine List for Node {self.node_id}")


        # Delete all files in input_files and output_files directories
        self.clear_input_output_files()

        # Get structures specified in the analysis template
        structures_list = []
        for key in self.parameters:
            if 'structures' in self.parameters[key]:
                structures_list.extend(self.parameters[key]['structures'])
        self.logger.info(f"Structures from parameters: {structures_list}")

        # Add the structures to output data under 'structures_list'
        self.output_data['structures_list'] = structures_list

        # The input_file, input_directory, and output_directory are already passed in self.data
        self.logger.info("Structures added to output data")


# Add other task classes (e.g., RWPTask, CleanupTask) as needed
