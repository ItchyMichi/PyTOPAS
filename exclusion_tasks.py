import logging

from numpy.ma.core import minimum

import tasks
from exclusion_criteria_tasks import BaseExclusionCriteriaTask, WorstExclusionCriteriaTask, FailingExclusionCriteriaTask, WorstNegativeExclusionCriteriaTask, FailingZScoreExclusionCriteriaTask, AEBExclusionCriteriaTask, WorstCombinedExclusionCriteriaTask, WorstNegativeCombinedExclusionCriteriaTask, FailingZScoreCombinedExclusionCriteriaTask, AEBCombinedExclusionCriteriaTask
from file_handling import parse_config



class BaseExclusionTask:
    def __init__(self, parameters, logger=None):
        self.parameters = parameters
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        self.exclusion_criteria_classes = {
            'Worst': WorstExclusionCriteriaTask,
            'Failing': FailingExclusionCriteriaTask,
            'Worst Negative': WorstNegativeExclusionCriteriaTask,
            'Failing Z-Score': FailingZScoreExclusionCriteriaTask,
            'All Failing Except Best': AEBExclusionCriteriaTask,
            'Worst Combined': WorstCombinedExclusionCriteriaTask,
            'Worst Negative Combined': WorstNegativeCombinedExclusionCriteriaTask,
            'Failing Z-Score Combined': FailingZScoreCombinedExclusionCriteriaTask,
            'All Failing Except Best Combined': AEBCombinedExclusionCriteriaTask


            # Add new task types here
        }

    def get_screening_params(self):
        raise NotImplementedError

    def apply_criteria(self, value, min_value, max_value):
        raise NotImplementedError

    def screen(self, parsed_data):
        raise NotImplementedError


