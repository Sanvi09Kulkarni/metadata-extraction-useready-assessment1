# Metadata Extraction from Rental Agreements (USEReady Assessment)

An AI system that extracts key metadata from rental agreements, whether uploaded as a scanned image (`.png`) or a Word file (`.docx`), **without regex or hand-written rules**. An LLM reads the document text and returns structured JSON, so the same pipeline works across different templates.

## Fields extracted

| Field | CSV column |
|---|---|
| Agreement Value (monthly rent) | `Aggrement Value` |
| Agreement Start Date | `Aggrement Start Date` |
| Agreement End Date | `Aggrement End Date` |
| Renewal Notice (days) | `Renewal Notice (Days)` |
| Party One (landlord / lessor) | `Party One` |
| Party Two (tenant / lessee) | `Party Two` |

The problem statement lists five fields, but `train.csv` and `test.csv` also contain `Aggrement Value`, so the system extracts all six. Column names keep the original (misspelled) spelling so the outputs match the provided CSVs.

## Approach

```
.docx / .png  ->  plain text  ->  LLM (instructions in a prompt)  ->  JSON with 6 fields
```

1. **Text extraction (`src/loader.py`)**
   - `.docx`: `python-docx` reads paragraphs and tables. If the docx contains embedded page images (scanned pages), those are OCR'd too and appended as a second version of the text.
   - `.png`: Tesseract OCR (`pytesseract`) after grayscale conversion and 2x upscaling.
2. **Extraction (`src/extractor.py`, `src/prompts.py`)**
   - The text and a rule-based *instruction prompt* go to Google Gemini, which is asked for JSON only (`response_mime_type="application/json"`, `temperature=0`).
   - The prompt describes what each field means, the output date format (`DD.MM.YYYY`), how to compute an end date from a duration, and to return `null` instead of guessing.
   - The model does the reading and reasoning. There is no regex, keyword matching, or template-specific code anywhere in the extraction path.
3. **Evaluation (`src/evaluate.py`)**
   - Per-field recall = exact matches / documents. Before comparing, values are trimmed and numbers compared numerically (`30.0` equals `30`). This is only in the scorer, not in extraction.
   - A retry with back-off handles temporary API errors (503/429).

**Why an LLM and not a trained model?** There are only 9 labeled training documents, which is far too few to fine-tune a model, and the task requires handling any template. A prompted LLM generalizes without training data. No few-shot examples from the train set are used, so train and test scores are not inflated by memorization.

## Project structure

```
assignment-1/
├── data/                    # provided dataset (train/, test/, train.csv, test.csv)
├── notebooks/               # exploration and evaluation
├── src/
│   ├── loader.py            # docx / image -> text
│   ├── prompts.py           # extraction instructions
│   ├── extractor.py         # LLM call, returns the 6 fields
│   └── evaluate.py          # per-field recall
├── outputs/                 # predictions and recall scores (v1, v2, v3)
├── app.py                   # FastAPI REST service
├── run_predictions.py       # generates test predictions
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

Requirements: Python 3.11, [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki), and a Google Gemini API key.

```bash
python -m venv venv
venv\Scripts\activate            # Windows (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`):

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

Tesseract path: `src/loader.py` sets the Windows default (`C:\Program Files\Tesseract-OCR\tesseract.exe`). On Linux/Mac, remove that line if `tesseract` is already on your PATH.

Place the provided `data/` folder in the project root.

## Reproduce the predictions

```bash
python run_predictions.py        # writes outputs/test_predictions.csv
```

Evaluation cells are in `notebooks/`. Each run makes one API call per document, so expect a few minutes.

## Run the API

```bash
uvicorn app:app --reload
```

- Interactive docs: http://127.0.0.1:8000/docs
- Example request:

```bash
curl -X POST "http://127.0.0.1:8000/extract" -F "file=@data/test/95980236-Rental-Agreement.png"
```

Example response:

```json
{
  "Aggrement Value": 12000,
  "Aggrement Start Date": "01.04.2008",
  "Aggrement End Date": "31.03.2009",
  "Renewal Notice (Days)": 60,
  "Party One": "Hanumaiah",
  "Party Two": "Vishal Bhardwaj"
}
```

Accepts `.docx`, `.png`, `.jpg`. Returns `400` for unsupported types, `422` if no text could be read.

## Results

Metric: per-field recall, exact match. The test set has only 4 documents (scores move in steps of 0.25) and train has 9 labeled documents, so these numbers are noisy.

