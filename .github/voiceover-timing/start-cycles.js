// Times guidepup start()/stop(). Usage: node start-cycles.js <lib> <label> <cycles>
const { voiceOver } = require(require("path").resolve(process.argv[2]));
const label = process.argv[3], cycles = Number(process.argv[4] || 20);
const med = (a) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
(async () => {
  const starts = [], stops = [], fails = [];
  let greetings = 0, spoke = 0;
  for (let i = 1; i <= cycles; i++) {
    const t0 = Date.now();
    try { await voiceOver.start(); }
    catch (e) { fails.push(`${i}: ${e.message.split("\n")[0]} | ${e.cause?.message?.split("\n")[0]}`); console.log(`${label} ${i}: START FAILED ${fails.at(-1)}`); continue; }
    const st = (Date.now() - t0) / 1000; starts.push(st);
    let first = "", after = "";
    try { first = await voiceOver.lastSpokenPhrase(); } catch {}
    try { await voiceOver.next(); after = await voiceOver.lastSpokenPhrase(); } catch (e) { after = `next() failed`; }
    if (/Guidepup/i.test(first)) greetings++;
    if (after && after !== "next() failed") spoke++;
    const t1 = Date.now();
    try { await voiceOver.stop(); } catch (e) { console.log(`${label} ${i}: STOP FAILED ${e.message}`); }
    stops.push((Date.now() - t1) / 1000);
    console.log(`${label} ${i}: start ${st.toFixed(1)}s stop ${stops.at(-1).toFixed(1)}s first "${first.slice(0, 40)}" next "${after.slice(0, 40)}"`);
  }
  const f = (a) => a.length ? `min ${Math.min(...a).toFixed(1)} median ${med(a).toFixed(1)} max ${Math.max(...a).toFixed(1)}` : "n/a";
  console.log(`SUMMARY ${label}: ${starts.length}/${cycles} started; start ${f(starts)}; stop ${f(stops)}; greeting "Guidepup" ${greetings}; next() spoke ${spoke}`);
})();
