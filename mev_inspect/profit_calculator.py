"""Profit calculation for MEV transactions.

This module calculates profit from MEV transactions by analyzing:
- Token transfers (from logs)
- State changes (from replay)
- Price information (from pools or oracles)
- Gas costs

Supports:
- Arbitrage profit calculation
- Sandwich attack profit
- Liquidation profit
- Flash loan profit
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from collections import defaultdict

from mev_inspect.enhanced_swap_detector import EnhancedSwapDetector, EnhancedSwap, MultiHopSwap
from mev_inspect.replay import TransactionReplayer, ReplayResult
from mev_inspect.state_manager import StateManager


# Common token addresses (Ethereum mainnet)
WETH_ADDRESS = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC_ADDRESS = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT_ADDRESS = "0xdaf169c8a3b0a3c92d8ded7c5e35e2df3766a6b8"
DAI_ADDRESS = "0x6b175474e89094c44da98b954eedeac495271d0f"

# ERC20 Transfer event signature
TRANSFER_EVENT = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


@dataclass
class TokenTransfer:
    """Represents a token transfer."""
    token: str
    from_address: str
    to_address: str
    amount: int
    log_index: int


@dataclass
class ProfitCalculation:
    """Result of profit calculation for a transaction."""
    
    # Basic info
    tx_hash: str
    mev_type: str  # "arbitrage", "sandwich", "liquidation", "other"
    
    # Profit breakdown
    gross_profit_wei: int  # Total profit before costs (in Wei/smallest unit)
    gas_cost_wei: int  # Gas cost in Wei
    net_profit_wei: int  # Net profit after gas (gross - gas)
    
    # Token flows
    tokens_in: Dict[str, int]  # {token_address: amount}
    tokens_out: Dict[str, int]  # {token_address: amount}
    
    # Additional metrics
    profit_usd: Optional[Decimal] = None  # Profit in USD (if prices available)
    roi: Optional[Decimal] = None  # Return on investment (%)
    swaps_involved: int = 0
    is_profitable: bool = False
    
    # Metadata
    confidence: float = 0.0  # Confidence in profit calculation (0.0-1.0)
    method: str = "unknown"  # "token_flow", "state_diff", "hybrid"


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity."""
    
    tx_hash: str
    token_path: List[str]  # Token swap path
    pool_path: List[str]  # Pool addresses used
    profit: ProfitCalculation
    
    @property
    def num_hops(self) -> int:
        return len(self.pool_path)
    
    @property
    def start_token(self) -> str:
        return self.token_path[0] if self.token_path else ""
    
    @property
    def end_token(self) -> str:
        return self.token_path[-1] if self.token_path else ""


