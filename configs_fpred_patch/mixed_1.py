import numpy as np
import data_transforms
import data_iterators
import pathfinder
import lasagne as nn
from collections import namedtuple
from functools import partial
import lasagne.layers.dnn as dnn

import theano.tensor as T
import utils
import utils_lung

restart_from_save = None
rng = np.random.RandomState(42)

# transformations
p_transform = {'patch_size': (48, 48, 48),
               'mm_patch_size': (48, 48, 48),
               'pixel_spacing': (1., 1., 1.)
               }
p_transform_augment = {
    'translation_range_z': [-3, 3],
    'translation_range_y': [-3, 3],
    'translation_range_x': [-3, 3],
    'rotation_range_z': [-180, 180],
    'rotation_range_y': [-180, 180],
    'rotation_range_x': [-180, 180]
}


# data preparation function
def data_prep_function(data, patch_center, pixel_spacing, luna_origin, p_transform,
                       p_transform_augment, world_coord_system, **kwargs):
    x, patch_annotation_tf = data_transforms.transform_patch3d_mixed(data=data,
                                                               luna_annotations=None,
                                                               patch_center=patch_center,
                                                               p_transform=p_transform,
                                                               p_transform_augment=p_transform_augment,
                                                               pixel_spacing=pixel_spacing,
                                                               luna_origin=luna_origin,
                                                               world_coord_system=world_coord_system)
    x = data_transforms.pixelnormHU(x)
    return x


data_prep_function_train = partial(data_prep_function, p_transform_augment=p_transform_augment,
                                   p_transform=p_transform, world_coord_system=True)
data_prep_function_valid = partial(data_prep_function, p_transform_augment=None,
                                   p_transform=p_transform, world_coord_system=True)

# data iterators
batch_size = 16
nbatches_chunk = 1
chunk_size = batch_size * nbatches_chunk



#FIXXME: for test purposes, we again just use the ids
aapm_train_valid_ids=utils_lung.get_aapm_ids(pathfinder.AAPM_LABELS_PATH)


#FIXXME: to try this out we separate only into a train set as well as validation set, testset is just the validation set all over again

aapm_train_pids, aapm_valid_pids = aapm_train_valid_ids[:50], aapm_train_valid_ids[50:] 

train_valid_ids = utils.load_pkl(pathfinder.LUNA_VALIDATION_SPLIT_PATH)
train_pids, valid_pids = train_valid_ids['train'], train_valid_ids['valid']

train_data_iterator = data_iterators.CandidatesMixedMalignantBenignGenerator(data_path=pathfinder.LUNA_DATA_PATH,aapm_data_path = pathfinder.AAPM_DATA_PATH,
                                                                 batch_size=chunk_size,
                                                                 transform_params=p_transform,
                                                                 data_prep_fun=data_prep_function_train,
                                                                 rng=rng,
                                                                 patient_ids=train_pids,
                                                                 aapm_patient_ids=aapm_train_pids,
                                                                 full_batch=True, random=True, infinite=True,
                                                                 positive_proportion=0.5)

valid_data_iterator = data_iterators.CandidatesMixedMalignantBenignGenerator(data_path=pathfinder.LUNA_DATA_PATH,aapm_data_path = pathfinder.AAPM_DATA_PATH,
                                                                 batch_size=chunk_size,
                                                                 transform_params=p_transform,
                                                                 data_prep_fun=data_prep_function_train,
                                                                 rng=rng,
                                                                 patient_ids=valid_pids,
                                                                 aapm_patient_ids=aapm_valid_pids,
                                                                 full_batch=True, random=True, infinite=True,
                                                                 positive_proportion=0.5)




nchunks_per_epoch = train_data_iterator.nsamples / chunk_size
max_nchunks = nchunks_per_epoch * 100

validate_every = int(5. * nchunks_per_epoch)
save_every = int(1. * nchunks_per_epoch)

learning_rate_schedule = {
    0: 5e-4,
    int(max_nchunks * 0.5): 2e-4,
    int(max_nchunks * 0.6): 1e-4,
    int(max_nchunks * 0.7): 5e-5,
    int(max_nchunks * 0.8): 2e-5,
    int(max_nchunks * 0.9): 1e-5
}

