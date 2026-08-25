"""H&E Stain Deconvolver

Ruifrok & Johnston (2001) color deconvolution for unmixing hematoxylin,
eosin, and DAB stain contributions in RGB histology images.
"""

from .stains import STAIN_VECTORS, build_stain_matrix, normalize_vector
from .deconvolution import (
    rgb_to_od,
    od_to_rgb,
    white_balance,
    deconvolve,
    reconstruct_stain_channel,
    compute_stain_statistics,
)

__all__ = [
    "STAIN_VECTORS",
    "build_stain_matrix",
    "normalize_vector",
    "rgb_to_od",
    "od_to_rgb",
    "white_balance",
    "deconvolve",
    "reconstruct_stain_channel",
    "compute_stain_statistics",
]
