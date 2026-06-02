#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["test", ...process.argv.slice(2)]);
