from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseNewsProvider(ABC):

    @abstractmethod
    def fetch_events(self) -> List[Dict[str, Any]]:
        """
        Must return:

        [
            {
                "time": ...,
                "currency": ...,
                "event": ...,
                "impact": ...,
                "forecast": ...,
                "previous": ...,
                "actual": ...
            }
        ]
        """
        pass