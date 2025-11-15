"""RPC client for Ethereum nodes (Alchemy Free Tier compatible - no trace support)."""

from typing import Any, Dict, List, Optional

from web3 import Web3
from web3.types import BlockData, TxData, TxReceipt


class RPCClient:
    """RPC client that works with Alchemy Free Tier (no trace support)."""

    def __init__(self, rpc_url: str):
        """Initialize RPC client."""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {rpc_url}")

    def get_block(self, block_number: int, full_transactions: bool = True) -> BlockData:
        """Get block data."""
        return self.w3.eth.get_block(block_number, full_transactions=full_transactions)

    def get_transaction(self, tx_hash: str) -> TxData:
        """Get transaction data."""
        return self.w3.eth.get_transaction(tx_hash)

    def get_transaction_receipt(self, tx_hash: str) -> TxReceipt:
        """Get transaction receipt."""
        return self.w3.eth.get_transaction_receipt(tx_hash)

    def get_code(self, address: str) -> str:
        """Get contract code at address."""
        return self.w3.eth.get_code(Web3.to_checksum_address(address))

    def get_balance(self, address: str, block_number: int) -> int:
        """Get balance at block."""
        return self.w3.eth.get_balance(Web3.to_checksum_address(address), block_number)

    def call(
        self,
        to: str,
        data: str,
        block_number: int,
        from_address: Optional[str] = None,
        value: int = 0,
    ) -> bytes:
        """Call contract at block number."""
        call_params = {
            "to": Web3.to_checksum_address(to),
            "data": data,
        }
        if from_address:
            call_params["from"] = Web3.to_checksum_address(from_address)
        if value > 0:
            call_params["value"] = value

        return self.w3.eth.call(call_params, block_number)

    def get_storage_at(self, address: str, position: int, block_number: int) -> bytes:
        """Get storage slot value."""
        return self.w3.eth.get_storage_at(
            Web3.to_checksum_address(address), position, block_number
        )

    def get_latest_block_number(self) -> int:
        """Get latest block number."""
        return self.w3.eth.block_number

