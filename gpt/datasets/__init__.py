"""Dataset abstraction."""

from .base import Dataset
from .hexagons import HexagonsDataset


def get_dataset(dataset_name: str = "hexagons", data_dir=None) -> Dataset:
    if dataset_name == "hexagons":
        return HexagonsDataset(data_dir)
    raise ValueError(f"Unknown dataset: {dataset_name}")


__all__ = ["Dataset", "HexagonsDataset", "get_dataset"]
