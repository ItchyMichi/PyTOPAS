import logging
from ast import parse

import numpy as np
from scipy.stats import norm
from fontTools.ttx import process
from numpy.ma.core import append
from numpy.random import logistic


class BaseExclusionCriteriaTask:
    def __init__(self, parameters, logger=None):
        self.parameters = parameters
        self.logger = logger or logging.getLogger(self.__class__.__name__)

class WorstExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing Worst criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures'] + parsed_data['invalid_structures']}")
        # Prepare your data
        structure_names = [name for name in parsed_data.keys() if
                           name not in ['valid_structures', 'invalid_structures']]
        logging.info(f"Structure names: {structure_names}")

        # Lists to hold values
        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            # We still select a "primary" metric for array calculations.
            # Later, we'll combine if both are available.
            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue  # Skip if neither metric is available

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Convert to numpy arrays
        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        # Calculate means and standard deviations
        PW_mean = PW_array.mean()
        PW_std = PW_array.std(ddof=1)
        metric_mean = metrics_array.mean()
        metric_std = metrics_array.std(ddof=1)

        # Calculate z-scores
        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]

            # Retrieve both RWP and CS for this structure
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')

            # Percentage Weight z-score
            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            # Calculate metric z-scores
            # If both RWP and CS are available, we compute both and average them.
            if RWP is not None and CS is not None:
                rwp_z = -((RWP - metric_mean) / metric_std) if metric_std != 0 else 0
                cs_z = -abs((CS - metric_mean) / metric_std) if metric_std != 0 else 0
                metric_z = (rwp_z + cs_z) / 2.0  # Average both metric z-scores
            elif RWP is not None:
                # Only RWP
                metric_z = -((RWP - metric_mean) / metric_std) if metric_std != 0 else 0
            elif CS is not None:
                # Only CS
                metric_z = -abs((CS - metric_mean) / metric_std) if metric_std != 0 else 0
            else:
                metric_z = 0

            # Combined z-score
            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)

            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Exclude the worst structure
        excluded_structure = sorted_structures[-1][0]
        parsed_data['excluded_structure_list'] = excluded_structure
        structure_list = [name + '.str' for name in structure_names if name != excluded_structure]
        parsed_data['structures_list'] = structure_list

        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data

        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data

        return processed_data

class WorstCombinedExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing Worst criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures'] + parsed_data['invalid_structures']}")
        # Prepare your data
        structure_names = [name for name in parsed_data.keys() if
                           name not in ['valid_structures', 'invalid_structures']]
        logging.info(f"Structure names: {structure_names}")

        # Lists to hold values for initial z-score computations
        percentage_weights = []
        metrics = []  # This will hold primary metric values (RWP or CS, whichever was found first)
        metric_names = []
        structures_with_metrics = []

        # Lists to hold all RWP and CS values for separate distributions
        all_RWP_values = []
        all_CS_values = []

        # First pass: determine primary metric per structure and store PW & metric
        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    # Neither metric available, skip
                    continue

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Second pass: collect all RWP and CS values for separate distributions
        for name in structures_with_metrics:
            data = parsed_data[name]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            if RWP is not None:
                all_RWP_values.append(RWP)
            if CS is not None:
                all_CS_values.append(CS)

        # Convert to numpy arrays
        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        # Calculate means and standard deviations for PW
        PW_mean = PW_array.mean() if len(PW_array) > 0 else 0
        PW_std = PW_array.std(ddof=1) if len(PW_array) > 1 else 0

        # Calculate means and std for RWP and CS separately
        RWP_mean = np.mean(all_RWP_values) if len(all_RWP_values) > 0 else 0
        RWP_std = np.std(all_RWP_values, ddof=1) if len(all_RWP_values) > 1 else 0
        CS_mean = np.mean(all_CS_values) if len(all_CS_values) > 0 else 0
        CS_std = np.std(all_CS_values, ddof=1) if len(all_CS_values) > 1 else 0

        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]

            # Retrieve both RWP and CS for this structure
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')

            # Percentage Weight z-score
            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            # Compute metric z-scores depending on availability
            metric_zs = []
            if RWP is not None:
                # RWP z-score (inverted)
                rwp_z = -((RWP - RWP_mean) / RWP_std) if RWP_std != 0 else 0
                metric_zs.append(rwp_z)

            if CS is not None:
                # CS z-score (negative absolute)
                cs_z = -abs((CS - CS_mean) / CS_std) if CS_std != 0 else 0
                metric_zs.append(cs_z)

            # If both present, average them; if only one, just use that
            metric_z = np.mean(metric_zs) if metric_zs else 0

            # Combined z-score
            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Exclude the worst structure
        excluded_structure = sorted_structures[-1][0]
        parsed_data['excluded_structure_list'] = excluded_structure
        structure_list = [name + '.str' for name in structure_names if name != excluded_structure]
        parsed_data['structures_list'] = structure_list

        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data

        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data

        return processed_data

class AEBExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing AEB criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures'] + parsed_data['invalid_structures']}")
        # Prepare your data
        invalid_structure_list = parsed_data['invalid_structures']
        valid_structure_list = parsed_data['valid_structures']
        structure_names = [structure + '.str' for structure in invalid_structure_list]
        logging.info(f"Structure names: {structure_names}")

        # Lists to hold values
        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue  # Skip if neither metric is available

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Convert to numpy arrays
        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        # Calculate means and standard deviations
        PW_mean = PW_array.mean()
        PW_std = PW_array.std(ddof=1)
        metric_mean = metrics_array.mean()
        metric_std = metrics_array.std(ddof=1)

        # Calculate z-scores
        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            metric = metrics_array[i]
            metric_name = metric_names[i]

            # Percentage Weight z-score
            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            # Metric z-score
            if metric_name == 'rwp':
                # Invert RWP z-score
                metric_z = -((metric - metric_mean) / metric_std) if metric_std != 0 else 0
            else:
                # Crystallite Size: Negative absolute z-score
                metric_z = -abs((metric - metric_mean) / metric_std) if metric_std != 0 else 0

            # Combined z-score
            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            # logging.info(f"{name}: PW Z = {PW_z:.2f}, Metric Z = {metric_z:.2f}, Combined Z = {combined_z:.2f}")
            # Store in data
            # data['percentage_weight_z'] = PW_z
            # data['metric_z'] = metric_z
            # data['combined_z'] = combined_z
            # data['metric_type'] = metric_name

            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Exclude the worst structure
        best_structure = sorted_structures[0][0]
        excluded_structure_list = [name + '.str' for name in structure_names if name != best_structure]
        parsed_data['excluded_structure_list'] = excluded_structure_list
        structure_list = [best_structure + '.str'] + [name + '.str' for name in valid_structure_list]
        parsed_data['structures_list'] = structure_list

        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure_list}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data


        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data


        return processed_data

class AEBCombinedExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing AEB criteria with separate RWP/CS distributions")
        logging.info(f"Before structure_list: {parsed_data['valid_structures'] + parsed_data['invalid_structures']}")

        invalid_structure_list = parsed_data['invalid_structures']
        valid_structure_list = parsed_data['valid_structures']
        structure_names = [structure + '.str' for structure in invalid_structure_list]
        logging.info(f"Structure names: {structure_names}")

        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        # Collect RWP/CS values for distributions
        all_RWP_values = []
        all_CS_values = []

        # Identify primary metric for each structure
        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Second pass: collect all RWP and CS values
        for name in structures_with_metrics:
            data = parsed_data[name]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            if RWP is not None:
                all_RWP_values.append(RWP)
            if CS is not None:
                all_CS_values.append(CS)

        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        PW_mean = PW_array.mean() if len(PW_array) > 0 else 0
        PW_std = PW_array.std(ddof=1) if len(PW_array) > 1 else 0

        RWP_mean = np.mean(all_RWP_values) if all_RWP_values else 0
        RWP_std = np.std(all_RWP_values, ddof=1) if len(all_RWP_values) > 1 else 0

        CS_mean = np.mean(all_CS_values) if all_CS_values else 0
        CS_std = np.std(all_CS_values, ddof=1) if len(all_CS_values) > 1 else 0

        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')

            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            metric_zs = []
            if RWP is not None:
                rwp_z = -((RWP - RWP_mean) / RWP_std) if RWP_std != 0 else 0
                metric_zs.append(rwp_z)
            if CS is not None:
                cs_z = -abs((CS - CS_mean) / CS_std) if CS_std != 0 else 0
                metric_zs.append(cs_z)

            metric_z = np.mean(metric_zs) if metric_zs else 0

            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Best structure kept, others excluded
        best_structure = sorted_structures[0][0]
        excluded_structure_list = [s for s in structure_names if s != best_structure]

        parsed_data['excluded_structure_list'] = excluded_structure_list
        structure_list = [best_structure] + [s + '.str' for s in valid_structure_list]
        parsed_data['structures_list'] = structure_list

        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure_list}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data

        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data

        return processed_data

class FailingExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing Failing criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures']+parsed_data['invalid_structures']}")
        valid_structure_list = parsed_data['valid_structures']
        invalid_structure_list = parsed_data['invalid_structures']
        structure_list = [structure + '.str' for structure in valid_structure_list]
        logging.info(f"structure_list: {structure_list}")
        parsed_data['structures_list'] = structure_list
        logging.info(f"parsed_data['structures_list']: {parsed_data['structures_list']}")
        logging.info(f"parsed_data: {parsed_data}")
        parsed_data['excluded_structure_list'] = invalid_structure_list
        logging.info(f"parsed_data['excluded_structure_list']: {parsed_data['excluded_structure_list']}")

        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']


        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {invalid_structure_list}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list


        return parsed_data

class FailingZScoreExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing Failing Z-Score criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures'] + parsed_data['invalid_structures']}")
        # Prepare your data
        structure_names = parsed_data['invalid_structures']

        logging.info(f"Invalid Structure names: {structure_names}")

        # Lists to hold values
        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue  # Skip if neither metric is available

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Convert to numpy arrays
        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        # Calculate means and standard deviations
        PW_mean = PW_array.mean()
        PW_std = PW_array.std(ddof=1)
        metric_mean = metrics_array.mean()
        metric_std = metrics_array.std(ddof=1)

        # Calculate z-scores
        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            metric = metrics_array[i]
            metric_name = metric_names[i]

            # Percentage Weight z-score
            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            # Metric z-score
            if metric_name == 'rwp':
                # Invert RWP z-score

                task_type = self.parameters["task_type"]

                if task_type in "RWPAddition":
                    # Example: negative of the normal RWP z-score
                    metric_z = -((metric - metric_mean) / metric_std) if metric_std != 0 else 0
                else:
                    # Or some alternative logic for other task types
                    metric_z = ((metric - metric_mean) / metric_std) if metric_std != 0 else 0


            else:
                # Crystallite Size: Negative absolute z-score
                metric_z = -abs((metric - metric_mean) / metric_std) if metric_std != 0 else 0

            # Combined z-score
            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            # logging.info(f"{name}: PW Z = {PW_z:.2f}, Metric Z = {metric_z:.2f}, Combined Z = {combined_z:.2f}")
            # Store in data
            # data['percentage_weight_z'] = PW_z
            # data['metric_z'] = metric_z
            # data['combined_z'] = combined_z
            # data['metric_type'] = metric_name

            combined_scores[name] = combined_z_conf


        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")

        threshold = np.float64(self.parameters['confidence'])
        excluded_structures = [name for name, score in sorted_structures if score < threshold]
        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']




        structure_list = [name + '.str' for name in complete_structure_names if name not in excluded_structures]

        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structures}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['excluded_structure_list'] = excluded_structures
        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list


        parsed_data['structures_list'] = structure_list


        processed_data = parsed_data
        return processed_data

class FailingZScoreCombinedExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def runs(self, parsed_data):
        logging.info("Processing Failing Z-Score criteria with separate RWP/CS distributions")
        logging.info(f"Before structure_list: {parsed_data['valid_structures'] + parsed_data['invalid_structures']}")
        structure_names = parsed_data['invalid_structures']
        logging.info(f"Invalid Structure names: {structure_names}")

        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        all_RWP_values = []
        all_CS_values = []

        # Identify primary metric and store PW/metrics
        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Collect all RWP and CS values
        for name in structures_with_metrics:
            data = parsed_data[name]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            if RWP is not None:
                all_RWP_values.append(RWP)
            if CS is not None:
                all_CS_values.append(CS)

        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        PW_mean = PW_array.mean() if len(PW_array) > 0 else 0
        PW_std = PW_array.std(ddof=1) if len(PW_array) > 1 else 0

        RWP_mean = np.mean(all_RWP_values) if all_RWP_values else 0
        RWP_std = np.std(all_RWP_values, ddof=1) if len(all_RWP_values) > 1 else 0
        CS_mean = np.mean(all_CS_values) if all_CS_values else 0
        CS_std = np.std(all_CS_values, ddof=1) if len(all_CS_values) > 1 else 0

        combined_scores = {}
        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')

            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            metric_zs = []
            if RWP is not None:
                rwp_z = -((RWP - RWP_mean) / RWP_std) if RWP_std != 0 else 0
                metric_zs.append(rwp_z)
            if CS is not None:
                cs_z = -abs((CS - CS_mean) / CS_std) if CS_std != 0 else 0
                metric_zs.append(cs_z)

            metric_z = np.mean(metric_zs) if metric_zs else 0

            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)

            combined_scores[name] = combined_z_conf

        # Rank and exclude based on threshold
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")

        threshold = np.float64(self.parameters['confidence'])
        excluded_structures = [name for name, score in sorted_structures if score < threshold]
        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']

        structure_list = [name + '.str' for name in complete_structure_names if name not in excluded_structures]

        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structures}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['excluded_structure_list'] = excluded_structures
        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['structures_list'] = structure_list

        processed_data = parsed_data
        return processed_data

class WorstNegativeExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing Worst Negative criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures']+parsed_data['invalid_structures']}")
        # Prepare your data
        structure_names = [name for name in parsed_data.keys() if
                           name not in ['valid_structures','invalid_structures']]

        #remove valid structures from the structure list
        structure_names = [name for name in structure_names if name not in parsed_data['valid_structures']]

        logging.info(f"Structure names: {structure_names}")

        # Lists to hold values
        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue  # Skip if neither metric is available

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Convert to numpy arrays
        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        # Calculate means and standard deviations
        PW_mean = PW_array.mean()
        PW_std = PW_array.std(ddof=1)
        metric_mean = metrics_array.mean()
        metric_std = metrics_array.std(ddof=1)

        # Calculate z-scores
        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            metric = metrics_array[i]
            metric_name = metric_names[i]

            # Percentage Weight z-score
            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            # Metric z-score
            if metric_name == 'rwp':
                # Invert RWP z-score
                metric_z = -((metric - metric_mean) / metric_std) if metric_std != 0 else 0
            else:
                # Crystallite Size: Negative absolute z-score
                metric_z = -abs((metric - metric_mean) / metric_std) if metric_std != 0 else 0

            # Combined z-score
            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            # logging.info(f"{name}: PW Z = {PW_z:.2f}, Metric Z = {metric_z:.2f}, Combined Z = {combined_z:.2f}")
            # Store in data
            # data['percentage_weight_z'] = PW_z
            # data['metric_z'] = metric_z
            # data['combined_z'] = combined_z
            # data['metric_type'] = metric_name

            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Exclude the worst structure
        excluded_structure = sorted_structures[-1][0]
        parsed_data['excluded_structure_list'] = excluded_structure
        structure_list = [name + '.str' for name in structure_names if name != excluded_structure]
        #add valid structures to the structure list from parsed_data['valid_structures']
        structure_list += [name + '.str' for name in parsed_data['valid_structures']]

        parsed_data['structures_list'] = structure_list



        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data

        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data

        return processed_data

