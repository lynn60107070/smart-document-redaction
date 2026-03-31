"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type {
  AnalyzeResponse,
  PdfRedactResult,
  PreviewMappedEntity,
  RedactionEntity,
  RedactionResult,
  RedactionSession,
} from "./types";

function migrateStoredSession(raw: RedactionSession): RedactionSession {
  let session = { ...raw };
  if (!session.inputMode) {
    session.inputMode = session.documentId ? "pdf" : "text";
  }
  const r = session.result;
  if (r && typeof r === "object" && !("kind" in r) && "downloadUrl" in r) {
    session = {
      ...session,
      result: { kind: "pdf", ...(r as Omit<PdfRedactResult, "kind">) },
    };
  }
  return session;
}

type SessionContextValue = {
  session: RedactionSession | null;
  loading: boolean;
  setAnalysis: (analysis: AnalyzeResponse) => void;
  setEntities: (entities: RedactionEntity[]) => void;
  setMappedEntities: (mappedEntities: PreviewMappedEntity[]) => void;
  setResult: (result: RedactionResult) => void;
  clearSession: () => void;
};

const STORAGE_KEY = "redactinator-session";

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<RedactionSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setSession(migrateStoredSession(JSON.parse(raw) as RedactionSession));
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loading) {
      return;
    }
    if (session) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [loading, session]);

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      loading,
      setAnalysis: (analysis) =>
        setSession({
          inputMode: analysis.inputMode ?? (analysis.documentId ? "pdf" : "text"),
          documentId: analysis.documentId,
          filename: analysis.filename,
          text: analysis.text,
          pageCount: analysis.pageCount,
          entities: analysis.entities,
          mappedEntities: analysis.mappedEntities,
          pages: analysis.pages,
          result: null,
        }),
      setEntities: (entities) =>
        setSession((current) =>
          current
            ? {
                ...current,
                entities,
                mappedEntities: current.mappedEntities.map((mapped) => {
                  const matching = entities.find(
                    (entity) =>
                      entity.start === mapped.start &&
                      entity.end === mapped.end &&
                      entity.label === mapped.label &&
                      entity.text === mapped.text
                  );
                  return matching ? { ...mapped, enabled: matching.enabled } : mapped;
                }),
                result: null,
              }
            : current
        ),
      setMappedEntities: (mappedEntities) =>
        setSession((current) =>
          current ? { ...current, mappedEntities, result: null } : current
        ),
      setResult: (result) =>
        setSession((current) => (current ? { ...current, result } : current)),
      clearSession: () => setSession(null),
    }),
    [loading, session]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}
