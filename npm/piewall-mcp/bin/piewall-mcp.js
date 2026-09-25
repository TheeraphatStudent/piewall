#!/usr/bin/env node
// Entry point for `npx piewall-mcp`. Nothing but the server may write to stdout.
import { main } from "../lib/launcher.js";

process.exitCode = await main();
