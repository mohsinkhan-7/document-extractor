from .extractor_service import extract_card_data
from .pdf_ocr_service import (
    pdf_to_word_chapters,
    extract_chapters_as_json,
    chapters_json_to_word,
    export_chapters_to_zip,
    extract_toc_entries,
    export_chapters_to_zip_from_toc,
)

class CardController:
    @staticmethod
    def process_card(image_path: str):
        return extract_card_data(image_path)

class PDFController:
    @staticmethod
    def pdf_to_word(pdf_path: str, output_docx: str, start_page: int = 1):
        return pdf_to_word_chapters(pdf_path, output_docx, start_page=start_page)

    @staticmethod
    def extract_chapters(pdf_path: str, start_page: int = 1):
        return extract_chapters_as_json(pdf_path, start_page=start_page)

    @staticmethod
    def chapters_to_word(chapters: list, output_docx: str):
        return chapters_json_to_word(chapters, output_docx)

    @staticmethod
    def chapters_zip(pdf_path: str, zip_path: str, start_page: int = 1):
        return export_chapters_to_zip(pdf_path, zip_path, start_page=start_page)

    @staticmethod
    def toc_entries(pdf_path: str, toc_page: int = 5):
        return extract_toc_entries(pdf_path, toc_page=toc_page)

    @staticmethod
    def chapters_zip_from_toc(pdf_path: str, zip_path: str, toc_page: int = 5, printed_to_pdf_offset: int = 0):
        return export_chapters_to_zip_from_toc(
            pdf_path, zip_path, toc_page=toc_page, printed_to_pdf_offset=printed_to_pdf_offset
        )