class CrystalliteSizeExclusionTask(BaseExclusionTask):
    def run(self, parsed_data):
        self.logger.info(f"Running {self.__class__.__name__} exclusion task.")

        # Retrieve and convert parameters
        try:
            min_percentage_weight = float(self.parameters.get('min_weight', 0.1))
            max_percentage_weight = float(self.parameters.get('max_weight', 8.0))
            minimum_crystallite_size = float(self.parameters.get('min_crystallite', 20.0))
            threshold_step = float(self.parameters.get('crystallite_step', 30.0))
            crystallite_size_start = float(self.parameters.get('crystallite_size_start', 40.0))
            steps = int(self.parameters.get('steps', 5))  # Number of steps, default to 5
            exclusion_criteria = self.parameters.get('exclusion_criteria', 'Worst')
        except (TypeError, ValueError) as e:
            self.logger.error(f"Invalid parameter value: {e}")
            return [], list(parsed_data.keys())  # All structures invalid if parameters are missing

        # Read config once at the beginning
        try:
            config = parse_config('config.txt')
            crystallite_size_min_config = float(config.get('crystallite_size_min', 20.0))
            crystallite_size_max_config = float(config.get('crystallite_size_max', 1700.0))
        except (KeyError, ValueError, FileNotFoundError) as e:
            self.logger.error(f"Error reading configuration: {e}")
            crystallite_size_min_config = 20.0
            crystallite_size_max_config = 1700.0

        self.logger.info(
            f"Crystallite size range from config: {crystallite_size_min_config} to {crystallite_size_max_config}")

        # Calculate the common ratio and boundaries
        common_ratio = (max_percentage_weight / min_percentage_weight) ** (1 / (steps - 1))
        boundaries = [min_percentage_weight * (common_ratio ** i) for i in range(steps)]
        boundaries.append(max_percentage_weight)  # Ensure the max weight is included

        self.logger.info(f"Calculated boundaries: {boundaries}")

        valid_structures = []
        invalid_structures = []

        for structure_name, data in parsed_data.items():
            self.logger.info(f"Evaluating structure: {structure_name}")

            try:
                percentage_weight = float(data.get('percentage_weight'))
                crystallite_size = float(data.get('crystallite_size'))
            except (TypeError, ValueError) as e:
                self.logger.warning(f"Invalid data for {structure_name}: {e}")
                invalid_structures.append(structure_name)
                continue

            # Check if percentage_weight is below the minimum acceptable weight
            if percentage_weight < min_percentage_weight:
                self.logger.info(
                    f"{structure_name}: Percentage weight {percentage_weight} is less than the minimum {min_percentage_weight}")
                invalid_structures.append(structure_name)
               #data['viable'] = False
                continue

            # Check if percentage_weight is above the maximum acceptable weight
            if percentage_weight > max_percentage_weight:
                self.logger.info(
                    f"{structure_name}: Percentage weight {percentage_weight} is greater than the maximum {max_percentage_weight}")
                valid_structures.append(structure_name)
                #data['viable'] = True
                continue

            # Determine which range the percentage_weight falls into
            for i in range(len(boundaries) - 1):
                lower_bound = boundaries[i]
                upper_bound = boundaries[i + 1]
                if lower_bound <= percentage_weight <= upper_bound:
                    # Calculate minimum crystallite size for this step
                    min_cs = crystallite_size_start + (threshold_step * i)
                    max_cs = (crystallite_size_max_config*0.95)

                    self.logger.info(
                        f"{structure_name}: Percentage weight {percentage_weight} is between {lower_bound} and {upper_bound}")
                    self.logger.info(f"{structure_name}: Required crystallite size between {min_cs} and {max_cs}")

                    if min_cs <= crystallite_size <= max_cs:
                        #data['viable'] = True
                        valid_structures.append(structure_name)
                        self.logger.info(f"{structure_name} is valid.")
                    else:
                        #data['viable'] = False
                        invalid_structures.append(structure_name)
                        self.logger.info(f"{structure_name} is invalid due to crystallite size.")
                    break  # Exit the loop once the correct range is found
            else:
                # If no boundary matches, mark as invalid
                self.logger.info(f"{structure_name}: No matching boundary found.")
                invalid_structures.append(structure_name)

        self.logger.info(f"Valid structures: {valid_structures}")
        self.logger.info(f"Invalid structures: {invalid_structures}")

        #append the valid structures to the parsed data under the key 'valid_structures'
        parsed_data['valid_structures'] = valid_structures
        parsed_data['invalid_structures'] = invalid_structures

        logging.info(f"parsed_data: {parsed_data}")
        logging.info(f"exclusion criteria: {exclusion_criteria}")



        exclusion_criteria_task_class = self.exclusion_criteria_classes.get(exclusion_criteria)
        exclusion_criterial_task = exclusion_criteria_task_class(parameters=self.parameters, logger=self.logger)

        screened_data = exclusion_criterial_task.run(parsed_data)

        return screened_data

        #exclusion_criteria_task_class = self.exclusion_criteria_classes.get(exclusion_criteria)
        #exclusion_criterial_task = exclusion_criteria_task_class(self.parameters, self.logger, parsed_data)

        #screened_data = exclusion_criterial_task.run(parsed_data)
        #return screened_data


