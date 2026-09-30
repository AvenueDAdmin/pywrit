// Fixture: a write already behind a writ gate counts as gated.
import { writCheck } from "./writ";

export async function chargeCard(url: string) {
  if ((await writCheck("payments.charge")) !== "ALLOW") throw new Error("denied");
  await fetch(url, { method: "POST" }); // expect: fetch-write
}
