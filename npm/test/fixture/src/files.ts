import fs from "fs";
import path from "path";

export function saveReport(name: string, body: string): string {
  const out = path.join("/tmp", name);
  fs.writeFileSync(out, body);
  return out;
}

export function cleanupReport(name: string): void {
  fs.unlinkSync(path.join("/tmp", name));
}
