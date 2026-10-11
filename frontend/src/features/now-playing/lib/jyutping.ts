/** "haang4 gwo3" → syllables with their tone digit split off, so the tone can be drawn
 *  small and raised (haang⁴ gwo³). Words that aren't Jyutping (English in a Cantonese
 *  line) come through with no tone. */
export function jyutpingSyllables(text: string): { base: string; tone: string }[] {
  return text
    .split(" ")
    .filter(Boolean)
    .map((word) => {
      const m = /^([a-z]+)([1-6])$/.exec(word);
      return m ? { base: m[1], tone: m[2] } : { base: word, tone: "" };
    });
}
