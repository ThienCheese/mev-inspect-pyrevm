"""Data models for MEV inspection."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


@dataclass
class Token:
    """Token information."""

    address: str
    symbol: str
    decimals: int


@dataclass
class Swap:
    """Swap transaction information."""

    tx_hash: str
    block_number: int
    dex: str  # uniswap_v2, uniswap_v3, balancer, sushiswap, curve
    pool_address: str
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    amount_in_eth: float = 0.0
    amount_out_eth: float = 0.0
    transaction_position: int = 0  # Position in block (for sandwich detection)
    from_address: str = ""  # Sender address (for sandwich detection)


@dataclass
class Arbitrage:
    """Arbitrage opportunity."""

    tx_hash: Optional[str]  # None for what-if scenarios
    block_number: int
    path: List[Swap]  # Sequence of swaps
    profit_eth: float
    profit_token: str
    profit_amount: int
    gas_cost_eth: float = 0.0
    net_profit_eth: float = 0.0


@dataclass
class Sandwich:
    """Sandwich attack."""

    frontrun_tx: Optional[str]  # None for what-if scenarios
    target_tx: str
    backrun_tx: Optional[str]  # None for what-if scenarios
    block_number: int
    profit_eth: float
    profit_token: str
    profit_amount: int
    victim_swap: Swap
    gas_cost_eth: float = 0.0
    net_profit_eth: float = 0.0
    frontrun_swap: Optional[Swap] = None
    backrun_swap: Optional[Swap] = None


@dataclass
class WhatIfOpportunity:
    """What-if MEV opportunity that was missed."""

    type: str  # "arbitrage" or "sandwich"
    block_number: int
    position: int  # Position in block where opportunity existed
    profit_eth: float
    profit_token: str
    profit_amount: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionInfo:
    """Transaction information for reporting."""

    hash: str
    from_address: str
    to_address: Optional[str]
    value: int
    gas_used: int
    gas_price: int
    status: int  # 1 = success, 0 = failed
    log_count: int
    swap_events_found: int
    parsed_swaps: int
    method_signature: Optional[str] = None
    error: Optional[str] = None
    event_signatures: List[str] = field(default_factory=list)  # All event signatures in logs


@dataclass
class InspectionResults:
    """Results from MEV inspection."""

    block_number: int
    historical_arbitrages: List[Arbitrage] = field(default_factory=list)
    historical_sandwiches: List[Sandwich] = field(default_factory=list)
    whatif_opportunities: List[WhatIfOpportunity] = field(default_factory=list)
    transactions: List[TransactionInfo] = field(default_factory=list)
    all_swaps: List[Swap] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Calculate summary statistics
        total_txs = len(self.transactions)
        successful_txs = sum(1 for tx in self.transactions if tx.status == 1)
        failed_txs = total_txs - successful_txs
        total_logs = sum(tx.log_count for tx in self.transactions)
        total_swap_events = sum(tx.swap_events_found for tx in self.transactions)
        total_parsed_swaps = len(self.all_swaps)
        
        return {
            "block_number": self.block_number,
            "summary": {
                "total_transactions": total_txs,
                "successful_transactions": successful_txs,
                "failed_transactions": failed_txs,
                "total_logs": total_logs,
                "swap_events_detected": total_swap_events,
                "swaps_parsed": total_parsed_swaps,
                "arbitrages_found": len(self.historical_arbitrages),
                "sandwiches_found": len(self.historical_sandwiches),
                "whatif_opportunities": len(self.whatif_opportunities),
            },
            "transactions": [
                {
                    "hash": tx.hash,
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "value": tx.value,
                    "value_eth": tx.value / 1e18,
                    "gas_used": tx.gas_used,
                    "gas_price": tx.gas_price,
                    "status": "success" if tx.status == 1 else "failed",
                    "log_count": tx.log_count,
                    "swap_events_found": tx.swap_events_found,
                    "parsed_swaps": tx.parsed_swaps,
                    "method_signature": tx.method_signature,
                    "error": tx.error,
                    "event_signatures": tx.event_signatures,
                }
                for tx in self.transactions
            ],
            "all_swaps": [
                {
                    "tx_hash": swap.tx_hash,
                    "block_number": swap.block_number,
                    "dex": swap.dex,
                    "pool_address": swap.pool_address,
                    "token_in": swap.token_in,
                    "token_out": swap.token_out,
                    "amount_in": swap.amount_in,
                    "amount_out": swap.amount_out,
                    "amount_in_eth": swap.amount_in_eth,
                    "amount_out_eth": swap.amount_out_eth,
                }
                for swap in self.all_swaps
            ],
            "historical_arbitrages": [
                {
                    "tx_hash": arb.tx_hash,
                    "block_number": arb.block_number,
                    "profit_eth": arb.profit_eth,
                    "profit_token": arb.profit_token,
                    "profit_amount": arb.profit_amount,
                    "gas_cost_eth": arb.gas_cost_eth,
                    "net_profit_eth": arb.net_profit_eth,
                    "path": [
                        {
                            "tx_hash": swap.tx_hash,
                            "dex": swap.dex,
                            "pool_address": swap.pool_address,
                            "token_in": swap.token_in,
                            "token_out": swap.token_out,
                            "amount_in": swap.amount_in,
                            "amount_out": swap.amount_out,
                        }
                        for swap in arb.path
                    ],
                }
                for arb in self.historical_arbitrages
            ],
            "historical_sandwiches": [
                {
                    "frontrun_tx": sand.frontrun_tx,
                    "target_tx": sand.target_tx,
                    "backrun_tx": sand.backrun_tx,
                    "block_number": sand.block_number,
                    "profit_eth": sand.profit_eth,
                    "profit_token": sand.profit_token,
                    "profit_amount": sand.profit_amount,
                    "gas_cost_eth": sand.gas_cost_eth,
                    "net_profit_eth": sand.net_profit_eth,
                }
                for sand in self.historical_sandwiches
            ],
            "whatif_opportunities": [
                {
                    "type": opp.type,
                    "block_number": opp.block_number,
                    "position": opp.position,
                    "profit_eth": opp.profit_eth,
                    "profit_token": opp.profit_token,
                    "profit_amount": opp.profit_amount,
                    "details": opp.details,
                }
                for opp in self.whatif_opportunities
            ],
        }

    def to_basic_dict(self) -> Dict[str, Any]:
        """Convert to basic dictionary with only MEV findings for JSON serialization."""
        # Calculate MEV summary
        total_arb_profit = sum(arb.profit_eth for arb in self.historical_arbitrages)
        total_sandwich_profit = sum(sand.profit_eth for sand in self.historical_sandwiches)
        total_mev_profit = total_arb_profit + total_sandwich_profit
        
        return {
            "block_number": self.block_number,
            "mev_summary": {
                "total_mev_profit_eth": round(total_mev_profit, 8),
                "arbitrages_found": len(self.historical_arbitrages),
                "arbitrage_profit_eth": round(total_arb_profit, 8),
                "sandwiches_found": len(self.historical_sandwiches),
                "sandwich_profit_eth": round(total_sandwich_profit, 8),
                "whatif_opportunities": len(self.whatif_opportunities),
            },
            "arbitrages": [
                {
                    "id": f"arb_{idx + 1}",
                    "transaction_hash": arb.tx_hash,
                    "profit_token_address": arb.profit_token,
                    "block_number": arb.block_number,
                    "start_amount": arb.path[0].amount_in if arb.path else 0,
                    "end_amount": arb.path[-1].amount_out if arb.path else 0,
                    "profit_amount": arb.profit_amount,
                    "profit_eth": round(arb.profit_eth, 8),
                    "gas_cost_eth": round(arb.gas_cost_eth, 8),
                    "net_profit_eth": round(arb.net_profit_eth, 8),
                    "swap_path": [
                        {
                            "dex": swap.dex,
                            "pool_address": swap.pool_address,
                            "token_in": swap.token_in,
                            "token_out": swap.token_out,
                            "amount_in": swap.amount_in,
                            "amount_out": swap.amount_out,
                        }
                        for swap in arb.path
                    ],
                }
                for idx, arb in enumerate(self.historical_arbitrages)
            ],
            "sandwiches": [
                {
                    "id": f"sand_{idx + 1}",
                    "frontrun_transaction_hash": sand.frontrun_tx,
                    "target_transaction_hash": sand.target_tx,
                    "backrun_transaction_hash": sand.backrun_tx,
                    "profit_token_address": sand.profit_token,
                    "block_number": sand.block_number,
                    "profit_amount": sand.profit_amount,
                    "profit_eth": round(sand.profit_eth, 8),
                    "gas_cost_eth": round(sand.gas_cost_eth, 8),
                    "net_profit_eth": round(sand.net_profit_eth, 8),
                    "victim_swap": {
                        "dex": sand.victim_swap.dex,
                        "pool_address": sand.victim_swap.pool_address,
                        "token_in": sand.victim_swap.token_in,
                        "token_out": sand.victim_swap.token_out,
                        "amount_in": sand.victim_swap.amount_in,
                        "amount_out": sand.victim_swap.amount_out,
                    } if sand.victim_swap else None,
                    "frontrun_swap": {
                        "dex": sand.frontrun_swap.dex,
                        "pool_address": sand.frontrun_swap.pool_address,
                        "token_in": sand.frontrun_swap.token_in,
                        "token_out": sand.frontrun_swap.token_out,
                        "amount_in": sand.frontrun_swap.amount_in,
                        "amount_out": sand.frontrun_swap.amount_out,
                    } if sand.frontrun_swap else None,
                    "backrun_swap": {
                        "dex": sand.backrun_swap.dex,
                        "pool_address": sand.backrun_swap.pool_address,
                        "token_in": sand.backrun_swap.token_in,
                        "token_out": sand.backrun_swap.token_out,
                        "amount_in": sand.backrun_swap.amount_in,
                        "amount_out": sand.backrun_swap.amount_out,
                    } if sand.backrun_swap else None,
                }
                for idx, sand in enumerate(self.historical_sandwiches)
            ],
            "whatif_opportunities": [
                {
                    "type": opp.type,
                    "block_number": opp.block_number,
                    "position": opp.position,
                    "profit_eth": round(opp.profit_eth, 8),
                    "profit_token": opp.profit_token,
                    "profit_amount": opp.profit_amount,
                    "details": opp.details,
                }
                for opp in self.whatif_opportunities
            ] if self.whatif_opportunities else [],
        }

