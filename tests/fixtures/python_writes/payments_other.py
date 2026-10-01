"""Other payment-provider regression fixtures (PayPal/Braintree/Square)."""


def create_paypal_payment(paypal, amount):
    paypal.create(amount=amount)


def square_charge(square, amount):
    square.create_payment(source_id="cnon:card-nonce-ok", amount_money=amount)


def braintree_sale(braintree, amount):
    braintree.create({"amount": amount})
