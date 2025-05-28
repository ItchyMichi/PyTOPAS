import os
import logging

import main_gui


class BaseConditionTask:
    def __init__(self, node_id, parameters, data, output_directory):
        self.node_id = node_id
        self.parameters = parameters
        self.data = data
        self.output_directory = output_directory


class ListLengthGreaterTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        # Get the structure list and check its length against the parameter
        logging.info(f"GData: {self.data.keys()}")
        structures_list = self.data.get('structures_list')
        logging.info(f"GData Structure list: {structures_list}")
        logging.info(f"GLength of structure list: {len(structures_list)}")
        if len(structures_list) >= int(condition_param):
            return True
        else:
            return False

class ListLengthLessTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        # Get the structure list and check its length against the parameter
        logging.info(f"LData: {self.data.keys()}")
        structures_list = self.data.get('structures_list')
        logging.info(f"LData Structure list: {structures_list}")
        logging.info(f"Length of structure list: {len(structures_list)}")
        if len(structures_list) <= int(condition_param):
            return True
        else:
            return False

class RWPGradientTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        # Get the structure list and check if the RWP gradient is greater than the parameter
        structure_list = self.data.get('structure_list')
        for structure in structure_list:
            rwp_gradient = structure.get('rwp_gradient')
            if rwp_gradient > condition_param:
                return True
        return False

class ContainsTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        # Get the structure list and check if it contains the parameter
        structure_list = self.data.get('structure_list')
        if condition_param in structure_list:
            return True
        else:
            return False

class NumberOfRunsGreaterTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        number_of_runs = int(iterations)
        logging.info(f"Number of runs greater than: {number_of_runs}")

        if number_of_runs >= int(condition_param):
            return True
        else:
            return False

class NumberOfRunsLessTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        number_of_runs = int(iterations)
        logging.info(f"Number of runs less than: {number_of_runs}")

        if number_of_runs <= int(condition_param):
            return True
        else:
            return False


class FinishedTask(BaseConditionTask):
    def run(self, condition_param, iterations):
        # Get the structure list and check its length against the parameter
        results = self.data.get('results', {})

        # Retrieve the 'finished' value from results. Adjust logic if your data is structured differently.
        finished = results.get('finished', False)

        # Convert 'condition_param' string to a boolean
        condition_param_bool = condition_param.lower() == 'true'

        logging.info(f"Finished: {finished} == {condition_param_bool}")

        if finished == condition_param_bool:
            logging.info("Finished: Yes")
            return True
        else:
            logging.info("Finished: No")
            return False
