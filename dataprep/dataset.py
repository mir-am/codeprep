import logging
import os
from datetime import datetime

from typing import Type, Optional

from dataprep.config import DEFAULT_PARSED_DATASETS_DIR, DEFAULT_PREP_DATASETS_DIR, USER_BPE_DIR, DEFAULT_FILE_LIST_DIR, \
    LIMIT_FILES_ON_LAST_MODIFICATION_CHECK
from dataprep.prepconfig import PrepConfig
from dataprep.split.bpe_config import BpeConfig
logger = logging.getLogger(__name__)

PP_PARAMS_FILENAME = 'params.json'
PREPROCESSING_TYPES_FILENAME = 'preprocessing_types.json'
BPE_VOCAB_FILE_NAME = "vocab"
FILE_LIST_FILENAME = "filelist"
DIR_LIST_FILENAME = "dirlist"

PARSED_EXTENSION = ".parsed"
PREPROCESSED_EXTENSION = ".prep"
NOT_FINISHED_EXTENSION = "part"
ARCHIVED_EXT = "archived"


class SubDataset(object):
    def __init__(self, dataset: 'Dataset', path, suffix: str = ''):
        self._dataset = dataset
        self._path = path
        self._suffix = suffix

    @property
    def path(self):
        return self._path

    def set_ready(self) -> None:
        set_path_ready(self.path)

    def is_outdated(self) -> None:
        return is_path_outdated(self.path)

    def file_iterator_from_file(self):
        for file in self._dataset.get_all_files():
            yield os.path.join(self.path, f'{file}{self._suffix}')

    def get_new_file_name(self, file_path: str, new_subdataset: 'SubDataset') -> str:
        rel_path = os.path.relpath(file_path, self.path)
        if rel_path == '.': # this check is needed and the result is true for cases when only one file is being preprocessed
            rel_path = os.path.basename(file_path)
        return os.path.join(new_subdataset.path, (rel_path[:-len(self._suffix)] if len(self._suffix) else rel_path) + new_subdataset._suffix)

    def ready(self) -> bool:
        return is_path_ready(self.path)

    def archive(self) -> None:
        modif_file = _get_last_modif_file_path_for_dir(self.path)
        timestamp = get_timestamp(self.path)
        if not os.path.exists(DEFAULT_PREP_DATASETS_DIR):
            os.makedirs(DEFAULT_PREP_DATASETS_DIR)
        os.rename(self.path, os.path.join(DEFAULT_PREP_DATASETS_DIR, f'{os.path.basename(self.path)}.{ARCHIVED_EXT}.{timestamp}'))
        os.rename(modif_file, os.path.join(DEFAULT_PREP_DATASETS_DIR, f'{os.path.basename(modif_file)}.{ARCHIVED_EXT}.{timestamp}'))

    def __eq__(self, o: object) -> bool:
        if isinstance(o, SubDataset):
            return self._dataset == o._dataset and self._path == o._path and self._suffix == o._suffix
        return False

    def __str__(self) -> str:
        return self._path


