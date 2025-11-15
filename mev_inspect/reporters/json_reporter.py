"""JSON report generator."""

import json
from pathlib import Path
from typing import Any, Dict

from mev_inspect.models import InspectionResults


class JSONReporter:
    """Generate JSON reports."""

    @staticmethod
    def generate(results: InspectionResults, output_path: Path, mode: str = "full") -> None:
        """Generate JSON report.
        
        Args:
            results: InspectionResults object
            output_path: Path to save the report
            mode: Report mode - 'basic' (MEV findings only) or 'full' (all details)
        """
        with open(output_path, "w") as f:
            if mode == "basic":
                json.dump(results.to_basic_dict(), f, indent=2, default=str)
            else:
                json.dump(results.to_dict(), f, indent=2, default=str)

