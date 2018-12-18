# config.py
import os.path

# gets home dir cross platform
HOME = os.path.expanduser("~")

# for making bounding boxes pretty
COLORS = ((255, 0, 0, 128), (0, 255, 0, 128), (0, 0, 255, 128),
          (0, 255, 255, 128), (255, 0, 255, 128), (255, 255, 0, 128))

MEANS = (104, 117, 123)

# SSD300 CONFIGS
voc = {
    'num_classes': 21,
    'lr_steps': (80000, 100000, 120000),
    'max_iter': 120000,
    'checkpoint_step': 2000,
    'feature_maps': [40, 20, 10, 5],
    'min_dim': 320,
    'steps': [8, 16, 32, 64],
    'min_sizes': [32, 64, 128, 256],
    'max_sizes': [],
    'aspect_ratios': [[2], [2], [2], [2]],
    'mbox': [3, 3, 3, 3],  # number of boxes per feature map location
    #'aspect_ratios': [[2, 3], [2,3], [2,3], [2,3]],
    #'mbox': [5, 5, 5, 5],  # number of boxes per feature map location
    #'mbox': [4, 4, 4, 4],  # number of boxes per feature map location
    'variance': [0.1, 0.2],
    'clip': False,
    # 'clip': True,
    'tcb_channles': 256,
    'gt_overlap_threshold': 0.5,
    'neg_pos_ratio': 3,
    # prior with positive probility less than this will be ignored
    'use_batch_norm': False,
    'pos_prior_threshold': 0.01,
    'top_k_pre_nms': 400,
    'top_k': 200,
    'detection_nms': 0.45,
    'detection_conf_threshold': 0.01,
    'name': 'VOC',
}

#
coco = {
    'num_classes': 81,
    'lr_steps': (280000, 360000, 400000), # ok
    'max_iter': 400000, # ok
    'checkpoint_step': 10000,
    'feature_maps': [40, 20, 10, 5], # ok
    'min_dim': 320, # ok
    'steps': [8, 16, 32, 64], # ok
    'min_sizes': [32, 64, 128, 256],
    'max_sizes': [],
    'aspect_ratios': [[2], [2], [2], [2]],
    'mbox': [3, 3, 3, 3],  # number of boxes per feature map location
    #'aspect_ratios': [[2, 3], [2,3], [2,3], [2,3]],
    #'mbox': [5, 5, 5, 5],  # number of boxes per feature map location
    #'mbox': [4, 4, 4, 4],  # number of boxes per feature map location
    'variance': [0.1, 0.2],
    'clip': False,
    # 'clip': True,
    'tcb_channles': 256,
    'gt_overlap_threshold': 0.5,
    'neg_pos_ratio': 3,
    # prior with positive probility less than this will be ignored
    'use_batch_norm': False,
    'pos_prior_threshold': 0.01,
    'top_k_pre_nms': 400,
    'top_k': 200,
    'detection_nms': 0.45,
    'detection_conf_threshold': 0.01,
    'name': 'COCO',
}


