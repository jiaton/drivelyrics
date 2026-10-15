import type { components } from "./api-types";

/** A request/response body type, generated from the backend's OpenAPI document. */
export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];
