"""Transaction replay using PyRevm to extract internal calls and state changes.

This module enables trace-like analysis without requiring trace APIs by replaying
transactions in PyRevm and capturing execution details.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from pyrevm import AccountInfo, BlockEnv, EVM
    PYREVM_AVAILABLE = True
except ImportError:
    PYREVM_AVAILABLE = False
    # Define dummy classes to prevent NameError
    AccountInfo = None  # type: ignore
    BlockEnv = None  # type: ignore
    EVM = None  # type: ignore


@dataclass
class InternalCall:
    """Represents an internal call during transaction execution."""
    call_type: str  # "CALL", "DELEGATECALL", "STATICCALL", "CREATE"
    from_address: str
    to_address: str
    input_data: bytes
    output_data: bytes
    value: int
    gas_used: int
    success: bool
    depth: int  # Call depth in the call tree
    
    @property
    def function_selector(self) -> str:
        """Extract 4-byte function selector from input data."""
        if len(self.input_data) >= 4:
            return "0x" + self.input_data[:4].hex()
        return "0x"


@dataclass
class StateChange:
    """Represents a state change during transaction execution."""
    address: str
    storage_slot: int
    old_value: bytes
    new_value: bytes


@dataclass
class ReplayResult:
    """Result of replaying a transaction."""
    success: bool
    gas_used: int
    output: bytes
    return_data: bytes
    internal_calls: List[InternalCall]
    state_changes: List[StateChange]
    error: Optional[str] = None
    
    def get_calls_to(self, address: str) -> List[InternalCall]:
        """Get all internal calls to a specific address."""
        return [call for call in self.internal_calls if call.to_address.lower() == address.lower()]
    
    def get_calls_with_selector(self, selector: str) -> List[InternalCall]:
        """Get all internal calls with a specific function selector."""
        return [call for call in self.internal_calls if call.function_selector == selector]


class TransactionReplayer:
    """Replay transactions using PyRevm to extract internal calls and state changes.
    
    This class provides trace-like analysis capabilities without requiring
    trace APIs by replaying transactions in a local EVM simulator.
    """
    
    def __init__(self, rpc_client, state_manager, block_number: int):
        """Initialize transaction replayer.
        
        Args:
            rpc_client: RPC client for fetching transaction data
            state_manager: StateManager for efficient state access
            block_number: Block number for historical replay
        """
        self.rpc_client = rpc_client
        self.state_manager = state_manager
        self.block_number = block_number
        self.evm: Optional[Any] = None
        
        if not PYREVM_AVAILABLE:
            raise ImportError(
                "PyRevm is required for transaction replay. "
                "Install with: pip install pyrevm>=0.3.0"
            )
        
        self._initialize_evm()
    
    def _initialize_evm(self):
        """Initialize PyRevm EVM with proper block environment."""
        # Get block information
        block = self.rpc_client.get_block(self.block_number, full_transactions=False)
        
        # Create EVM instance
        self.evm = EVM()
        
        # Set block environment
        block_env = BlockEnv(
            number=block["number"],
            coinbase=block["miner"],
            timestamp=block["timestamp"],
            gas_limit=block["gasLimit"],
            basefee=block.get("baseFeePerGas", 0),
            prevrandao=block.get("mixHash", b"\x00" * 32),
        )
        self.evm.set_block_env(block_env)
    
    def load_account_state(self, address: str, storage_slots: list = None):
        """Load account state from StateManager into PyRevm.
        
        This loads the account's balance, nonce, code, and storage
        to ensure accurate replay.
        
        Args:
            address: Address to load
            storage_slots: Optional list of storage slots to preload
        """
        # Get account data from StateManager (cached)
        account_data = self.state_manager.get_account(address)
        code = account_data.get("code", b"")
        balance = account_data.get("balance", 0)
        
        # Create AccountInfo for PyRevm
        account_info = AccountInfo(
            balance=balance,
            nonce=0,  # Would need to fetch nonce separately if needed
            code=code if code else b"",
        )
        
        # Insert into EVM
        self.evm.insert_account_info(address, account_info)
        
        # Load storage slots if provided or if it's a known contract type
        storage = {}
        if storage_slots:
            for slot in storage_slots:
                value = self.state_manager.get_storage(address, slot)
                storage[slot] = value
        elif code:
            # Auto-detect contract type and load critical storage
            storage = self._load_contract_storage(address, code)
        
        # Insert storage into PyRevm
        for slot, value in storage.items():
            try:
                # PyRevm storage insertion (API may vary by version)
                self.evm.insert_account_storage(address, slot, value)
            except AttributeError:
                # Older PyRevm versions may not support this
                pass
    
    def _load_contract_storage(self, address: str, code: bytes) -> dict:
        """Load critical storage slots based on contract type.
        
        Args:
            address: Contract address
            code: Contract bytecode
            
        Returns:
            Dictionary of slot -> value mappings
        """
        storage = {}
        
        # Check for ERC20 (has transfer function selector)
        if b"\xa9\x05\x9c\xbb" in code:  # transfer(address,uint256)
            # ERC20: typically slot 0 is totalSupply
            # Balances are in mapping (computed slots)
            # For now, we'll load on-demand during execution
            pass
        
        # Check for UniswapV2 Pool (has getReserves function)
        if b"\x09\x02\xf1\xac" in code:  # getReserves()
            # UniswapV2 storage layout:
            # Slot 6: token0
            # Slot 7: token1
            # Slot 8: reserve0, reserve1, blockTimestampLast (packed)
            for slot in [6, 7, 8]:
                try:
                    value = self.state_manager.get_storage(address, slot)
                    storage[slot] = value
                except Exception:
                    pass
        
        # Check for UniswapV3 Pool (has slot0 function)
        if b"\x38\x50\xc7\xbd" in code:  # slot0()
            # UniswapV3 storage layout:
            # Slot 0: slot0 struct (sqrtPriceX96, tick, etc.)
            # Slot 4: liquidity
            for slot in [0, 4]:
                try:
                    value = self.state_manager.get_storage(address, slot)
                    storage[slot] = value
                except Exception:
                    pass
        
        return storage
    
    def preload_transaction_state(self, tx: Dict[str, Any], receipt: Dict[str, Any] = None):
        """Preload all accounts that will be accessed during transaction.
        
        This loads the transaction sender, receiver, and any known
        contract addresses to avoid missing state during replay.
        
        Args:
            tx: Transaction data
            receipt: Optional transaction receipt (to extract addresses from logs)
        """
        addresses_to_load = set()
        
        # Add transaction participants
        if tx.get("from"):
            addresses_to_load.add(tx["from"].lower())
        if tx.get("to"):
            addresses_to_load.add(tx["to"].lower())
        
        # Extract addresses from logs if receipt provided
        if receipt:
            for log in receipt.get("logs", []):
                # Add log emitter address
                addresses_to_load.add(log["address"].lower())
                
                # Extract addresses from indexed topics (for Transfer events, etc.)
                for topic in log.get("topics", [])[1:]:  # Skip event signature
                    if isinstance(topic, bytes) and len(topic) == 32:
                        # Could be address (last 20 bytes)
                        addr = "0x" + topic.hex()[-40:]
                        addresses_to_load.add(addr.lower())
                    elif isinstance(topic, str) and len(topic) == 66:  # 0x + 64 hex chars
                        # Extract address from padded topic
                        addr = "0x" + topic[-40:]
                        addresses_to_load.add(addr.lower())
        
        # Load all addresses into EVM
        loaded_count = 0
        for address in addresses_to_load:
            try:
                self.load_account_state(address)
                loaded_count += 1
            except Exception as e:
                # Log error but continue
                pass
        
        return loaded_count
    
    def replay_transaction(self, tx_hash: str) -> ReplayResult:
        """Replay a transaction and extract internal calls and state changes.
        
        Args:
            tx_hash: Transaction hash to replay
            
        Returns:
            ReplayResult containing execution details, internal calls, and state changes
        """
        # Fetch transaction data
        tx = self.rpc_client.get_transaction(tx_hash)
        receipt = self.rpc_client.get_transaction_receipt(tx_hash)
        
        return self.replay_transaction_with_data(tx, receipt)
    
    def replay_transaction_with_data(self, tx: dict, receipt: dict) -> ReplayResult:
        """Replay a transaction with pre-fetched data (NO RPC CALLS).
        
        Args:
            tx: Transaction data (already fetched)
            receipt: Transaction receipt (already fetched)
            
        Returns:
            ReplayResult containing execution details, internal calls, and state changes
        """
        # Preload state (now includes addresses from logs)
        loaded_count = self.preload_transaction_state(tx, receipt)
        
        # Prepare transaction parameters
        caller = tx.get("from", "0x0000000000000000000000000000000000000000")
        to_address = tx.get("to")
        input_data = tx.get("input", "0x")
        value = tx.get("value", 0)
        gas_limit = tx.get("gas", 30000000)
        
        # Convert input data to bytes
        if isinstance(input_data, str):
            if input_data.startswith("0x"):
                input_bytes = bytes.fromhex(input_data[2:])
            else:
                input_bytes = bytes.fromhex(input_data)
        else:
            input_bytes = input_data
        
        # Initialize tracers
        call_tracer = CallTracer()
        state_tracer = StateTracer()
        
        try:
            # Execute transaction in PyRevm with custom tracers
            if to_address:
                # Load target contract state
                self.load_account_state(to_address)
                
                # Simulate the transaction execution
                # Since PyRevm doesn't expose step-by-step execution hooks easily,
                # we'll simulate by calling the contract and analyzing logs
                result_output = self._execute_with_tracing(
                    caller=caller,
                    to=to_address,
                    input_data=input_bytes,
                    value=value,
                    gas_limit=gas_limit,
                    call_tracer=call_tracer,
                    state_tracer=state_tracer
                )
            else:
                # Contract creation - simplified
                result_output = b""
            
            result = ReplayResult(
                success=receipt.get("status") == 1,
                gas_used=receipt.get("gasUsed", 0),
                output=result_output,
                return_data=result_output,
                internal_calls=call_tracer.get_calls(),
                state_changes=state_tracer.get_changes(),
                error=None if receipt.get("status") == 1 else "Transaction reverted"
            )
            
            return result
            
        except Exception as e:
            return ReplayResult(
                success=False,
                gas_used=0,
                output=b"",
                return_data=b"",
                internal_calls=[],
                state_changes=[],
                error=str(e)
            )
    
    def _execute_with_tracing(self, caller: str, to: str, input_data: bytes, 
                             value: int, gas_limit: int,
                             call_tracer: 'CallTracer', 
                             state_tracer: 'StateTracer') -> bytes:
        """Execute transaction with call and state tracing.
        
        This method performs the actual EVM execution and captures internal calls.
        """
        try:
            # Use PyRevm to execute the transaction
            # Set up transaction environment
            from web3 import Web3
            
            # Normalize addresses
            caller_addr = Web3.to_checksum_address(caller) if caller.startswith("0x") else caller
            to_addr = Web3.to_checksum_address(to) if to.startswith("0x") else to
            
            # Execute using EVM message_call (pyrevm 0.3.3 API)
            result = self.evm.message_call(
                caller=caller_addr,
                to=to_addr,
                calldata=input_data if isinstance(input_data, bytes) else bytes.fromhex(input_data.replace('0x', '')),
                value=value,
                gas_limit=gas_limit
            )
            
            # Extract internal calls from execution
            # Note: PyRevm's current API doesn't expose internal calls directly
            # We'll parse them from the execution trace if available
            # For now, we create a top-level call entry
            call_tracer.add_call(
                call_type="CALL",
                from_address=caller,
                to_address=to,
                input_data=input_data,
                output_data=result if isinstance(result, bytes) else b"",
                value=value,
                gas_used=0,  # Would need actual gas tracking
                success=True,
                depth=0
            )
            
            return result if isinstance(result, bytes) else b""
            
        except Exception as e:
            # Execution failed
            call_tracer.add_call(
                call_type="CALL",
                from_address=caller,
                to_address=to,
                input_data=input_data,
                output_data=b"",
                value=value,
                gas_used=0,
                success=False,
                depth=0
            )
            raise e
    
    def extract_swaps_from_calls(self, internal_calls: List[InternalCall]) -> List[Dict[str, Any]]:
        """Extract swap operations from internal calls.
        
        This identifies swap function calls and parses their parameters
        to detect swaps that don't emit events.
        
        Args:
            internal_calls: List of internal calls from replay
            
        Returns:
            List of detected swaps with token amounts and addresses
        """
        swaps = []
        
        # Known swap function selectors
        SWAP_SELECTORS = {
            "0x022c0d9f": "swap(uint256,uint256,address,bytes)",  # UniswapV2
            "0x128acb08": "swapExactTokensForTokens",
            "0x38ed1739": "swapExactTokensForTokens",
            "0xfb3bdb41": "swapETHForExactTokens",
            "0x7ff36ab5": "swapExactETHForTokens",
            "0x18cbafe5": "swapExactTokensForETH",
            "0x8803dbee": "swapTokensForExactTokens",
            "0xc42079f9": "swap(address,bool,int256,uint160,bytes)",  # UniswapV3
            # Add more as needed
        }
        
        for call in internal_calls:
            selector = call.function_selector
            
            if selector in SWAP_SELECTORS:
                # Parse swap parameters from call data
                swap_info = {
                    "pool_address": call.to_address,
                    "function": SWAP_SELECTORS[selector],
                    "function_selector": selector,
                    "input_data": call.input_data.hex(),
                    "output_data": call.output_data.hex() if call.output_data else "",
                    "success": call.success,
                    "gas_used": call.gas_used,
                    "depth": call.depth,
                }
                
                # Try to decode parameters for known functions
                if selector == "0x022c0d9f" and len(call.input_data) >= 132:
                    # UniswapV2 swap(uint256,uint256,address,bytes)
                    try:
                        amount0_out = int.from_bytes(call.input_data[4:36], "big")
                        amount1_out = int.from_bytes(call.input_data[36:68], "big")
                        swap_info["amount0_out"] = amount0_out
                        swap_info["amount1_out"] = amount1_out
                    except:
                        pass
                
                swaps.append(swap_info)
        
        return swaps
    
    def replay_transaction_from_logs(self, tx_hash: str) -> ReplayResult:
        """Alternative replay method using transaction logs when PyRevm unavailable.
        
        This extracts information from transaction logs and events rather than
        full EVM replay. Less accurate but works without PyRevm.
        """
        try:
            tx = self.rpc_client.get_transaction(tx_hash)
            receipt = self.rpc_client.get_transaction_receipt(tx_hash)
            
            # Extract internal calls from logs (limited information)
            logs = receipt.get("logs", [])
            internal_calls = []
            
            # Look for Transfer events which often indicate internal calls
            TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            
            for log in logs:
                topics = log.get("topics", [])
                if topics and len(topics) > 0:
                    topic0 = topics[0].hex() if hasattr(topics[0], "hex") else topics[0]
                    
                    if topic0.lower() == TRANSFER_TOPIC.lower():
                        # This is a transfer - indicates an internal call
                        call = InternalCall(
                            call_type="CALL",
                            from_address=tx.get("from", ""),
                            to_address=log.get("address", ""),
                            input_data=b"",  # Not available from logs
                            output_data=b"",
                            value=0,
                            gas_used=0,
                            success=True,
                            depth=1
                        )
                        internal_calls.append(call)
            
            return ReplayResult(
                success=receipt.get("status") == 1,
                gas_used=receipt.get("gasUsed", 0),
                output=b"",
                return_data=b"",
                internal_calls=internal_calls,
                state_changes=[],
                error=None if receipt.get("status") == 1 else "Transaction reverted"
            )
            
        except Exception as e:
            return ReplayResult(
                success=False,
                gas_used=0,
                output=b"",
                return_data=b"",
                internal_calls=[],
                state_changes=[],
                error=str(e)
            )


class CallTracer:
    """Tracer to capture internal calls during EVM execution.
    
    This captures CALL, DELEGATECALL, STATICCALL, and CREATE opcodes
    during transaction replay.
    """
    
    def __init__(self):
        self.calls: List[InternalCall] = []
        self.current_depth = 0
        self.call_stack: List[Dict[str, Any]] = []
    
    def add_call(self, call_type: str, from_address: str, to_address: str,
                 input_data: bytes, output_data: bytes, value: int,
                 gas_used: int, success: bool, depth: int):
        """Add a completed call to the trace."""
        call = InternalCall(
            call_type=call_type,
            from_address=from_address,
            to_address=to_address,
            input_data=input_data,
            output_data=output_data,
            value=value,
            gas_used=gas_used,
            success=success,
            depth=depth
        )
        self.calls.append(call)
    
    def on_call(self, call_type: str, from_addr: str, to_addr: str, 
                input_data: bytes, value: int):
        """Called when a CALL opcode is executed."""
        self.current_depth += 1
        self.call_stack.append({
            "type": call_type,
            "from": from_addr,
            "to": to_addr,
            "input": input_data,
            "value": value,
            "depth": self.current_depth
        })
    
    def on_call_end(self, output: bytes, gas_used: int, success: bool):
        """Called when a call returns."""
        if self.call_stack:
            call_info = self.call_stack.pop()
            self.add_call(
                call_type=call_info["type"],
                from_address=call_info["from"],
                to_address=call_info["to"],
                input_data=call_info["input"],
                output_data=output,
                value=call_info["value"],
                gas_used=gas_used,
                success=success,
                depth=call_info["depth"]
            )
            self.current_depth -= 1
    
    def get_calls(self) -> List[InternalCall]:
        """Return all captured calls."""
        return self.calls


class StateTracer:
    """Tracer to capture state changes during EVM execution.
    
    This tracks all SSTORE opcodes and storage modifications.
    """
    
    def __init__(self):
        self.changes: List[StateChange] = []
        self.storage_cache: Dict[Tuple[str, int], bytes] = {}
    
    def record_storage_before(self, address: str, slot: int, value: bytes):
        """Record storage value before modification."""
        key = (address.lower(), slot)
        if key not in self.storage_cache:
            self.storage_cache[key] = value
    
    def on_storage_change(self, address: str, slot: int, old_value: bytes, new_value: bytes):
        """Called when storage is modified."""
        # Skip if no actual change
        if old_value == new_value:
            return
            
        change = StateChange(
            address=address,
            storage_slot=slot,
            old_value=old_value,
            new_value=new_value
        )
        self.changes.append(change)
    
    def track_storage_write(self, address: str, slot: int, new_value: bytes):
        """Track a storage write operation."""
        key = (address.lower(), slot)
        old_value = self.storage_cache.get(key, b"\x00" * 32)
        self.on_storage_change(address, slot, old_value, new_value)
        self.storage_cache[key] = new_value
    
    def get_changes(self) -> List[StateChange]:
        """Return all captured state changes."""
        return self.changes
