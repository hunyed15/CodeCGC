#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["audit", ...process.argv.slice(2)]);
