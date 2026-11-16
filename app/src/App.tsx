import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { configError, supabase } from "./supabase";
import Login from "./Login";
import AddWord from "./AddWord";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (configError) return setLoading(false);
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  if (configError) {
    return (
      <main className="shell">
        <p className="error" role="alert">{configError}</p>
      </main>
    );
  }
  if (loading) return <main className="shell" aria-busy="true" />;

  return (
    <main className="shell">
      <header className="top">
        <span className="brand">Words</span>
        {session && (
          <button className="link" onClick={() => supabase.auth.signOut()}>
            Sign out
          </button>
        )}
      </header>
      {session ? <AddWord /> : <Login />}
    </main>
  );
}
