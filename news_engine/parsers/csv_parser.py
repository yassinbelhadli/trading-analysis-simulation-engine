from pathlib import Path
from typing import List, Dict, Union

import pandas as pd


class CSVParser:
    """
    Generic CSV parser.

    Responsibilities:
    - Read CSV files
    - Return List[Dict]
    - Save List[Dict] to CSV
    """

    def read(self, file_path: Union[str, Path]) -> List[Dict]:
        file_path = Path(file_path)

        if not file_path.exists():
            return []

        df = pd.read_csv(file_path)

        if df.empty:
            return []

        return df.to_dict("records")

    def to_dataframe(self, file_path: Union[str, Path]) -> pd.DataFrame:
        file_path = Path(file_path)

        if not file_path.exists():
            return pd.DataFrame()

        return pd.read_csv(file_path)

    def write(
        self,
        file_path: Union[str, Path],
        data: List[Dict],
    ) -> None:

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(data)

        df.to_csv(file_path, index=False)

    def append(
        self,
        file_path: Union[str, Path],
        row: Dict,
    ) -> None:

        file_path = Path(file_path)

        data = self.read(file_path)

        data.append(row)

        self.write(file_path, data)