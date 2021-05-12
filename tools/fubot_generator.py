from fubot_config import fubot_config
from fubot_chunker import chunk_dataset
from fubot_feature_gen import generate_trainingset
import sys
import os

def generate_dataset(config_fp: None):
    if config_fp is None:
        if len(sys.argv) <= 1:
            print('Fubot Config Filepath required...')
            return

        config_fp = sys.argv[1]

    if not os.path.exists(config_fp):
        print(f'Fubot Configuration file not found... (\'{config_fp}\'')
        return

    print(config_fp)
    config = fubot_config(config_fp)
    config.set_working_directory()

    print(">> Chunking Dataset")
    chunk_dataset(config)
    print(">> Generating Training Features")
    generate_trainingset(config)

if __name__ == "__main__":
    #generate_dataset('samples/config_default6p.json')
    generate_dataset(None)
