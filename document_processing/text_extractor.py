from __future__ import annotations

from typing import List, Tuple, Union, IO

from .pdf_utils import ExtractedDocument, ExtractedPage, WordBox, PAGE_SEPARATOR, open_pdf


def extract_text(pdf_file: Union[str, bytes, IO[bytes]]) -> ExtractedDocument:
    """
    Extract structured text and word-level bounding boxes from a PDF.

    Returns:
        ExtractedDocument with:
        - full concatenated text across pages
        - per-page text and offsets
        - flat word index with global offsets
    """

    doc = open_pdf(pdf_file)
    try:
        full_text_parts: List[str] = []
        pages: List[ExtractedPage] = []
        word_index: List[WordBox] = []

        page_count = doc.page_count
        full_text_len = 0

        for page_index in range(page_count):
            page = doc.load_page(page_index)
            words = page.get_text("words")

            # words: (x0, y0, x1, y1, text, block_no, line_no, word_no)
            words_sorted = sorted(words, key=lambda w: (w[5], w[6], w[7]))

            page_text_parts: List[str] = []
            page_words: List[WordBox] = []
            page_offset_start = full_text_len
            page_text_len = 0

            # Group words by (block_no, line_no)
            current_key: Tuple[int, int] | None = None
            line_words: List[Tuple[float, float, float, float, str]] = []

            def flush_line() -> None:
                nonlocal page_text_parts, page_words, page_text_len
                if not line_words:
                    return

                if page_text_len > 0:
                    page_text_parts.append("\n")
                    page_text_len += 1

                line_text = ""
                line_cursor = 0
                for idx, (x0, y0, x1, y1, text) in enumerate(line_words):
                    if idx > 0:
                        line_text += " "
                        line_cursor += 1
                    start = page_offset_start + page_text_len + line_cursor
                    end = start + len(text)
                    page_words.append(
                        WordBox(
                            text=text,
                            start=start,
                            end=end,
                            bbox=(x0, y0, x1, y1),
                            page_index=page_index,
                        )
                    )
                    line_text += text
                    line_cursor += len(text)

                page_text_parts.append(line_text)
                page_text_len += len(line_text)

            for w in words_sorted:
                key = (w[5], w[6])
                if current_key is None:
                    current_key = key
                if key != current_key:
                    flush_line()
                    line_words = []
                    current_key = key

                line_words.append((w[0], w[1], w[2], w[3], w[4]))

            flush_line()

            page_text = "".join(page_text_parts)
            pages.append(
                ExtractedPage(
                    page_index=page_index,
                    text=page_text,
                    char_offset_start=page_offset_start,
                    words=page_words,
                )
            )

            word_index.extend(page_words)
            full_text_parts.append(page_text)
            full_text_len += len(page_text)

            if page_index < page_count - 1:
                full_text_parts.append(PAGE_SEPARATOR)
                full_text_len += len(PAGE_SEPARATOR)

        full_text = "".join(full_text_parts)
        return ExtractedDocument(text=full_text, pages=pages, word_index=word_index)
    finally:
        doc.close()
