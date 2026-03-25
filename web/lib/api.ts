import type {
  AnalyzeResponse,
  PreviewMappedEntity,
  RedactResponse,
  RedactionEntity,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "Request failed.";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // ignore non-json responses
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function analyzePdf(file: File): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: formData,
  });

  return parseJson<AnalyzeResponse>(response);
}

export async function redactPdf(
  documentId: string,
  entities: RedactionEntity[]
): Promise<RedactResponse> {
  const response = await fetch(`${API_BASE}/api/redact`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      documentId,
      entities,
    }),
  });

  return parseJson<RedactResponse>(response);
}

export async function mapEntities(
  documentId: string,
  entities: RedactionEntity[]
): Promise<{ mappedEntities: PreviewMappedEntity[]; text: string }> {
  const response = await fetch(`${API_BASE}/api/map`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      documentId,
      entities,
    }),
  });

  return parseJson<{ mappedEntities: PreviewMappedEntity[]; text: string }>(response);
}
