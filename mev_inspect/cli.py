"""CLI interface for MEV inspection."""

import json
import os
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from mev_inspect.inspector import MEVInspector
from mev_inspect.rpc import RPCClient

# Load environment variables
load_dotenv()

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """MEV Inspector for Ethereum using pyrevm."""
    pass


@main.command()
@click.argument("block_number", type=int)
@click.option(
    "--what-if",
    is_flag=True,
    help="Also analyze what-if scenarios for missed MEV opportunities",
)
@click.option(
    "--report",
    type=click.Path(),
    help="Path to save detailed report (JSON format)",
)
@click.option(
    "--report-mode",
    type=click.Choice(["basic", "full"], case_sensitive=False),
    default="full",
    help="Report mode: 'basic' (MEV findings only) or 'full' (all transaction details)",
)
@click.option(
    "--rpc-url",
    envvar="ALCHEMY_RPC_URL",
    help="Alchemy RPC URL (or set ALCHEMY_RPC_URL env var)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed debug information including all event signatures",
)
def block(block_number: int, what_if: bool, report: Optional[str], report_mode: str, rpc_url: Optional[str], verbose: bool):
    """Inspect a single block for MEV opportunities."""
    if not rpc_url:
        console.print("[red]Error: RPC URL required. Set ALCHEMY_RPC_URL or use --rpc-url[/red]")
        raise click.Abort()

    console.print(f"[bold blue]Inspecting block {block_number}...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            rpc_client = RPCClient(rpc_url)
            inspector = MEVInspector(rpc_client)

            progress.update(task, description="Fetching block data...")
            block_data = rpc_client.get_block(block_number, full_transactions=True)
            
            # Count transactions
            total_txs = len(block_data.get("transactions", []))
            successful_txs = 0
            total_logs = 0
            swap_event_logs = 0
            
            # Count successful transactions and logs
            for tx in block_data.get("transactions", []):
                if not tx.get("to"):
                    continue
                try:
                    tx_hash = tx["hash"].hex() if hasattr(tx["hash"], "hex") else tx["hash"]
                    receipt = rpc_client.get_transaction_receipt(tx_hash)
                    if receipt.get("status") == 1:
                        successful_txs += 1
                        logs = receipt.get("logs", [])
                        total_logs += len(logs)
                        # Count swap event logs
                        for log in logs:
                            if log.get("topics") and len(log["topics"]) > 0:
                                first_topic = log["topics"][0]
                                topic_hex = first_topic.hex() if hasattr(first_topic, "hex") else (first_topic if isinstance(first_topic, str) else first_topic.hex())
                                # Check for known swap event signatures
                                if topic_hex in [
                                    "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",  # UniswapV2
                                    "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",  # UniswapV3
                                ]:
                                    swap_event_logs += 1
                except Exception:
                    pass
            
            console.print(f"[dim]Block {block_number} stats:[/dim]")
            console.print(f"[dim]  - Total transactions: {total_txs}[/dim]")
            console.print(f"[dim]  - Successful transactions: {successful_txs}[/dim]")
            console.print(f"[dim]  - Total logs: {total_logs}[/dim]")
            console.print(f"[dim]  - Swap event logs: {swap_event_logs}[/dim]\n")
            
            results = inspector.inspect_block(block_number, what_if=what_if)

            progress.update(task, description="Analyzing MEV...")
            
            # Debug: show how many swaps were found
            swaps_found = inspector._extract_swaps(block_number, block_data["transactions"])
            console.print(f"[dim]Found {len(swaps_found)} parsed swaps in block {block_number}[/dim]\n")
            
            # Show verbose information if requested
            if verbose:
                console.print("\n[bold yellow]Verbose Debug Information:[/bold yellow]\n")
                # Show transactions with logs but no swap events
                txs_with_logs_no_swaps = [
                    tx for tx in results.transactions
                    if tx.log_count > 0 and tx.swap_events_found == 0
                ]
                if txs_with_logs_no_swaps:
                    console.print(f"[yellow]Transactions with logs but no swap events detected: {len(txs_with_logs_no_swaps)}[/yellow]")
                    for tx in txs_with_logs_no_swaps[:5]:  # Show first 5
                        console.print(f"  TX: {tx.hash[:16]}... | Logs: {tx.log_count} | Events: {len(tx.event_signatures)}")
                        if len(tx.event_signatures) > 0:
                            console.print(f"    First event: {tx.event_signatures[0]}")
                    console.print("")
            
            console.print("\n[bold green]MEV Detection Results:[/bold green]\n")

            # Display results
            _display_results(results)

            # Save report if requested
            if report:
                progress.update(task, description="Generating report...")
                report_path = Path(report)
                with open(report_path, "w") as f:
                    if report_mode == "basic":
                        json.dump(results.to_basic_dict(), f, indent=2, default=str)
                    else:
                        json.dump(results.to_dict(), f, indent=2, default=str)
                console.print(f"\n[green]Report saved to {report_path} (mode: {report_mode})[/green]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()


@main.command("range")
@click.argument("start_block", type=int)
@click.argument("end_block", type=int)
@click.option(
    "--what-if",
    is_flag=True,
    help="Also analyze what-if scenarios for missed MEV opportunities",
)
@click.option(
    "--report",
    type=click.Path(),
    help="Path to save detailed report (JSON format)",
)
@click.option(
    "--report-mode",
    type=click.Choice(["basic", "full"], case_sensitive=False),
    default="full",
    help="Report mode: 'basic' (MEV findings only) or 'full' (all transaction details)",
)
@click.option(
    "--rpc-url",
    envvar="ALCHEMY_RPC_URL",
    help="Alchemy RPC URL (or set ALCHEMY_RPC_URL env var)",
)
def range_cmd(
    start_block: int,
    end_block: int,
    what_if: bool,
    report: Optional[str],
    report_mode: str,
    rpc_url: Optional[str],
):
    """Inspect a range of blocks for MEV opportunities."""
    if not rpc_url:
        console.print("[red]Error: RPC URL required. Set ALCHEMY_RPC_URL or use --rpc-url[/red]")
        raise click.Abort()

    if start_block > end_block:
        console.print("[red]Error: start_block must be <= end_block[/red]")
        raise click.Abort()

    console.print(f"[bold blue]Inspecting blocks {start_block} to {end_block}...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            rpc_client = RPCClient(rpc_url)
            inspector = MEVInspector(rpc_client)

            all_results = []
            total_blocks = end_block - start_block + 1

            for block_num in range(start_block, end_block + 1):
                progress.update(
                    task,
                    description=f"Processing block {block_num} ({block_num - start_block + 1}/{total_blocks})...",
                )
                results = inspector.inspect_block(block_num, what_if=what_if)
                all_results.append(results)

            progress.update(task, description="Aggregating results...")
            console.print("\n[bold green]MEV Detection Results:[/bold green]\n")

            # Aggregate and display results
            aggregated = _aggregate_results(all_results)
            _display_results(aggregated)

            # Save report if requested
            if report:
                progress.update(task, description="Generating report...")
                report_path = Path(report)
                if report_mode == "basic":
                    report_data = {
                        "blocks": [r.to_basic_dict() for r in all_results],
                        "aggregated": aggregated.to_basic_dict(),
                    }
                else:
                    report_data = {
                        "blocks": [r.to_dict() for r in all_results],
                        "aggregated": aggregated.to_dict(),
                    }
                with open(report_path, "w") as f:
                    json.dump(report_data, f, indent=2, default=str)
                console.print(f"\n[green]Report saved to {report_path} (mode: {report_mode})[/green]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()


def _display_results(results):
    """Display MEV detection results in a formatted table."""
    from rich.table import Table

    # Historical MEV
    if results.historical_arbitrages or results.historical_sandwiches:
        table = Table(title="Historical MEV Detected")
        table.add_column("Type", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_column("Total Profit (ETH)", style="green")

        arb_count = len(results.historical_arbitrages)
        arb_profit = sum(a.profit_eth for a in results.historical_arbitrages)
        table.add_row("Arbitrage", str(arb_count), f"{arb_profit:.6f}")

        sand_count = len(results.historical_sandwiches)
        sand_profit = sum(s.profit_eth for s in results.historical_sandwiches)
        table.add_row("Sandwich", str(sand_count), f"{sand_profit:.6f}")

        console.print(table)

    # What-if scenarios
    if results.whatif_opportunities:
        table = Table(title="What-If MEV Opportunities (Missed)")
        table.add_column("Type", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_column("Total Potential Profit (ETH)", style="yellow")

        whatif_arb = [o for o in results.whatif_opportunities if o.type == "arbitrage"]
        whatif_sand = [o for o in results.whatif_opportunities if o.type == "sandwich"]

        if whatif_arb:
            arb_profit = sum(o.profit_eth for o in whatif_arb)
            table.add_row("Arbitrage", str(len(whatif_arb)), f"{arb_profit:.6f}")

        if whatif_sand:
            sand_profit = sum(o.profit_eth for o in whatif_sand)
            table.add_row("Sandwich", str(len(whatif_sand)), f"{sand_profit:.6f}")

        console.print(table)


def _aggregate_results(results_list):
    """Aggregate results from multiple blocks."""
    from mev_inspect.models import InspectionResults

    all_arbs = []
    all_sandwiches = []
    all_whatif = []

    for results in results_list:
        all_arbs.extend(results.historical_arbitrages)
        all_sandwiches.extend(results.historical_sandwiches)
        all_whatif.extend(results.whatif_opportunities)

    return InspectionResults(
        block_number=0,  # Aggregated
        historical_arbitrages=all_arbs,
        historical_sandwiches=all_sandwiches,
        whatif_opportunities=all_whatif,
    )


if __name__ == "__main__":
    main()

