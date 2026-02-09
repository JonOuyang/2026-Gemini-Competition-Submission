"""
CUA Vision Agent - Image Utilities

Provides image comparison and change detection utilities.
"""
import numpy as np
from PIL import Image

# Global state for tracking image changes
_prev_image = None
_still_count = 0


def reset_image_state():
    """Reset the image comparison state."""
    global _prev_image, _still_count
    _prev_image = None
    _still_count = 0


def image_change(image: Image.Image) -> bool:
    """Check if screen has stopped moving for a certain amount of time.

    Args:
        image: The current screen image to compare

    Returns:
        True if the screen has been stable long enough (4 frames at 0.2s each)
    """
    global _prev_image, _still_count

    if _still_count == 4:  # Counted every 0.2 seconds
        _still_count += 1
        return True
    else:
        image_arr = np.array(image)
        if _still_count == 0:
            _prev_image = np.array(image)

        if (_prev_image is not None and
            image_arr.shape == _prev_image.shape and
            similarity_score(image_arr, _prev_image) > 0.95):
            _still_count += 1
        else:
            _still_count = 0
            _prev_image = image_arr

        return False


def similarity_score(arr1: np.ndarray, arr2: np.ndarray) -> float:
    """Calculate the similarity between 2 images by pixel.

    Args:
        arr1: First image as numpy array
        arr2: Second image as numpy array

    Returns:
        Similarity percentage as float [0, 1]
    """
    comparison = arr1 == arr2
    matching_elements = np.sum(comparison)
    similarity = matching_elements / np.prod(arr1.shape)
    return similarity