### Versions

- **v1:** first prompt.
- **v2:** added the terminate/vacate notice rule, kept connectors (`&`, `and/or`) as written, removed titles (Mr./Mrs./Prof./Dr.), and told the model not to guess garbled digits. **Frozen before the test set was run**, so its test score is the clean held-out result.
- **v3:** added the Indian titles `Sri/Shri/Smt./Kum.` after noticing them in v2's test errors. Because this change was chosen after seeing test errors, **v3's test score is optimistic**.

### Test set (4 documents)

| Field | v2 (clean held-out) | v3 (after seeing test errors) |
|---|---|---|
| Agreement Value | 1.00 | 1.00 |
| Start Date | 1.00 | 1.00 |
| End Date | 0.75 | 0.75 |
| Renewal Notice | 1.00 | 1.00 |
| Party One | 0.75 | 1.00 |
| Party Two | 0.25 | 0.50 |

### Train set (9 labeled documents)

### Train set (9 labeled documents)

| Field | v2 strict | v3 strict | v2 adjusted* |
|---|---|---|---|
| Agreement Value | 0.67 | 0.67 | 0.89 |
| Start Date | 0.67 | 0.67 | 0.78 |
| End Date | 0.33 | 0.33 | 0.44 |
| Renewal Notice | 0.67 | 0.67 | 0.89 |
| Party One | 0.33 | 0.33 | 0.44 |
| Party Two | 0.56 | 0.56 | 0.67 |

The Sri/Smt. change (v3) did not affect train scores. \*Adjusted was computed for v2 only.

\*Adjusted = a diagnostic where the labels of two files with apparently swapped labels are swapped in a copy (see below). **Strict is the headline number.** `train.csv` was never modified.

## Data quality issues found

Many remaining misses come from the data, not the model. I checked each against the document text.

1. **Swapped labels (`54770958`, `54945838`).** The CSV labels of these two files appear to be exchanged: the parties, rent and notice period in each document match the other file's row. I verified this by reading both documents. The model's output follows the document text.
2. **Impossible label dates.** Some labels are not real calendar dates (`31.11.2009`, `31.04.2011`, `31.02.2011`). The model returns valid dates, so these can never match exactly.
3. **Label inconsistent with document (`95980236`).** The document states "11 (Eleven) months from 1st April 2010", giving `28.02.2011`, which the model returned. The label `31.03.2011` implies 12 months.
4. **Unreadable scan (`44737744`).** This `.docx` holds a scanned page whose embedded text is corrupted OCR (dates and rent are unreadable) and the embedded page images were also not readable by Tesseract. The model correctly returns `null` instead of guessing.
5. **Renewal notice not in text (`6683127`, `6683129`).** The label is 15 days, but no such clause appears in the extracted text (these look like partial pages). The model returns `null`.
6. **Label noise.** Stray characters or inconsistent honorifics in labels (`.B.Kishore`, `MR.K.Kuttan` vs other names without titles, `Ingles, Jr.` vs `Ingles. Jr.`).
7. **Train/test overlap.** `24158401` appears in both `train.csv` and `test.csv`, but its file exists only in `test/`. It is scored once, as a test file. `46239065` is in `train/` but has no label, so it is skipped.

## Limitations

- **Small data.** 9 train and 4 test documents make every score noisy. Strict scores are lowered by the data issues above.
- **Title removal is not fully reliable.** In test, `SRI VYSHNAVI DAIRY...` kept its title and a trailing period (`Ltd.`) in v3.
- **OCR quality limits accuracy.** Poor scans can cause misspelled names (for example `GERALDINE O.` vs `Q.`) or null fields.
- **Hosted LLM.** Document text is sent to Google's Gemini API, so it needs an API key and internet access and is unsuitable for confidential documents. Free-tier models can return 503 or rate-limit errors (handled with retries). The code reads the model name from `.env`, so another provider or a local model can be swapped in by editing `src/extractor.py`.
- **Prompt rules are not code rules.** "End date = start + duration − 1 day" is an instruction to the model, which does the calculation. It may not match every labeling convention.
- Tesseract path is set for Windows.

## Possible improvements

- Better OCR (preprocessing, or a vision-capable model for scanned pages).
- A larger labeled set to measure accuracy reliably and to fine-tune a smaller local model.
- A normalization step for honorifics and punctuation that does not rely on hand-written patterns.