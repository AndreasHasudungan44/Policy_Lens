from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = False  ### Most EFRAG reports are text-native PDFs, no need for OCR. 
                                 ### Set to True if pdf's are scanned images base

converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF],
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options
        )
    }
)

input_dir = Path("data/bronze/raw_efrag_pdf")
output_dir = Path("data/silver/md_text")
output_dir.mkdir(parents=True, exist_ok=True)

pdf_files = [p for p in sorted(input_dir.rglob("*.pdf")) if p.is_file()]

if not pdf_files:
    print(f"No PDF files found in {input_dir.resolve()}")
else:
    for result in converter.convert_all(pdf_files):
        try:
            src = Path(result.input.file)
            md_path = output_dir / f"{src.stem}.md"
            md_path.write_text(
                result.document.export_to_markdown(),
                encoding="utf-8"
            )
            print(f"OK: {src.name}")
        except Exception as e:
            print(f"FAILED: {getattr(result.input, 'file', 'unknown')} -> {type(e).__name__}: {e}")