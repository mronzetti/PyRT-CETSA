
from __future__ import annotations
import argparse
from pathlib import Path
import string
import numpy as np
import pandas as pd
import sys
import re

# ---------- Robust import of MoltenProt core ----------
def _import_moltenprot(base_dir: Path):
    try:
        from moltenprot import core as mp_core  # type: ignore
        return mp_core
    except Exception:
        pass
    core_py = base_dir / "core.py"
    models_py = base_dir / "models.py"
    if core_py.exists() and models_py.exists():
        pkg_dir = base_dir / "moltenprot"
        pkg_dir.mkdir(exist_ok=True)
        (pkg_dir / "__init__.py").write_text("# MoltenProt package\n")
        (pkg_dir / "VERSION").write_text("git")
        if not (pkg_dir / "core.py").exists():
            (pkg_dir / "core.py").write_bytes(core_py.read_bytes())
        if not (pkg_dir / "models.py").exists():
            (pkg_dir / "models.py").write_bytes(models_py.read_bytes())
        if str(base_dir) not in sys.path:
            sys.path.insert(0, str(base_dir))
        from moltenprot import core as mp_core  # type: ignore
        return mp_core
    import core as mp_core  # last resort
    return mp_core

# ---------- Helpers ----------

def all_well_ids_384():
    rows = list(string.ascii_uppercase[:16])  # A..P
    return [f"{r}{c}" for r in rows for c in range(1, 25)]

def well_id_from_rowcol(row_no: int, col_no: int) -> str:
    letters = list(string.ascii_uppercase)[:16]  # A..P
    return f"{letters[int(row_no)-1]}{int(col_no)}"

