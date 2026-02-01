from PIL import Image
from typing import Dict

class ImagePreprocessor:
    def create_centered_crop(self, image: Image.Image, bbox: Dict[str, float], crop_size: int = 1000) -> Image.Image:
        """
        Create a square crop centered on the bounding box.
        Ensures crop stays within image boundaries.
        """
        img_w, img_h = image.size
        
        # Calculate center of bbox
        center_x = (bbox["x_min"] + bbox["x_max"]) / 2
        center_y = (bbox["y_min"] + bbox["y_max"]) / 2
        
        # Calculate crop coordinates
        half_size = crop_size / 2
        left = center_x - half_size
        top = center_y - half_size
        right = center_x + half_size
        bottom = center_y + half_size
        
        # Cast to int for pixel coordinates
        src_left = int(round(left))
        src_top = int(round(top))
        src_right = int(round(right))
        src_bottom = int(round(bottom))
        
        # Create new image with white background
        result = Image.new('RGB', (crop_size, crop_size), (255, 255, 255))
        
        # Calculate intersection with original image
        valid_src_left = max(0, src_left)
        valid_src_top = max(0, src_top)
        valid_src_right = min(img_w, src_right)
        valid_src_bottom = min(img_h, src_bottom)
        
        # If there is valid intersection
        if valid_src_right > valid_src_left and valid_src_bottom > valid_src_top:
            # Crop the valid part from original image
            crop_part = image.crop((valid_src_left, valid_src_top, valid_src_right, valid_src_bottom))
            
            # Calculate paste position
            dst_left = valid_src_left - src_left
            dst_top = valid_src_top - src_top
            
            # Paste onto white background
            result.paste(crop_part, (dst_left, dst_top))
            
        return result
