# H&E Stain Deconvolver

> **Domain:** Clinical Decision Support & Biomedical Computing
> **Reference Guidelines & Standards:** Ruifrok & Johnston (2001), CAP / CLSI / ISO Standards

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-55%20Passed-brightgreen.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

Command-line interface and library for H&E / H-DAB color deconvolution using the Ruifrok & Johnston (2001) method. Separates hematoxylin, eosin, and DAB stain contributions in RGB histology images.

**Pipeline:**
1. (Optional) White-balance the raw RGB image against a background reference so the unstained background reads as pure white.
2. Convert RGB intensities to optical density (OD): `OD = -log10(I / 255)`.
3. Solve, per pixel, `OD = C @ M` for the stain concentration vector `C`, given a 3x3 matrix `M` whose rows are known/normalized stain OD vectors. This is a linear unmixing problem solved by inverting `M`.
4. Reconstruct single-stain images by re-projecting one stain's concentration back through its own OD vector and inverting the OD transform.

---

## ⚙️ Key Capabilities & Algorithmic Modules

### Core Deconvolution (`he_stain_deconvolver/`)

- **`build_stain_matrix()`** — Build a 3x3 stain matrix from reference OD vectors (supports 2 or 3 stain vectors, with automatic orthogonal residual computation).
- **`deconvolve()`** — Unmix an RGB image into per-stain concentration maps via matrix inversion.
- **`reconstruct_stain_channel()`** — Render a single stain channel as a viewable RGB image (pseudocolor or grayscale modes).
- **`white_balance()`** — Normalize image so that a reference white point maps to (255, 255, 255).
- **`compute_stain_statistics()`** — Per-channel intensity statistics (mean OD, max/min, percent-positive area).

### Enterprise Supervisor System (`agents/`)

- **PHI Outbound Guard** — Active regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
- **HMAC-SHA256 Audit Trail** — Chained, cryptographically signed logs for every evaluation and state transition.
- **Multi-Agent Workers** — QC Invariant, Safety Escalation, and Protocol Conformance workers.
- **FastAPI REST API** — OpenAPI 3.1 REST endpoints with `/health`, `/metrics`, `/api/audit`, `/api/chat`.

---

## 💻 Installation

### From Source
```bash
git clone https://github.com/abusuraihsakhri/he-stain-deconvolver.git
cd he-stain-deconvolver
pip install -e ".[dev]"
```

### With Web Dependencies (for FastAPI server)
```bash
pip install -e ".[all]"
```

### Docker
```bash
docker build -t he-stain-deconvolver .
docker run -p 8000:8000 he-stain-deconvolver
```

Or with docker-compose:
```bash
# Set your audit secret key (recommended for production)
export AUDIT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
docker-compose up -d
```

---

## 💻 CLI Quickstart & Usage

### Single Image Deconvolution
```bash
python -m he_stain_deconvolver.cli path/to/image.png -o output_dir
```

### Batch Directory Processing
```bash
python -m he_stain_deconvolver.cli path/to/image_directory/ -o output_dir
```

### With Custom Stain Vectors
```bash
python -m he_stain_deconvolver.cli image.png \
  --custom-vectors 0.65,0.70,0.29 0.07,0.99,0.11 \
  --stain-names hematoxylin eosin
```

### With White Balance Correction
```bash
python -m he_stain_deconvolver.cli image.png \
  --white-ref 240,240,240 \
  --mode grayscale
```

### Parameters
| Parameter | Description | Default |
|:----------|:------------|:--------|
| `input` | Input image file, or a directory for batch processing | (required) |
| `-o, --output` | Output directory | `deconv_output` |
| `--stain-type` | Built-in reference stain vectors (`HE` or `HDAB`) | `HE` |
| `--custom-vectors` | Override with 2 or 3 custom stain OD vectors | (preset) |
| `--stain-names` | Names for custom vectors | (auto-generated) |
| `--mode` | Rendering mode (`pseudocolor` or `grayscale`) | `pseudocolor` |
| `--white-ref` | Background white reference for white-balance correction | (none) |
| `--threshold` | OD threshold for percent-positive-area statistic | `0.15` |

---

## 🧪 Testing & Verification

### Run All Tests
```bash
pytest -v
```

### Run Specific Test Modules
```bash
pytest tests/test_cli.py -v          # CLI tests
pytest tests/test_security.py -v     # Security tests
pytest test_deconvolution.py -v      # Core deconvolution tests
```

### Run Simulation Benchmark
```bash
python simulator.py --tasks 1000
```

---

## 🐳 Container Deployment

```bash
docker build -t he-stain-deconvolver .
docker run -p 8000:8000 \
  -e AUDIT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  he-stain-deconvolver
```

---

## 🛡️ Security

- **Zero-PHI Outbound Interceptor:** Active regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
- **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition.
- **Secure Key Management:** Audit keys are generated using `secrets.token_bytes(32)` per process, or can be set via `AUDIT_SECRET_KEY` environment variable for multi-process deployments.
- **Input Validation:** All stain vectors and image inputs are validated before processing.

---

## 📁 Project Structure

```
he-stain-deconvolver/
├── he_stain_deconvolver/     # Core deconvolution library
│   ├── __init__.py           # Package exports
│   ├── stains.py             # Reference stain OD vectors
│   ├── deconvolution.py      # Core deconvolution algorithms
│   └── cli.py                # CLI for image processing
├── agents/                   # Enterprise supervisor system
│   ├── base.py               # PHI guard, HMAC audit trail
│   ├── models.py             # Pydantic data models
│   ├── supervisor.py         # Multi-agent orchestrator
│   ├── workers.py            # Specialized worker agents
│   ├── api.py                # FastAPI REST server
│   ├── llm_factory.py        # LLM provider abstraction
│   ├── metrics.py            # Prometheus metrics
│   ├── learning.py           # Bayesian calibration engine
│   └── streamer.py           # WebSocket telemetry
├── tests/                    # Test suite
│   ├── test_cli.py           # CLI tests
│   ├── test_security.py      # Security tests
│   ├── test_enrichment.py    # Enrichment engine tests
│   └── test_he_stain_deconvolver.py  # Supervisor tests
├── test_deconvolution.py     # Core deconvolution tests
├── enrichment.py             # Feature enrichment engines
├── simulator.py              # High-throughput simulation
├── cli.py                    # Root CLI (supervisor system)
├── pyproject.toml            # Package configuration
├── Dockerfile                # Container build
├── docker-compose.yml        # Container orchestration
└── requirements.txt          # Legacy dependencies
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
