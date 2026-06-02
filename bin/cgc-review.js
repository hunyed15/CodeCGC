#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["review", ...process.argv.slice(2)]);
