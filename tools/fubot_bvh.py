from collections import OrderedDict
from bvhtoolbox import Bvh
import transforms3d as t3d
from math import radians
import numpy as np
import pandas as pd
import os
from fubot_config import *

class bvh_skeleton_node:
    def __init__(self, name, offset):
        self.children = []
        self.parent:bvh_skeleton_node = None

        self.name = name
        self.local_position = offset
        self.local_rotation_mat = None
        self.local_rotation_quat = [0,0,0,0]
        self.local_transform = None

        self.world_position = None
        self.world_rotation_mat = None
        self.world_rotation_quat = None
        self.world_transform = None

    def CalculateWorld(self):
        self.local_transform = t3d.affines.compose(self.local_position, self.local_rotation_mat, [1,1,1])

        if self.parent != None:
            self.world_transform = self.parent.world_transform.dot(self.local_transform)
        else:
            self.world_transform = self.local_transform

        self.world_position, self.world_rotation_mat, _, _ = t3d.affines.decompose(self.world_transform)
        self.world_rotation_quat = t3d.quaternions.mat2quat(self.world_rotation_mat)

        for child in self.children:
            child.CalculateWorld()

    def SetLocalRotation(self, new_rotation):
        self.local_rotation_quat = new_rotation
        self.UpdateLocalRotation()

    def UpdateLocalRotation(self):
        self.local_rotation_mat = t3d.quaternions.quat2mat(self.local_rotation_quat)

    def AddChild(self, child):
        self.children.append(child)
        child.parent = self
        return child #Enables chaining

    def print_tree(self):
        if self.parent is None:
            print(f'{self.name} : ROOT ')
        else:
            print(f'{self.name} : {self.parent.name}')

        print(f'\t{self.name}_world {{{self.world_position}, {self.world_rotation_quat}}}')
        print(f'\t{self.name}_local {{{self.local_position}, {self.local_rotation_quat}}}')

        for child in self.children:
            child.print_tree()

class bvh_skeleton: 
    def __init__(self, bvh_fp = None):
        self.root = None
        self.nodes = OrderedDict()
        self.nodes_flat = []
        self.fp_bvh = bvh_fp
        self.bvh:Bvh = None

        self.load_skeleton(bvh_fp)

    def set_motion_source(self, bvh_fp):
        self.fp_bvh = bvh_fp
        with open(self.fp_bvh) as f:
            self.bvh = Bvh(f.read())

    def load_skeleton(self, bvh_fp):
        if bvh_fp is None:
            return

        self.fp_bvh = bvh_fp
        with open(self.fp_bvh) as f:
            self.bvh = Bvh(f.read())
        
        joint_names = self.bvh.get_joints_names() 
        skDef = OrderedDict()
        for joint_name in joint_names:
            j = self.bvh.get_joint(joint_name)
            j_parent = j.parent.value[1] if len(j.parent.value) > 1 else None
            j_offset = [float(val) for val in j['OFFSET']]
            skDef[joint_name] = (j_offset, j_parent)

        #Construct Skeleton
        self.nodes.clear()
        for key, value in skDef.items():
            value[0][0] = -value[0][0]
            new_node = bvh_skeleton_node(key, value[0])
            self.nodes[key] = new_node

            if value[1] != None:
                self.nodes[value[1]].AddChild(new_node)
            else:
                self.root = new_node

        self.nodes_flat = list(self.nodes.values())

    def __convertToUnityPos(self, v, y_up = True):
        if y_up:
            return v * [-1,1,1]

        return v * [-1,1,-1]

    def __convertToUnityQuat(self, e, y_up = True):
        qZ = t3d.quaternions.axangle2quat([0,0,1], radians(e[0]), True) #FORWARD/Z
        qX = t3d.quaternions.axangle2quat([1,0,0], radians(e[1]), True) #RIGHT/X
        qY = t3d.quaternions.axangle2quat([0,1,0], radians(e[2]), True) #UP/Y
        q = t3d.quaternions.qmult(t3d.quaternions.qmult(qZ , qX) , qY)
        #q /= t3dq.qnorm(q)

        if y_up:
            return q * [1,1,-1,-1]
        
        return q * [1,1,1,-1]

    def __getFeature(self, joint_name, ft:fubot_config.feat_group.feat_type):
        joint = self.nodes[joint_name]
        val = None

        if ft.T == 1: #POS
            return ft.getValue(joint.local_position, joint.world_position)
        if ft.T == 2: #QROT
            return ft.getValue(joint.local_rotation_quat, joint.world_rotation_quat)
        if ft.T == 3: #ROT (euler)
            print('Euler rotations not yet supported')
            return 0

    def set_motion_frame(self,index):
        frame = self.bvh.frames[index]
        
        #semi-hardcoded
        self.root.local_position = self.__convertToUnityPos(np.array(frame[0:3]).astype(np.float))

        for idx, n in enumerate(self.nodes_flat):
            i = 3 + (idx*3)
            q = self.__convertToUnityQuat(np.array(frame[i:i+3]).astype(np.float))
            n.SetLocalRotation(q)

        self.root.CalculateWorld()

    def extract_features(self, config:fubot_config):
        #Input Features
        features_input = np.empty(config.features_input_size)
        feature_id = 0
        for fg in config.features_input:
            for ft in fg.elements:
                features_input[feature_id] = self.__getFeature(fg.bone_name, ft)
                feature_id += 1

        #Output Features
        features_output = np.empty(config.features_output_size)
        feature_id = 0
        for fg in config.features_output:
            for ft in fg.elements:
                features_output[feature_id] = self.__getFeature(fg.bone_name, ft)
                feature_id += 1

        return features_input, features_output

    def convert_to_training_set(self, config:fubot_config, output_path, output_name):
        config.set_working_directory()

        num_f_in = config.features_input_size
        num_f_out = config.features_output_size
        num_frames = len(self.bvh.frames)

        train_input = np.empty(shape=(num_frames, num_f_in))
        train_output = np.empty(shape=(num_frames, num_f_out))

        for i in range(num_frames):
            self.set_motion_frame(i)
            f_in, f_out = self.extract_features(config)

            train_input[i,:] = f_in
            train_output[i,:] = f_out
        
        pd.DataFrame(data=train_input, columns=config.features_input_header).to_csv(os.path.join(output_path, f'{output_name}_in.csv'), index=False, float_format='%.7f')   
        pd.DataFrame(data=train_output, columns=config.features_output_header).to_csv(os.path.join(output_path, f'{output_name}_out.csv'), index=False, float_format='%.7f')

if __name__ == "__main__":
    skeleton = bvh_skeleton('samples/beatsaber_0_1_b.bvh')
    config = fubot_config('samples/config_default6p.json')

    skeleton.set_motion_frame(0)
    skeleton.convert_to_training_set(config, '', 'temp')