"""Base class for DEX parsers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from mev_inspect.models import Swap


class DEXParser(ABC):
    """Base class for DEX contract parsers."""

    def __init__(self, rpc_client):
        """Initialize parser with RPC client."""
        self.rpc_client = rpc_client

    @abstractmethod
    def is_pool(self, address: str) -> bool:
        """Check if address is a pool of this DEX type."""
        pass

    @abstractmethod
    def parse_swap(
        self, tx_hash: str, tx_input: str, receipt_logs: List[Dict], block_number: int
    ) -> Optional[Swap]:
        """Parse a swap from transaction data."""
        pass

    @abstractmethod
    def get_reserves(self, pool_address: str, block_number: int) -> Dict[str, int]:
        """Get current reserves/state of pool."""
        pass

    @abstractmethod
    def calculate_output(
        self,
        pool_address: str,
        token_in: str,
        token_out: str,
        amount_in: int,
        block_number: int,
    ) -> int:
        """Calculate output amount for a given input."""
        pass

