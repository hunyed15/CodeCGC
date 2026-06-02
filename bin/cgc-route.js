#!/usr/bin/env node
import { runCgc } from "./cgc-proxy.js";

runCgc(["route", ...process.argv.slice(2)]);
