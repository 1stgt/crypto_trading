import requests
import os
from dotenv import load_dotenv

load_dotenv()

class OneInchService:
    """
    Service wrapper for the 1inch Swap API v6.0.
    Documentation: https://portal.1inch.dev/documentation/swap/swagger
    """

    def __init__(self, chain_id=1):
        """
        Initializes the 1inch service.
        :param chain_id: The ID of the blockchain (1 for Ethereum, 56 for BSC, 137 for Polygon, etc.)
        """
        self.base_url = f"https://api.1inch.dev/swap/v6.0/{chain_id}"
        self.api_key = os.getenv("ONE_INCH_API_KEY")
        
        # Headers required for 1inch Developer Portal API
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "accept": "application/json"
        }

    def _make_request(self, endpoint, params):
        """Internal helper to handle API requests."""
        if not self.api_key:
            return {"error": "1inch API Key not found. Please add ONE_INCH_API_KEY to your .env file."}

        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"1inch API Error {response.status_code}",
                    "message": response.text
                }
        except Exception as e:
            return {"error": "Connection Error", "message": str(e)}

    def get_quote(self, from_token, to_token, amount):
        """
        Gets an estimated return amount for a swap.
        :param from_token: Source token contract address (e.g., '0xeeee...' for ETH)
        :param to_token: Destination token contract address
        :param amount: Amount in units of the source token (Wei/Decimals)
        :return: JSON response containing destination amount and routing info.
        """
        params = {
            "src": from_token,
            "dst": to_token,
            "amount": str(amount)
        }
        return self._make_request("/quote", params)

    def get_swap_transaction(self, from_token, to_token, amount, wallet_address, slippage=1):
        """
        Generates the raw transaction data (calldata) needed to execute a swap.
        :param from_token: Source token contract address
        :param to_token: Destination token contract address
        :param amount: Amount in units of source token
        :param wallet_address: The address that will trigger the transaction
        :param slippage: Max allowed price slippage (default 1%)
        :return: JSON containing 'tx' object with 'data', 'to', 'value', etc.
        """
        params = {
            "src": from_token,
            "dst": to_token,
            "amount": str(amount),
            "from": wallet_address,
            "slippage": slippage
        }
        return self._make_request("/swap", params)

    def get_approve_transaction(self, token_address, amount=None):
        """
        Generates the raw transaction data (calldata) to approve the 1inch Router to spend tokens.
        :param token_address: The contract address of the token to approve.
        :param amount: The amount to approve (None for infinite approval).
        """
        params = {"tokenAddress": token_address}
        if amount:
            params["amount"] = str(amount)
        return self._make_request("/approve/transaction", params)

if __name__ == "__main__":
    # Quick Test Block
    # Example: ETH (0xeeee...) to USDT (0xdac...) on Ethereum (chain 1)
    service = OneInchService(chain_id=1)
    
    # These will fail without a valid API Key but demonstrate the call structure
    print("Testing 1inch Quote...")
    quote = service.get_quote(
        from_token="0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", 
        to_token="0xdac17f958d2ee523a2206206994597c13d831ec7", 
        amount=1000000000000000000 # 1 ETH
    )
    print(quote)
