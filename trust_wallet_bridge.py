import urllib.parse

def generate_buy_link(coin_address, amount_usd=0):
    """
    Generates a Trust Wallet Deep Link that opens the 1inch dApp browser 
    with a specific token swap pre-selected.
    
    :param coin_address: The contract address of the token to buy.
    :param amount_usd: Optional amount parameter (for UI reference).
    :return: A string containing the Deep Link URL.
    """
    # 1inch Ethereum Mainnet Swap URL
    # Format: https://app.1inch.io/#/1/simple/swap/USDT/[TOKEN_ADDRESS]
    one_inch_url = f"https://app.1inch.io/#/1/simple/swap/USDT/{coin_address}"
    
    # Trust Wallet Deep Link for opening a URL in the dApp browser
    # coin_id=60 is for Ethereum
    base_url = "https://link.trustwallet.com/open_url"
    
    params = {
        "coin_id": "60",
        "url": one_inch_url
    }
    
    # URL encode the parameters
    query_string = urllib.parse.urlencode(params)
    
    return f"{base_url}?{query_string}"

if __name__ == "__main__":
    # Example: Buy SHIB (0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE)
    shib_address = "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE"
    link = generate_buy_link(shib_address)
    print("Generated Deep Link for Trust Wallet:")
    print(link)
