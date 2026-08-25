"""Core Ruifrok & Johnston (2001) color deconvolution logic.

Pipeline:
  1. (optional) white-balance the raw RGB image against a background
     reference so the unstained background reads as pure white.
  2. Convert RGB intensities to optical density (OD): OD = -log10(I / 255).
  3. Solve, per pixel, OD = C @ M for the stain concentration vector C,
     given a 3x3 matrix M whose rows are known/normalized stain OD
     vectors. This is a linear unmixing problem solved by inverting M.
  4. Reconstruct single-stain images by re-projecting one stain's
     concentration back through its own OD vector and inverting the OD
     transform.
"""

import numpy as np


def white_balance(image, white_ref=None):
    """Normalize `image` so that `white_ref` maps to (255, 255, 255).

    image: (H, W, 3) array, values in [0, 255].
    white_ref: (R, G, B) background/white-point reference, or None to
        skip correction (background is assumed to already be ~white).

    Returns a float64 (H, W, 3) array clipped to [0, 255].
    """
    img = image.astype(np.float64)
    if white_ref is None:
        return np.clip(img, 0, 255)

    wr = np.asarray(white_ref, dtype=np.float64).copy()
    wr[wr < 1.0] = 1.0  # avoid division blow-up on a near-black reference
    corrected = img / wr * 255.0
    return np.clip(corrected, 0, 255)


def rgb_to_od(image):
    """Ruifrok & Johnston optical-density transform: OD = -log10(I / 255).

    Intensities are clipped to [1, 255] first so log10(0) never occurs;
    a pixel value of 0 (true black) is treated as OD equal to a value of
    1, which is standard practice for this transform.
    """
    img = np.clip(image.astype(np.float64), 1.0, 255.0)
    return -np.log10(img / 255.0)


def od_to_rgb(od):
    """Inverse of `rgb_to_od`: intensity = 255 * 10^(-OD), clipped to [0, 255]."""
    rgb = 255.0 * np.power(10.0, -np.asarray(od, dtype=np.float64))
    return np.clip(rgb, 0, 255)


def deconvolve(image, stain_matrix):
    """Unmix an RGB image into per-stain concentration maps.

    image: (H, W, 3) array, RGB intensities in [0, 255].
    stain_matrix: (3, 3) array, rows are normalized stain OD vectors, as
        returned by `stains.build_stain_matrix`.

    Returns a (H, W, 3) float64 array of stain concentrations, where
    channel i corresponds to row i of `stain_matrix`. Solves, for every
    pixel, the linear system OD = C @ M by matrix inversion (the
    Ruifrok & Johnston deconvolution step).
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must have shape (H, W, 3).")
    h, w, _ = image.shape
    od = rgb_to_od(image).reshape(-1, 3)
    stain_matrix_inv = np.linalg.inv(stain_matrix)
    concentrations = od @ stain_matrix_inv
    return concentrations.reshape(h, w, 3)


def reconstruct_stain_channel(concentrations, stain_matrix, index, mode="pseudocolor"):
    """Render a single stain channel as a viewable RGB image.

    concentrations: (H, W, 3) array from `deconvolve`.
    stain_matrix: the (3, 3) matrix used to produce `concentrations`.
    index: which stain/channel (row of stain_matrix) to render.
    mode:
        "pseudocolor" - re-project the isolated stain's OD through its own
            stain vector and invert back to RGB, i.e. what that stain
            alone would look like on a white slide.
        "grayscale" - treat the concentration itself as a scalar OD and
            invert it to a single grayscale intensity per pixel (darker
            pixel = higher stain concentration).

    Returns a (H, W, 3) uint8 array.
    """
    h, w, _ = concentrations.shape
    channel_concentration = concentrations[:, :, index]

    if mode == "grayscale":
        gray = od_to_rgb(channel_concentration)
        rgb = np.stack([gray, gray, gray], axis=-1)
    elif mode == "pseudocolor":
        stain_vector = stain_matrix[index]
        od_image = np.outer(channel_concentration.ravel(), stain_vector).reshape(h, w, 3)
        rgb = od_to_rgb(od_image)
    else:
        raise ValueError("mode must be 'grayscale' or 'pseudocolor'.")

    return rgb.astype(np.uint8)


def compute_stain_statistics(concentrations, stain_names, threshold=0.15):
    """Per-channel intensity statistics for simple quantitative/IHC analysis.

    concentrations: (H, W, 3) array from `deconvolve`.
    stain_names: names for each of the 3 channels, in order.
    threshold: OD (concentration) above which a pixel counts as
        "positive" for that stain.

    Returns a dict: name -> {mean_od, max_od, min_od, percent_positive_area}.
    """
    total_pixels = concentrations.shape[0] * concentrations.shape[1]
    stats = {}
    for i, name in enumerate(stain_names):
        channel = concentrations[:, :, i]
        positive = channel > threshold
        stats[name] = {
            "mean_od": float(np.mean(channel)),
            "max_od": float(np.max(channel)),
            "min_od": float(np.min(channel)),
            "percent_positive_area": float(np.sum(positive)) / total_pixels * 100.0,
        }
    return stats
