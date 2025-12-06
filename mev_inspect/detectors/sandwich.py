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

        # Group swaps by pool (not token pair, to allow direction changes)
        swaps_by_pool: Dict[str, List[Swap]] = {}
        for swap in swaps:
            pool_key = swap.pool_address.lower()
            if pool_key not in swaps_by_pool:
                swaps_by_pool[pool_key] = []
            swaps_by_pool[pool_key].append(swap)

        # For each pool, look for sandwich patterns
        for pool_key, pool_swaps in swaps_by_pool.items():
            if len(pool_swaps) < 3:
                continue
            
            # Sort by transaction position to ensure correct order
            pool_swaps.sort(key=lambda s: s.transaction_position)

            # Look for pattern: frontrun -> victim(s) -> backrun
            # Same pool, but tokens can be in different directions
            for i in range(len(pool_swaps) - 2):
                frontrun = pool_swaps[i]
                
                # Check for victims and backrun after frontrun
                for j in range(i + 2, len(pool_swaps)):
                    backrun = pool_swaps[j]
                    
                    # Check if frontrun and backrun are from same address
                    if not frontrun.from_address or not backrun.from_address:
                        continue
                    if frontrun.from_address.lower() != backrun.from_address.lower():
                        continue
                    
                    # Check if this looks like a sandwich
                    # Collect all victims between frontrun and backrun
                    victims = pool_swaps[i + 1:j]
                    
                    if self._is_sandwich_pattern(frontrun, victims, backrun):
                        profit = self._calculate_sandwich_profit(frontrun, victims, backrun)
                        
                        # Create sandwich with first victim as target
                        if victims and profit > 0:
                            sandwiches.append(
                                Sandwich(
                                    frontrun_tx=frontrun.tx_hash,
                                    target_tx=victims[0].tx_hash,
                                    backrun_tx=backrun.tx_hash,
                                    block_number=block_number,
                                    profit_eth=profit,
                                    profit_token=backrun.token_out,
                                    profit_amount=int(profit * 1e18),
                                    victim_swap=victims[0],
                                    frontrun_swap=frontrun,
                                    backrun_swap=backrun,
                                )
                            )
                            # Only report first sandwich per frontrun
                            break

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

    def _is_sandwich_pattern(
        self, frontrun: Swap, victims: List[Swap], backrun: Swap
    ) -> bool:
        """Check if swaps form a sandwich attack pattern."""
        if not victims:
            return False
        
        # Pattern: 
        # Frontrun: A -> B (same direction as victims, pushes price up)
        # Victims: A -> B (buy at worse price)
        # Backrun: B -> A (opposite direction, sells for profit)
        
        # Check if frontrun and victims go same direction
        victim = victims[0]
        if (frontrun.token_in.lower() == victim.token_in.lower() and 
            frontrun.token_out.lower() == victim.token_out.lower()):
            # Check if backrun is opposite direction
            if (backrun.token_in.lower() == victim.token_out.lower() and 
                backrun.token_out.lower() == victim.token_in.lower()):
                return True
        
        return False

    def _calculate_sandwich_profit(
        self, frontrun: Swap, victims: List[Swap], backrun: Swap
    ) -> float:
        """Calculate profit from sandwich attack."""
        # Profit = backrun_out - frontrun_in (in same token)
        # If frontrun: 12 WETH -> 1114 BONE
        # If backrun: 1114 BONE -> 12.05 WETH
        # Profit = 12.05 - 12 = 0.05 WETH
        
        if frontrun.token_in.lower() == backrun.token_out.lower():
            # Both use same base token
            profit = backrun.amount_out - frontrun.amount_in
            # Convert to ETH
            return profit / 1e18 if profit > 0 else 0.0
        
        return 0.0

    def _calculate_potential_sandwich_profit(
        self, victim_swap: Swap, all_swaps: List[Swap], position: int, block_number: int
    ) -> float:
        """Calculate potential profit if victim swap was sandwiched."""
        # Simulate what would happen if we frontran and backran this swap
        # Would use simulator to get pool state before and after
        return 0.0  # Placeholder

