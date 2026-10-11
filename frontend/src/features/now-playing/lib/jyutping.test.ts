import { describe, expect, it } from "vitest";
import { jyutpingSyllables } from "./jyutping";

describe("jyutpingSyllables", () => {
  it("splits the tone digit off each syllable and leaves other words alone", () => {
    expect(jyutpingSyllables("Hey haang4 gwo3")).toEqual([
      { base: "Hey", tone: "" },
      { base: "haang", tone: "4" },
      { base: "gwo", tone: "3" },
    ]);
  });
});
