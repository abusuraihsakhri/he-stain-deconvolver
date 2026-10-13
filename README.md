# H&E Stain Deconvolver

Color deconvolution for RGB histology images using Ruifrok–Johnston optical-density linear unmixing. Separate hematoxylin/eosin (H&E) or hematoxylin/DAB (H-DAB) contributions.

## Browser application

The `web/` application processes images **entirely in your browser**, without uploads or backend services. It supports:

- PNG, JPEG, WebP and browser-supported BMP images (maximum 12 megapixels / 50 MB).
- H&E and H-DAB reference vectors, optional RGB white-point correction, and an adjustable positive-area threshold.
- Pseudocolor or grayscale display, reconstructed channel PNG downloads, and a per-channel statistics CSV.
- An orthogonal residual channel, in addition to the two measured stain bases.

To run locally:

```bash
python -m http.server 8080 --directory web
# Visit http://localhost:8080/
```

The GitHub Actions workflow includes a Pages deployment job. A live link belongs here once Pages is enabled and the deployed site has been verified.

**Scientific limitations:** Reference stain vectors are scanner- and protocol-dependent. The two-stain model estimates an orthogonal residual, not an independently measured third stain. Unconstrained linear unmixing can yield negative concentrations. The outputs are not validated for clinical diagnostic use without independent calibration and verification.

## Python installation

Python 3.10 or later:

```bash
pip install -e ".[dev]"
```

### Image processing CLI

```bash
python -m he_stain_deconvolver.cli slide.png -o deconv_output
python -m he_stain_deconvolver.cli slides/ --stain-type HDAB --mode grayscale
python -m he_stain_deconvolver.cli slide.png --white-ref 240,240,240 --threshold 0.15
python -m he_stain_deconvolver.cli slide.png --custom-vectors 0.65,0.70,0.29 0.07,0.99,0.11 --stain-names hematoxylin eosin
```

The CLI supports PNG, JPEG, TIFF and BMP inputs, writes three PNG images per image and a `stain_statistics.csv`. Custom stain names may contain letters, numbers, underscores and hyphens.

### Library usage

```python
from PIL import Image
import numpy as np
from he_stain_deconvolver.stains import STAIN_VECTORS, build_stain_matrix
from he_stain_deconvolver.deconvolution import deconvolve, compute_stain_statistics

rgb = np.asarray(Image.open("slide.png").convert("RGB"))
matrix, names = build_stain_matrix(STAIN_VECTORS["HE"])
concentrations = deconvolve(rgb, matrix)
statistics = compute_stain_statistics(concentrations, names)
```

Mathematically, optical density is `OD = -log10(clip(I, 1, 255)/255)`, with the row-based stain-matrix model `OD = concentrations @ M`.

## Optional supervisor service

The separate `agents/` module supplies a rule-based supervisor, in-memory HMAC audit log, mock chat provider, and a FastAPI interface. **Its REST endpoints do not process image pixels.** Its generic escalation thresholds are not medically validated clinical cutoffs.

```bash
pip install -e ".[all]"
python cli.py serve --host 127.0.0.1 --port 8000
# GET /health, /metrics, /api/audit/logs; POST /api/audit, /api/chat
```

For Docker: `docker build -t he-stain-deconvolver .` then `docker run -p 8000:8000 he-stain-deconvolver`. Supply `AUDIT_SECRET_KEY` from a secure environment for signatures that must remain stable across processes. The audit trail is in-memory, not persistent record retention; regex filtering does **not** ensure complete PHI de-identification. Do not deploy this API as a production clinical system without a separate security and clinical review.

## Tests

```bash
python -m pip install -e ".[all]"
python -m pytest -q
node --test tests/browser.test.mjs   # Node.js 24+
python simulator.py --tasks 1000
```

The CI workflow covers Python 3.10–3.12 and JavaScript math tests, with Pages deployment gated on passing tests.

## Technology, privacy, browser support and license

Python, NumPy, Pillow, optional FastAPI/Pydantic, and dependency-free JavaScript/Canvas. Browser processing is local, and downloads remain on the user device. Modern browsers with ES modules, Canvas and `createImageBitmap` are required. MIT License — see [LICENSE](LICENSE).

**Reference:** Ruifrok AC, Johnston DA. Quantification of histochemical staining by color deconvolution. *Anal Quant Cytol Histol.* 2001;23(4):291–299.
