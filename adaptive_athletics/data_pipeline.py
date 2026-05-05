from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

EXPECTED_COLUMNS = [
    "First Name",
    "Last Name",
    "FT Attempted",
    "FT Makes",
    "2PT Attempts",
    "2PT Makes",
    "3PT Attempts",
    "3PT Makes",
    "OVR FG Per",
    "Turnovers",
    "Forced TO",
    "Blocks",
]

NUMERIC_COLUMNS = [
    "FT Attempted",
    "FT Makes",
    "2PT Attempts",
    "2PT Makes",
    "3PT Attempts",
    "3PT Makes",
    "Turnovers",
    "Forced TO",
    "Blocks",
]

NAME_ALIASES = {
    ("Elizabeth", "Pentecost"): ("Liz", "Pentecost"),
}


def load_practice_data(data_dir: str | Path = "Data") -> pd.DataFrame:
    data_path = Path(data_dir)
    csv_files = sorted(data_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_path.resolve()}")

    frames = []
    for csv_file in csv_files:
        frame = pd.read_csv(csv_file)
        missing_columns = sorted(set(EXPECTED_COLUMNS) - set(frame.columns))
        if missing_columns:
            raise ValueError(
                f"{csv_file.name} is missing expected columns: {', '.join(missing_columns)}"
            )

        frame = frame.loc[:, EXPECTED_COLUMNS].copy()
        practice_date = _parse_practice_date(csv_file.stem)
        frame["source_file"] = csv_file.name
        frame["practice_date"] = practice_date
        frame["practice_label"] = f"{practice_date.month}/{practice_date.day}"
        frames.append(frame)

    raw_data = pd.concat(frames, ignore_index=True)
    return clean_practice_data(raw_data)


def clean_practice_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [column.strip() for column in cleaned.columns]

    cleaned["First Name"] = _clean_text_series(cleaned["First Name"])
    cleaned["Last Name"] = _clean_text_series(cleaned["Last Name"])
    cleaned[["First Name", "Last Name"]] = cleaned.apply(
        lambda row: pd.Series(
            NAME_ALIASES.get((row["First Name"], row["Last Name"]), (row["First Name"], row["Last Name"]))
        ),
        axis=1,
    )

    cleaned = cleaned.loc[_valid_player_rows(cleaned)].copy()

    cleaned["player_name"] = (
        cleaned["First Name"].fillna("").str.cat(cleaned["Last Name"].fillna(""), sep=" ").str.strip()
    )

    for column in NUMERIC_COLUMNS:
        cleaned[column] = _coerce_numeric_series(cleaned[column]).fillna(0)

    cleaned["raw_ovr_fg_pct"] = _coerce_percent_series(cleaned["OVR FG Per"])
    cleaned["practice_sessions"] = 1

    cleaned["FG Attempts"] = cleaned["2PT Attempts"] + cleaned["3PT Attempts"]
    cleaned["FG Makes"] = cleaned["2PT Makes"] + cleaned["3PT Makes"]

    cleaned["FT %"] = _safe_divide(cleaned["FT Makes"], cleaned["FT Attempted"])
    cleaned["2PT %"] = _safe_divide(cleaned["2PT Makes"], cleaned["2PT Attempts"])
    cleaned["3PT %"] = _safe_divide(cleaned["3PT Makes"], cleaned["3PT Attempts"])
    cleaned["FG %"] = _safe_divide(cleaned["FG Makes"], cleaned["FG Attempts"])

    cleaned.sort_values(["practice_date", "player_name"], inplace=True)
    cleaned.reset_index(drop=True, inplace=True)
    return cleaned


def build_player_summary(cleaned: pd.DataFrame) -> pd.DataFrame:
    summary = (
        cleaned.groupby(["player_name", "First Name", "Last Name"], as_index=False)[
            NUMERIC_COLUMNS + ["FG Attempts", "FG Makes", "practice_sessions"]
        ]
        .sum()
        .rename(columns={"practice_sessions": "Practices"})
    )

    summary["FT %"] = _safe_divide(summary["FT Makes"], summary["FT Attempted"])
    summary["2PT %"] = _safe_divide(summary["2PT Makes"], summary["2PT Attempts"])
    summary["3PT %"] = _safe_divide(summary["3PT Makes"], summary["3PT Attempts"])
    summary["FG %"] = _safe_divide(summary["FG Makes"], summary["FG Attempts"])
    summary["Attempts / Practice"] = _safe_divide(summary["FG Attempts"], summary["Practices"])

    summary.sort_values(["FG Attempts", "FG %", "player_name"], ascending=[False, False, True], inplace=True)
    summary.reset_index(drop=True, inplace=True)
    return summary


def build_practice_summary(cleaned: pd.DataFrame) -> pd.DataFrame:
    summary = (
        cleaned.groupby(["practice_date", "practice_label"], as_index=False)[
            NUMERIC_COLUMNS + ["FG Attempts", "FG Makes", "practice_sessions"]
        ]
        .sum()
        .rename(columns={"practice_sessions": "Player Entries"})
    )

    summary["FT %"] = _safe_divide(summary["FT Makes"], summary["FT Attempted"])
    summary["2PT %"] = _safe_divide(summary["2PT Makes"], summary["2PT Attempts"])
    summary["3PT %"] = _safe_divide(summary["3PT Makes"], summary["3PT Attempts"])
    summary["FG %"] = _safe_divide(summary["FG Makes"], summary["FG Attempts"])
    summary.sort_values("practice_date", inplace=True)
    summary.reset_index(drop=True, inplace=True)
    return summary


def _parse_practice_date(stem: str) -> pd.Timestamp:
    match = re.search(r"(\d{1,2})_(\d{1,2})$", stem)
    if not match:
        raise ValueError(f"Unable to parse practice date from filename: {stem}")

    month = int(match.group(1))
    day = int(match.group(2))
    return pd.Timestamp(year=2000, month=month, day=day)


def _clean_text_series(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("").astype(str).str.strip()
    cleaned = cleaned.replace({"nan": "", "None": ""})
    return cleaned


def _valid_player_rows(df: pd.DataFrame) -> pd.Series:
    first_name = df["First Name"].fillna("")
    last_name = df["Last Name"].fillna("")
    has_name = (first_name != "") | (last_name != "")
    is_note_row = first_name.str.startswith("(") | last_name.str.startswith("(")
    return has_name & ~is_note_row


def _coerce_numeric_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.fillna("")
        .astype(str)
        .str.strip()
        .replace({"": None, "#DIV/0!": None, "nan": None})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _coerce_percent_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace("%", "", regex=False)
        .replace({"": None, "#DIV/0!": None, "nan": None})
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return numeric / 100.0


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    safe_denominator = denominator.where(denominator != 0)
    return numerator.div(safe_denominator)