def _grid_to_series(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """Convert a 16x24 grid to a Series indexed by well ID with a given column name."""
    row_no_col = df.columns[0]
    rows = []
    for _, row in df.iterrows():
        row_no = int(row[row_no_col])
        row_letter = string.ascii_uppercase[row_no - 1]
        for col in df.columns[1:]:
            try:
                col_no = int(str(col).strip())
            except Exception:
                continue
            wid = f"{row_letter}{col_no}"
            rows.append({"ID": wid, value_name: row[col]})
    out = pd.DataFrame(rows).set_index("ID")
    out.index.name = "ID"
    return out

def load_platemap_384(path: Path, sample_sheet: str | None, conc_sheet: str | None) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    sheets = xls.sheet_names
    # Auto-detect sample sheet
    if sample_sheet is None:
        cand = [s for s in sheets if re.search(r"(sample|id|map|layout)", s, re.I)]
        sample_sheet = cand[0] if cand else sheets[0]
    if conc_sheet is None:
        conc = [s for s in sheets if re.search(r"(conc|concentration)", s, re.I)]
        conc_sheet = conc[0] if conc else None

    sample_df = pd.read_excel(path, sheet_name=sample_sheet)
    sample_ser = _grid_to_series(sample_df, "Condition")

    if conc_sheet is not None:
        conc_df = pd.read_excel(path, sheet_name=conc_sheet)
        conc_ser = _grid_to_series(conc_df, "Concentration")
        pm = sample_ser.join(conc_ser, how="outer")
    else:
        pm = sample_ser
        pm["Concentration"] = np.nan

    # Reindex to full 384 layout so missing wells are present (e.g., A1)
    pm = pm.reindex(all_well_ids_384())

    return pm

def build_uniform_temperature_grid(n_points: int, t_min_c: float, t_max_c: float) -> np.ndarray:
    return np.linspace(float(t_min_c), float(t_max_c), int(n_points))

def load_plate_384(path: Path, t_min_c: float, t_max_c: float, include_wells: list[str] | None = None) -> pd.DataFrame:
    df = pd.read_excel(path)
    if df.shape[1] < 3:
        raise ValueError("Expected at least 3 columns: row, col, and one or more measurement columns.")
    rowcol = df.iloc[:, :2].copy()
    data = df.iloc[:, 2:].apply(pd.to_numeric, errors="coerce")
    n_points = data.shape[1]
    if n_points < 2:
        raise ValueError("Found fewer than 2 measurement columns; cannot build a temperature grid.")
    temp_grid = build_uniform_temperature_grid(n_points, t_min_c, t_max_c)

    # Build in one shot
    well_ids = [well_id_from_rowcol(r, c) for r, c in rowcol.to_numpy()]
    wide = pd.DataFrame(data.to_numpy().T, index=temp_grid, columns=well_ids).T

    # Ensure specified wells exist (even if not measured) as NaN columns
    if include_wells is not None:
        for wid in include_wells:
            if wid not in wide.index:
                # create an all-NaN row, then fill later after transpose back
                pass
        # Convert to Temperature x wells wide
        wide = wide.T
        # Add missing columns as NaN arrays
        for wid in include_wells:
            if wid not in wide.columns:
                wide[wid] = np.nan
        # restore column order
        wide = wide.reindex(columns=include_wells)
        wide.index.name = 'Temperature'
        return wide

    # Default behavior: drop all-NaN wells
    wide = wide.T.dropna(how="all").T
    wide.index.name = "Temperature"
    return wide

def to_long_with_platemap(wide_df: pd.DataFrame, platemap: pd.DataFrame, value_name: str) -> pd.DataFrame:
    long = wide_df.reset_index().melt(id_vars=["Temperature"], var_name="ID", value_name=value_name)
    long = long.join(platemap, on="ID")
    return long

def ensure_complete_wells_wide(wide_df: pd.DataFrame, well_order: list[str]) -> pd.DataFrame:
    out = wide_df.copy()
    for w in well_order:
        if w not in out.columns:
            out[w] = np.nan
    out = out.reindex(columns=well_order)
    return out

def run_analysis(plate_wide_c: pd.DataFrame, platemap_df: pd.DataFrame, model: str, mp_core) -> dict:
    mpfm = mp_core.MoltenProtFitMultiple(scan_rate=None, denaturant="C", layout=platemap_df, source="plate")
    mpfm.AddDataset(plate_wide_c, "Signal")
    mpfm.SetAnalysisOptions(which="all", printout=False, model=model)
    mpfm.PrepareAndAnalyseAll(n_jobs=1)
    mpf = mpfm.datasets["Signal"]
    return {
        "params": mpf.plate_results.copy(),
        "params_stdev": mpf.plate_results_stdev.copy(),
        "raw_wide": mpf.plate_raw.copy(),
        "preproc_wide": mpf.plate.copy(),
        "fit_wide": mpf.plate_fit.copy(),
        "raw_corr_wide": mpf.plate_raw_corr.copy(),
    }

def write_analysis_with_platemap(analysis: dict, platemap_df: pd.DataFrame, outfile: Path, include_all_wells: bool):
    params = analysis["params"]
    params_stdev = analysis["params_stdev"]
    raw_wide = analysis["raw_wide"]
    raw_corr_wide = analysis["raw_corr_wide"]

    # Optionally add missing wells (like A1) as NaNs so they appear in outputs
    well_order = all_well_ids_384()
    if include_all_wells:
        raw_wide = ensure_complete_wells_wide(raw_wide, well_order)
        raw_corr_wide = ensure_complete_wells_wide(raw_corr_wide, well_order)

    to_c = lambda k: k - 273.15
    raw_long = to_long_with_platemap(
        raw_wide.rename_axis("Temperature").rename_axis(None, axis=1).rename(index=to_c),
        platemap_df,
        "Raw",
    )
    rawcorr_long = to_long_with_platemap(
        raw_corr_wide.rename_axis("Temperature").rename_axis(None, axis=1).rename(index=to_c),
        platemap_df,
        "BaselineCorrected",
    )

    with pd.ExcelWriter(outfile) as writer:
        params.to_excel(writer, sheet_name="Fit parameters", index=False)
        params_stdev.to_excel(writer, sheet_name="Fit stddev", index=False)
        raw_wide.to_excel(writer, sheet_name="Raw (wide, K)")
        raw_corr_wide.to_excel(writer, sheet_name="Baseline-corr (wide, K)")
        raw_long.to_excel(writer, sheet_name="Raw+Map (long, C)", index=False)
        rawcorr_long.to_excel(writer, sheet_name="BaselineCorrected+Map (C)", index=False)

# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="MoltenProt on 384-well plate with platemap (sample+concentration) and uniform temperature grid.")
    parser.add_argument("--platemap", default="platemap.xlsx", help="Path to platemap Excel file (with sample and conc sheets).")
    parser.add_argument("--pm-sample", default=None, help="Name of sample/ID sheet (auto-detect if omitted).")
    parser.add_argument("--pm-conc", default=None, help="Name of concentration sheet (auto-detect if omitted).")
    parser.add_argument("--plate", default="example_plate.xlsx", help="Path to 384-well data Excel file (long form).")
    parser.add_argument("--tmin", type=float, default=37.0, help="Minimum temperature (°C).")
    parser.add_argument("--tmax", type=float, default=90.0, help="Maximum temperature (°C).")
    parser.add_argument("--model", default="santoro1988", help="Thermodynamic model name.")
    parser.add_argument("--out", default="analysis_384.xlsx", help="Output Excel path.")
    parser.add_argument("--include-all-wells", action="store_true", help="Include all 384 wells from platemap even if data is missing (values will be NaN).")

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    mp_core = _import_moltenprot(base_dir)

    platemap_df = load_platemap_384(Path(args.platemap), sample_sheet=args.pm_sample, conc_sheet=args.pm_conc)
    # Always include all wells so A1 etc. exist even if not measured
    plate_wide_c = load_plate_384(Path(args.plate), t_min_c=args.tmin, t_max_c=args.tmax, include_wells=list(platemap_df.index))
    analysis = run_analysis(plate_wide_c, platemap_df, model=args.model, mp_core=mp_core)
    write_analysis_with_platemap(analysis, platemap_df, Path(args.out), include_all_wells=args.include_all_wells)
    print(f"Done. Wrote: {args.out}")

if __name__ == "__main__":
    main()
