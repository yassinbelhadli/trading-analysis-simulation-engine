from pathlib import Path
from typing import List, Dict, Union, Any
import json


class JSONParser:
    """
    Generic JSON parser.
    """

    def read(self, file_path: Union[str, Path]) -> Any:
        file_path = Path(file_path)

        if not file_path.exists():
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write(
        self,
        file_path: Union[str, Path],
        data: Any,
    ) -> None:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def read_list(self, file_path: Union[str, Path]) -> List[Dict]:
        data = self.read(file_path)

        if isinstance(data, list):
            return data

        return []