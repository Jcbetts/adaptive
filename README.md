# adaptive athletics workspace

This repo builds a Quarto report for women's adaptive basketball practice statistics.

## Setup

1. Install Python 3.10+.
2. Install Quarto and make sure `quarto` is on your `PATH`.
3. Create and activate a virtual environment.
4. Install the project in editable mode:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## Render the workbook

From the repo root, run:

```powershell
quarto render Workbook.qmd
```

The report reads all CSV files in `Data/` and writes the rendered output to `Workbook.html`.

## Data assumptions

- Each practice CSV should use the same columns as the existing files in `Data/`.
- The cleanup layer removes blank rows and note rows such as `(No Shooting today)`.
- Shooting percentages in the report are recalculated from makes and attempts instead of trusting spreadsheet percentage strings.