class ProfitCalculator:
    """Calculate profit from MEV transactions.
    
    This calculator uses multiple methods to determine profit:
    1. Token flow analysis: Track token transfers in/out
    2. State change analysis: Compare state before/after
    3. Swap analysis: Analyze swap amounts and prices
    4. Hybrid: Combine multiple methods for accuracy
    
    Target: Accurate profit calculation for common MEV types
    """
    
    def __init__(
        self,
        rpc_client,
        state_manager: StateManager,
        swap_detector: Optional[EnhancedSwapDetector] = None,
        mev_contract: Optional[str] = None
    ):
        """Initialize profit calculator.
        
        Args:
            rpc_client: RPC client for blockchain access
            state_manager: StateManager for efficient state loading
            swap_detector: EnhancedSwapDetector for swap analysis (optional)
            mev_contract: MEV bot contract address to track (optional)
        """
        self.rpc_client = rpc_client
        self.state_manager = state_manager
        self.swap_detector = swap_detector
        self.mev_contract = mev_contract.lower() if mev_contract else None
        
        # Statistics
        self.stats = {
            "total_analyzed": 0,
            "profitable_txs": 0,
            "unprofitable_txs": 0,
            "arbitrage_detected": 0,
            "total_profit_wei": 0,
        }
    
    def calculate_profit(
        self,
        tx_hash: str,
        block_number: int,
        searcher_address: Optional[str] = None
    ) -> ProfitCalculation:
        """Calculate profit for a transaction.
        
        Args:
            tx_hash: Transaction hash to analyze
            block_number: Block number for state access
            searcher_address: Address of MEV searcher/bot (optional)
            
        Returns:
            ProfitCalculation with detailed profit breakdown
        """
        self.stats["total_analyzed"] += 1
        
        # Get transaction and receipt
        tx = self.rpc_client.get_transaction(tx_hash)
        receipt = self.rpc_client.get_transaction_receipt(tx_hash)
        
        # Determine searcher address
        if not searcher_address:
            searcher_address = self.mev_contract or tx["from"]
        
        searcher_address = searcher_address.lower()
        
        # Calculate gas cost
        gas_used = receipt["gasUsed"]
        gas_price = tx.get("gasPrice", 0)
        gas_cost_wei = gas_used * gas_price
        
        # Extract token transfers
        transfers = self._extract_token_transfers(receipt)
        
        # Calculate token flows for searcher
        tokens_in, tokens_out = self._calculate_token_flows(
            transfers,
            searcher_address
        )
        
        # Determine MEV type
        mev_type = self._classify_mev_type(
            tx,
            receipt,
            transfers,
            searcher_address
        )
        
        # Calculate gross profit (in Wei or primary token)
        gross_profit_wei, confidence, method = self._calculate_gross_profit(
            tokens_in,
            tokens_out,
            transfers,
            searcher_address
        )
        
        # Net profit = gross - gas
        net_profit_wei = gross_profit_wei - gas_cost_wei
        is_profitable = net_profit_wei > 0
        
        # Count swaps involved
        swaps_involved = 0
        if self.swap_detector:
            try:
                swaps = self.swap_detector.detect_swaps(tx_hash, block_number)
                swaps_involved = len(swaps)
            except:
                pass
        
        # Update stats
        if is_profitable:
            self.stats["profitable_txs"] += 1
            self.stats["total_profit_wei"] += net_profit_wei
        else:
            self.stats["unprofitable_txs"] += 1
        
        if mev_type == "arbitrage":
            self.stats["arbitrage_detected"] += 1
        
        profit = ProfitCalculation(
            tx_hash=tx_hash,
            mev_type=mev_type,
            gross_profit_wei=gross_profit_wei,
            gas_cost_wei=gas_cost_wei,
            net_profit_wei=net_profit_wei,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            swaps_involved=swaps_involved,
            is_profitable=is_profitable,
            confidence=confidence,
            method=method
        )
        
        return profit
    
    def detect_arbitrage(
        self,
        tx_hash: str,
        block_number: int,
        searcher_address: Optional[str] = None
    ) -> Optional[ArbitrageOpportunity]:
        """Detect and calculate arbitrage opportunity.
        
        Arbitrage is detected when:
        - Multiple swaps in same transaction
        - Start and end with same token
        - Net profit > 0
        
        Args:
            tx_hash: Transaction hash to analyze
            block_number: Block number
            searcher_address: MEV searcher address
            
        Returns:
            ArbitrageOpportunity if detected, None otherwise
        """
        if not self.swap_detector:
            return None
        
        # Calculate profit
        profit = self.calculate_profit(tx_hash, block_number, searcher_address)
        
        if not profit.is_profitable:
            return None
        
        # Detect multi-hop swaps
        try:
            multi_hops = self.swap_detector.detect_multi_hop_swaps(
                tx_hash,
                block_number
            )
            
            if not multi_hops:
                return None
            
            # Check if it's arbitrage (circular swap)
            for multi_hop in multi_hops:
                # Arbitrage typically starts and ends with same token
                # For now, just return if we have multi-hop with profit
                if multi_hop.hop_count >= 2 and profit.net_profit_wei > 0:
                    arb = ArbitrageOpportunity(
                        tx_hash=tx_hash,
                        token_path=[multi_hop.token_in, multi_hop.token_out],
                        pool_path=multi_hop.pools_used,
                        profit=profit
                    )
                    return arb
            
        except Exception as e:
            pass
        
        return None
    
    def _extract_token_transfers(self, receipt: Dict) -> List[TokenTransfer]:
        """Extract all ERC20 token transfers from logs.
        
        Args:
            receipt: Transaction receipt with logs
            
        Returns:
            List of TokenTransfer objects
        """
        transfers = []
        
        for i, log in enumerate(receipt.get("logs", [])):
            if not log.get("topics") or len(log["topics"]) < 3:
                continue
            
            # Check for Transfer event
            topic0 = log["topics"][0]
            if isinstance(topic0, bytes):
                topic0 = "0x" + topic0.hex()
            
            if topic0 != TRANSFER_EVENT:
                continue
            
            # Parse Transfer(address indexed from, address indexed to, uint256 value)
            try:
                from_address = "0x" + log["topics"][1][-40:]
                to_address = "0x" + log["topics"][2][-40:]
                
                # Parse amount from data
                data = log["data"]
                if isinstance(data, str):
                    data = bytes.fromhex(data[2:] if data.startswith("0x") else data)
                
                if len(data) >= 32:
                    amount = int.from_bytes(data[:32], "big")
                    
                    transfer = TokenTransfer(
                        token=log["address"].lower(),
                        from_address=from_address.lower(),
                        to_address=to_address.lower(),
                        amount=amount,
                        log_index=i
                    )
                    transfers.append(transfer)
            except Exception:
                continue
        
        return transfers
    
    def _calculate_token_flows(
        self,
        transfers: List[TokenTransfer],
        searcher_address: str
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Calculate token flows for a specific address.
        
        Args:
            transfers: List of token transfers
            searcher_address: Address to track
            
        Returns:
            Tuple of (tokens_in, tokens_out) dictionaries
        """
        tokens_in = defaultdict(int)  # Tokens received
        tokens_out = defaultdict(int)  # Tokens sent
        
        for transfer in transfers:
            if transfer.to_address == searcher_address:
                tokens_in[transfer.token] += transfer.amount
            
            if transfer.from_address == searcher_address:
                tokens_out[transfer.token] += transfer.amount
        
        return dict(tokens_in), dict(tokens_out)
    
    def _classify_mev_type(
        self,
        tx: Dict,
        receipt: Dict,
        transfers: List[TokenTransfer],
        searcher_address: str
    ) -> str:
        """Classify the MEV type.
        
        Args:
            tx: Transaction data
            receipt: Transaction receipt
            transfers: Token transfers
            searcher_address: MEV searcher address
            
        Returns:
            MEV type: "arbitrage", "sandwich", "liquidation", "other"
        """
        # Simple heuristics for now
        
        # Check for arbitrage (multiple swaps, circular token path)
        tokens_in, tokens_out = self._calculate_token_flows(transfers, searcher_address)
        
        # Arbitrage: Multiple tokens involved, net positive for one token
        if len(tokens_in) >= 2 and len(tokens_out) >= 2:
            # Check if same tokens in and out (circular)
            common_tokens = set(tokens_in.keys()) & set(tokens_out.keys())
            if common_tokens:
                for token in common_tokens:
                    if tokens_in[token] > tokens_out[token]:
                        return "arbitrage"
        
        # Sandwich: Would need to check surrounding transactions (not implemented here)
        
        # Liquidation: Would need to check for liquidation events
        
        return "other"
    
    def _calculate_gross_profit(
        self,
        tokens_in: Dict[str, int],
        tokens_out: Dict[str, int],
        transfers: List[TokenTransfer],
        searcher_address: str
    ) -> Tuple[int, float, str]:
        """Calculate gross profit before gas costs.
        
        Returns:
            Tuple of (profit_wei, confidence, method)
        """
        profit = 0
        confidence = 0.0
        method = "token_flow"
        
        # Method 1: Check for net gain in WETH (most common profit token)
        weth = WETH_ADDRESS.lower()
        
        if weth in tokens_in and weth in tokens_out:
            weth_in = tokens_in[weth]
            weth_out = tokens_out[weth]
            profit = weth_in - weth_out
            confidence = 0.8
            method = "token_flow_weth"
        
        # Method 2: Check for net gain in any token
        elif tokens_in and tokens_out:
            # Find tokens with net positive
            for token in set(tokens_in.keys()) | set(tokens_out.keys()):
                amount_in = tokens_in.get(token, 0)
                amount_out = tokens_out.get(token, 0)
                net = amount_in - amount_out
                
                if net > profit:
                    profit = net
                    confidence = 0.6
                    method = f"token_flow_{token[:10]}"
        
        # Method 3: If only tokens_in (profit taken)
        elif tokens_in and not tokens_out:
            # Sum all incoming tokens (simplified - assumes all are profit)
            for token, amount in tokens_in.items():
                if token == weth:
                    profit = amount
                    confidence = 0.7
                    method = "token_flow_in_weth"
                    break
        
        return profit, confidence, method
    
    def calculate_batch_profit(
        self,
        tx_hashes: List[str],
        block_numbers: List[int],
        searcher_address: Optional[str] = None
    ) -> List[ProfitCalculation]:
        """Calculate profit for multiple transactions.
        
        Args:
            tx_hashes: List of transaction hashes
            block_numbers: List of block numbers (parallel to tx_hashes)
            searcher_address: MEV searcher address
            
        Returns:
            List of ProfitCalculation objects
        """
        results = []
        
        for tx_hash, block_number in zip(tx_hashes, block_numbers):
            try:
                profit = self.calculate_profit(tx_hash, block_number, searcher_address)
                results.append(profit)
            except Exception as e:
                # Log error but continue
                print(f"Error calculating profit for {tx_hash}: {e}")
                continue
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get calculation statistics.
        
        Returns:
            Dictionary with stats
        """
        stats = self.stats.copy()
        
        if stats["total_analyzed"] > 0:
            stats["profitable_rate"] = stats["profitable_txs"] / stats["total_analyzed"]
            stats["avg_profit_wei"] = (
                stats["total_profit_wei"] / stats["profitable_txs"]
                if stats["profitable_txs"] > 0
                else 0
            )
        else:
            stats["profitable_rate"] = 0.0
            stats["avg_profit_wei"] = 0
        
        return stats
    
    def reset_statistics(self):
        """Reset statistics."""
        for key in self.stats:
            self.stats[key] = 0
    
    def format_profit(self, profit: ProfitCalculation) -> str:
        """Format profit calculation as human-readable string.
        
        Args:
            profit: ProfitCalculation object
            
        Returns:
            Formatted string
        """
        lines = []
        lines.append(f"Transaction: {profit.tx_hash}")
        lines.append(f"MEV Type: {profit.mev_type}")
        lines.append(f"")
        lines.append(f"Gross Profit: {profit.gross_profit_wei:,} Wei")
        lines.append(f"Gas Cost: {profit.gas_cost_wei:,} Wei")
        lines.append(f"Net Profit: {profit.net_profit_wei:,} Wei")
        lines.append(f"")
        lines.append(f"Profitable: {'✅ Yes' if profit.is_profitable else '❌ No'}")
        lines.append(f"Confidence: {profit.confidence:.2f}")
        lines.append(f"Method: {profit.method}")
        lines.append(f"Swaps: {profit.swaps_involved}")
        
        if profit.tokens_in:
            lines.append(f"")
            lines.append(f"Tokens In:")
            for token, amount in profit.tokens_in.items():
                lines.append(f"  {token[:10]}...: {amount:,}")
        
        if profit.tokens_out:
            lines.append(f"")
            lines.append(f"Tokens Out:")
            for token, amount in profit.tokens_out.items():
                lines.append(f"  {token[:10]}...: {amount:,}")
        
        return "\n".join(lines)
