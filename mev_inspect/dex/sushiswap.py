"""Sushiswap DEX parser (uses UniswapV2 interface)."""

from typing import Dict, List, Optional

from mev_inspect.dex.uniswap_v2 import UniswapV2Parser
from mev_inspect.models import Swap


class SushiswapParser(UniswapV2Parser):
    """Parser for Sushiswap pools (compatible with UniswapV2)."""

    def parse_swap(
        self, tx_hash: str, tx_input: str, receipt_logs: List[Dict], block_number: int
    ) -> Optional[Swap]:
        """Parse swap from Sushiswap pool."""
        swap = super().parse_swap(tx_hash, tx_input, receipt_logs, block_number)
        if swap:
            swap.dex = "sushiswap"
        return swap

