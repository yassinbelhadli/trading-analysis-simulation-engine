from typing import List, Dict
import xml.etree.ElementTree as ET
import pandas as pd


class XMLParser:

    def parse_forexfactory(self, xml_content: str) -> List[Dict]:

        root = ET.fromstring(xml_content)

        events = []

        for item in root.findall(".//event"):

            date = item.findtext("date")
            time = item.findtext("time")

            try:
                dt = pd.to_datetime(
                    f"{date} {time}",
                    errors="coerce",
                    utc=False
                )
            except Exception:
                dt = pd.NaT

            events.append({
                "time": dt,
                "currency": item.findtext("country"),
                "event": item.findtext("title"),
                "impact": (
                    item.findtext("impact") or ""
                ).upper(),
                "actual": item.findtext("actual"),
                "forecast": item.findtext("forecast"),
                "previous": item.findtext("previous"),
            })

        return events