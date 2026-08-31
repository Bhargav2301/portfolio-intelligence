import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../lib/hash.js";

test("manual portfolio source hashes use canonical SHA-256 hex", async () => {
  const holdings = [{
    symbol: "EXMPL",
    name: "Example Industries",
    exchange: "NSE",
    quantity: 1,
    averageCost: 125,
    currentPrice: 140,
  }];

  const digest = await sha256Hex(JSON.stringify(holdings));

  assert.match(digest, /^[a-f0-9]{64}$/);
  assert.equal(digest.length, 64);
});

test("file bytes and text both use the same hexadecimal contract", async () => {
  const bytes = new TextEncoder().encode("portfolio-intelligence");

  assert.equal(await sha256Hex(bytes), await sha256Hex("portfolio-intelligence"));
});
