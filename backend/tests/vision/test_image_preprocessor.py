import pytest
from PIL import Image
from app.services.vision.image_preprocessor import ImagePreprocessor

def test_crop_centered_on_equipment():
    # Create a dummy 2000x2000 image
    img = Image.new('RGB', (2000, 2000), color='white')
    
    # Define equipment at (500, 500)
    bbox = {"x_min": 450, "y_min": 450, "x_max": 550, "y_max": 550}
    
    preprocessor = ImagePreprocessor()
    crop = preprocessor.create_centered_crop(img, bbox, crop_size=1000)
    
    # Expected: crop should be 1000x1000
    assert crop.size == (1000, 1000)
    # The center of the equipment (500,500) should be at center of crop (500,500)
    # So crop should be from (0, 0) to (1000, 1000)
    
def test_crop_at_boundary():
    # Equipment at edge (100, 100)
    img = Image.new('RGB', (2000, 2000), color='white')
    bbox = {"x_min": 50, "y_min": 50, "x_max": 150, "y_max": 150}
    
    preprocessor = ImagePreprocessor()
    crop = preprocessor.create_centered_crop(img, bbox, crop_size=1000)
    
    # Should handle boundary by shifting crop or padding? 
    # For simplicity, let's shift to stay within bounds: (0,0) to (1000,1000)
    assert crop.size == (1000, 1000)

def test_crop_with_padding():
    # Small image 500x500
    img = Image.new('RGB', (500, 500), color='blue')
    
    # Equipment at center (250, 250)
    bbox = {"x_min": 200, "y_min": 200, "x_max": 300, "y_max": 300}
    
    preprocessor = ImagePreprocessor()
    # Request 1000x1000 crop (larger than image)
    crop = preprocessor.create_centered_crop(img, bbox, crop_size=1000)
    
    # Expected: crop should be 1000x1000, padded with white
    assert crop.size == (1000, 1000)
    
    # Check padding (top-left pixel should be white default background)
    # Note: PIL default new image is black unless specified, but we want white padding per requirements
    assert crop.getpixel((0, 0)) == (255, 255, 255)
    
    # Check content (center pixel should be blue from original image)
    # Center of 1000x1000 is 500,500. Center of bbox is 250,250.
    # The image is 500x500. 
    # If we crop 1000x1000 centered on 250,250:
    # Left bound: 250 - 500 = -250. Top bound: 250 - 500 = -250.
    # The original image (0,0) starts at crop coordinates (250, 250).
    # So crop(500, 500) corresponds to original image(250, 250) which is blue.
    assert crop.getpixel((500, 500)) == (0, 0, 255)
