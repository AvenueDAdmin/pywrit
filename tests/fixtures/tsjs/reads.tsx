// Fixture (negative): reads and look-alikes. Nothing here may be flagged.
import axios from "axios";
import fs from "fs";
import express from "express";

const router = express.Router();
const app = express();
const cache = new Map<string, string>();

export async function loadOrders(url: string, pool: any, db: any, prisma: any, method: string) {
  await fetch(url);
  await fetch(url, { method: "GET" });
  await fetch(url, { method });
  await axios.get(url);
  await axios({ url, method: "get" });
  fs.readFileSync("x");
  await fs.promises.readFile("x");
  await pool.query("SELECT * FROM users");
  await db.query(`WITH t AS (SELECT 1) SELECT * FROM t`);
  await prisma.user.findMany();
  cache.delete("k");
  /\d+/.exec("123");
  return null;
}

router.post("/orders", (req: any, res: any) => res.json({}));
app.put("/orders/:id", (req: any, res: any) => res.json({}));

export function OrderList() {
  return <div onClick={() => fetch("/api/orders")}>orders</div>;
}
