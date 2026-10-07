import { Fragment, type ReactNode } from "react";

/** "Click **Save**" → Click <b>Save</b>; {name} placeholders filled from `slots`
 *  (strings or elements, e.g. a link). Enough markup for translated UI copy. */
export function rich(text: string, slots: Record<string, ReactNode> = {}): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|\{\w+\})/).map((part, i) => {
    if (part.startsWith("**")) return <b key={i}>{part.slice(2, -2)}</b>;
    const slot = part.match(/^\{(\w+)\}$/);
    if (slot && slot[1] in slots) return <Fragment key={i}>{slots[slot[1]]}</Fragment>;
    return part;
  });
}

/** Plain-string placeholder fill, for attributes and confirm() dialogs. */
export function fill(text: string, values: Record<string, string>): string {
  return text.replace(/\{(\w+)\}/g, (m, k) => values[k] ?? m);
}
