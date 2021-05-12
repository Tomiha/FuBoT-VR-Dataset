import os
import glob
from tqdm import tqdm

from fubot_config import *
from fubot_bvh import *

def generate_trainingset(config: fubot_config):
    config.set_working_directory()

    input_root = config.params['output_root']
    ds_root = os.path.join(input_root, config.params['output_name'])
    
    #parse DS Metafile
    ds_meta_fp = os.path.join(ds_root, config.params['output_name']+'.json')
    with open(ds_meta_fp) as f:
        ds_meta = json.loads(f.read())

    pbar_game_id = tqdm(ds_meta['game_ids'])
    for game_id in pbar_game_id:
        game_name = game_id['name']
        pbar_game_id.set_description(f'Processing \'{game_name}\'')
        pbar_cat = tqdm(ds_meta['split_categories'])
        for cat in pbar_cat:
            pbar_cat.set_description(f'Category > \'{cat}\'')
            cat_path = os.path.join(ds_root, game_id['name'], cat)
            bvh_filter = os.path.join(cat_path, 'bvh', '*_b.bvh')
            training_output = os.path.join(cat_path, 'training')
            os.makedirs(training_output, exist_ok=True)

            skeleton = None
            pbar_sample = tqdm(glob.glob(bvh_filter))
            pbar_sample.set_description('BVH Chunks')
            for bvh_fp in pbar_sample:
                s = os.path.basename(bvh_fp).split('_')
                
                if skeleton is None:
                    skeleton = bvh_skeleton(bvh_fp)
                else:
                    skeleton.set_motion_source(bvh_fp)

                skeleton.convert_to_training_set(config, training_output ,f'{s[0]}_{s[1]}_{s[2]}')

if __name__ == "__main__":
    config = fubot_config('samples/config_default6p.json')
    generate_trainingset(config)