"""This module runs different stages of preprocessing flow and makes sure not to rerun a stage if its results are already available.
"""
from typing import Optional

from dataprep import parse_projects, to_repr
from dataprep.bpepkg.bperegistry import CustomBpeConfig
from dataprep.dataset import Dataset, is_path_ready, is_path_outdated, archive_path
from dataprep.vocab import vocab


def run_parsing(dataset: Dataset) -> None:
    print("--- Parsing...")
    if not dataset.parsed.ready():
        parse_projects.run(dataset)
    elif dataset.parsed.is_outdated():
        dataset.parsed.archive()
        parse_projects.run(dataset)
    else:
        print("Parsed dataset is up-to-date.")


def run_until_preprocessing(dataset: Dataset, custom_bpe_config: Optional[CustomBpeConfig]=None) -> None:
    run_parsing(dataset)
    print("--- Preprocessing...")
    if not dataset.preprocessed.ready():
        to_repr.run(dataset, custom_bpe_config)
    elif dataset.preprocessed.is_outdated():
        dataset.preprocessed.archive()
        to_repr.run(dataset, custom_bpe_config)
    else:
        print(f"Dataset is already preprocessed and up-to-date.")


def run_until_vocab(dataset: Dataset) -> None:
    run_until_preprocessing(dataset)
    print("--- Computing vocab...")
    if not is_path_ready(dataset.path_to_bpe_vocab_file):
        vocab.run(dataset)
    elif is_path_outdated(dataset.path_to_bpe_vocab_file):
        archive_path(dataset.path_to_bpe_vocab_file)
        vocab.run(dataset)
    else:
        print("Vocabulary is already computed and up-to-date")