"""Arbitrage detection algorithm."""

from typing import Dict, List, Optional, Set, Tuple

from mev_inspect.dex import (
    BalancerParser,
    CurveParser,
    SushiswapParser,
    UniswapV2Parser,
    UniswapV3Parser,
)
from mev_inspect.models import Arbitrage, Swap
from mev_inspect.simulator import StateSimulator


class ArbitrageDetector:
    """Detects arbitrage opportunities."""

    def __init__(self, rpc_client, simulator: StateSimulator):
        """Initialize arbitrage detector."""
        self.rpc_client = rpc_client
        self.simulator = simulator
        self.dex_parsers = {
            "uniswap_v2": UniswapV2Parser(rpc_client),
            "uniswap_v3": UniswapV3Parser(rpc_client),
            "sushiswap": SushiswapParser(rpc_client),
            "balancer": BalancerParser(rpc_client),
            "curve": CurveParser(rpc_client),
        }

    def detect_historical(
        self, swaps: List[Swap], block_number: int
    ) -> List[Arbitrage]:
        """Detect arbitrage that actually occurred in the block."""
        arbitrages = []
        

        # Group swaps by transaction
        swaps_by_tx: Dict[str, List[Swap]] = {}
        for swap in swaps:
            if swap.tx_hash not in swaps_by_tx:
                swaps_by_tx[swap.tx_hash] = []
            swaps_by_tx[swap.tx_hash].append(swap)
        
        
        # Check each transaction for arbitrage patterns
        for tx_hash, tx_swaps in swaps_by_tx.items():
            # Check all possible paths within this transaction
            if len(tx_swaps) >= 2:
                # Try all combinations of swaps that form a cycle
                for i in range(len(tx_swaps)):
                    for j in range(i + 1, len(tx_swaps) + 1):
                        path = tx_swaps[i:j]
                        if len(path) >= 2:
                            arb = self._check_arbitrage_path(path, tx_hash, block_number)
                            if arb:
                                arbitrages.append(arb)
                                # Found arbitrage, move to next transaction
                                break
                    if any(a.tx_hash == tx_hash for a in arbitrages):
                        break

        return arbitrages

    def detect_whatif(
        self,
        swaps: List[Swap],
        block_number: int,
        max_path_length: int = 3,
    ) -> List[Dict]:
        """Detect missed arbitrage opportunities (what-if scenarios)."""
        opportunities = []

        # Build graph of all pools and tokens
        pool_graph = self._build_pool_graph(swaps)

        # For each token pair, check if there's an arbitrage path
        tokens = set()
        for swap in swaps:
            tokens.add(swap.token_in)
            tokens.add(swap.token_out)

        # Check arbitrage opportunities between all token pairs
        token_list = list(tokens)
        for i, token_start in enumerate(token_list):
            for token_end in token_list[i + 1 :]:
                if token_start == token_end:
                    continue

                # Find arbitrage paths
                paths = self._find_arbitrage_paths(
                    token_start, token_end, pool_graph, max_path_length
                )

                for path in paths:
                    profit = self._calculate_path_profit(path, block_number)
                    if profit > 0:
                        opportunities.append(
                            {
                                "type": "arbitrage",
                                "token_start": token_start,
                                "token_end": token_end,
                                "path": path,
                                "profit_eth": profit,
                            }
                        )

        return opportunities

    def _check_arbitrage_path(
        self, swaps: List[Swap], tx_hash: str, block_number: int
    ) -> Optional[Arbitrage]:
        """Check if a sequence of swaps forms an arbitrage."""
        if len(swaps) < 2:
            return None

        # Check if swaps form a cycle (start and end with same token)
        first_swap = swaps[0]
        last_swap = swaps[-1]
        
        is_cycle = first_swap.token_in.lower() == last_swap.token_out.lower()

        # Check if we start and end with the same token (arbitrage cycle)
        if is_cycle:
            # Track amounts through the path
            current_token = first_swap.token_in
            
            # Verify the path is connected
            for i, swap in enumerate(swaps):
                if swap.token_in != current_token:
                    # Path is broken
                    return None
                current_token = swap.token_out
                
                # For intermediate swaps, we need to check if amounts match
                # This is simplified - in reality we'd need to account for slippage
                if i < len(swaps) - 1:
                    # Check if next swap's input token matches this swap's output
                    if swaps[i + 1].token_in != swap.token_out:
                        return None
            
            # Calculate profit: compare first input vs last output
            # For arbitrage cycles, we expect to get back more than we put in
            total_in = first_swap.amount_in
            total_out = last_swap.amount_out
            
            # Calculate profit ratio (independent of decimals)
            # If profit_ratio > 1.0, it means we got more out than we put in
            profit_ratio = total_out / total_in if total_in > 0 else 0
            
            
            # Consider it profitable if we get back at least 0.1% more (to account for gas)
            MIN_PROFIT_RATIO = 1.001
            
            if profit_ratio >= MIN_PROFIT_RATIO:
                # Estimate profit (simplified - assumes same decimals)
                profit_amount = total_out - total_in
                # Try to estimate ETH value (simplified)
                # If it's WETH, use 1e18, otherwise this is approximate
                profit_eth = profit_amount / 1e18  # Simplified

                return Arbitrage(
                    tx_hash=tx_hash,
                    block_number=block_number,
                    path=swaps,
                    profit_eth=profit_eth,
                    profit_token=first_swap.token_in,
                    profit_amount=profit_amount,
                )

        return None

    def _build_pool_graph(self, swaps: List[Swap]) -> Dict[str, List[Dict]]:
        """Build graph of pools and tokens for path finding."""
        graph: Dict[str, List[Dict]] = {}

        for swap in swaps:
            if swap.token_in not in graph:
                graph[swap.token_in] = []
            graph[swap.token_in].append(
                {
                    "token_out": swap.token_out,
                    "pool": swap.pool_address,
                    "dex": swap.dex,
                }
            )

        return graph

    def _find_arbitrage_paths(
        self,
        token_start: str,
        token_end: str,
        pool_graph: Dict[str, List[Dict]],
        max_length: int,
    ) -> List[List[Dict]]:
        """Find all paths from token_start to token_end."""
        paths = []

        def dfs(current: str, path: List[Dict], visited: Set[str]):
            if len(path) >= max_length:
                return

            if current == token_end and len(path) > 0:
                paths.append(path.copy())
                return

            if current not in pool_graph:
                return

            for edge in pool_graph[current]:
                next_token = edge["token_out"]
                if next_token not in visited:
                    visited.add(next_token)
                    path.append(edge)
                    dfs(next_token, path, visited)
                    path.pop()
                    visited.remove(next_token)

        dfs(token_start, [], {token_start})
        return paths

    def _calculate_path_profit(
        self, path: List[Dict], block_number: int
    ) -> float:
        """Calculate profit for an arbitrage path."""
        if not path:
            return 0.0

        # Start with 1 ETH worth of tokens (simplified)
        amount_in = 1e18
        current_token = path[0].get("token_in", "")

        for edge in path:
            pool = edge["pool"]
            dex = edge["dex"]
            token_out = edge["token_out"]

            parser = self.dex_parsers.get(dex)
            if not parser:
                return 0.0

            amount_out = parser.calculate_output(
                pool, current_token, token_out, int(amount_in), block_number
            )

            if amount_out == 0:
                return 0.0

            amount_in = amount_out
            current_token = token_out

        # If we end up with more than we started, it's profitable
        # This is simplified - would need to check if we return to original token
        return (amount_in - 1e18) / 1e18

