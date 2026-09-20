/**
 * React 19 requires an explicit opt-in flag for `act` in test environments.
 * Without it, rendering async components logs warnings that fail the
 * zero-warning policy.
 */
(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

/**
 * Zero-warning policy: make any console.error / console.warn thrown during a
 * test fail that test. The original method still logs so the failure output
 * shows the offending message.
 */
const consoleError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  consoleError(...args);
  throw new Error(`console.error called: ${String(args[0])}`);
};

const consoleWarn = console.warn.bind(console);
console.warn = (...args: unknown[]) => {
  consoleWarn(...args);
  throw new Error(`console.warn called: ${String(args[0])}`);
};
