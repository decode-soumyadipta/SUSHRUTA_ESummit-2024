import json
from web3 import Web3
import os
from dotenv import load_dotenv

# Load environment variables (for sensitive information like private keys, contract address, etc.)
load_dotenv()

# Kaleido RPC URL for Ethereum node
KALEIDO_RPC_URL = os.getenv("KALEIDO_RPC_URL")  # Make sure this is in your .env file
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")  # Smart contract address on Kaleido
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # Your private key (used to sign transactions)

# Connect to Kaleido blockchain using Web3
w3 = Web3(Web3.HTTPProvider(KALEIDO_RPC_URL))

# Check if the connection is successful
if not w3.is_connected():
    raise ConnectionError("Unable to connect to Kaleido. Please check your RPC URL and internet connection.")

# Load the contract ABI (assuming you have already deployed the contract)
with open('utils/ABI.json', 'r') as abi_file:
    contract_abi = json.load(abi_file)

# Convert the contract address to checksum format
contract_address = Web3.to_checksum_address(CONTRACT_ADDRESS)

# Derive the public address from the private key
account = w3.eth.account.from_key(PRIVATE_KEY)
user_address = account.address  # This is the 'from' address, derived from the private key
print(f"Derived user address: {user_address}")

# Initialize the contract
contract = w3.eth.contract(address=contract_address, abi=contract_abi)

def store_data_on_blockchain(prescription_hash, test_results_hash):
    """
    Store prescription and test results hash on the Kaleido blockchain.
    
    Arguments:
    - prescription_hash: The IPFS hash of the prescription file.
    - test_results_hash: The IPFS hash of the test results file.
    
    Returns:
    - Transaction hash as a string if successful, or None if there was an error.
    """
    try:
        # Get the latest nonce for your account (needed for transaction)
        nonce = w3.eth.get_transaction_count(user_address)

        # Check the balance to ensure there are enough funds
        balance = w3.eth.get_balance(user_address)
        print(f"Account balance: {w3.from_wei(balance, 'ether')} ETH")
        if balance == 0:
            raise ValueError("Insufficient funds in the account to cover gas fees")

        # Call the storeMedicalData function and build the transaction
        txn = contract.functions.storeMedicalData(prescription_hash, test_results_hash).build_transaction({
            'chainId': 1337,  # Replace with Kaleido's actual chain ID (check the Kaleido console)
            'gas': 2000000,    # Gas limit for the transaction
            'gasPrice': w3.to_wei('20', 'gwei'),  # Gas price in Gwei
            'nonce': nonce,    # Nonce value for transaction uniqueness
            'from': user_address  # Use the derived address from the private key
        })
        
        # Sign the transaction with your private key
        signed_txn = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)

        # Send the signed transaction to the blockchain
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        # Print or return the transaction hash
        print(f"Transaction successful with hash: {tx_hash.hex()}")
        return tx_hash.hex()

    except Exception as e:
        print(f"An error occurred while storing data on the blockchain: {e}")
        return None
