import { useState, type FormEvent } from "react";
import { FunctionsHttpError } from "@supabase/supabase-js";
import { CARD_FIELDS, supabase, type FieldKey, type GeneratedCard } from "./supabase";

type Step = "word" | "review" | "saved";

const LANGUAGES = ["French", "Spanish", "German", "Italian", "Portuguese", "Japanese"];

async function errorMessage(err: unknown): Promise<string> {
  // Edge Function errors carry our { error } JSON body; surface it.
  if (err instanceof FunctionsHttpError) {
    try {
      const body = await err.context.json();
      if (body?.error) return body.error;
    } catch { /* fall through */ }
  }
  return err instanceof Error ? err.message : String(err);
}

export default function AddWord() {
  const [step, setStep] = useState<Step>("word");
  const [word, setWord] = useState("");
  const [language, setLanguage] = useState(() => localStorage.getItem("language") ?? "French");
  const [card, setCard] = useState<GeneratedCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    localStorage.setItem("language", language);
    const { data, error } = await supabase.functions.invoke<GeneratedCard>("generate-word", {
      body: { word: word.trim(), language },
    });
    setBusy(false);
    if (error || !data) return setError(await errorMessage(error ?? new Error("No response")));
    setCard(data);
    setStep("review");
  }

  async function save() {
    if (!card) return;
    setBusy(true);
    setError(null);
    const fields = Object.fromEntries(CARD_FIELDS.map(({ key }) => [key, card[key]]));
    const { error } = await supabase.rpc("save_word", {
      p_language: card.language,
      p_surface_form: card.word,
      p_lemma: card.lemma,
      p_fields: fields,
    });
    setBusy(false);
    if (error) {
      return setError(
        error.code === "23505" ? `“${card.lemma}” is already in your ${card.language} words.` : error.message,
      );
    }
    setStep("saved");
  }

  function startOver() {
    setWord("");
    setCard(null);
    setError(null);
    setStep("word");
  }

  const edit = (key: FieldKey | "lemma", value: string) =>
    setCard((c) => (c ? { ...c, [key]: value } : c));

  return (
    <>
      <ol className="steps" aria-label="Progress">
        {(["word", "review", "saved"] as Step[]).map((s, i) => (
          <li key={s} aria-current={s === step ? "step" : undefined}>
            {i + 1}. {s === "word" ? "Word" : s === "review" ? "Card" : "Saved"}
          </li>
        ))}
      </ol>

      {step === "word" && (
        <form className="panel" onSubmit={generate}>
          <h1>Add a word</h1>
          <label>
            Word
            <input autoFocus autoCapitalize="off" autoCorrect="off" spellCheck={false}
              required maxLength={100} value={word} placeholder="e.g. dépaysement"
              onChange={(e) => setWord(e.target.value)} />
          </label>
          <label>
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary" disabled={busy || !word.trim()}>
            {busy ? "Generating…" : "Generate card"}
          </button>
        </form>
      )}

      {step === "review" && card && (
        <section className="panel">
          <p className="eyebrow">{card.language}</p>
          <h1 className="headword">{card.word}</h1>
          <label className="lemma">
            Dictionary form
            <input value={card.lemma} onChange={(e) => edit("lemma", e.target.value)} />
          </label>

          {CARD_FIELDS.map(({ key, label }) => (
            <label key={key} className="field">
              {label}
              <textarea rows={2} value={card[key]} placeholder="None found — add your own"
                onChange={(e) => edit(key, e.target.value)} />
            </label>
          ))}

          {error && <p className="error" role="alert">{error}</p>}
          <div className="row">
            <button className="secondary" onClick={startOver} disabled={busy}>Discard</button>
            <button className="primary" onClick={save} disabled={busy || !card.lemma.trim()}>
              {busy ? "Saving…" : "Save card"}
            </button>
          </div>
        </section>
      )}

      {step === "saved" && card && (
        <section className="panel center">
          <h1>Saved</h1>
          <p>
            <strong>{card.word}</strong> is in your {card.language} words, and its card is due for review now.
          </p>
          <button className="primary" onClick={startOver}>Add another word</button>
        </section>
      )}
    </>
  );
}
