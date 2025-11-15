"""Main MEV inspector that coordinates all components."""

from typing import List, Tuple

from mev_inspect.dex import (
    BalancerParser,
    CurveParser,
    SushiswapParser,
    UniswapV2Parser,
    UniswapV3Parser,
)
from mev_inspect.detectors import ArbitrageDetector, SandwichDetector
from mev_inspect.models import InspectionResults, Swap, TransactionInfo
from mev_inspect.rpc import RPCClient
from mev_inspect.simulator import StateSimulator


class MEVInspector:
    """Main MEV inspection engine."""

    def __init__(self, rpc_client: RPCClient):
        """Initialize MEV inspector."""
        self.rpc_client = rpc_client
        self.dex_parsers = {
            "uniswap_v2": UniswapV2Parser(rpc_client),
            "uniswap_v3": UniswapV3Parser(rpc_client),
            "sushiswap": SushiswapParser(rpc_client),
            "balancer": BalancerParser(rpc_client),
            "curve": CurveParser(rpc_client),
        }

    def inspect_block(
        self, block_number: int, what_if: bool = False
    ) -> InspectionResults:
        """Inspect a block for MEV opportunities."""
        # Get block data
        block = self.rpc_client.get_block(block_number, full_transactions=True)

        # Initialize simulator
        simulator = StateSimulator(self.rpc_client, block_number)

        # Initialize detectors
        arbitrage_detector = ArbitrageDetector(self.rpc_client, simulator)
        sandwich_detector = SandwichDetector(self.rpc_client, simulator)

        # Extract swaps from all transactions and collect transaction info
        swaps, transactions_info = self._extract_swaps_with_info(block_number, block["transactions"])

        # Detect historical MEV
        historical_arbitrages = arbitrage_detector.detect_historical(swaps, block_number)
        historical_sandwiches = sandwich_detector.detect_historical(swaps, block_number)

        # Detect what-if scenarios if requested
        whatif_opportunities = []
        if what_if:
            whatif_arbs = arbitrage_detector.detect_whatif(swaps, block_number)
            whatif_sands = sandwich_detector.detect_whatif(swaps, block_number)

            # Convert to WhatIfOpportunity objects
            from mev_inspect.models import WhatIfOpportunity

            for opp in whatif_arbs:
                whatif_opportunities.append(
                    WhatIfOpportunity(
                        type="arbitrage",
                        block_number=block_number,
                        position=0,  # Would track position
                        profit_eth=opp["profit_eth"],
                        profit_token=opp.get("token_start", ""),
                        profit_amount=0,
                        details=opp,
                    )
                )

            for opp in whatif_sands:
                whatif_opportunities.append(
                    WhatIfOpportunity(
                        type="sandwich",
                        block_number=block_number,
                        position=opp["position"],
                        profit_eth=opp["profit_eth"],
                        profit_token=opp["profit_token"],
                        profit_amount=0,
                        details=opp["details"],
                    )
                )

        return InspectionResults(
            block_number=block_number,
            historical_arbitrages=historical_arbitrages,
            historical_sandwiches=historical_sandwiches,
            whatif_opportunities=whatif_opportunities,
            transactions=transactions_info,
            all_swaps=swaps,
        )

    def _extract_swaps(
        self, block_number: int, transactions: List[dict]
    ) -> List[Swap]:
        """Extract all swaps from block transactions."""
        swaps, _ = self._extract_swaps_with_info(block_number, transactions)
        return swaps

    def _extract_swaps_with_info(
        self, block_number: int, transactions: List[dict]
    ) -> Tuple[List[Swap], List[TransactionInfo]]:
        """Extract all swaps from block transactions and collect transaction info."""
        swaps = []
        transactions_info = []
        
        # Known swap event signatures (without 0x prefix for comparison)
        swap_event_sigs = {
            "d78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",  # UniswapV2 Swap
            "c42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",  # UniswapV3 Swap
        }

        for tx in transactions:
            tx_hash = tx["hash"].hex() if hasattr(tx["hash"], "hex") else tx["hash"]
            tx_from = tx.get("from", "")
            tx_to = tx.get("to")
            tx_value = tx.get("value", 0)
            tx_input = tx.get("input", "0x")
            tx_gas_price = tx.get("gasPrice", 0)
            
            # Extract method signature if available
            method_sig = None
            if tx_input and len(tx_input) >= 10:
                if isinstance(tx_input, bytes):
                    method_sig = tx_input[:4].hex()
                elif isinstance(tx_input, str):
                    method_sig = tx_input[:10] if tx_input.startswith("0x") else "0x" + tx_input[:8]
                else:
                    method_sig = str(tx_input)[:10]

            # Get transaction receipt for logs
            try:
                receipt = self.rpc_client.get_transaction_receipt(tx_hash)
                status = receipt.get("status", 0)
                gas_used = receipt.get("gasUsed", 0)
                logs = receipt.get("logs", [])
                
                # Collect all event signatures and count swap events
                swap_events_found = 0
                event_signatures = []
                for log in logs:
                    if log.get("topics") and len(log["topics"]) > 0:
                        first_topic = log["topics"][0]
                        topic_hex = first_topic.hex() if hasattr(first_topic, "hex") else (
                            first_topic if isinstance(first_topic, str) else first_topic.hex()
                        )
                        # Normalize: remove 0x prefix and convert to lowercase
                        if topic_hex.startswith("0x"):
                            topic_hex_clean = topic_hex[2:].lower()
                        else:
                            topic_hex_clean = topic_hex.lower()
                        event_signatures.append(topic_hex_clean)
                        
                        # Check against known swap signatures (already normalized)
                        if topic_hex_clean in swap_event_sigs:
                            swap_events_found += 1
                
                # Try to parse swaps
                parsed_swaps_count = 0
                parsed_swap_keys = set()
                
                if status == 1 and logs:
                    for log in logs:
                        for parser_name, parser in self.dex_parsers.items():
                            try:
                                swap = parser.parse_swap(tx_hash, tx_input, [log], block_number)
                                if swap:
                                    swap_key = (swap.pool_address, swap.token_in, swap.token_out, swap.amount_in)
                                    if swap_key not in parsed_swap_keys:
                                        parsed_swap_keys.add(swap_key)
                                        swaps.append(swap)
                                        parsed_swaps_count += 1
                            except Exception:
                                continue
                
                # Create transaction info
                tx_info = TransactionInfo(
                    hash=tx_hash,
                    from_address=tx_from,
                    to_address=tx_to,
                    value=tx_value,
                    gas_used=gas_used,
                    gas_price=tx_gas_price,
                    status=status,
                    log_count=len(logs),
                    swap_events_found=swap_events_found,
                    parsed_swaps=parsed_swaps_count,
                    method_signature=method_sig,
                    event_signatures=event_signatures,
                )
                transactions_info.append(tx_info)
                
            except Exception as e:
                # Transaction might have failed or not exist
                tx_info = TransactionInfo(
                    hash=tx_hash,
                    from_address=tx_from,
                    to_address=tx_to,
                    value=tx_value,
                    gas_used=0,
                    gas_price=tx_gas_price,
                    status=0,
                    log_count=0,
                    swap_events_found=0,
                    parsed_swaps=0,
                    method_signature=method_sig,
                    error=str(e),
                    event_signatures=[],
                )
                transactions_info.append(tx_info)
                continue

        return swaps, transactions_info