class WorstNegativeCombinedExclusionCriteriaTask(BaseExclusionCriteriaTask):
    def run(self, parsed_data):
        logging.info("Processing Worst Negative criteria")
        logging.info(f"Before structure_list: {parsed_data['valid_structures']+parsed_data['invalid_structures']}")
        # Prepare your data
        structure_names = [name for name in parsed_data.keys() if
                           name not in ['valid_structures','invalid_structures']]

        #remove valid structures from the structure list
        structure_names = [name for name in structure_names if name not in parsed_data['valid_structures']]

        logging.info(f"Structure names: {structure_names}")

        # Lists to hold values
        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue  # Skip if neither metric is available

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        # Convert to numpy arrays
        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        # Calculate means and standard deviations
        PW_mean = PW_array.mean()
        PW_std = PW_array.std(ddof=1)
        metric_mean = metrics_array.mean()
        metric_std = metrics_array.std(ddof=1)

        # Calculate z-scores
        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            metric = metrics_array[i]
            metric_name = metric_names[i]

            # Percentage Weight z-score
            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            # Metric z-score
            if metric_name == 'rwp':
                # Invert RWP z-score
                metric_z = -((metric - metric_mean) / metric_std) if metric_std != 0 else 0
            else:
                # Crystallite Size: Negative absolute z-score
                metric_z = -abs((metric - metric_mean) / metric_std) if metric_std != 0 else 0

            # Combined z-score
            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            # logging.info(f"{name}: PW Z = {PW_z:.2f}, Metric Z = {metric_z:.2f}, Combined Z = {combined_z:.2f}")
            # Store in data
            # data['percentage_weight_z'] = PW_z
            # data['metric_z'] = metric_z
            # data['combined_z'] = combined_z
            # data['metric_type'] = metric_name

            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Exclude the worst structure
        excluded_structure = sorted_structures[-1][0]
        parsed_data['excluded_structure_list'] = excluded_structure
        structure_list = [name + '.str' for name in structure_names if name != excluded_structure]
        #add valid structures to the structure list from parsed_data['valid_structures']
        structure_list += [name + '.str' for name in parsed_data['valid_structures']]

        parsed_data['structures_list'] = structure_list



        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data

        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data

        return processed_data
    def run(self, parsed_data):
        logging.info("Processing Worst Negative criteria with separate RWP/CS distributions")
        logging.info(f"Before structure_list: {parsed_data['valid_structures']+parsed_data['invalid_structures']}")
        # Prepare data
        structure_names = [name for name in parsed_data.keys() if
                           name not in ['valid_structures','invalid_structures']]
        # Remove valid structures (as original code suggests)
        structure_names = [name for name in structure_names if name not in parsed_data['valid_structures']]
        logging.info(f"Structure names: {structure_names}")

        percentage_weights = []
        metrics = []
        metric_names = []
        structures_with_metrics = []

        all_RWP_values = []
        all_CS_values = []

        for name in structure_names:
            data = parsed_data[name]
            PW = data.get('percentage_weight')
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            logging.info(f"Processing {name} with PW: {PW}, RWP: {RWP}, CS: {CS}")

            if PW is not None:
                if RWP is not None:
                    metric = RWP
                    metric_name = 'rwp'
                elif CS is not None:
                    metric = CS
                    metric_name = 'crystallite_size'
                else:
                    continue

                percentage_weights.append(PW)
                metrics.append(metric)
                metric_names.append(metric_name)
                structures_with_metrics.append(name)

        for name in structures_with_metrics:
            data = parsed_data[name]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')
            if RWP is not None:
                all_RWP_values.append(RWP)
            if CS is not None:
                all_CS_values.append(CS)

        PW_array = np.array(percentage_weights)
        metrics_array = np.array(metrics)
        logging.info(f"PW_array: {PW_array}")
        logging.info(f"metrics_array: {metrics_array}")

        PW_mean = PW_array.mean() if len(PW_array) > 0 else 0
        PW_std = PW_array.std(ddof=1) if len(PW_array) > 1 else 0

        RWP_mean = np.mean(all_RWP_values) if all_RWP_values else 0
        RWP_std = np.std(all_RWP_values, ddof=1) if len(all_RWP_values) > 1 else 0
        CS_mean = np.mean(all_CS_values) if all_CS_values else 0
        CS_std = np.std(all_CS_values, ddof=1) if len(all_CS_values) > 1 else 0

        combined_scores = {}

        for i, name in enumerate(structures_with_metrics):
            data = parsed_data[name]
            PW = PW_array[i]
            RWP = data.get('RWP')
            CS = data.get('crystallite_size')

            PW_z = (PW - PW_mean) / PW_std if PW_std != 0 else 0

            metric_zs = []
            if RWP is not None:
                rwp_z = -((RWP - RWP_mean) / RWP_std) if RWP_std != 0 else 0
                metric_zs.append(rwp_z)
            if CS is not None:
                cs_z = -abs((CS - CS_mean) / CS_std) if CS_std != 0 else 0
                metric_zs.append(cs_z)

            metric_z = np.mean(metric_zs) if metric_zs else 0

            combined_z = PW_z + metric_z
            combined_z_conf = norm.cdf(combined_z)
            combined_scores[name] = combined_z_conf

        # Rank structures
        sorted_structures = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        logging.info(f"Ranked structures: {sorted_structures}")
        logging.info(f"Best structure: {sorted_structures[0][0]}")
        logging.info(f"Worst structure: {sorted_structures[-1][0]}")

        # Exclude the worst structure
        excluded_structure = sorted_structures[-1][0]
        parsed_data['excluded_structure_list'] = excluded_structure
        structure_list = [n + '.str' for n in structure_names if n != excluded_structure]
        # Add valid structures back
        structure_list += [n + '.str' for n in parsed_data['valid_structures']]

        parsed_data['structures_list'] = structure_list

        complete_structure_names = parsed_data['valid_structures'] + parsed_data['invalid_structures']
        logging.info(f"Complete Structure names: {complete_structure_names}")
        logging.info(f"Excluded Structure names: {excluded_structure}")
        logging.info(f"Final Structure names: {structure_list}")

        parsed_data['initial_structure_list'] = complete_structure_names
        parsed_data['final_structure_list'] = structure_list
        parsed_data['finished'] = False

        processed_data = parsed_data

        if len(structure_list) == 0:
            old_structure_list = [name + '.str' for name in complete_structure_names]
            parsed_data['structures_list'] = old_structure_list
            parsed_data['finished'] = True
            processed_data = parsed_data

        return processed_data


