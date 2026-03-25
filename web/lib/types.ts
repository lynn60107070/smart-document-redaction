export type EntitySource = "model" | "manual";

export type RedactionEntity = {
  text: string;
  label: string;
  start: number;
  end: number;
  enabled: boolean;
  source: EntitySource;
};

export type PreviewPage = {
  pageIndex: number;
  width: number;
  height: number;
  imageUrl: string;
};

export type PreviewMappedEntity = {
  text: string;
  label: string;
  start: number;
  end: number;
  enabled: boolean;
  source: EntitySource;
  page: number;
  rect: [number, number, number, number];
};

export type AnalyzeResponse = {
  documentId: string;
  filename: string;
  text: string;
  pageCount: number;
  entities: RedactionEntity[];
  mappedEntities: PreviewMappedEntity[];
  pages: PreviewPage[];
};

export type RedactResponse = {
  filename: string;
  outputToken: string;
  downloadUrl: string;
  previewBaseUrl: string;
  entityCount: number;
  summary: Record<string, number>;
};

export type RedactionSession = {
  documentId: string;
  filename: string;
  text: string;
  pageCount: number;
  entities: RedactionEntity[];
  mappedEntities: PreviewMappedEntity[];
  pages: PreviewPage[];
  result: RedactResponse | null;
};
