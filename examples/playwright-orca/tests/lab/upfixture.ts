// Lab (untracked): upstream's orcaTest plus Orca test logs + timeline markers per test.
import { begin, end } from "./fidelity";
import { orcaTest } from "../../orca-test";

export const labTest = orcaTest.extend<{ labLogs: void }>({
  labLogs: [
    async ({ orca }, use, info) => {
      await begin(info, orca);
      await use();
      await end(info, orca);
    },
    { auto: true },
  ],
});
export { labTest as orcaTest };
