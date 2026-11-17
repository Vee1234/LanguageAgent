import { describe, expect, it, vi } from "vitest";
import {
  normalizeKey,
  resolveWord,
  validate,
  type CardFields,
  type ResolveDeps,
  type SharedWord,
} from "../../../supabase/functions/generate-word/logic";

const fields = (over: Partial<CardFields> = {}): CardFields => ({
  lemma: "maison",
  definition: "Bâtiment d'habitation.",
  example: "Ma maison est grande.",
  register: "Casual",
  emotional_colour: "chaleur",
  usage_conditions: "courant",
  notable_use: "",
  lyric: "",
  ...over,
});

const shared = (lemma = "maison"): SharedWord => ({
  id: `w-${lemma}`,
  language: "French",
  lemma,
  notes: { definition: "Bâtiment d'habitation." },
});

function deps(over: Partial<ResolveDeps> = {}): ResolveDeps {
  return {
    findByForm: vi.fn().mockResolvedValue(null),
    findByLemma: vi.fn().mockResolvedValue(null),
    generate: vi.fn().mockResolvedValue(fields()),
    insertWord: vi.fn().mockImplementation(async (_lang: string, f: CardFields) => shared(f.lemma)),
    // By default this request wins: the form ends up mapped to the word it offered.
    addForm: vi.fn().mockImplementation(async (_lang: string, _form: string, wordId: string) => wordId),
    findById: vi.fn().mockImplementation(async (id: string) => shared(id.replace(/^w-/, ""))),
    ...over,
  };
}

describe("normalizeKey", () => {
  it("trims, lower-cases and NFC-normalises so lookups match regardless of typing", () => {
    expect(normalizeKey("  Maison ")).toBe("maison");
    expect(normalizeKey("été")).toBe("été"); // decomposed accents → composed
  });
});

describe("resolveWord", () => {
  it("returns a cached word for a form seen before, without calling Gemini", async () => {
    const d = deps({ findByForm: vi.fn().mockResolvedValue(shared()) });

    const result = await resolveWord("Maisons", "French", d);

    expect(result).toEqual({ word: shared(), source: "cache" });
    expect(d.findByForm).toHaveBeenCalledWith("French", "maisons");
    expect(d.generate).not.toHaveBeenCalled();
    expect(d.insertWord).not.toHaveBeenCalled();
  });

  it("generates and stores a new word once, remembering both the typed form and the lemma", async () => {
    const d = deps({ generate: vi.fn().mockResolvedValue(fields({ lemma: "maison" })) });

    const result = await resolveWord("maisons", "French", d);

    expect(result.source).toBe("generated");
    expect(d.generate).toHaveBeenCalledTimes(1);
    expect(d.insertWord).toHaveBeenCalledWith("French", fields({ lemma: "maison" }));
    expect(d.addForm).toHaveBeenCalledWith("French", "maisons", "w-maison");
    expect(d.addForm).toHaveBeenCalledWith("French", "maison", "w-maison");
  });

  it("reuses an existing word when Gemini's lemma is already cached, and remembers the new form", async () => {
    const d = deps({ findByLemma: vi.fn().mockResolvedValue(shared()) });

    const result = await resolveWord("maisons", "French", d);

    expect(result).toEqual({ word: shared(), source: "lemma" });
    expect(d.findByLemma).toHaveBeenCalledWith("French", "maison");
    expect(d.insertWord).not.toHaveBeenCalled();
    expect(d.addForm).toHaveBeenCalledWith("French", "maisons", "w-maison");
  });
});

describe("validate", () => {
  it("turns NONE into an empty string and rejects an unknown register", () => {
    expect(validate({ ...fields(), notable_use: " NONE " }).notable_use).toBe("");
    expect(() => validate({ ...fields(), register: "Slangy" })).toThrow(/register/);
  });

  it("rejects a response with a missing field", () => {
    const { lyric: _lyric, ...partial } = fields();
    expect(() => validate(partial)).toThrow(/lyric/);
  });
});

describe("resolveWord under concurrency (Bug 12, optimistic)", () => {
  it("returns the winner's word when another request registered the same new form first", async () => {
    // This request generated "maisonnette", but a concurrent one already mapped "maisons" to "maison".
    const d = deps({
      generate: vi.fn().mockResolvedValue(fields({ lemma: "maisonnette" })),
      addForm: vi.fn().mockImplementation(async (_l: string, form: string, wordId: string) =>
        form === "maisons" ? "w-maison" : wordId),
    });

    const result = await resolveWord("maisons", "French", d);

    expect(result).toEqual({ word: shared("maison"), source: "cache" });
    expect(d.findById).toHaveBeenCalledWith("w-maison");
  });

  it("returns the winner's word when the lemma was already cached but the form was claimed meanwhile", async () => {
    const d = deps({
      findByLemma: vi.fn().mockResolvedValue(shared("maison")),
      addForm: vi.fn().mockResolvedValue("w-other"),
    });

    const result = await resolveWord("maisons", "French", d);

    expect(result.word).toEqual(shared("other"));
    expect(result.source).toBe("cache");
  });

  it("keeps its own word when it wins the race", async () => {
    const result = await resolveWord("maisons", "French", deps());
    expect(result).toEqual({ word: shared("maison"), source: "generated" });
  });
});
