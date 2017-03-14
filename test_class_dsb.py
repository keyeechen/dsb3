"""
Script to run your model config on the DSB test data.
The output of this script are the predictions stored as pkl and a Kaggle submission csv file.

Run with python test_class_dsb.py <configuration_name>
"""
import csv
import pickle
import string
import sys
import lasagne as nn
import numpy as np
import theano
import buffering
import data_iterators
import pathfinder
import utils
from configuration import config, set_configuration
from utils_plots import plot_slice_3d_3
import utils_lung
import logger

theano.config.warn_float64 = 'raise'

if len(sys.argv) < 2:
    sys.exit("Usage: test_class_dsb.py <configuration_name>")

config_name = sys.argv[1]
set_configuration('configs_class_dsb', config_name)

# metadata
metadata_dir = utils.get_dir_path('models', pathfinder.METADATA_PATH)
metadata_path = utils.find_model_metadata(metadata_dir, config_name)
metadata = utils.load_pkl(metadata_path)
expid = metadata['experiment_id']

# logs
logs_dir = utils.get_dir_path('logs', pathfinder.METADATA_PATH)
sys.stdout = logger.Logger(logs_dir + '/%s-test.log' % expid)
sys.stderr = sys.stdout

# predictions path
predictions_dir = utils.get_dir_path('model-predictions', pathfinder.METADATA_PATH)
outputs_path = predictions_dir + '/' + expid
utils.auto_make_dir(outputs_path)

print 'Build model'
model = config().build_model()
all_layers = nn.layers.get_all_layers(model.l_out)
all_params = nn.layers.get_all_params(model.l_out)
num_params = nn.layers.count_params(model.l_out)
print '  number of parameters: %d' % num_params
print string.ljust('  layer output shapes:', 36),
print string.ljust('#params:', 10),
print 'output shape:'
for layer in all_layers:
    name = string.ljust(layer.__class__.__name__, 32)
    num_param = sum([np.prod(p.get_value().shape) for p in layer.get_params()])
    num_param = string.ljust(num_param.__str__(), 10)
    print '    %s %s %s' % (name, num_param, layer.output_shape)

nn.layers.set_all_param_values(model.l_out, metadata['param_values'])

valid_loss = config().build_objective(model, deterministic=True)

x_shared = nn.utils.shared_empty(dim=len(model.l_in.shape))

givens_valid = {}
givens_valid[model.l_in.input_var] = x_shared

# theano functions
iter_get_predictions = theano.function([], nn.layers.get_output(model.l_out, deterministic=True), givens=givens_valid)
try:
    hasattr(config(), 'test_data_iterator')
except AttributeError:
    sys.exit('Your configuration file ({}) is missing a test_data_iterator'.format(config_name))

test_data_iterator = config().test_data_iterator

print
print 'Data'
print 'n test: %d' % test_data_iterator.nsamples

# Iterate over test samples and pickle predictions
preds = {}
for n, (x_chunk, id_chunk) in enumerate(buffering.buffered_gen_threaded(test_data_iterator.generate())):
    # load chunk to GPU
    x_shared.set_value(x_chunk)
    # predict
    predictions = iter_get_predictions()

    preds[id_chunk] = predictions

# pickle predictions
predictions_pickle_file = outputs_path + 'test_predictions.pkl'
with open(predictions_pickle_file, 'w') as f:
    pickle.dump(preds, f, pickle.HIGHEST_PROTOCOL)

# pickle predictions to kaggle csv submission file
SUBMISSION_PATH = outputs_path
kaggle_submission_file = SUBMISSION_PATH + 'submission.csv'
csv_writer = csv.writer(open(kaggle_submission_file, 'w'))
csv_writer.writerow(['id', 'cancer'])
with open(predictions_pickle_file, 'rb') as f:
    predictions = pickle.load(f)
    for pid, prediction in predictions.iteritems():
        csv_writer.writerow([pid, prediction])
