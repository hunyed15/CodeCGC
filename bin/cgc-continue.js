#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["continue", ...process.argv.slice(2)]);
