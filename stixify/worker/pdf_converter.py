from pathlib import Path
import shutil
import subprocess
import sys
from mistune import markdown
import pandas as pd
from PIL import Image


class ConversionError(Exception):
    pass


def convert_with_libreoffice(input_file: Path, output_file: Path):
    subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_file.parent),
            str(input_file),
        ],
        check=True,
    )
    # LibreOffice writes to <same-name>.pdf in same dir
    converted_file = output_file.parent / (input_file.stem + ".pdf")
    if converted_file != output_file:
        converted_file.rename(output_file)


def convert_image_to_pdf(input_file: Path, output_file: Path):
    image = Image.open(input_file).convert("RGB")
    image.save(output_file, "PDF")


def convert_csv_to_pdf(input_file: Path, output_file: Path):
    df = pd.read_csv(input_file)
    html = df.to_html(index=False)
    temp_html = output_file.with_suffix(".step.html")
    temp_html.write_text(html, encoding="utf-8")
    convert_with_libreoffice(temp_html, output_file)
    temp_html.unlink()


def convert_md_to_pdf(input_file: Path, output_file: Path):
    html = markdown(input_file.read_text())
    temp_html = output_file.with_suffix(".step.html")
    temp_html.write_text(html, encoding="utf-8")
    convert_with_libreoffice(temp_html, output_file)
    temp_html.unlink()


def make_conversion(input_file: Path, output_file: Path):
    input_file = Path(input_file)
    output_file = Path(output_file)
    ext = input_file.suffix.lower()

    doc_formats = {".doc", ".ppt", ".xls", ".odt", ".pptx", ".xlsx"}
    pandoc_formats = {".docx", ".txt", ".html", ".htm"}
    markdown_formats = {".md", ".markdown"}
    image_formats = {".jpg", ".jpeg", ".png", ".webp"}
    csv_formats = {".csv", ".tsv"}
    doc_formats = doc_formats.union(pandoc_formats)

    try:
        if ext in doc_formats:
            convert_with_libreoffice(input_file, output_file)
        elif ext in image_formats:
            convert_image_to_pdf(input_file, output_file)
        elif ext in csv_formats:
            convert_csv_to_pdf(input_file, output_file)
        elif ext in markdown_formats:
            convert_md_to_pdf(input_file, output_file)
        elif ext == ".pdf":
            shutil.copy(input_file, output_file)
        else:
            raise ConversionError(f"Unsupported file extension: {ext}")
    except Exception as e:
        raise ConversionError(f"failed to convert {input_file.name}") from e
    return output_file


def convert_mhtml_to_pdf(input_file: Path):
    from playwright.sync_api import sync_playwright

    input_file = Path(input_file)
    input_file = Path(input_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = f"file://{input_file.resolve()}"
        page.goto(url, wait_until="domcontentloaded")
        dimensions = page.evaluate(
            """
        function(){
            const rect = document.body.getBoundingClientRect();
            return {
                "width": rect.width.toString(),
                "height": rect.height.toString(),
            }
        }
        """
        )
        pdf_bytes = page.pdf(**dimensions)
        browser.close()
        return bytes(pdf_bytes)
