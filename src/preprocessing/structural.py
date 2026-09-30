"""Gradient maps and dark-pixel masks; darkness is only a shadow proxy."""
import cv2
import numpy as np
from src.preprocessing.optical import normalize


def layers(image, valid, dark_threshold=12):
    gray, valid, info = normalize(image, valid)
    smooth = cv2.GaussianBlur(gray, (3, 3), .7)
    magnitude = cv2.magnitude(cv2.Scharr(smooth, cv2.CV_32F, 1, 0), cv2.Scharr(smooth, cv2.CV_32F, 0, 1))
    structural, _, _ = normalize(magnitude, valid, (1, 99))
    dark = valid & (gray <= dark_threshold)
    clean = cv2.erode((valid & ~dark).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    return gray, structural, dark, clean, info
