import os
import json
import random
import datetime

from fubot_config import *

def calculate_frames_and_chunks(num_frames, split, minC, maxC):
    f = int(num_frames * split)
    c = int(f / maxC)
    if f - (c * maxC) > minC:
        c += 1

    return f, c

def chunk_frames(num_frames, split_params):
    #read params
    min_chunk_size = split_params['min_chunk_size']
    max_chunk_size = split_params['max_chunk_size']
    ratios = split_params['split_ratios']
    categories = split_params['split_categories']
    num_categories = len(categories)

    sp_frames = [0] * num_categories
    sp_chunks = [0] * num_categories
    tot_frames = 0
    tot_chunks = 0
    rnd_distribution = list()
    for cat_id in range(num_categories):
        sp_frames[cat_id], sp_chunks[cat_id] = calculate_frames_and_chunks(num_frames, ratios[cat_id], min_chunk_size, max_chunk_size)
        tot_frames += sp_frames[cat_id]
        tot_chunks += sp_chunks[cat_id]

        rnd_distribution.extend([cat_id] * sp_chunks[cat_id])

    #store params
    split_params['sp_frames'] = sp_frames.copy()
    split_params['sp_chunks'] = sp_chunks
    split_params['tot_frames'] = tot_frames
    split_params['tot_chunks'] = tot_chunks

    random.shuffle(rnd_distribution)

    split_order = list()
    for rnd_id in rnd_distribution:
        chunkSize = max_chunk_size
        if sp_frames[rnd_id] < chunkSize:
            chunkSize = sp_frames[rnd_id]
        sp_frames[rnd_id] -= chunkSize
        
        split_order.append(f'{categories[rnd_id]}_{chunkSize}')

    return split_order, split_params

def split_source_file(split_params):
    #read params
    sample_name = split_params['sample_name']
    source_file = split_params['sample_source_path']
    output_root = split_params['sample_output']    

    with open(source_file) as f_in:
        #collect hierarchy
        hierarchy_str = ''

        while True:
            line = f_in.readline()
            hierarchy_str += line
            if line.startswith('MOTION'):
                break

        #split bvh motion
        source_num_frames = int(f_in.readline().split('    ')[1])
        split_key, split_params = chunk_frames(source_num_frames, split_params)
        frame_time = f_in.readline()

        split_cat_counter = {}
        for split_id, split_entry in enumerate(split_key):
            split_cat = split_entry.split('_')[0]
            num_frames = int(split_entry.split('_')[1])

            if split_cat in split_cat_counter:
                split_cat_counter[split_cat] += 1
            else:
                split_cat_counter[split_cat] = 1
            
            filepath = os.path.join(output_root, split_cat, 'bvh')
            os.makedirs(filepath, exist_ok=True)
            filepath = os.path.join(filepath, f'{sample_name}_{split_cat_counter[split_cat]}_b.bvh')
            #filepath = os.path.join(filepath, f'{sample_name}_{split_id}_b.bvh')

            with open(filepath, 'w') as f_out:
                f_out.write(hierarchy_str)
                f_out.write(f'Frames:    {num_frames}\n')
                f_out.write(frame_time)

                #Frames
                for _ in range(num_frames):
                    f_out.write(f_in.readline())

    return split_params

def create_sample_metafile(split_params, gds_meta):
    game_meta_root = os.path.join(split_params['sample_output'], 'meta')
    os.makedirs(game_meta_root, exist_ok=True)

    sample_data = {
        'name':split_params['sample_name'],
        'game_id':split_params['game_id'],
        'sample_id':split_params['sample_id'],
        'source_file':split_params['source_file_path'],
        'min_chunk_size':split_params['min_chunk_size'],
        'max_chunk_size':split_params['max_chunk_size'],
        'split_categories':split_params['split_categories'],
        'split_ratios':split_params['split_ratios'],
        'num_chunks':{
            'total':split_params['tot_chunks']
        },
        'num_frames':{
            'total':split_params['tot_frames']
        }
    }

    #update game ds meta
    gds_meta['sample_ids'].append(sample_data['name'])
    gds_meta['total_chunks']['total'] += split_params['tot_chunks']
    gds_meta['total_frames']['total'] += split_params['tot_frames']

    for cat_id, cat_name in enumerate(split_params['split_categories']):   
        sample_data['num_chunks'][cat_name] = split_params['sp_chunks'][cat_id]
        sample_data['num_frames'][cat_name] = split_params['sp_frames'][cat_id]

        #gds meta
        gds_meta['total_chunks'][cat_name] += split_params['sp_chunks'][cat_id]
        gds_meta['total_frames'][cat_name] += split_params['sp_frames'][cat_id]

    metafile_path = os.path.join(game_meta_root, split_params['sample_name'] + '.json')
    with open(metafile_path, 'w') as f:
        json.dump(sample_data, f, indent=2)

