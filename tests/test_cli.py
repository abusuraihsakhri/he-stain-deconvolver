"""
Tests for the H&E stain deconvolution CLI.
"""
import sys
import os
import tempfile
import csv
from pathlib import Path
from io import StringIO

import numpy as np
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from he_stain_deconvolver.cli import (
    parse_vector,
    load_image,
    save_image,
    find_images,
    process_image,
    resolve_stain_setup,
    build_parser,
    main,
)
from he_stain_deconvolver.stains import STAIN_VECTORS, build_stain_matrix


@pytest.fixture
def sample_image(tmp_path):
    """Create a small synthetic RGB image for testing."""
    img_array = np.random.randint(50, 200, (10, 10, 3), dtype=np.uint8)
    img_path = tmp_path / "test_image.png"
    Image.fromarray(img_array).save(img_path)
    return img_path


@pytest.fixture
def sample_image_dir(tmp_path):
    """Create a directory with multiple images."""
    for i in range(3):
        img_array = np.random.randint(50, 200, (10, 10, 3), dtype=np.uint8)
        Image.fromarray(img_array).save(tmp_path / f"test_image_{i}.png")
    return tmp_path


class TestParseVector:
    def test_valid_vector(self):
        result = parse_vector("0.65,0.70,0.29")
        assert result == (0.65, 0.70, 0.29)

    def test_vector_with_spaces(self):
        result = parse_vector("0.65, 0.70, 0.29")
        assert result == (0.65, 0.70, 0.29)

    def test_invalid_too_few(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            parse_vector("0.65,0.70")

    def test_invalid_too_many(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            parse_vector("0.65,0.70,0.29,0.1")

    def test_invalid_non_numeric(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            parse_vector("abc,def,ghi")


class TestLoadImage:
    def test_load_png(self, sample_image):
        img = load_image(sample_image)
        assert img.shape == (10, 10, 3)
        assert img.dtype == np.uint8

    def test_load_converts_to_rgb(self, tmp_path):
        # Create RGBA image
        img_array = np.random.randint(0, 255, (10, 10, 4), dtype=np.uint8)
        img_path = tmp_path / "rgba.png"
        Image.fromarray(img_array, "RGBA").save(img_path)
        img = load_image(img_path)
        assert img.shape[2] == 3  # Should be converted to RGB


class TestSaveImage:
    def test_save_and_reload(self, tmp_path):
        arr = np.random.randint(0, 255, (10, 10, 3), dtype=np.uint8)
        out_path = tmp_path / "output.png"
        save_image(arr, out_path)
        assert out_path.exists()
        # Reload and verify
        reloaded = load_image(out_path)
        np.testing.assert_array_equal(arr, reloaded)


class TestFindImages:
    def test_single_file(self, sample_image):
        result = find_images(sample_image)
        assert result == [Path(sample_image)]

    def test_directory(self, sample_image_dir):
        result = find_images(sample_image_dir)
        assert len(result) == 3
        assert all(f.suffix == ".png" for f in result)

    def test_directory_sorted(self, sample_image_dir):
        result = find_images(sample_image_dir)
        assert result == sorted(result)


class TestProcessImage:
    def test_basic_processing(self, sample_image, tmp_path):
        out_dir = tmp_path / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        matrix, names = build_stain_matrix(STAIN_VECTORS["HE"])
        stats = process_image(
            sample_image, out_dir, matrix, names,
            mode="pseudocolor", threshold=0.15, white_ref=None
        )
        assert "hematoxylin" in stats
        assert "eosin" in stats
        assert "residual" in stats
        # Check output files exist
        stem = sample_image.stem
        for name in names:
            assert (out_dir / f"{stem}_{name}.png").exists()

    def test_grayscale_mode(self, sample_image, tmp_path):
        out_dir = tmp_path / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        matrix, names = build_stain_matrix(STAIN_VECTORS["HE"])
        stats = process_image(
            sample_image, out_dir, matrix, names,
            mode="grayscale", threshold=0.15, white_ref=None
        )
        assert len(stats) == 3


class TestResolveStainSetup:
    def test_he_preset(self):
        parser = build_parser()
        args = parser.parse_args(["dummy.png", "--stain-type", "HE"])
        matrix, names = resolve_stain_setup(args)
        assert matrix.shape == (3, 3)
        assert names == ["hematoxylin", "eosin", "residual"]

    def test_hdab_preset(self):
        parser = build_parser()
        args = parser.parse_args(["dummy.png", "--stain-type", "HDAB"])
        matrix, names = resolve_stain_setup(args)
        assert matrix.shape == (3, 3)
        assert names == ["hematoxylin", "dab", "residual"]

    def test_custom_vectors(self):
        parser = build_parser()
        args = parser.parse_args([
            "dummy.png",
            "--custom-vectors", "0.65,0.70,0.29", "0.07,0.99,0.11",
            "--stain-names", "my_stain_a", "my_stain_b",
        ])
        matrix, names = resolve_stain_setup(args)
        assert matrix.shape == (3, 3)
        assert names[0] == "my_stain_a"
        assert names[1] == "my_stain_b"


class TestMainCli:
    def test_full_pipeline(self, sample_image, tmp_path):
        out_dir = tmp_path / "cli_output"
        ret = main([str(sample_image), "-o", str(out_dir), "--stain-type", "HE"])
        assert ret == 0
        # Check summary CSV exists
        assert (out_dir / "stain_statistics.csv").exists()

    def test_no_images_found(self, tmp_path):
        ret = main([str(tmp_path / "nonexistent.png")])
        assert ret == 1

    def test_batch_directory(self, sample_image_dir, tmp_path):
        out_dir = tmp_path / "batch_output"
        ret = main([str(sample_image_dir), "-o", str(out_dir)])
        assert ret == 0
        # Should produce summary CSV
        assert (out_dir / "stain_statistics.csv").exists()
