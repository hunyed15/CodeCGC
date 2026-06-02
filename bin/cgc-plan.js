#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["plan", ...process.argv.slice(2)]);
