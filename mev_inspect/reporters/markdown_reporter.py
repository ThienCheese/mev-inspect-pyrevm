"""Markdown report generator."""

from pathlib import Path

from mev_inspect.models import InspectionResults


class MarkdownReporter:
    """Generate Markdown reports."""

    @staticmethod
    def generate(results: InspectionResults, output_path: Path) -> None:
        """Generate Markdown report."""
        lines = [
            f"# MEV Inspection Report - Block {results.block_number}",
            "",
            "## Summary",
            "",
            f"- **Block Number**: {results.block_number}",
            f"- **Historical Arbitrages**: {len(results.historical_arbitrages)}",
            f"- **Historical Sandwiches**: {len(results.historical_sandwiches)}",
            f"- **What-If Opportunities**: {len(results.whatif_opportunities)}",
            "",
        ]

        # Historical Arbitrages
        if results.historical_arbitrages:
            lines.extend([
                "## Historical Arbitrages",
                "",
                "| TX Hash | Profit (ETH) | Profit Token | Path Length |",
                "|---------|--------------|--------------|-------------|",
            ])
            for arb in results.historical_arbitrages:
                lines.append(
                    f"| {arb.tx_hash or 'N/A'} | {arb.profit_eth:.6f} | {arb.profit_token} | {len(arb.path)} |"
                )
            lines.append("")

        # Historical Sandwiches
        if results.historical_sandwiches:
            lines.extend([
                "## Historical Sandwiches",
                "",
                "| Target TX | Frontrun TX | Backrun TX | Profit (ETH) |",
                "|-----------|-------------|------------|--------------|",
            ])
            for sand in results.historical_sandwiches:
                lines.append(
                    f"| {sand.target_tx} | {sand.frontrun_tx or 'N/A'} | {sand.backrun_tx or 'N/A'} | {sand.profit_eth:.6f} |"
                )
            lines.append("")

        # What-If Opportunities
        if results.whatif_opportunities:
            lines.extend([
                "## What-If Opportunities",
                "",
                "| Type | Position | Profit (ETH) | Profit Token |",
                "|------|----------|--------------|--------------|",
            ])
            for opp in results.whatif_opportunities:
                lines.append(
                    f"| {opp.type} | {opp.position} | {opp.profit_eth:.6f} | {opp.profit_token} |"
                )
            lines.append("")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

