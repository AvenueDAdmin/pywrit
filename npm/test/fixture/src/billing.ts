import Stripe from "stripe";
import { prisma } from "./client";

const stripe = new Stripe(process.env.STRIPE_KEY as string);

export async function chargeCustomer(amount: number) {
  await stripe.charges.create({ amount, currency: "usd" });
}

export async function addUser(email: string) {
  await prisma.user.create({ data: { email } });
}
