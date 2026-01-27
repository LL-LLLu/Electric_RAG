import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from pdf2image import convert_from_path
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Lazy load PaddleOCR only when needed (it's slow to initialize)
_paddle_ocr = None

def get_paddle_ocr():
    """Lazy initialization of PaddleOCR"""
    global _paddle_ocr
    if _paddle_ocr is None:
        from paddleocr import PaddleOCR
        logger.info("Initializing PaddleOCR (this may take a moment)...")
        _paddle_ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,
            show_log=False
        )
    return _paddle_ocr


class OCRService:
    # Supported image formats
    SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.webp', '.heic', '.heif'}
    SUPPORTED_PDF_EXTENSIONS = {'.pdf'}

    def __init__(self):
        self.dpi = int(os.environ.get("OCR_DPI", 200))  # Lower DPI for faster processing
        self.min_text_threshold = 50  # Minimum characters to consider text extraction successful

    def is_image_file(self, file_path: str) -> bool:
        """Check if file is a supported image format"""
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_IMAGE_EXTENSIONS

    def is_pdf_file(self, file_path: str) -> bool:
        """Check if file is a PDF"""
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_PDF_EXTENSIONS

    def extract_text_from_pdf_direct(self, pdf_path: str) -> List[Dict]:
        """Extract text directly from PDF using PyMuPDF (fast, for vector PDFs)"""
        doc = fitz.open(pdf_path)
        pages_data = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            # Get text blocks with positions for element data
            blocks = page.get_text("dict")["blocks"]
            elements = []

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["text"].strip():
                                bbox = span["bbox"]
                                elements.append({
                                    "text": span["text"],
                                    "confidence": 1.0,  # Direct extraction is 100% accurate
                                    "bbox": {
                                        "x_min": bbox[0],
                                        "y_min": bbox[1],
                                        "x_max": bbox[2],
                                        "y_max": bbox[3]
                                    }
                                })

            pages_data.append({
                "page_number": page_num + 1,
                "text": text.strip(),
                "elements": elements
            })

        doc.close()
        return pages_data

    def check_pdf_has_text(self, pdf_path: str) -> Tuple[bool, int]:
        """Check if PDF has extractable text and return page count"""
        print(f"\n{'='*60}")
        print(f"[OCR] Analyzing PDF: {pdf_path}")
        print(f"{'='*60}")

        doc = fitz.open(pdf_path)
        page_count = len(doc)
        total_text_len = 0

        # Sample first few pages to check for text
        sample_pages = min(3, page_count)
        for i in range(sample_pages):
            text = doc[i].get_text()
            total_text_len += len(text.strip())
            print(f"[OCR] Sample page {i+1}: {len(text.strip())} characters")

        doc.close()

        avg_text_per_page = total_text_len / sample_pages if sample_pages > 0 else 0
        has_text = avg_text_per_page > self.min_text_threshold

        print(f"[OCR] Total pages: {page_count}")
        print(f"[OCR] Avg chars/page: {avg_text_per_page:.0f}")
        print(f"[OCR] Has extractable text: {has_text}")
        print(f"[OCR] Method: {'DIRECT EXTRACTION (fast)' if has_text else 'OCR (slow)'}")
        print(f"{'='*60}\n")

        logger.info(f"PDF check: {page_count} pages, avg {avg_text_per_page:.0f} chars/page, has_text={has_text}")
        return has_text, page_count

    def pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """Convert PDF pages to images"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        images = convert_from_path(pdf_path, dpi=self.dpi)
        image_paths = []

        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f"page_{i + 1}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)
            logger.info(f"Saved page {i + 1} to {image_path}")

        return image_paths

    def extract_text_from_image(self, image_path: str) -> Dict:
        """Extract text and bounding boxes from an image using OCR"""
        ocr = get_paddle_ocr()
        result = ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return {"text": "", "elements": []}

        elements = []
        full_text_parts = []

        for line in result[0]:
            bbox, (text, confidence) = line

            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]

            elements.append({
                "text": text,
                "confidence": confidence,
                "bbox": {
                    "x_min": min(x_coords),
                    "y_min": min(y_coords),
                    "x_max": max(x_coords),
                    "y_max": max(y_coords)
                }
            })
            full_text_parts.append(text)

        return {
            "text": "\n".join(full_text_parts),
            "elements": elements
        }

    def process_image_file(self, image_path: str, document_id: int) -> List[Dict]:
        """Process a single image file as a document"""
        import time
        import shutil
        from PIL import Image

        start_time = time.time()

        output_dir = os.path.join(
            os.environ.get("UPLOAD_DIR", "/app/uploads"),
            f"doc_{document_id}",
            "pages"
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"[OCR] Processing IMAGE file: {image_path}")
        print(f"{'='*60}")

        # Convert HEIC/HEIF to PNG if needed
        ext = Path(image_path).suffix.lower()
        if ext in {'.heic', '.heif'}:
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                logger.warning("pillow-heif not installed, HEIC support limited")

        # Copy/convert image to output directory as page_1.png
        output_image_path = os.path.join(output_dir, "page_1.png")
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (for RGBA, P mode, etc.)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(output_image_path, "PNG")
        except Exception as e:
            logger.error(f"Failed to convert image: {e}")
            shutil.copy(image_path, output_image_path)

        # OCR the image
        print(f"[OCR] Running OCR on image...")
        ocr_result = self.extract_text_from_image(output_image_path)

        total_time = time.time() - start_time
        text_preview = ocr_result["text"][:100].replace('\n', ' ') if ocr_result["text"] else "(no text)"
        print(f"[OCR] COMPLETED: 1 page in {total_time:.1f}s | {len(ocr_result['text'])} chars | {text_preview}...")

        return [{
            "page_number": 1,
            "image_path": output_image_path,
            "ocr_text": ocr_result["text"],
            "elements": ocr_result["elements"]
        }]

    def process_document(self, file_path: str, document_id: int) -> List[Dict]:
        """Process a document (PDF or image) using hybrid approach"""
        import time
        start_time = time.time()

        # Check if this is an image file
        if self.is_image_file(file_path):
            return self.process_image_file(file_path, document_id)

        # PDF processing (original logic)
        pdf_path = file_path
        output_dir = os.path.join(
            os.environ.get("UPLOAD_DIR", "/app/uploads"),
            f"doc_{document_id}",
            "pages"
        )

        # Step 1: Check if PDF has extractable text
        has_text, page_count = self.check_pdf_has_text(pdf_path)

        if has_text:
            # Fast path: Direct text extraction
            print(f"\n[OCR] Starting DIRECT TEXT EXTRACTION for {page_count} pages...")
            logger.info(f"Using DIRECT TEXT EXTRACTION (fast) for {page_count} pages")

            extract_start = time.time()
            direct_data = self.extract_text_from_pdf_direct(pdf_path)
            print(f"[OCR] Text extraction completed in {time.time() - extract_start:.1f}s")

            # Still generate page images for viewing (but at lower DPI for speed)
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            pages_data = []
            for page_info in direct_data:
                page_num = page_info["page_number"]
                progress = (page_num / page_count) * 100

                # Generate image for this page only (for viewing)
                try:
                    img_start = time.time()
                    images = convert_from_path(
                        pdf_path,
                        dpi=150,  # Lower DPI for preview images
                        first_page=page_num,
                        last_page=page_num
                    )
                    if images:
                        image_path = os.path.join(output_dir, f"page_{page_num}.png")
                        images[0].save(image_path, "PNG")
                    else:
                        image_path = None
                    img_time = time.time() - img_start
                except Exception as e:
                    logger.warning(f"Could not generate image for page {page_num}: {e}")
                    image_path = None
                    img_time = 0

                text_preview = page_info["text"][:100].replace('\n', ' ') if page_info["text"] else "(no text)"
                print(f"[OCR] Page {page_num}/{page_count} ({progress:.0f}%) | {len(page_info['text'])} chars | img:{img_time:.1f}s | {text_preview}...")

                pages_data.append({
                    "page_number": page_num,
                    "image_path": image_path,
                    "ocr_text": page_info["text"],
                    "elements": page_info["elements"]
                })
                logger.info(f"Extracted text from page {page_num}/{page_count} (direct)")

            total_time = time.time() - start_time
            print(f"\n[OCR] COMPLETED: {page_count} pages in {total_time:.1f}s ({total_time/page_count:.2f}s/page)")
            return pages_data

        else:
            # Slow path: OCR required
            print(f"\n[OCR] Starting OCR (slow path) for {page_count} pages...")
            print(f"[OCR] This may take a while - estimated {page_count * 15}s ({page_count * 15 / 60:.1f} min)")
            logger.info(f"Using OCR (slow) for {page_count} pages - PDF has no extractable text")

            print(f"[OCR] Converting PDF to images...")
            img_start = time.time()
            image_paths = self.pdf_to_images(pdf_path, output_dir)
            print(f"[OCR] Image conversion completed in {time.time() - img_start:.1f}s")

            pages_data = []
            for i, image_path in enumerate(image_paths):
                page_num = i + 1
                progress = (page_num / len(image_paths)) * 100
                page_start = time.time()

                print(f"[OCR] Processing page {page_num}/{len(image_paths)} ({progress:.0f}%)...", end=" ", flush=True)
                logger.info(f"OCR processing page {page_num}/{len(image_paths)}")

                ocr_result = self.extract_text_from_image(image_path)
                page_time = time.time() - page_start

                text_preview = ocr_result["text"][:80].replace('\n', ' ') if ocr_result["text"] else "(no text)"
                print(f"done in {page_time:.1f}s | {len(ocr_result['text'])} chars | {text_preview}...")

                pages_data.append({
                    "page_number": page_num,
                    "image_path": image_path,
                    "ocr_text": ocr_result["text"],
                    "elements": ocr_result["elements"]
                })

            total_time = time.time() - start_time
            print(f"\n[OCR] COMPLETED: {len(image_paths)} pages in {total_time:.1f}s ({total_time/len(image_paths):.2f}s/page)")
            return pages_data


ocr_service = OCRService()
