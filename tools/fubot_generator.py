from fubot_config import fubot_config
from fubot_chunker import chunk_dataset
from fubot_feature_gen import generate_trainingset

def generate_dataset(config_fp):
    config = fubot_config(config_fp)
    config.set_working_directory()

    print(">> Chunking Dataset")
    chunk_dataset(config)
    print(">> Generating Training Features")
    generate_trainingset(config)

if __name__ == "__main__":
    generate_dataset('samples/config_default6p.json')
