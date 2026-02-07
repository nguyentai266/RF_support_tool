import os

import yaml


config_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"config.yaml")
def load_yaml():
		with open(config_path, 'r', encoding='utf-8') as file:
			config = yaml.safe_load(file)
			return config
