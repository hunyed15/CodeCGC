#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["fix", "issue", ...process.argv.slice(2)]);