# model
conv3d = partial(dnn.Conv3DDNNLayer,
                 filter_size=3,
                 pad='same',
                 W=nn.init.Orthogonal(),
                 nonlinearity=nn.nonlinearities.very_leaky_rectify)

max_pool3d = partial(dnn.MaxPool3DDNNLayer,
                     pool_size=2)

drop = nn.layers.DropoutLayer

dense = partial(nn.layers.DenseLayer,
                W=nn.init.Orthogonal(),
                nonlinearity=nn.nonlinearities.very_leaky_rectify)


def inrn_v2(lin):
    n_base_filter = 32

    l1 = conv3d(lin, n_base_filter, filter_size=1)

    l2 = conv3d(lin, n_base_filter, filter_size=1)
    l2 = conv3d(l2, n_base_filter, filter_size=3)

    l3 = conv3d(lin, n_base_filter, filter_size=1)
    l3 = conv3d(l3, n_base_filter, filter_size=3)
    l3 = conv3d(l3, n_base_filter, filter_size=3)

    l = nn.layers.ConcatLayer([l1, l2, l3])

    l = conv3d(l, lin.output_shape[1], filter_size=1)

    l = nn.layers.ElemwiseSumLayer([l, lin])

    l = nn.layers.NonlinearityLayer(l, nonlinearity=nn.nonlinearities.rectify)

    return l


def inrn_v2_red(lin):
    # We want to reduce our total volume /4

    den = 16
    nom2 = 4
    nom3 = 5
    nom4 = 7

    ins = lin.output_shape[1]

    l1 = max_pool3d(lin)

    l2 = conv3d(lin, ins // den * nom2, filter_size=3, stride=2)

    l3 = conv3d(lin, ins // den * nom2, filter_size=1)
    l3 = conv3d(l3, ins // den * nom3, filter_size=3, stride=2)

    l4 = conv3d(lin, ins // den * nom2, filter_size=1)
    l4 = conv3d(l4, ins // den * nom3, filter_size=3)
    l4 = conv3d(l4, ins // den * nom4, filter_size=3, stride=2)

    l = nn.layers.ConcatLayer([l1, l2, l3, l4])

    return l


def feat_red(lin):
    # We want to reduce the feature maps by a factor of 2
    ins = lin.output_shape[1]
    l = conv3d(lin, ins // 2, filter_size=1)
    return l


def build_model():
    l_in = nn.layers.InputLayer((None, 1,) + p_transform['patch_size'])
    l_target = nn.layers.InputLayer((None, 3))

    l = conv3d(l_in, 64)
    l = inrn_v2_red(l)
    l = inrn_v2(l)
    l = feat_red(l)
    l = inrn_v2(l)

    l = inrn_v2_red(l)
    l = inrn_v2(l)
    l = feat_red(l)
    l = inrn_v2(l)

    l = feat_red(l)

    l = dense(drop(l), 128)


    l_out = nn.layers.DenseLayer(l, num_units=2,
                                 W=nn.init.Constant(0.),
                                 b=nn.init.Constant(0.5),
                                 nonlinearity=nn.nonlinearities.sigmoid)

    return namedtuple('Model', ['l_in', 'l_out', 'l_target'])(l_in, l_out, l_target)


def build_objective(model, deterministic=False, epsilon=1e-12):
    predictions = nn.layers.get_output(model.l_out, deterministic=deterministic)
    targets = nn.layers.get_output(model.l_target).astype('float32')

    enum_batch=T.arange(predictions.shape[0])
    p_1 = predictions[enum_batch,0]
    p_2 = predictions[enum_batch,1]
    t_1=targets[enum_batch,0]
    t_2=targets[enum_batch,2]
    inc_mb=targets[enum_batch,1]

    loss_fp=T.mean(nn.objectives.binary_crossentropy(p_1,t_1))
    loss_mb=T.mean(inc_mb*nn.objectives.binary_crossentropy(p_2,t_2))
    return loss_fp + loss_mb


def build_updates(train_loss, model, learning_rate):
    updates = nn.updates.adam(train_loss, nn.layers.get_all_params(model.l_out, trainable=True), learning_rate)
    return updates