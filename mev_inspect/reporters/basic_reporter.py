"""Basic MEV report generator - shows only MEV findings."""

import json
from pathlib import Path
from typing import Any, Dict

from mev_inspect.models import InspectionResults


class BasicReporter:
    """Generate basic MEV reports showing only arbitrages and sandwiches."""

    @staticmethod
    def generate(results: InspectionResults, output_path: Path) -> None:
        """Generate basic JSON report with only MEV findings."""
        report_data = BasicReporter._format_basic_report(results)
        
        with open(output_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

    @staticmethod
    def _format_basic_report(results: InspectionResults) -> Dict[str, Any]:
        """Format results into a basic report structure."""
        
        # Calculate MEV summary
        total_arb_profit = sum(arb.profit_eth for arb in results.historical_arbitrages)
        total_sandwich_profit = sum(sand.profit_eth for sand in results.historical_sandwiches)
        total_mev_profit = total_arb_profit + total_sandwich_profit
        
        return {
            "block_number": results.block_number,
            "mev_summary": {
                "total_mev_profit_eth": round(total_mev_profit, 8),
                "arbitrages_found": len(results.historical_arbitrages),
                "arbitrage_profit_eth": round(total_arb_profit, 8),
                "sandwiches_found": len(results.historical_sandwiches),
                "sandwich_profit_eth": round(total_sandwich_profit, 8),
                "whatif_opportunities": len(results.whatif_opportunities),
            },
            "arbitrages": [
                {
                    "id": f"arb_{idx + 1}",
                    "transaction_hash": arb.tx_hash,
                    "created_at": None,  # Would need block timestamp
                    "account_address": None,  # Would need to extract from tx
                    "profit_token_address": arb.profit_token,
                    "block_number": arb.block_number,
                    "transaction_hash_full": arb.tx_hash,
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
                for idx, arb in enumerate(results.historical_arbitrages)
            ],
            "sandwiches": [
                {
                    "id": f"sand_{idx + 1}",
                    "frontrun_transaction_hash": sand.frontrun_tx,
                    "target_transaction_hash": sand.target_tx,
                    "backrun_transaction_hash": sand.backrun_tx,
                    "created_at": None,  # Would need block timestamp
                    "account_address": None,  # Would need to extract from tx
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
                for idx, sand in enumerate(results.historical_sandwiches)
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
                for opp in results.whatif_opportunities
            ] if results.whatif_opportunities else [],
        }
