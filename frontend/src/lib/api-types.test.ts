import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";
// @ts-expect-error plain .mjs script, no type declarations
import { generate } from "../../scripts/gen-api.mjs";

it("api-types.ts matches openapi.json (else run `npm run gen:api`)", async () => {
  const committed = await readFile(new URL("./api-types.ts", import.meta.url), "utf8");
  expect(committed).toBe(await generate());
});
