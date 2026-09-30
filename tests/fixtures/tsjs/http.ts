// Fixture: HTTP write calls. Lines tagged `expect:` must be flagged with that rule.
import axios from "axios";
import got from "got";
import ky from "ky";
import request from "superagent";
import * as https from "node:https";
import http from "http";

export async function createOrder(url: string, body: unknown) {
  await fetch(url, { method: "POST", body: JSON.stringify(body) }); // expect: fetch-write
  await fetch(url, { method: "put" }); // expect: fetch-write
  await window.fetch(url, { headers: {}, method: "PATCH" }); // expect: fetch-write
  await globalThis.fetch(url, { method: `DELETE` }); // expect: fetch-write
}

export const updateOrder = async (id: string) => {
  await axios.post("/orders", { id }); // expect: http-client-write
  await axios.put(`/orders/${id}`, {}); // expect: http-client-write
  await axios.patch(`/orders/${id}`, {}); // expect: http-client-write
  await axios.delete(`/orders/${id}`); // expect: http-client-write
  await axios({ url: "/orders", method: "post" }); // expect: http-config-write
  await axios.request({ url: "/orders", method: "DELETE" }); // expect: http-config-write
  await got.post("https://example.test/orders"); // expect: http-client-write
  await got("https://example.test/orders", { method: "PUT" }); // expect: http-config-write
  await ky.patch("https://example.test/orders"); // expect: http-client-write
  await request.del("/orders/1"); // expect: http-client-write
  await request("POST", "/orders"); // expect: http-config-write
};

export class OrderClient {
  client: any;
  deleteRemote(id: string) {
    this.client.delete(`/orders/${id}`); // expect: http-client-write
    https.request({ host: "example.test", method: "DELETE" }); // expect: http-config-write
    http.request("http://example.test/x", { method: "POST" }); // expect: http-config-write
  }
}
