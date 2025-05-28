import logging
import os
import re
import json
import shutil
import configparser




def parse_config(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    # Flatten the config into a dictionary
    flat_config = {}
    for section in config.sections():
        for key, value in config.items(section):
            flat_config[key] = value
    # Include defaults
    for key, value in config.defaults().items():
        flat_config[key] = value
    return flat_config

def rebuild_line(line_name, values, settings):
    """Replace or add the line with the correct values, formatting, and tab spacing."""
    tab_space = '\t'  # Define the tab spacing
    if line_name in ['LVol_FWHM_CS_G_L', 'CS']:
        # Add a semicolon after the 'min' value
        return f'{tab_space}{line_name}({", ".join(values[:-1])}, 1000 min ={settings["crystallite_size_min"]}; max ={settings["crystallite_size_max"]};)\n'
    elif line_name == 'e0_from_Strain':
        # Add a semicolon after the 'min' value and also after the 'max' value before the double commas
        return f'{tab_space}{line_name}({", ".join(values[:-1])}, 0.01 min ={settings["strain_min"]}; max ={settings["strain_max"]};,,)\n'

def modify_structure_file(file_path, settings):
    """Modify the structure file based on the process described."""
    with open(file_path, 'r') as file:
        lines = file.readlines()

    new_lines = []
    for line in lines:
        if 'LVol_FWHM_CS_G_L' in line:
            values = re.findall(r'\(([^)]+)\)', line)[0].split(', ')
            new_line = rebuild_line('LVol_FWHM_CS_G_L', values, settings)
            new_lines.append(new_line)
        elif 'CS(' in line:
            values = re.findall(r'\(([^)]+)\)', line)[0].split(', ')
            new_line = rebuild_line('CS', values, settings)
            new_lines.append(new_line)
        elif 'e0_from_Strain' in line:
            values = re.findall(r'\(([^)]+)\)', line)[0].split(', ')
            new_line = rebuild_line('e0_from_Strain', values, settings)
            new_lines.append(new_line)
        else:
            new_lines.append(line)  # Keep all other lines as they are

    with open(file_path, 'w') as file:
        file.writelines(new_lines)

def update_structure_files(structures_dir, config_path):
    """Updates all structure files in the given directory based on the configuration."""
    if not os.path.exists(structures_dir):
        raise FileNotFoundError(f"Structures directory {structures_dir} not found.")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file {config_path} not found.")

    # Parse the configuration settings
    settings = parse_config(config_path)

    # Iterate over each file in the directory and modify it if it's a structure file
    for filename in os.listdir(structures_dir):
        if filename.endswith('.str'):
            file_path = os.path.join(structures_dir, filename)
            modify_structure_file(file_path, settings)
            print(f"Updated {file_path}")

    # Update the all_structures.json file
    update_all_structures_template(structures_dir)

def load_template(template_path):
    """Load a template from a JSON file."""
    with open(template_path, 'r') as file:
        template = json.load(file)
    return template

def save_template(template, template_path, selected_structures):
    """Save a template to a JSON file, creating or overwriting as necessary."""
    # Ensure the directory exists
    os.makedirs('structure templates', exist_ok=True)

    # Correct the path for the template file
    template_path = os.path.join('structure templates', os.path.basename(template_path))

    # Add selected structures to the template
    template['structures'] = selected_structures

    # Save the template to the file
    with open(template_path, 'w') as file:
        json.dump(template, file, indent=4)

def get_all_structure_files(structures_dir):
    """Get a list of all structure files in the structure database directory."""
    return [filename for filename in os.listdir(structures_dir) if filename.endswith('.str')]

def update_all_structures_template(structures_dir):
    """Update the all_structures.json file with the current list of structures."""
    all_structures = get_all_structure_files(structures_dir)
    template = {
        "template_name": "All Structures",
        "structures": all_structures
    }
    template_path = os.path.join('structure templates', 'all_structures.json')
    save_template(template, template_path, all_structures)

def get_content(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def get_structure_content_in_content(content, structure_name):
    logging.info("Searching for structure in the content.")
    logging.info(f"Searching for structure {structure_name} in the content.")
    start_marker = f"/*{structure_name}_START*/"
    end_marker = f"/*{structure_name}_END*/"

    if start_marker in content and end_marker in content:
        logging.info(f"Structure {structure_name} found in the content.")
        start_index = content.index(start_marker) + len(start_marker)
        end_index = content.index(end_marker)
        section_content = content[start_index:end_index]

        return section_content
    else:
        logging.info(f"Structure {structure_name} not found in the content.")
        return None

def parse_crystallite_size(content):
    regex = re.compile(r'(?:cs_\w+|csl_\w+|@)\s*,?\s*([\d.]+)')
    cs_match = regex.search(content)
    if cs_match:
        return float(cs_match.group(1))
    else:
        logging.info("Crystallite size not found in the content.")
        return None

def parse_percentage_weight(content):
    regrex2 = re.compile(r'MVW\(\s*[\d.]+`?\s*,\s*[\d.]+`?\s*,\s*([\d.]+)`?\s*\)')
    weight_match = regrex2.search(content)
    if weight_match:
        return float(weight_match.group(1))
    else:
        logging.info("Percentage weight not found in the content.")
        return None

def parse_RWP(content):
    regrex3 = re.compile(r'r_wp\s+([\d.]+)')
    RWP_match = regrex3.search(content)
    if RWP_match:
        return float(RWP_match.group(1))
    else:
        logging.info("RWP not found in the content.")
        return None




if __name__ == "__main__":
    structures_dir = './structure database'
    config_path = './config.txt'
    update_structure_files(structures_dir, config_path)
    print(f"Structure files in {structures_dir} updated successfully.")
