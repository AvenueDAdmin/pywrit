// Fixture: SQL write strings and query builders.
import knex from "knex";

export async function insertUser(pool, db, client, conn, prisma, name) {
  await pool.query("INSERT INTO users (name) VALUES ($1)", [name]); // expect: sql-write
  await db.execute(`UPDATE users SET name = ${name}`); // expect: sql-write
  await knex.raw("delete from users where id = 1"); // expect: sql-write
  await client.query(" DROP TABLE sessions"); // expect: sql-write
  await conn.query("ALTER TABLE users ADD COLUMN x int"); // expect: sql-write
  await prisma.$executeRaw`DELETE FROM users WHERE id = 1`; // expect: sql-write
  await knex("users").insert({ name }); // expect: db-write
  await db("users").where({ name }).update({ name: "x" }); // expect: db-write
  await knex("users").where({ name }).del(); // expect: db-write
  await db.collection("users").insertOne({ name }); // expect: db-write
}