class RWPExclusionTask(BaseExclusionTask):
    def run(self, parsed_data):
        self.logger.info(f"Running {self.__class__.__name__} exclusion task.")

        # 1. Log the incoming parameters and parsed_data keys for overall context
        self.logger.info(f"Parameters: {self.parameters}")
        self.logger.info(f"parsed_data keys at start: {list(parsed_data.keys())}")

        # 2. Log the attempt to retrieve rwp_threshold
        try:
            rwp_threshold = float(self.parameters.get('rwp_threshold', 0.05))
            self.logger.info(f"Using RWP threshold: {rwp_threshold}")
        except (TypeError, ValueError) as e:
            self.logger.error(f"Invalid RWP threshold parameter value: {e}")
            return [], list(parsed_data.keys())  # If no valid threshold, all structures are invalid

        # 3. Safely get the 'rwp_all' dictionary before trying to get 'RWP'
        rwp_all_dict = parsed_data.get('rwp_all', None)
        self.logger.info(f"rwp_all_dict: {rwp_all_dict}")

        if not isinstance(rwp_all_dict, dict):
            self.logger.error("parsed_data['rwp_all'] is missing or not a dict.")
            return [], list(parsed_data.keys())

        # Extract the float from the nested dictionary
        rwp_all_float = rwp_all_dict.get('RWP')
        # If rwp_all_float is itself a dict, grab the actual float inside it
        if isinstance(rwp_all_float, dict):
            rwp_all_float = rwp_all_float.get('RWP')

        self.logger.info(f"rwp_all: {rwp_all_float}")

        if rwp_all_float is None:
            self.logger.error("No 'rwp_all' float value found in parsed_data['rwp_all'].")
            return [], list(parsed_data.keys())  # Without a baseline, we can't compute deltas

        # 4. Before potentially dividing by rwp_all_float, log if it's zero or suspicious
        if rwp_all_float == 0:
            self.logger.warning("rwp_all is 0. This will cause a divide-by-zero error.")
            return [], list(parsed_data.keys())

        valid_structures = []
        invalid_structures = []
        excluded_structures = []

        # 5. Log the structure_keys we are about to process
        ignore_keys = ['valid_structures', 'invalid_structures', 'structures_list',
                       'excluded_structure_list', 'rwp_all']
        structure_keys = [k for k in parsed_data.keys() if k not in ignore_keys]
        self.logger.info(f"Structure keys to process: {structure_keys}")

        for structure_name in structure_keys:
            self.logger.info(f"Evaluating structure: {structure_name}")
            data = parsed_data.get(structure_name, {})
            self.logger.info(f"Data for {structure_name}: {data}")

            # 6. Grab the 'RWP' entry, which may itself be a dict or float
            rwp_structure_data = data.get('RWP', None)
            if rwp_structure_data is None:
                self.logger.warning(f"No RWP data for structure: {structure_name}. Marking as invalid.")
                invalid_structures.append(structure_name)
                continue

            # If rwp_structure_data is a dict, extract the actual float
            if isinstance(rwp_structure_data, dict):
                rwp_structure_float = rwp_structure_data.get('RWP')
            else:
                # If it's already a float, just use it
                rwp_structure_float = rwp_structure_data

            # Check if we actually got a float
            if rwp_structure_float is None:
                self.logger.warning(f"RWP data for {structure_name} was missing or invalid. Marking as invalid.")
                invalid_structures.append(structure_name)
                continue

            self.logger.info(f"{structure_name} - rwp_all={rwp_all_float}, rwp_structure={rwp_structure_float}")

            # 7. Wrap delta computation in a try/except to catch ZeroDivision or Type errors
            try:
                #delta_rwp = (rwp_structure_float - rwp_all_float) / rwp_all_float
                delta_rwp = (rwp_structure_float - rwp_all_float) / rwp_all_float
            except ZeroDivisionError:
                self.logger.error(
                    f"ZeroDivisionError computing delta RWP for {structure_name}. "
                    f"rwp_all={rwp_all_float}, rwp_structure={rwp_structure_float}"
                )
                invalid_structures.append(structure_name)
                continue
            except TypeError as te:
                self.logger.error(
                    f"TypeError encountered computing delta RWP for {structure_name}: {te}"
                )
                invalid_structures.append(structure_name)
                continue

            self.logger.info(f"{structure_name} - Computed delta RWP: {delta_rwp}")

            # Overwrite data['RWP'] with the delta, if desired. Otherwise, store it in another key.
            data['RWP'] = delta_rwp
            task_type = self.parameters["task_type"]

            if task_type in "RWPAddition":
                # 8. Log the decision logic
                if delta_rwp == 0.0:
                    self.logger.info(f"{structure_name}: Addition causes Delta RWP == 0.0 -> inValid")
                    valid_structures.append(structure_name)
                elif delta_rwp < 0.0:
                    self.logger.info(
                        f"{structure_name}: Addition causes Negative delta RWP, structure improves fit -> Valid")
                    valid_structures.append(structure_name)
                elif 0.0 <= delta_rwp < rwp_threshold:
                    self.logger.info(f"{structure_name}: Delta RWP below threshold ({rwp_threshold}) -> Valid")
                    valid_structures.append(structure_name)
                else:
                    self.logger.info(f"{structure_name}: Delta RWP above threshold ({rwp_threshold}) -> Invalid")
                    invalid_structures.append(structure_name)
                # 8. Log the decision logic
                #if delta_rwp == 0.0:
                    #self.logger.info(f"{structure_name}: Addition causes Delta RWP == 0.0 -> Valid")
                    #valid_structures.append(structure_name)
                #elif delta_rwp < 0.0:
                    #self.logger.info(f"{structure_name}: Addition causes Negative delta RWP, structure improves fit -> Valid")
                    #invalid_structures.append(structure_name)
                #elif 0.0 <= delta_rwp < rwp_threshold:
                    #self.logger.info(f"{structure_name}: Delta RWP below threshold ({rwp_threshold}) -> Valid")
                    #invalid_structures.append(structure_name)
                #else:
                    #self.logger.info(f"{structure_name}: Delta RWP above threshold ({rwp_threshold}) -> Invalid")
                    #invalid_structures.append(structure_name)
            else:
                # 8. Log the decision logic
                if delta_rwp == 0.0:
                    self.logger.info(f"{structure_name}: Removal causes Delta RWP == 0.0 -> Invalid")
                    invalid_structures.append(structure_name)
                elif 0.0 <= delta_rwp < rwp_threshold:
                    self.logger.info(f"{structure_name}: Removal causes Delta RWP below threshold ({rwp_threshold}) -> Invalid")
                    invalid_structures.append(structure_name)
                elif delta_rwp < 0.0:
                    self.logger.info(f"{structure_name}: Removal causes Negative delta RWP, structure improves fit -> Invalid")
                    invalid_structures.append(structure_name)
                elif 0.0 < delta_rwp:
                    self.logger.info(
                        f"{structure_name}: Removal causes Delta RWP increase -> Valid")
                    valid_structures.append(structure_name)
                else:
                    self.logger.info(f"{structure_name}: Removal causes Delta RWP above threshold ({rwp_threshold}) -> Invalid")
                    invalid_structures.append(structure_name)


        # 9. Log the final sets of structures
        self.logger.info(f"Valid structures: {valid_structures}")
        self.logger.info(f"Invalid structures: {invalid_structures}")

        # Store results in parsed_data
        parsed_data['valid_structures'] = valid_structures
        parsed_data['invalid_structures'] = invalid_structures

        # 10. Log the exclusion criteria we are about to use
        exclusion_criteria = self.parameters.get('exclusion_criteria', 'Worst')
        self.logger.info(f"Exclusion criteria: {exclusion_criteria}")

        exclusion_criteria_task_class = self.exclusion_criteria_classes.get(exclusion_criteria)
        self.logger.info(f"Exclusion criteria task class: {exclusion_criteria_task_class}")

        if not exclusion_criteria_task_class:
            self.logger.warning(f"No exclusion criteria class found for '{exclusion_criteria}'. Using default.")
            return parsed_data

        # 11. Log before and after calling the exclusion_criteria task
        self.logger.info(f"Initializing exclusion criteria task: {exclusion_criteria}")
        exclusion_criterial_task = exclusion_criteria_task_class(parameters=self.parameters, logger=self.logger)
        self.logger.info("Running exclusion criteria task")
        screened_data = exclusion_criterial_task.run(parsed_data)

        self.logger.info("Exclusion criteria task complete.")
        return screened_data


class PercentageWeightExclusionTask(BaseExclusionTask):
    def run(self):
        self.logger.info(f"Running {self.__class__.__name__} exclusion task.")
        screening_params = self.get_screening_params()
        self.logger.info(f"Screening parameters: {screening_params}")
        return self.screen(screening_params)

