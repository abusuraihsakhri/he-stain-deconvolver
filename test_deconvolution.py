"""Tests for the Ruifrok & Johnston color deconvolution core logic."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from he_stain_deconvolver.stains import build_stain_matrix, STAIN_VECTORS, normalize_vector
from he_stain_deconvolver.deconvolution import (
    od_to_rgb,
    deconvolve,
    reconstruct_stain_channel,
    compute_stain_statistics,
    white_balance,
)


class TestStainMatrix(unittest.TestCase):
    def test_two_vector_matrix_is_invertible_with_unit_rows(self):
        matrix, names = build_stain_matrix(STAIN_VECTORS["HE"])
        self.assertEqual(matrix.shape, (3, 3))
        self.assertGreater(abs(np.linalg.det(matrix)), 1e-6)
        for row in matrix:
            self.assertAlmostEqual(np.linalg.norm(row), 1.0, places=6)
        self.assertEqual(names, ["hematoxylin", "eosin", "residual"])

    def test_normalize_vector(self):
        v = normalize_vector((3, 4, 0))
        self.assertAlmostEqual(np.linalg.norm(v), 1.0, places=8)
        np.testing.assert_allclose(v, [0.6, 0.8, 0.0], atol=1e-8)

    def test_rejects_parallel_vectors(self):
        with self.assertRaises(ValueError):
            build_stain_matrix([(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)])


class TestRoundTripDeconvolution(unittest.TestCase):
    """Build a synthetic image from a known concentration, then verify
    that `deconvolve` recovers the same concentration (linear unmixing
    should be an exact inverse of the forward optical-density model up
    to floating-point precision)."""

    def setUp(self):
        self.matrix, self.names = build_stain_matrix(STAIN_VECTORS["HE"])

    def _synthetic_image(self, concentration, shape=(4, 4)):
        c = np.array(concentration, dtype=np.float64)
        od = c @ self.matrix
        pixel_rgb = od_to_rgb(od)
        return np.tile(pixel_rgb, (shape[0], shape[1], 1))

    def test_pure_hematoxylin_recovered(self):
        image = self._synthetic_image([1.0, 0.0, 0.0])
        mean_c = deconvolve(image, self.matrix).reshape(-1, 3).mean(axis=0)
        np.testing.assert_allclose(mean_c, [1.0, 0.0, 0.0], atol=1e-3)

    def test_pure_eosin_recovered(self):
        image = self._synthetic_image([0.0, 1.2, 0.0])
        mean_c = deconvolve(image, self.matrix).reshape(-1, 3).mean(axis=0)
        np.testing.assert_allclose(mean_c, [0.0, 1.2, 0.0], atol=1e-3)

    def test_mixed_stain_recovered(self):
        image = self._synthetic_image([0.6, 0.4, 0.0])
        mean_c = deconvolve(image, self.matrix).reshape(-1, 3).mean(axis=0)
        np.testing.assert_allclose(mean_c, [0.6, 0.4, 0.0], atol=1e-3)

    def test_white_background_gives_near_zero_concentration(self):
        white_image = np.full((4, 4, 3), 255, dtype=np.uint8)
        mean_c = deconvolve(white_image, self.matrix).reshape(-1, 3).mean(axis=0)
        np.testing.assert_allclose(mean_c, [0.0, 0.0, 0.0], atol=1e-2)


class TestStainStatistics(unittest.TestCase):
    def test_mean_od_and_percent_positive_area(self):
        concentrations = np.zeros((10, 10, 3))
        concentrations[:5, :, 0] = 0.5  # above threshold, 50 of 100 pixels
        stats = compute_stain_statistics(concentrations, ["h", "e", "r"], threshold=0.15)
        self.assertAlmostEqual(stats["h"]["percent_positive_area"], 50.0, places=5)
        self.assertAlmostEqual(stats["h"]["mean_od"], 0.25, places=6)
        self.assertEqual(stats["e"]["percent_positive_area"], 0.0)


class TestWhiteBalance(unittest.TestCase):
    def test_scales_reference_toward_white(self):
        image = np.full((2, 2, 3), 200, dtype=np.uint8)
        corrected = white_balance(image, white_ref=(200, 200, 200))
        np.testing.assert_allclose(corrected, 255.0, atol=1e-6)

    def test_no_reference_leaves_image_unchanged(self):
        image = np.full((2, 2, 3), 100, dtype=np.uint8)
        corrected = white_balance(image, white_ref=None)
        np.testing.assert_allclose(corrected, 100.0)


class TestReconstruction(unittest.TestCase):
    def setUp(self):
        self.matrix, self.names = build_stain_matrix(STAIN_VECTORS["HE"])
        self.image = np.full((5, 5, 3), 180, dtype=np.uint8)
        self.concentrations = deconvolve(self.image, self.matrix)

    def test_grayscale_output_is_valid_uint8_image(self):
        gray = reconstruct_stain_channel(self.concentrations, self.matrix, 0, mode="grayscale")
        self.assertEqual(gray.shape, (5, 5, 3))
        self.assertTrue((gray >= 0).all() and (gray <= 255).all())

    def test_pseudocolor_output_is_valid_uint8_image(self):
        pseudo = reconstruct_stain_channel(self.concentrations, self.matrix, 1, mode="pseudocolor")
        self.assertEqual(pseudo.shape, (5, 5, 3))
        self.assertTrue((pseudo >= 0).all() and (pseudo <= 255).all())

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            reconstruct_stain_channel(self.concentrations, self.matrix, 0, mode="nonsense")


if __name__ == "__main__":
    unittest.main()
