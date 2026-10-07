import { describe, expect, it } from "vitest";
import { detectLang } from "./index";

describe("detectLang", () => {
  it("follows the browser's first English or Chinese language", () => {
    expect(detectLang(["en-US", "zh-CN"])).toBe("en");
    expect(detectLang(["zh-CN", "en-US"])).toBe("zh");
    expect(detectLang(["zh-TW"])).toBe("zh");
    expect(detectLang(["fr-FR", "zh-CN", "en"])).toBe("zh");
    expect(detectLang(["ja-JP", "fr"])).toBe("en");
    expect(detectLang([])).toBe("en");
  });
});
