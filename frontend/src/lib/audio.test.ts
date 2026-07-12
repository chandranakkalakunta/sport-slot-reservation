import { describe, expect, it } from "vitest";

import { base64ToBlob } from "./audio";

// jsdom's Blob polyfill doesn't implement .text()/.arrayBuffer() — read
// contents back out via FileReader instead, which jsdom does support.
function readBlobAsText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

describe("base64ToBlob", () => {
  it("decodes a base64 string into a Blob with the given mime type", async () => {
    const original = "hello world";
    const base64 = btoa(original);

    const blob = base64ToBlob(base64, "audio/mpeg");

    expect(blob.type).toBe("audio/mpeg");
    expect(blob.size).toBe(original.length);
    expect(await readBlobAsText(blob)).toBe(original);
  });

  it("handles an empty base64 string", () => {
    const blob = base64ToBlob("", "audio/mpeg");
    expect(blob.size).toBe(0);
  });
});
