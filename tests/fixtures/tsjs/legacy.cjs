// Fixture: CommonJS.
const fs = require("fs");
exports.writeConfig = function (p) {
  fs.writeFileSync(p, "{}"); // expect: fs-write
};
