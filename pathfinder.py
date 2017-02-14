import json
import utils
import os

if utils.hostname() == 'user':
    with open('SETTINGS_user.json') as data_file:
        paths = json.load(data_file)
elif utils.hostname() == 'paard':
    with open('SETTINGS_paard.json') as data_file:
        paths = json.load(data_file)
else:
    with open('SETTINGS.json') as data_file:
        paths = json.load(data_file)

METADATA_PATH = paths["METADATA_PATH"]

# kaggle data
DATA_PATH = paths["DATA_PATH"]
utils.check_data_paths(DATA_PATH)

LABELS_PATH = paths["LABELS_PATH"]
if not os.path.isfile(LABELS_PATH):
    raise ValueError('no file with train labels')

SAMPLE_SUBMISSION_PATH = paths["SAMPLE_SUBMISSION_PATH"]
if not os.path.isfile(SAMPLE_SUBMISSION_PATH):
    raise ValueError('no sample submission file')

VALIDATION_SPLIT_PATH = paths["VALIDATION_SPLIT_PATH"]
# if not os.path.isfile(VALIDATION_SPLIT_PATH):
#     raise ValueError('no validation file')

# luna data
LUNA_DATA_PATH = paths["LUNA_DATA_PATH"]
utils.check_data_paths(LUNA_DATA_PATH)

LUNA_CANDIDATES_PATH = paths["LUNA_CANDIDATES_PATH"]
if not os.path.isfile(LUNA_CANDIDATES_PATH):
    raise ValueError('no LUNA file candidates_V2.csv')

LUNA_LABELS_PATH = paths["LUNA_LABELS_PATH"]
if not os.path.isfile(LUNA_LABELS_PATH):
    raise ValueError('no file with luna annotations')

LUNA_VALIDATION_SPLIT_PATH = paths["LUNA_VALIDATION_SPLIT_PATH"]
if not os.path.isfile(LUNA_VALIDATION_SPLIT_PATH):
    raise ValueError('no LUNA validation split file')