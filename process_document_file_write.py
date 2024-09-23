from vault_client import get_vault_secrets
from typing import Optional, Sequence
from google.api_core.client_options import ClientOptions
from google.cloud import documentai
import argparse
import mimetypes
import os

location = "eu"
processor_version = "rc"

# Main function to process the document using Document AI's OCR capabilities
def process_document_ocr_sample(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version: str,
    file_path: str,
    mime_type: str,
) -> None:
    # Determine if the file is a PDF
    is_pdf = mime_type == "application/pdf"

    # Set enable_native_pdf_parsing based on the file type
    process_options = documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(
            enable_native_pdf_parsing=is_pdf,
            enable_image_quality_scores=True,
            enable_symbol=True,
            premium_features=documentai.OcrConfig.PremiumFeatures(
                compute_style_info=True,
                enable_math_ocr=False,
                enable_selection_mark_detection=True,
            ),
        )
    )

    # Process the document using Document AI
    document = process_document(
        project_id,
        location,
        processor_id,
        processor_version,
        file_path,
        mime_type,
        process_options=process_options,
    )

    # Write output to a file
    with open("document_output.txt", "w", encoding='utf-8') as f:
        text = document.text
        f.write(f"Full document text: {text}\n")
        f.write(f"There are {len(document.pages)} page(s) in this document.\n\n")

        for page in document.pages:
            f.write(f"Page {page.page_number}:\n")
            write_page_dimensions(f, page.dimension)
            write_detected_languages(f, page.detected_languages)
            write_blocks(f, page.blocks, text)
            write_paragraphs(f, page.paragraphs, text)
            write_lines(f, page.lines, text)
            write_tokens(f, page.tokens, text)

            if page.symbols:
                write_symbols(f, page.symbols, text)

            if page.image_quality_scores:
                write_image_quality_scores(f, page.image_quality_scores)

            if page.visual_elements:
                write_visual_elements(f, page.visual_elements, text)

# Helper functions that write structured data to the file

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process a document using Google Cloud Document AI.')
    parser.add_argument('file_path', type=str, help='Path to the file to process (PDF or image).')
    return parser.parse_args()

def write_page_dimensions(f, dimension: documentai.Document.Page.Dimension) -> None:
    f.write(f"    Width: {str(dimension.width)}\n")
    f.write(f"    Height: {str(dimension.height)}\n")

def write_detected_languages(
    f, detected_languages: Sequence[documentai.Document.Page.DetectedLanguage]
) -> None:
    f.write("    Detected languages:\n")
    for lang in detected_languages:
        f.write(f"        {lang.language_code} ({lang.confidence:.1%} confidence)\n")

def write_blocks(f, blocks: Sequence[documentai.Document.Page.Block], text: str) -> None:
    num_blocks = len(blocks)
    f.write(f"    {num_blocks} blocks detected:\n")
    if num_blocks > 0:
        first_block_text = layout_to_text(blocks[0].layout, text)
        f.write(f"        First text block: {repr(first_block_text)}\n")
        last_block_text = layout_to_text(blocks[-1].layout, text)
        f.write(f"        Last text block: {repr(last_block_text)}\n")
    else:
        f.write("        No blocks detected.\n")

def write_paragraphs(
    f, paragraphs: Sequence[documentai.Document.Page.Paragraph], text: str
) -> None:
    num_paragraphs = len(paragraphs)
    f.write(f"    {num_paragraphs} paragraphs detected:\n")
    if num_paragraphs > 0:
        first_paragraph_text = layout_to_text(paragraphs[0].layout, text)
        f.write(f"        First paragraph text: {repr(first_paragraph_text)}\n")
        last_paragraph_text = layout_to_text(paragraphs[-1].layout, text)
        f.write(f"        Last paragraph text: {repr(last_paragraph_text)}\n")
    else:
        f.write("        No paragraphs detected.\n")

def write_lines(f, lines: Sequence[documentai.Document.Page.Line], text: str) -> None:
    num_lines = len(lines)
    f.write(f"    {num_lines} lines detected:\n")
    if num_lines > 0:
        first_line_text = layout_to_text(lines[0].layout, text)
        f.write(f"        First line text: {repr(first_line_text)}\n")
        last_line_text = layout_to_text(lines[-1].layout, text)
        f.write(f"        Last line text: {repr(last_line_text)}\n")
    else:
        f.write("        No lines detected.\n")

