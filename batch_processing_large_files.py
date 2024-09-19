from vault_client import get_vault_secrets
from typing import Optional, Sequence
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
import argparse
import time

location = "eu"
processor_version = "rc"
mime_type = "application/pdf"

def process_document_ocr_sample(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
    mime_type: str,
) -> None:
    # Optional configurations for Document OCR Processor
    process_options = documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(
            enable_native_pdf_parsing=True,
            enable_image_quality_scores=True,
            enable_symbol=True,
            premium_features=documentai.OcrConfig.PremiumFeatures(
                compute_style_info=True,
                enable_math_ocr=False,
                enable_selection_mark_detection=True,
            ),
        )
    )

    # Start batch processing
    operation = batch_process_document(
        project_id,
        location,
        processor_id,
        processor_version,
        gcs_input_uri,
        gcs_output_uri,
        mime_type,
        process_options=process_options,
    )

    print("Waiting for operation to complete...")
    operation.result(timeout=3600)  # Adjust timeout as needed
    print("Batch processing complete.")

    # Download and process the output files from GCS
    download_and_process_output(gcs_output_uri)

def batch_process_document(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version: str,
    gcs_input_uri: str,
    gcs_output_uri: str,
    mime_type: str,
    process_options: Optional[documentai.ProcessOptions] = None,
):
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    )

    name = client.processor_version_path(
        project_id, location, processor_id, processor_version
    )

    # Configure the batch process request
    input_config = documentai.BatchDocumentsInputConfig(
        gcs_prefix=documentai.GcsPrefix(gcs_uri_prefix=gcs_input_uri)
    )

    output_config = documentai.DocumentOutputConfig(
        gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
            gcs_uri=gcs_output_uri
        )
    )

    request = documentai.BatchProcessRequest(
        name=name,
        input_documents=input_config,
        document_output_config=output_config,
        process_options=process_options,
    )

    operation = client.batch_process_documents(request)
    return operation  # Return the operation to wait on it later

def download_and_process_output(gcs_output_uri: str) -> None:
    storage_client = storage.Client()
    bucket_name, prefix = extract_bucket_and_prefix(gcs_output_uri)
    bucket = storage_client.bucket(bucket_name)
    
    # List blobs in the output folder
    blobs = bucket.list_blobs(prefix=prefix)
    
    # Initialize output file
    with open("document_output.txt", "w", encoding='utf-8') as f:
        for blob in blobs:
            # Process only JSON files within the output folder and ignore non-Document files
            if blob.name.endswith(".json") and 'generated_workspace' not in blob.name and blob.name.startswith(prefix):
                print(f"Processing output file: {blob.name}")
                content = blob.download_as_bytes()
                try:
                    document = documentai.Document.from_json(content)
                except Exception as e:
                    print(f"Error parsing {blob.name}: {e}")
                    continue  # Skip to the next file

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
            else:
                print(f"Skipping non-Document file: {blob.name}")

def extract_bucket_and_prefix(gcs_uri: str):
    if not gcs_uri.startswith("gs://"):
        raise ValueError("Invalid GCS URI: must start with 'gs://'")
    path = gcs_uri[5:]  # Remove 'gs://' prefix
    parts = path.split('/', 1)
    if len(parts) == 1:
        return parts[0], ''
    else:
        return parts[0], parts[1]

# Helper functions that write structured data to the file (same as before)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process a PDF document using Google Cloud Document AI.')
    parser.add_argument('gcs_input_uri', type=str, help='GCS URI of the input document(s).')
    parser.add_argument('gcs_output_uri', type=str, help='GCS URI for the output.')
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
    location = "eu"
    processor_version = "rc"
    mime_type = "application/pdf"

    process_document_ocr_sample(
        project_id=project_id,
        location=location,
        processor_id=processor_id,
        processor_version=processor_version,
        gcs_input_uri=args.gcs_input_uri,
        gcs_output_uri=args.gcs_output_uri,
        mime_type=mime_type
    )
else:
    print("Failed to retrieve Vault secrets.")
