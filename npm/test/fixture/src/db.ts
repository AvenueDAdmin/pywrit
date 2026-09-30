import { Pool } from "pg";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export async function createTicket(title: string) {
  await pool.query("INSERT INTO tickets (title) VALUES ($1)", [title]);
}

export async function closeTicket(id: number) {
  await pool.query("UPDATE tickets SET status = 'closed' WHERE id = $1", [id]);
}
