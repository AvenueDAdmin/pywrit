import axios from "axios";

export async function notifySlack(webhookUrl: string, text: string) {
  await axios.post(webhookUrl, { text });
}

export async function fetchStatus(url: string) {
  const res = await axios.get(url);
  return res.data;
}
