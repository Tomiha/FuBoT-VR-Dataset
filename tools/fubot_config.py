import json
import re
import os
from pathlib import Path

class fubot_config():
    class feat_group():
        class feat_type():
            lut_C = {'w': 1, 'x':2, 'y':3, 'z':4}
            lut_C_inv = list(lut_C.keys())
            lut_S = {'l': 1, 'w':2}
            lut_T = {'pos': 1, 'qrot':2, 'rot':3}

            def __init__(self, S, T, C):              
                self.S = self.lut_S[S]
                self.T = self.lut_T[T]
                self.C = self.lut_C[C]
                self.C_id = self.C - (1 if self.T == 2 else 2)
                self.valid = (self.S * self.T * self.C) > 0

            def getValue(self, v_local, v_world):
                return v_local[self.C_id] if self.S == 1 else v_world[self.C_id]

            def getPostFix(self):
                pt = 'p' if self.T == 1 else 'r'
                pc = self.lut_C_inv[self.C - 1]
                
                return f'_{pt}{pc}'

        def __init__(self, feature_config):
            self.name = None
            self.bone_name = None
            self.elements = []
            self.size = 0
            self.rgx_el = re.compile(r'(.+)\[(.+)\]_(.)')
            self.__parse__(feature_config)

        def __parse__(self, feature_config):
            self.name = feature_config[0]
            self.bone_name = feature_config[1] if len(feature_config[1]) > 0 else self.name

            #Feature Elements
            for f_el in feature_config[2]:
                m = self.rgx_el.match(f_el)
                g = m.groups()
                if len(g) is not 3:
                    print(f'Invalid feature element found. ({self.name} >> {f_el})')
                    continue

                for comp in g[1]:
                    ft = self.feat_type(g[2], g[0], comp)
                    if not ft.valid:
                        print(f'Invalid feature element found. ({self.name} >> {f_el} [{g[2]}, {g[0]}, {comp}])')
                        continue

                    self.elements.append(ft)
            
            self.size = len(self.elements)

    def __init__(self, config_path):
        self.features_output:self.feat_group = []
        self.features_output_header = []
        self.features_output_size = 0

        self.features_input:self.feat_group = []
        self.features_input_header = []
        self.features_input_size = 0
        self.params = None

        self.config_path = config_path

        self.__loadConfig__(config_path)

    def __loadConfig__(self, config_path):
        with open(config_path) as f:
            self.params = json.loads(f.read())

        #Training Features
        #input
        features = self.params['training']['input_features']
        if features is not None:
            for feat in features:
                fg = self.feat_group(feat)
                self.features_input.append(fg)
                self.features_input_size += fg.size

                #Create Header
                for ft in fg.elements:
                    self.features_input_header.append(f'{fg.bone_name}{ft.getPostFix()}')

                

        #output
        features = self.params['training']['output_features']
        if features is not None:
            for feat in features:
                fg = self.feat_group(feat)
                self.features_output.append(fg)
                self.features_output_size += fg.size

                #Create Header
                for ft in fg.elements:
                    self.features_output_header.append(f'{fg.bone_name}{ft.getPostFix()}')

    def set_working_directory(self):
        p = Path(self.config_path)
        if not os.path.exists(p.parent):
            return 
        
        if not os.path.samefile(p.parent, os.getcwd()):
            os.chdir(p.parent)

if __name__ == "__main__":
    config = fubot_config('samples/config_default6p.json')
    #print(config.params)
    config.set_working_directory()
    print(os.getcwd())
