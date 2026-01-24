import os
import logging
from pathlib import Path
from typing import List, Dict
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,
            show_log=False
        )
        self.dpi = int(os.environ.get("OCR_DPI", 300))

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
        """Extract text and bounding boxes from an image"""
        result = self.ocr.ocr(image_path, cls=True)

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

    def process_document(self, pdf_path: str, document_id: int) -> List[Dict]:
        """Process entire PDF document"""
        output_dir = os.path.join(
            os.environ.get("UPLOAD_DIR", "/app/uploads"),
            f"doc_{document_id}",
            "pages"
        )

        image_paths = self.pdf_to_images(pdf_path, output_dir)

        pages_data = []
        for i, image_path in enumerate(image_paths):
            logger.info(f"Processing page {i + 1}/{len(image_paths)}")

            ocr_result = self.extract_text_from_image(image_path)

            pages_data.append({
                "page_number": i + 1,
                "image_path": image_path,
                "ocr_text": ocr_result["text"],
                "elements": ocr_result["elements"]
            })

        return pages_data


ocr_service = OCRService()
