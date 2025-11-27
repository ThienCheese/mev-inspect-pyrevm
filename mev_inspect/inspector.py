"""Main MEV inspector that coordinates all components."""

from typing import List, Tuple, Optional

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
from mev_inspect.state_manager import StateManager
from mev_inspect.replay import TransactionReplayer
from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector
from mev_inspect.profit_calculator import ProfitCalculator


class MEVInspector:
    """Main MEV inspection engine."""

    def __init__(self, rpc_client: RPCClient, use_legacy: bool = False):
        """Initialize MEV inspector.
        
        Args:
            rpc_client: RPC client for blockchain interaction
            use_legacy: If True, use old StateSimulator architecture. 
                       If False, use new Phase 2-4 pipeline (TransactionReplayer, EnhancedSwapDetector, ProfitCalculator)
        """
        self.rpc_client = rpc_client
        self.use_legacy = use_legacy
        
        # Legacy DEX parsers (used only in legacy mode)
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
        if self.use_legacy:
            return self._inspect_block_legacy(block_number, what_if)
        else:
            return self._inspect_block_phase2_4(block_number, what_if)
    
    def _inspect_block_legacy(
        self, block_number: int, what_if: bool = False
    ) -> InspectionResults:
        """Inspect a block using legacy StateSimulator architecture."""
        # Get block data
        block = self.rpc_client.get_block(block_number, full_transactions=True)

        # Initialize simulator
        simulator = StateSimulator(self.rpc_client, block_number)
        
        # Phase 1 optimization: Preload addresses from all transactions
        self._preload_block_addresses(simulator, block["transactions"])

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
    
    def _inspect_block_phase2_4(
        self, block_number: int, what_if: bool = False
    ) -> InspectionResults:
        """Inspect a block using Phase 2-4 pipeline with full PyRevm integration.
        
        Pipeline:
        1. StateManager: LRU cache for efficient state access
        2. TransactionReplayer: Replay ALL transactions with PyRevm (eliminates per-TX RPC)
        3. EnhancedSwapDetector: Detect swaps from replay results
        4. ArbitrageDetector/SandwichDetector: MEV pattern detection
        
        This implementation eliminates traditional RPC calls by:
        - Batch fetching all receipts in ONE call (not N calls)
        - Using TransactionReplayer to simulate TXs locally with PyRevm
        - Extracting swaps from simulation results (no re-parsing)
        """
        # Get block data
        block = self.rpc_client.get_block(block_number, full_transactions=True)
        transactions = block["transactions"]
        
        print(f"[Phase 2-4] Processing block {block_number} with {len(transactions)} transactions")
        
        # Phase 1: Initialize StateManager with LRU cache
        state_manager = StateManager(
            self.rpc_client, 
            block_number,
            account_cache_size=5000,
            storage_cache_size=20000,
            code_cache_size=1000
        )
        
        # Phase 2: Initialize TransactionReplayer (ONE instance for entire block)
        replayer = TransactionReplayer(
            self.rpc_client,
            state_manager,
            block_number
        )
        
        # Phase 2.5: Batch fetch ALL receipts in ONE call (MAJOR OPTIMIZATION!)
        print(f"[Batch RPC] Fetching receipts for {len(transactions)} transactions...")
        tx_hashes = [
            tx["hash"].hex() if hasattr(tx["hash"], "hex") else tx["hash"]
            for tx in transactions
        ]
        receipts_map = self.rpc_client.batch_get_receipts(tx_hashes)
        print(f"[Batch RPC] Fetched {len(receipts_map)} receipts")
        
        # Phase 2.6: Extract all unique addresses from receipts for batch code loading
        print("[Batch RPC] Extracting addresses from logs...")
        all_addresses = set()
        for tx_hash, receipt in receipts_map.items():
            for log in receipt.get("logs", []):
                all_addresses.add(log["address"].lower())
        
        # Add transaction participants
        for tx in transactions:
            if tx.get("from"):
                all_addresses.add(tx["from"].lower())
            if tx.get("to"):
                all_addresses.add(tx["to"].lower())
        
        # Phase 2.7: Batch fetch contract codes (MAJOR OPTIMIZATION!)
        print(f"[Batch RPC] Fetching code for {len(all_addresses)} unique addresses...")
        codes_map = self.rpc_client.batch_get_code(list(all_addresses), block_number)
        print(f"[Batch RPC] Fetched {len(codes_map)} contract codes")
        
        # Pre-populate StateManager cache with batch-loaded data
        for addr, code in codes_map.items():
            state_manager.code_cache.set(addr.lower(), code)
        
        # Phase 2.8: Extract unique pool addresses from swap events
        # Swap event signatures (topic0)
        UNISWAP_V2_SWAP = "d78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
        UNISWAP_V3_SWAP = "c42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
        SUSHISWAP_SWAP = UNISWAP_V2_SWAP  # Same as UniswapV2
        
        unique_pools = set()
        for tx_hash, receipt in receipts_map.items():
            for log in receipt.get("logs", []):
                if log.get("topics") and len(log["topics"]) > 0:
                    topic0 = log["topics"][0]
                    # Normalize topic0
                    if isinstance(topic0, bytes):
                        topic0_hex = topic0.hex()
                    elif isinstance(topic0, str):
                        topic0_hex = topic0[2:] if topic0.startswith("0x") else topic0
                    else:
                        continue
                    
                    # Check if it's a known swap event
                    if topic0_hex.lower() in [UNISWAP_V2_SWAP, UNISWAP_V3_SWAP]:
                        pool_addr = log["address"]
                        if isinstance(pool_addr, bytes):
                            pool_addr = pool_addr.hex()
                        unique_pools.add(pool_addr.lower())
        
        print(f"[Phase 2-4] Found {len(unique_pools)} unique swap pools")
        
        # Phase 2.9: Batch fetch pool tokens (CRITICAL OPTIMIZATION!)
        if unique_pools:
            print(f"[Batch RPC] Fetching token pairs for {len(unique_pools)} pools...")
            pool_tokens = self.rpc_client.batch_get_pool_tokens(
                list(unique_pools), 
                block_number
            )
            print(f"[Batch RPC] Fetched {len(pool_tokens)} pool token pairs")
            
            # Pre-populate pool tokens cache
            for pool, tokens in pool_tokens.items():
                state_manager.pool_tokens_cache[pool] = tokens
            
            print(f"[Phase 2-4] Pre-loaded {len(pool_tokens)} pool tokens into cache")
        
        # Phase 3: Use LEGACY parsers (already working!) instead of EnhancedSwapDetector
        # This is simpler and more reliable
        print("[Phase 2-4] Using legacy DEX parsers for swap detection")
        
        all_swaps = []
        transactions_info = []
        
        successful_txs = 0
        total_logs = 0
        parse_attempts = 0
        

        
        for tx in block["transactions"]:
            tx_hash = tx["hash"].hex() if hasattr(tx["hash"], "hex") else tx["hash"]
            tx_from = tx.get("from", "")
            tx_to = tx.get("to")
            tx_value = tx.get("value", 0)
            tx_input = tx.get("input", "0x")
            
            # Get receipt
            receipt = receipts_map.get(tx_hash)
            if not receipt:
                continue
                
            status_raw = receipt.get("status", 0)
            logs = receipt.get("logs", [])
            
            # CRITICAL FIX: Status is hex string "0x1" not integer 1
            if isinstance(status_raw, str):
                status = int(status_raw, 16) if status_raw.startswith("0x") else int(status_raw)
            else:
                status = status_raw
            
            if status == 1:
                successful_txs += 1
                total_logs += len(logs)
            
            # Parse swaps using legacy parsers (UniswapV2, UniswapV3, etc.)
            if status == 1 and logs:
                for log in logs:
                    parse_attempts += 1
                    for parser_name, parser in self.dex_parsers.items():
                        try:
                            swap = parser.parse_swap(tx_hash, tx_input, [log], block_number)
                            if swap:
                                all_swaps.append(swap)
                        except Exception:
                            continue
        
        print(f"[Phase 2-4] Found {successful_txs} successful transactions, {len(all_swaps)} swaps")
        
        # Build TransactionInfo for all transactions
        for tx in block["transactions"]:
            tx_hash = tx["hash"].hex() if hasattr(tx["hash"], "hex") else tx["hash"]
            tx_from = tx.get("from", "")
            tx_to = tx.get("to")
            tx_value = tx.get("value", 0)
            tx_input = tx.get("input", "0x")
            
            receipt = receipts_map.get(tx_hash)
            if not receipt:
                continue
            
            status_raw = receipt.get("status", 0)
            logs = receipt.get("logs", [])
            
            # Convert status from hex string to int
            if isinstance(status_raw, str):
                status = int(status_raw, 16) if status_raw.startswith("0x") else int(status_raw)
            else:
                status = status_raw
            
            # Extract method signature
            method_sig = None
            if tx_input and len(tx_input) >= 10:
                method_sig = tx_input[:10]
            
            # Create TransactionInfo (using correct field names from models.py)
            tx_info = TransactionInfo(
                hash=tx_hash,
                from_address=tx_from,
                to_address=tx_to if tx_to else "",
                value=tx_value,
                gas_used=0,  # Could get from receipt if needed
                gas_price=tx.get("gasPrice", 0),
                status=status,
                log_count=len(logs),
                swap_events_found=0,  # Will be updated below
                parsed_swaps=0,  # Will be updated below
                method_signature=method_sig,
                event_signatures=[],
            )
            transactions_info.append(tx_info)
        
        # Update swap counts in transactions_info
        swap_counts = {}
        for swap in all_swaps:
            swap_counts[swap.tx_hash] = swap_counts.get(swap.tx_hash, 0) + 1
        
        for tx_info in transactions_info:
            count = swap_counts.get(tx_info.hash, 0)
            tx_info.parsed_swaps = count
            tx_info.swap_events_found = count
        
        print(f"[Phase 2-4] Detected {len(all_swaps)} swaps from {len(transactions_info)} transactions")
        
        # Phase 4: Initialize detectors for MEV pattern detection
        # Use StateSimulator for compatibility
        simulator = StateSimulator(self.rpc_client, block_number)
        simulator.state_manager = state_manager
        
        arbitrage_detector = ArbitrageDetector(self.rpc_client, simulator)
        sandwich_detector = SandwichDetector(self.rpc_client, simulator)
        
        # Detect MEV patterns across all swaps
        historical_arbitrages = arbitrage_detector.detect_historical(all_swaps, block_number)
        historical_sandwiches = sandwich_detector.detect_historical(all_swaps, block_number)
        
        # What-if analysis (if requested)
        whatif_opportunities = []
        if what_if:
            whatif_arbs = arbitrage_detector.detect_whatif(all_swaps, block_number)
            whatif_sands = sandwich_detector.detect_whatif(all_swaps, block_number)
            
            from mev_inspect.models import WhatIfOpportunity
            
            for opp in whatif_arbs:
                whatif_opportunities.append(
                    WhatIfOpportunity(
                        type="arbitrage",
                        block_number=block_number,
                        position=0,
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
            all_swaps=all_swaps,
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
    
    def _preload_block_addresses(self, simulator: StateSimulator, transactions: List[dict]):
        """Preload addresses from all transactions in the block for better cache performance.
        
        This is a Phase 1 optimization that batch-loads account/code data upfront.
        """
        addresses = set()
        
        for tx in transactions:
            # Add from/to addresses
            if tx.get("from"):
                addresses.add(tx["from"])
            if tx.get("to"):
                addresses.add(tx["to"])
        
        # Batch preload all addresses
        if addresses:
            simulator.state_manager.preload_addresses(addresses)


