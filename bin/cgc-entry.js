#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["entry", ...process.argv.slice(2)]);
