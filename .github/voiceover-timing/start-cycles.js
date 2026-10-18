// Times guidepup's voiceOver.start() and stop() over several cycles.
// Usage: node start-cycles.js <path to built lib> [cycles]
const { voiceOver } = require(require("path").resolve(process.argv[2]));
const cycles = Number(process.argv[3] || 5);

(async () => {
  for (let i = 1; i <= cycles; i++) {
    const t0 = Date.now();
    try {
      await voiceOver.start();
    } catch (error) {
      console.log(`cycle ${i}: start FAILED after ${((Date.now() - t0) / 1000).toFixed(1)}s: ${error.message.split("\n")[0]} | ${error.cause?.message?.split("\n")[0]}`);
      continue;
    }
    const started = (Date.now() - t0) / 1000;
    let phrase;
    try {
      await voiceOver.next();
      phrase = await voiceOver.lastSpokenPhrase();
    } catch (error) {
      phrase = `next() failed: ${error.cause?.message?.split("\n")[1] ?? error.message}`;
    }
    const t1 = Date.now();
    await voiceOver.stop();
    console.log(`cycle ${i}: start ${started.toFixed(1)}s, stop ${((Date.now() - t1) / 1000).toFixed(1)}s, spoke "${phrase.slice(0, 50)}"`);
  }
})();
