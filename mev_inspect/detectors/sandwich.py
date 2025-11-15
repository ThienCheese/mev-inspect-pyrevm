"""Sandwich attack detection algorithm."""

from typing import Dict, List, Optional

from mev_inspect.models import Sandwich, Swap


class SandwichDetector:
    """Detects sandwich attacks."""

    def __init__(self, rpc_client, simulator):
        """Initialize sandwich detector."""
        self.rpc_client = rpc_client
        self.simulator = simulator

    def detect_historical(
        self, swaps: List[Swap], block_number: int
    ) -> List[Sandwich]:
        """Detect sandwich attacks that actually occurred."""
        sandwiches = []

        # Group swaps by pool and token pair
        swaps_by_pool: Dict[str, List[Swap]] = {}
        for swap in swaps:
            key = f"{swap.pool_address}:{swap.token_in}:{swap.token_out}"
            if key not in swaps_by_pool:
                swaps_by_pool[key] = []
            swaps_by_pool[key].append(swap)

        # For each pool, look for sandwich patterns
        for key, pool_swaps in swaps_by_pool.items():
            if len(pool_swaps) < 3:
                continue

            # Look for pattern: frontrun -> victim -> backrun
            # All in same pool, same token pair
            for i in range(len(pool_swaps) - 2):
                frontrun = pool_swaps[i]
                victim = pool_swaps[i + 1]
                backrun = pool_swaps[i + 2]

                # Check if this looks like a sandwich
                if self._is_sandwich(frontrun, victim, backrun):
                    profit = self._calculate_sandwich_profit(frontrun, victim, backrun)
                    if profit > 0:
                        sandwiches.append(
                            Sandwich(
                                frontrun_tx=frontrun.tx_hash,
                                target_tx=victim.tx_hash,
                                backrun_tx=backrun.tx_hash,
                                block_number=block_number,
                                profit_eth=profit,
                                profit_token=victim.token_out,
                                profit_amount=0,  # Would calculate properly
                                victim_swap=victim,
                                frontrun_swap=frontrun,
                                backrun_swap=backrun,
                            )
                        )

        return sandwiches

    def detect_whatif(
        self, swaps: List[Swap], block_number: int
    ) -> List[Dict]:
        """Detect missed sandwich opportunities."""
        opportunities = []

        # For each swap, check if it could have been sandwiched
        for i, victim_swap in enumerate(swaps):
            # Check if we could frontrun and backrun this swap
            potential_profit = self._calculate_potential_sandwich_profit(
                victim_swap, swaps, i, block_number
            )

            if potential_profit > 0:
                opportunities.append(
                    {
                        "type": "sandwich",
                        "target_tx": victim_swap.tx_hash,
                        "position": i,
                        "profit_eth": potential_profit,
                        "profit_token": victim_swap.token_out,
                        "details": {
                            "pool": victim_swap.pool_address,
                            "token_in": victim_swap.token_in,
                            "token_out": victim_swap.token_out,
                        },
                    }
                )

        return opportunities

    def _is_sandwich(
        self, frontrun: Swap, victim: Swap, backrun: Swap
    ) -> bool:
        """Check if three swaps form a sandwich attack."""
        # All must be in same pool
        if (
            frontrun.pool_address != victim.pool_address
            or victim.pool_address != backrun.pool_address
        ):
            return False

        # Frontrun and backrun should be in opposite direction to victim
        # Victim: A -> B
        # Frontrun: A -> B (same direction, pushes price)
        # Backrun: B -> A (opposite direction, takes profit)

        # Simplified check
        if (
            frontrun.token_in == victim.token_in
            and backrun.token_in == victim.token_out
            and backrun.token_out == victim.token_in
        ):
            return True

        return False

    def _calculate_sandwich_profit(
        self, frontrun: Swap, victim: Swap, backrun: Swap
    ) -> float:
        """Calculate profit from sandwich attack."""
        # Simplified calculation
        # Frontrun pushes price, victim trades at worse price, backrun takes profit
        # Would need to simulate state changes properly
        return 0.0  # Placeholder

    def _calculate_potential_sandwich_profit(
        self, victim_swap: Swap, all_swaps: List[Swap], position: int, block_number: int
    ) -> float:
        """Calculate potential profit if victim swap was sandwiched."""
        # Simulate what would happen if we frontran and backran this swap
        # Would use simulator to get pool state before and after
        return 0.0  # Placeholder

