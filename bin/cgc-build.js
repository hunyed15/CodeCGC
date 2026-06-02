#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["build", "feature", ...process.argv.slice(2)]);
