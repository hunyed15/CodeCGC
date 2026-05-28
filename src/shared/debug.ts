/**
 * Debug logger — logs only when DEBUG=codecgc or DEBUG=* is set
 */
export function createDebugLogger(namespace: string) {
  const isDebug = process.env.DEBUG === "*" || process.env.DEBUG?.includes("codecgc");

  return {
    log: (...args: unknown[]) => {
      if (isDebug) {
        console.error(`[${namespace}]`, ...args);
      }
    },
    warn: (...args: unknown[]) => {
      console.error(`[${namespace}] WARNING:`, ...args);
    },
  };
}
