export type EntitySource = "model" | "manual";

export type InputMode = "pdf" | "text";

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
  inputMode: InputMode;
  documentId: string;
  filename: string;
  text: string;
  pageCount: number;
  entities: RedactionEntity[];
  mappedEntities: PreviewMappedEntity[];
  pages: PreviewPage[];
};

export type PdfRedactResult = {
  kind: "pdf";
  filename: string;
  outputToken: string;
  downloadUrl: string;
  previewBaseUrl: string;
  entityCount: number;
  summary: Record<string, number>;
};

export type TextRedactResult = {
  kind: "text";
  redactedText: string;
  entityCount: number;
  summary: Record<string, number>;
};

export type RedactionResult = PdfRedactResult | TextRedactResult;

export type RedactionSession = {
  inputMode: InputMode;
  documentId: string;
  filename: string;
  text: string;
  pageCount: number;
  entities: RedactionEntity[];
  mappedEntities: PreviewMappedEntity[];
  pages: PreviewPage[];
  result: RedactionResult | null;
};
