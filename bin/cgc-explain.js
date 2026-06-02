#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["explain", ...process.argv.slice(2)]);
