// Fixture: filesystem writes (callbacks, sync, promises, aliases).
const fs = require("fs");
const { renameSync, unlink: removeFile } = require("node:fs");
const fsp = require("fs").promises;
import { writeFile as writeFileP, rm } from "fs/promises";
import { promises as pfs } from "fs";

function saveReport(path, data) {
  fs.writeFile(path, data, () => {}); // expect: fs-write
  fs.appendFileSync(path, data); // expect: fs-write
  fs.promises.unlink(path); // expect: fs-write
  renameSync(path, path + ".bak"); // expect: fs-write
  removeFile(path, () => {}); // expect: fs-write
}

async function purgeCache(dir) {
  await fsp.rm(dir, { recursive: true }); // expect: fs-write
  await writeFileP(dir + "/x", "y"); // expect: fs-write
  await rm(dir); // expect: fs-write
  await pfs.rename(dir, dir + "2"); // expect: fs-write
  fs.createWriteStream(dir + "/log"); // expect: fs-write
}

module.exports = { saveReport, purgeCache };
