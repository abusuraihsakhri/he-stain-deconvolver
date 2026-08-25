"""Reference stain optical-density vectors and stain-matrix construction.

The vectors below are the standard hematoxylin, eosin, and DAB reference
values published in:

    Ruifrok AC, Johnston DA. "Quantification of histochemical staining by
    color deconvolution." Anal Quant Cytol Histol. 2001;23(4):291-9.

Each vector describes the relative RGB optical-density absorption of one
stain when imaged alone. They are not unit vectors as tabulated; this
module normalizes them before use.
"""

import numpy as np

# Built-in reference vectors for common stain combinations.
STAIN_VECTORS = {
    "HE": {
        "hematoxylin": (0.650, 0.704, 0.286),
        "eosin": (0.072, 0.990, 0.105),
    },
    "HDAB": {
        "hematoxylin": (0.650, 0.704, 0.286),
        "dab": (0.268, 0.570, 0.776),
    },
}


def normalize_vector(vector):
    """Return `vector` scaled to unit length."""
    v = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        raise ValueError("Stain vector has zero norm and cannot be normalized.")
    return v / norm


def build_stain_matrix(stain_vectors):
    """Build a 3x3 stain matrix (rows = normalized OD stain vectors).

    `stain_vectors` may be a dict of name -> (R, G, B) tuple, or a plain
    list/tuple of 2 or 3 such vectors. When only 2 stains are given (the
    common case for H&E or H-DAB), a third orthogonal "residual" vector is
    computed as the normalized cross product of the two, following
    Ruifrok & Johnston's original method — this guarantees the resulting
    3x3 matrix is invertible so pixelwise deconvolution has a unique
    solution.

    Returns (matrix, names) where matrix is a (3, 3) ndarray and names is
    a list of the 3 stain/channel names in row order.
    """
    if isinstance(stain_vectors, dict):
        names = list(stain_vectors.keys())
        vectors = [stain_vectors[n] for n in names]
    else:
        vectors = list(stain_vectors)
        names = [f"stain{i + 1}" for i in range(len(vectors))]

    if len(vectors) not in (2, 3):
        raise ValueError("Provide 2 or 3 stain vectors, got %d." % len(vectors))

    normed = [normalize_vector(v) for v in vectors]

    if len(normed) == 2:
        third = np.cross(normed[0], normed[1])
        norm3 = np.linalg.norm(third)
        if norm3 < 1e-10:
            raise ValueError(
                "The two stain vectors are parallel; cannot derive a third "
                "orthogonal residual vector."
            )
        normed.append(third / norm3)
        names.append("residual")

    matrix = np.stack(normed, axis=0)
    if abs(np.linalg.det(matrix)) < 1e-10:
        raise ValueError("Stain vectors are linearly dependent; matrix is not invertible.")
    return matrix, names
