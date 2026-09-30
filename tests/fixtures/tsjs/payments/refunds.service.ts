// Fixture: SDK writes (Stripe, Prisma) and child_process.
import Stripe from "stripe";
import { exec, spawn } from "node:child_process";
const cp = require("child_process");

const stripe = new Stripe(process.env.STRIPE_API_KEY ?? "");

export class RefundService {
  async issueRefund(chargeId: string) {
    await stripe.refunds.create({ charge: chargeId }); // expect: stripe-write
    await stripe.charges.create({ amount: 100 }); // expect: stripe-write
    await stripe.customers.update("cus_1", {}); // expect: stripe-write
    await stripe.customers.del("cus_1"); // expect: stripe-write
  }

  async recordRefund(id: string) {
    await this.prisma.refund.create({ data: { id } }); // expect: prisma-write
    await prisma.refund.update({ where: { id }, data: {} }); // expect: prisma-write
    await prisma.refund.upsert({ where: { id }, create: {}, update: {} }); // expect: prisma-write
    await prisma.refund.delete({ where: { id } }); // expect: prisma-write
    await prisma.refund.deleteMany({}); // expect: prisma-write
    await prisma.refund.updateMany({ data: {} }); // expect: prisma-write
  }

  prisma: any;
}

export function runExport() {
  exec("ls"); // expect: child-process
  spawn("tar", ["-czf", "x.tgz", "."]); // expect: child-process
  cp.execSync("rm -rf /tmp/x"); // expect: child-process
}
