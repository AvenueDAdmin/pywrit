"""web3.py / crypto regression fixture."""


def send_eth(w3, to, value):
    w3.eth.send_transaction({"to": to, "value": value})


def mint_token(contract):
    contract.functions.mint().transact()