def write_tokens(f, tokens: Sequence[documentai.Document.Page.Token], text: str) -> None:
    num_tokens = len(tokens)
    f.write(f"    {num_tokens} tokens detected:\n")
    if num_tokens > 0:
        first_token_text = layout_to_text(tokens[0].layout, text)
        first_token_break_type = tokens[0].detected_break.type_.name if tokens[0].detected_break else "Unknown"
        f.write(f"        First token text: {repr(first_token_text)}\n")
        f.write(f"        First token break type: {repr(first_token_break_type)}\n")
        if tokens[0].style_info:
            write_style_info(f, tokens[0].style_info)

        last_token_text = layout_to_text(tokens[-1].layout, text)
        last_token_break_type = tokens[-1].detected_break.type_.name if tokens[-1].detected_break else "Unknown"
        f.write(f"        Last token text: {repr(last_token_text)}\n")
        f.write(f"        Last token break type: {repr(last_token_break_type)}\n")
        if tokens[-1].style_info:
            write_style_info(f, tokens[-1].style_info)
    else:
        f.write("        No tokens detected.\n")

def write_symbols(
    f, symbols: Sequence[documentai.Document.Page.Symbol], text: str
) -> None:
    num_symbols = len(symbols)
    f.write(f"    {num_symbols} symbols detected:\n")
    if num_symbols > 0:
        first_symbol_text = layout_to_text(symbols[0].layout, text)
        f.write(f"        First symbol text: {repr(first_symbol_text)}\n")
        last_symbol_text = layout_to_text(symbols[-1].layout, text)
        f.write(f"        Last symbol text: {repr(last_symbol_text)}\n")
    else:
        f.write("        No symbols detected.\n")

def write_image_quality_scores(
    f, image_quality_scores: documentai.Document.Page.ImageQualityScores
) -> None:
    f.write(f"    Quality score: {image_quality_scores.quality_score:.1%}\n")
    f.write("    Detected defects:\n")
    for detected_defect in image_quality_scores.detected_defects:
        f.write(f"        {detected_defect.type_}: {detected_defect.confidence:.1%}\n")

def write_style_info(f, style_info: documentai.Document.Page.Token.StyleInfo) -> None:
    f.write(f"           Font Size: {style_info.font_size}pt\n")
    f.write(f"           Font Type: {style_info.font_type}\n")
    f.write(f"           Bold: {style_info.bold}\n")
    f.write(f"           Italic: {style_info.italic}\n")
    f.write(f"           Underlined: {style_info.underlined}\n")
    f.write(f"           Handwritten: {style_info.handwritten}\n")
    f.write(f"           Text Color (RGBa): {style_info.text_color.red}, {style_info.text_color.green}, {style_info.text_color.blue}, {style_info.text_color.alpha}\n")

def write_visual_elements(
    f, visual_elements: Sequence[documentai.Document.Page.VisualElement], text: str
) -> None:
    checkboxes = [x for x in visual_elements if "checkbox" in x.type]
    math_symbols = [x for x in visual_elements if x.type == "math_formula"]

    if checkboxes:
        num_checkboxes = len(checkboxes)
        f.write(f"    {num_checkboxes} checkboxes detected:\n")
        f.write(f"        First checkbox: {repr(checkboxes[0].type)}\n")
        f.write(f"        Last checkbox: {repr(checkboxes[-1].type)}\n")
    else:
        f.write("        No checkboxes detected.\n")

    if math_symbols:
        num_math_symbols = len(math_symbols)
        f.write(f"    {num_math_symbols} math symbols detected:\n")
        if num_math_symbols > 0:
            first_math_symbol_text = layout_to_text(math_symbols[0].layout, text)
            f.write(f"        First math symbol: {repr(first_math_symbol_text)}\n")
    else:
        f.write("        No math symbols detected.\n")

# Function to call Document AI for processing
def process_document(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version: str,
    file_path: str,
    mime_type: str,
    process_options: Optional[documentai.ProcessOptions] = None,
) -> documentai.Document:
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    )

    name = client.processor_version_path(
        project_id, location, processor_id, processor_version
    )

    # Read the file into memory
    with open(file_path, "rb") as image:
        image_content = image.read()

    # Configure the process request
    request = documentai.ProcessRequest(
        name=name,
        raw_document=documentai.RawDocument(content=image_content, mime_type=mime_type),
        process_options=process_options,
    )

    result = client.process_document(request=request)
    return result.document

def layout_to_text(layout: documentai.Document.Page.Layout, text: str) -> str:
    if layout.text_anchor and layout.text_anchor.text_segments:
        return "".join(
            text[int(segment.start_index): int(segment.end_index)]
            for segment in layout.text_anchor.text_segments
        )
    return ""

project_id, processor_id = get_vault_secrets()

if project_id and processor_id:

    args = parse_arguments()

    # Determine the MIME type based on the file extension
    mime_type, _ = mimetypes.guess_type(args.file_path)

    # If MIME type couldn't be determined, default to application/pdf
    if mime_type is None:
        print("Could not determine MIME type. Defaulting to application/pdf.")
        mime_type = "application/pdf"

    # Convert MIME type to lowercase to avoid case sensitivity issues
    mime_type = mime_type.lower()

    process_document_ocr_sample(
        project_id=project_id,
        location=location,
        processor_id=processor_id,
        processor_version=processor_version,
        file_path=args.file_path,
        mime_type=mime_type
    )
else:
    print("Failed to retrieve Vault secrets.")