def chunk_dataset(config:fubot_config):
    config.set_working_directory()

    #Random Seed
    rnd_seed = config.params['split']['seed']
    if rnd_seed < 0:
        rnd_seed = datetime.now()
    
    random.seed(rnd_seed)


    #Split Params
    sp = {
        'dataset_root': config.params['fubot_root'],
        'output_root': os.path.join(config.params['output_root'],config.params['output_name']),
        'split_categories':config.params['split']['categories'],
        'split_ratios':config.params['split']['ratios'],
        'min_chunk_size':config.params['split']['min_chunk_size'],
        'max_chunk_size':config.params['split']['max_chunk_size']
    }

    dataset_root = sp['dataset_root']
    meta_root_path = os.path.join(dataset_root, 'meta')
    game_ids = next(os.walk(meta_root_path))[1]

    def summary_dict():
        d = {'total':0}
        for c in sp['split_categories']:
            d[c] = 0

        return d

    def append_dicts(a, b):
        a['total'] += b['total']
        for c in sp['split_categories']:
            a[c] += b[c]

    ds_meta = {
        'name':config.params['output_name'],
        'sample_rate':30, #fixed for now
        'length':-1,
        'split_categories':sp['split_categories'],
        'split_ratios':sp['split_ratios'],
        'split_seed':rnd_seed,
        'min_chunk_size':sp['min_chunk_size'],
        'max_chunk_size':sp['max_chunk_size'],
        'total_chunks': summary_dict(),
        'total_frames': summary_dict(),
        'game_ids':list()
    }

    for game_id in game_ids:
        meta_game_root_path = os.path.join(meta_root_path, game_id)
        game_samples = next(os.walk(meta_game_root_path))[2]

        #update DS META
        game_ds_meta = {
            'name':game_id,
            'sample_ids': list(),
            'total_chunks':summary_dict(),
            'total_frames':summary_dict(),
        }
        ds_meta['game_ids'].append(game_ds_meta)

        for game_sample in game_samples:
            meta_sample_path = os.path.join(meta_game_root_path, game_sample)
            with open(meta_sample_path) as f:
                sample_json = json.loads(f.read())

            sp['sample_source_path'] = os.path.join(dataset_root, sample_json['source_file'])
            sp['source_file_path'] = sample_json['source_file']
            sample_name = os.path.basename(sample_json['source_file'])
            sample_name = os.path.splitext(sample_name)[0]
            sp['sample_name'] = sample_name
            sp['game_id'] = sample_json['game_id'].lower()
            sp['sample_id'] = sample_json['sample_id']
            sp['sample_output'] = os.path.join(sp['output_root'], sp['game_id'])

            sp = split_source_file(sp)
            #Generate Metafile
            create_sample_metafile(sp, game_ds_meta)

        append_dicts(ds_meta['total_chunks'], game_ds_meta['total_chunks'])
        append_dicts(ds_meta['total_frames'], game_ds_meta['total_frames'])

    ds_meta['length'] = str(datetime.timedelta(seconds=ds_meta['total_frames']['total']/ds_meta['sample_rate']))

    #Save DS Meta
    with open(os.path.join(sp['output_root'], config.params['output_name'] + '_meta.json'), 'w') as f:
        json.dump(ds_meta, f, indent=2)

if __name__ == "__main__":
    config = fubot_config('samples/config_default6p.json')
    chunk_dataset(config)