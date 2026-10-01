"""Stripe payment-mutation surface regression fixture."""

import stripe


def refund_charge(charge_id, amount_cents):
    stripe.Refund.create(charge=charge_id, amount=amount_cents)


def capture_charge(charge_id):
    stripe.Charge.capture(charge_id)


def create_payment_intent(amount_cents):
    stripe.PaymentIntent.create(amount=amount_cents, currency="usd")


def cancel_payment_intent(pi_id):
    stripe.PaymentIntent.cancel(pi_id)


def create_payout(amount_cents):
    stripe.Payout.create(amount=amount_cents, currency="usd")


def create_transfer(amount_cents):
    stripe.Transfer.create(amount=amount_cents, currency="usd",
                           destination="acct_123")


def pay_invoice(invoice_id):
    stripe.Invoice.pay(invoice_id)


def update_subscription(sub_id, items):
    stripe.Subscription.update(sub_id, items=items)