class Dataset(object):
    """
    Abstaction that incapsulates the location of the dataset in the file system and assures integrity of intermediate
    representation of data when the data preprocessing operation consists of multiple steps.
    """
    def __init__(self, path: str, prep_config: PrepConfig, extension: Optional[str],
                 bpe_config: Optional[BpeConfig],
                 overridden_path_to_prep_dataset):
        self._path = path
        self._prep_config = prep_config
        self._extension = extension
        self._bpe_config = bpe_config
        self._dataset_last_modified = get_timestamp(path)

        self._original = SubDataset(self, self.path)
        self._parsed = SubDataset(self, self._get_path_to_parsed_dataset(), suffix=PARSED_EXTENSION)
        self._preprocessed = SubDataset(self, self._get_path_to_prep_dataset(overridden_path_to_prep_dataset), suffix=PREPROCESSED_EXTENSION)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Dataset):
            return self._path == o._path and \
                   self._prep_config == o._prep_config and \
                   self._extension == o._extension and \
                   self._bpe_config == o._bpe_config and \
                   self._dataset_last_modified == o._dataset_last_modified and \
                   self._original == o._original and \
                   self._parsed == o._parsed and \
                   self._preprocessed == o._preprocessed
        return False

    #####################################################


    @classmethod
    def create(cls: Type['Dataset'], path_to_dataset: str, prep_config: PrepConfig, extension: Optional[str],
               bpe_config: Optional[BpeConfig] = None,
               overriden_path_to_prep_dataset: Optional[str] = None) -> 'Dataset':
        if not os.path.exists(path_to_dataset):
            raise ValueError(f"Path {path_to_dataset} does not exist")

        dataset = cls(path_to_dataset, prep_config, extension, bpe_config, overriden_path_to_prep_dataset)

        if not os.path.exists(dataset.parsed.path):
            os.makedirs(dataset.parsed.path)

        if not os.path.exists(dataset.preprocessed.path):
            os.makedirs(dataset.preprocessed.path)

        if not os.path.exists(DEFAULT_FILE_LIST_DIR):
            os.makedirs(DEFAULT_FILE_LIST_DIR)

        return dataset

    #####################################################

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def dataset_last_modified(self) -> str:
        return self._dataset_last_modified

    @property
    def prep_config(self) -> PrepConfig:
        return self._prep_config

    @property
    def get_dataset_dir_name(self) -> str:
        return f'{self.name}_{self.dataset_last_modified}'

    @property
    def parsed(self) -> SubDataset:
        return self._parsed

    @property
    def preprocessed(self) -> SubDataset:
        return self._preprocessed

    def _get_path_to_parsed_dataset(self) -> str:
        return os.path.join(DEFAULT_PARSED_DATASETS_DIR, self.get_dataset_dir_name)

    def _get_path_to_prep_dataset(self, overriden_path_to_prep_dataset: Optional[str]) -> str:
        if overriden_path_to_prep_dataset:
            return overriden_path_to_prep_dataset

        if overriden_path_to_prep_dataset == '':
            return f'{self.path}_{self.dataset_last_modified}_preprocessed_{self.prep_config}'

        return os.path.join(DEFAULT_PREP_DATASETS_DIR, self.get_dataset_dir_name)

    @property
    def original(self) -> SubDataset:
        return self._original

    @property
    def bpe_path(self) -> str:
        return os.path.join(USER_BPE_DIR, self.name)

    @property
    def path_to_bpe_vocab_file(self) -> str:
        return os.path.join(self.bpe_path, BPE_VOCAB_FILE_NAME)

    @property
    def path_to_file_list(self) -> str:
        return os.path.join(DEFAULT_FILE_LIST_DIR, f'{self.get_dataset_dir_name}.{FILE_LIST_FILENAME}')

    @property
    def path_to_dir_list(self) -> str:
        return os.path.join(DEFAULT_FILE_LIST_DIR, f'{self.get_dataset_dir_name}.{DIR_LIST_FILENAME}')

    def get_all_files(self):
        self.list_and_save_dir_contents_if_necessary()

        with open(self.path_to_file_list) as f:
            for line in f:
                yield line.rstrip('\n')

    def get_all_dirs(self):
        self.list_and_save_dir_contents_if_necessary()

        with open(self.path_to_dir_list) as f:
            for line in f:
                yield line.rstrip('\n')

    ###################################

    def to_summary(self) -> str:
        return f"Original dataset: {self.original.path}\nParsed dataset (internal): {self.parsed.path}\nPreprocessed dataset: {self.preprocessed.path}"

    def __str__(self) -> str:
        return self.to_summary()

    def list_and_save_dir_contents_if_necessary(self):
        if not is_path_ready(DEFAULT_FILE_LIST_DIR) or is_path_outdated(DEFAULT_FILE_LIST_DIR):
            save_all_files(self.original.path, self.path_to_file_list, self.path_to_dir_list, self._extension)
            set_path_ready(DEFAULT_FILE_LIST_DIR)


def _get_last_modif_file_path_for_dir(path: str) -> str:
    dirname, filename = os.path.split(path)
    return os.path.join(dirname, f'.{filename}.lastmodif')


def get_dir_last_modification(path: str, limit: int = LIMIT_FILES_ON_LAST_MODIFICATION_CHECK) -> datetime:

    def walk_path(path):
        counter = 0
        if os.path.isfile(path) or len(os.listdir(path)) == 0:
            yield os.path.getmtime(path)
        else:
            for root, dirs, files in os.walk(path):
                for dir in dirs:
                    if counter >= limit:
                        return
                    counter += 1
                    yield os.path.getmtime(os.path.join(root, dir))
                for file in files:
                    if counter >= limit:
                        return
                    counter += 1
                    yield os.path.getmtime(os.path.join(root, file))

    mtime = max(walk_path(path))
    return datetime.fromtimestamp(mtime)


def save_all_files(path: str, save_to_files: str, save_to_dirs: str, extension: str) -> None:
    with open(save_to_dirs, 'w') as d, open(save_to_files, 'w') as f:
        counter = 0
        if os.path.isfile(path):
            f.write(f'{path}\n')
        else:
            for root, dirs, files in os.walk(path):
                for dir in dirs:
                    d.write(f'{os.path.join(os.path.relpath(root, path), dir)}\n')
                for file in files:
                    if not extension or file.endswith(f".{extension}"):
                        counter += 1
                        print(f'Files/dirs scanned: {counter}', end='\r')
                        f.write(f'{os.path.join(os.path.relpath(root, path), file)}\n')
    print()


def get_timestamp(path: str) -> str:
    last_modif_time = get_dir_last_modification(path)
    return last_modif_time.strftime("%y-%m-%dT%H-%M-%S")


def set_path_ready(path: str) -> None:
    modif_file = _get_last_modif_file_path_for_dir(path)
    with open(modif_file, 'w') as f:
        f.write(get_timestamp(path))


def is_path_outdated(path: str) -> bool:
    modif_file = _get_last_modif_file_path_for_dir(path)
    if not os.path.exists(modif_file):
        raise FileNotFoundError()
    with open(modif_file) as f:
        expected_timestamp = f.read()
        actual_timestamp = get_timestamp(path)
        return (expected_timestamp != actual_timestamp)


def is_path_ready(path: str) -> bool:
    if not os.path.exists(path):
        return False
    modif_file = _get_last_modif_file_path_for_dir(path)
    return os.path.exists(modif_file)
