# pyrt_cetsa_384_cli_v7.py
from __future__ import annotations
import argparse
from pathlib import Path
import string, re, sys, os, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap

# ------------------------ MoltenProt import ------------------------
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

# ------------------------ Helpers ------------------------
def all_well_ids_384():
    rows = list(string.ascii_uppercase[:16])  # A..P
    return [f"{r}{c}" for r in rows for c in range(1, 25)]

def well_id_from_rowcol(row_no: int, col_no: int) -> str:
    letters = list(string.ascii_uppercase)[:16]  # A..P
    return f"{letters[int(row_no)-1]}{int(col_no)}"

def normalize_well_id(x: str) -> str:
    x = str(x).strip().upper()
    m = re.match(r"^([A-P])0*([1-9]|1[0-9]|2[0-4])$", x)
    return f"{m.group(1)}{int(m.group(2))}" if m else x

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
            rows.append({"ID": normalize_well_id(wid), value_name: row[col]})
    out = pd.DataFrame(rows).set_index("ID")
    out.index.name = "ID"
    return out

# ------------------------ Platemap ------------------------
def load_platemap_384(path: Path, sample_sheet: str | None, conc_sheet: str | None) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    sheets = xls.sheet_names
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

    pm = pm.reindex(all_well_ids_384())
    return pm

# ------------------------ Plate data (°C input) ------------------------
def build_uniform_temperature_grid(n_points: int, t_min_c: float, t_max_c: float) -> np.ndarray:
    return np.linspace(float(t_min_c), float(t_max_c), int(n_points))

def load_plate_long(path: Path, t_min_c: float, t_max_c: float) -> pd.DataFrame:
    """Long-form: col1=row(1..16), col2=col(1..24), rest=signal steps. Index in °C."""
    df = pd.read_excel(path, header=None)
    if df.shape[1] < 3:
        raise ValueError("Expected at least 3 columns: row, col, and one or more measurement columns.")
    r = pd.to_numeric(df.iloc[:,0], errors="coerce")
    c = pd.to_numeric(df.iloc[:,1], errors="coerce")
    data = df.iloc[:, 2:].apply(pd.to_numeric, errors="coerce")

    # 0/1 aware normalization
    # Accept both 0- and 1-based inputs; convert to 1-based
    r = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    c = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    # If we detect zeros, shift the whole vector up by 1 (leave 1-based untouched)
    if (r.min() == 0) or (c.min() == 0):
        r = r + 1
        c = c + 1
    mask_valid = r.between(1, 16) & c.between(1, 24)

    r, c, data = r[mask_valid], c[mask_valid], data[mask_valid]
    n_points = data.shape[1]
    if n_points < 2:
        raise ValueError("Fewer than 2 measurement columns; cannot build a temperature grid.")
    temp_grid_c = build_uniform_temperature_grid(n_points, t_min_c, t_max_c)
    well_ids = [normalize_well_id(well_id_from_rowcol(rv, cv)) for rv, cv in zip(r, c)]
    wide = pd.DataFrame(data.to_numpy().T, index=temp_grid_c, columns=well_ids).T
    wide = wide.T  # Temperature(°C) x well
    wide.index.name = "Temperature"
    for wid in all_well_ids_384():
        if wid not in wide.columns:
            wide[wid] = np.nan
    return wide.reindex(columns=all_well_ids_384())

def _score_header_pair(row_hdr: pd.Series, col_hdr: pd.Series) -> int:
    """Score how well two header rows look like row=1..16 repeated, col=1..24 repeating. Return count of valid positions up to 384."""
    try:
        row_vals = pd.to_numeric(row_hdr, errors="coerce").astype("Int64")
        col_vals = pd.to_numeric(col_hdr, errors="coerce").astype("Int64")
    except Exception:
        return -1
    valid = ((row_vals >= 1) & (row_vals <= 16) & (col_vals >= 1) & (col_vals <= 24)).fillna(False)
    return int(valid.sum())

def load_plate_matrix_auto(df: pd.DataFrame, t_min_c: float, t_max_c: float, search_max_start: int = 20) -> (pd.DataFrame, dict):
    """Auto-detect header offsets across a wider window. Returns (dataframe, debug)."""
    best = None
    ncols = df.shape[1]
    row_pairs = [(0,1), (1,2), (2,3), (3,4)]
    for r1, r2 in row_pairs:
        for start in range(0, min(search_max_start, max(1, ncols-384))+1):
            end = start + 384
            if end > ncols:
                break
            row_hdr = df.iloc[r1, start:end]
            col_hdr = df.iloc[r2, start:end]
            score = _score_header_pair(row_hdr, col_hdr)
            if score > (best[4] if best else -1):
                best = (r1, r2, start, end, score)
    if not best or best[4] < 300:
        raise ValueError(f"Could not auto-detect 384-well window (best score={best[4] if best else 'NA'}).")
    r1, r2, start, end, score = best
    dbg = {"row_header_row": r1, "col_header_row": r2, "start_col": start, "end_col": end, "score": int(score)}
    row_nums = pd.to_numeric(df.iloc[r1, start:end], errors="coerce").astype(int)
    col_nums = pd.to_numeric(df.iloc[r2, start:end], errors="coerce").astype(int)

    # NEW: normalize to 1-based if zeros present
    if (row_nums.min() == 0) or (col_nums.min() == 0):
        row_nums = row_nums + 1
        col_nums = col_nums + 1

    row_letters = [string.ascii_uppercase[int(r)-1] for r in row_nums]
    well_ids = [normalize_well_id(f"{r}{int(c)}") for r, c in zip(row_letters, col_nums)]
    data = df.iloc[r2+1:, start:end].copy()
    n_points = data.shape[0]
    temps_c = build_uniform_temperature_grid(n_points, t_min_c, t_max_c)
    data.index = temps_c
    data.index.name = "Temperature"
    data.columns = well_ids
    for wid in all_well_ids_384():
        if wid not in data.columns:
            data[wid] = np.nan
    data = data.reindex(columns=all_well_ids_384())
    return data, dbg

def load_plate_matrix(path: Path, sheet: str, t_min_c: float, t_max_c: float) -> (pd.DataFrame, dict):
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    return load_plate_matrix_auto(df, t_min_c, t_max_c)

def load_plate_auto(path: Path, t_min_c: float, t_max_c: float, matrix_sheet: str | None) -> (pd.DataFrame, dict):
    if matrix_sheet:
        plate, dbg = load_plate_matrix(path, sheet=matrix_sheet, t_min_c=t_min_c, t_max_c=t_max_c)
        return plate, dbg
    plate = load_plate_long(path, t_min_c=t_min_c, t_max_c=t_max_c)
    return plate, {"mode": "long"}

# ------------------------ Analysis ------------------------
def to_long_with_platemap(wide_k_df: pd.DataFrame, platemap: pd.DataFrame, value_name: str) -> pd.DataFrame:
    long = wide_k_df.reset_index().melt(id_vars=["Temperature"], var_name="ID", value_name=value_name)
    long = long.join(platemap, on="ID")
    long["Temperature"] = long["Temperature"] - 273.15
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
        "raw_wide": mpf.plate_raw.copy(),          # K index
        "preproc_wide": mpf.plate.copy(),          # K index
        "fit_wide": mpf.plate_fit.copy(),          # K index
        "raw_corr_wide": mpf.plate_raw_corr.copy() # K index
    }

# ------------------------ Plotting ------------------------
def _to_celsius_index(df_k: pd.DataFrame) -> pd.DataFrame:
    try:
        return df_k.rename_axis("Temperature").rename_axis(None, axis=1).rename(index=lambda k: k - 273.15)
    except Exception:
        return df_k

def _first_derivative(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.gradient(y, x)

def _sanitize(name: str) -> str:
    keep = "-_.()[]{} "
    return "".join(c if (c.isalnum() or c in keep) else "_" for c in str(name))

def _group_mask(platemap: pd.DataFrame, pattern: str | None):
    if not pattern:
        return pd.Series(False, index=platemap.index)
    return platemap["Condition"].fillna("").str.contains(pattern, case=False, regex=True)

def export_well_plots(raw_wide_k: pd.DataFrame,
                      raw_corr_wide_k: pd.DataFrame,
                      fit_wide_k: pd.DataFrame,
                      params: pd.DataFrame,
                      platemap: pd.DataFrame,
                      outdir: Path,
                      pos_label: str | None,
                      neg_label: str | None,
                      limit_wells: int | None = None):
    outdir.mkdir(parents=True, exist_ok=True)
    raw_c = _to_celsius_index(raw_wide_k)
    corr_c = _to_celsius_index(raw_corr_wide_k)
    fit_c  = _to_celsius_index(fit_wide_k)

    temps = raw_c.index.to_numpy(dtype=float)

    pos_mask = _group_mask(platemap, pos_label)
    neg_mask = _group_mask(platemap, neg_label)

    def mean_sd(wide_df: pd.DataFrame, mask: pd.Series):
        wells = [w for w in mask.index[mask].tolist() if w in wide_df.columns]
        Y = wide_df[wells].to_numpy(dtype=float, copy=True) if wells else np.empty((len(wide_df), 0))
        mu = np.nanmean(Y, axis=1) if Y.size else None
        sd = np.nanstd(Y, axis=1) if Y.size else None
        return mu, sd

    pos_mu_raw, pos_sd_raw = mean_sd(raw_c, pos_mask)
    neg_mu_raw, neg_sd_raw = mean_sd(raw_c, neg_mask)
    pos_mu_cor, pos_sd_cor = mean_sd(corr_c, pos_mask)
    neg_mu_cor, neg_sd_cor = mean_sd(corr_c, neg_mask)

    d_cor = corr_c.apply(lambda col: _first_derivative(col.to_numpy(dtype=float), temps), axis=0, result_type="expand")
    d_cor.index = corr_c.index
    pos_mu_d, pos_sd_d = mean_sd(d_cor, pos_mask)
    neg_mu_d, neg_sd_d = mean_sd(d_cor, neg_mask)

    wells = list(raw_c.columns)
    if limit_wells:
        wells = wells[:int(limit_wells)]

    tm_lookup = {}
    if "Tm_fit" in params.columns:
        for wid, tm in params["Tm_fit"].dropna().items():
            try:
                tm_lookup[str(wid)] = float(tm) - 273.15
            except Exception:
                pass

    for wid in wells:
        cond = platemap.loc[wid, "Condition"] if wid in platemap.index else ""
        conc = platemap.loc[wid, "Concentration"] if wid in platemap.index else np.nan
        title_suffix = f"{wid} | {cond} | {conc:g}" if pd.notna(conc) else f"{wid} | {cond}"

        # Raw + Fit
        fig, ax = plt.subplots(figsize=(6,4), dpi=150)
        y = raw_c.get(wid, pd.Series(index=raw_c.index, dtype=float)).to_numpy(dtype=float)
        ax.plot(temps, y, label="Raw")
        if wid in fit_c.columns:
            ax.plot(temps, fit_c[wid].to_numpy(dtype=float), linestyle="--", label="Fit")
        tm_c = tm_lookup.get(wid)
        if tm_c is not None:
            ax.axvline(tm_c, linestyle=":", label=f"Tm={tm_c:.2f}°C")
        if pos_mu_raw is not None:
            ax.plot(temps, pos_mu_raw, alpha=0.75, label=f"{pos_label} μ")
            ax.fill_between(temps, pos_mu_raw-pos_sd_raw, pos_mu_raw+pos_sd_raw, alpha=0.15, label=f"{pos_label} ±σ")
        if neg_mu_raw is not None:
            ax.plot(temps, neg_mu_raw, alpha=0.75, label=f"{neg_label} μ")
            ax.fill_between(temps, neg_mu_raw-neg_sd_raw, neg_mu_raw+neg_sd_raw, alpha=0.15, label=f"{neg_label} ±σ")
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel("Signal (raw)")
        ax.set_title(f"Raw + Fit | {title_suffix}")
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / f"{_sanitize(wid)}_raw.png")
        plt.close(fig)

        # Baseline-corrected + Fit
        fig, ax = plt.subplots(figsize=(6,4), dpi=150)
        y = corr_c.get(wid, pd.Series(index=corr_c.index, dtype=float)).to_numpy(dtype=float)
        ax.plot(temps, y, label="Baseline-corrected")
        if wid in fit_c.columns:
            ax.plot(temps, fit_c[wid].to_numpy(dtype=float), linestyle="--", label="Fit")
        tm_c = tm_lookup.get(wid)
        if tm_c is not None:
            ax.axvline(tm_c, linestyle=":", label=f"Tm={tm_c:.2f}°C")
        if pos_mu_cor is not None:
            ax.plot(temps, pos_mu_cor, alpha=0.75, label=f"{pos_label} μ")
            ax.fill_between(temps, pos_mu_cor-pos_sd_cor, pos_mu_cor+pos_sd_cor, alpha=0.15, label=f"{pos_label} ±σ")
        if neg_mu_cor is not None:
            ax.plot(temps, neg_mu_cor, alpha=0.75, label=f"{neg_label} μ")
            ax.fill_between(temps, neg_mu_cor-neg_sd_cor, neg_mu_cor+neg_sd_cor, alpha=0.15, label=f"{neg_label} ±σ")
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel("Signal (baseline-corr)")
        ax.set_title(f"Baseline-corrected + Fit | {title_suffix}")
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / f"{_sanitize(wid)}_baseline.png")
        plt.close(fig)

        # First derivative
        fig, ax = plt.subplots(figsize=(6,4), dpi=150)
        y = corr_c.get(wid, pd.Series(index=corr_c.index, dtype=float)).to_numpy(dtype=float)
        yd = np.gradient(y, temps)
        ax.plot(temps, yd, label="d/dT (corrected)")
        tm_c = tm_lookup.get(wid)
        if tm_c is not None:
            ax.axvline(tm_c, linestyle=":", label=f"Tm={tm_c:.2f}°C")
        ax.set_xlabel("Temperature (°C)")
        ax.set_ylabel("d Signal / dT")
        ax.set_title(f"First derivative | {title_suffix}")
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / f"{_sanitize(wid)}_derivative.png")
        plt.close(fig)

def export_compound_plots(raw_wide_k: pd.DataFrame,
                          raw_corr_wide_k: pd.DataFrame,
                          fit_wide_k: pd.DataFrame,
                          params: pd.DataFrame,
                          platemap: pd.DataFrame,
                          outdir: Path,
                          cmap_name: str,
                          pos_label: str | None,
                          neg_label: str | None,
                          limit_compounds: int | None = None):
    outdir.mkdir(parents=True, exist_ok=True)
    raw_c = _to_celsius_index(raw_wide_k)
    corr_c = _to_celsius_index(raw_corr_wide_k)
    fit_c  = _to_celsius_index(fit_wide_k)
    temps = raw_c.index.to_numpy(dtype=float)

    tm_lookup = {}
    if "Tm_fit" in params.columns:
        for wid, tm in params["Tm_fit"].dropna().items():
            try:
                tm_lookup[str(wid)] = float(tm) - 273.15
            except Exception:
                pass

    pos_mask = _group_mask(platemap, pos_label)
    neg_mask = _group_mask(platemap, neg_label)

    cond_groups = platemap.reset_index().groupby("Condition")["ID"].apply(list)
    conditions = [c for c in cond_groups.index if pd.notna(c) and str(c).strip() != ""]
    if limit_compounds:
        conditions = conditions[:int(limit_compounds)]

    for cond in conditions:
        wells = cond_groups.get(cond, [])
        if not wells:
            continue
        sub = platemap.loc[wells]
        concs = sub["Concentration"].astype(float)
        order = np.argsort(concs.fillna(np.inf).to_numpy())
        wells_sorted = list(np.array(wells)[order])
        conc_sorted  = list(concs.to_numpy()[order])

        n = max(2, len(wells_sorted))
        cmap = get_cmap(cmap_name)
        colors = [cmap(i/(n-1)) for i in range(n)]

        fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(7,8), dpi=150, sharex=True)

        # Top: raw + control overlays
        for idx, wid in enumerate(wells_sorted):
            y = raw_c.get(wid, pd.Series(index=raw_c.index, dtype=float)).to_numpy(dtype=float)
            lbl = f"{wid} | {conc_sorted[idx]:g}" if pd.notna(conc_sorted[idx]) else wid
            ax_top.plot(temps, y, label=lbl, color=colors[idx])
        pos_wells = [w for w in pos_mask.index[pos_mask].tolist() if w in raw_c.columns]
        if pos_wells:
            Y = raw_c[pos_wells].to_numpy(dtype=float)
            mu = np.nanmean(Y, axis=1); sd = np.nanstd(Y, axis=1)
            ax_top.plot(temps, mu, color="black", alpha=0.9, linewidth=1.5, label=f"{pos_label} μ")
            ax_top.fill_between(temps, mu-sd, mu+sd, color="black", alpha=0.15, label=f"{pos_label} ±σ")
        neg_wells = [w for w in neg_mask.index[neg_mask].tolist() if w in raw_c.columns]
        if neg_wells:
            Y = raw_c[neg_wells].to_numpy(dtype=float)
            mu = np.nanmean(Y, axis=1); sd = np.nanstd(Y, axis=1)
            ax_top.plot(temps, mu, color="gray", alpha=0.9, linewidth=1.5, label=f"{neg_label} μ")
            ax_top.fill_between(temps, mu-sd, mu+sd, color="gray", alpha=0.15, label=f"{neg_label} ±σ")
        ax_top.set_ylabel("Signal (raw)")
        ax_top.set_title(f"{cond} — Raw curves (colored by concentration)")
        ax_top.legend(loc="best", fontsize=7)

        # Bottom: corrected + fits + derivative
        ax2 = ax_bot.twinx()
        for idx, wid in enumerate(wells_sorted):
            yc = corr_c.get(wid, pd.Series(index=corr_c.index, dtype=float)).to_numpy(dtype=float)
            ax_bot.plot(temps, yc, label=f"{conc_sorted[idx]:g}" if pd.notna(conc_sorted[idx]) else f"{idx+1}", color=colors[idx])
            if wid in fit_c.columns:
                ax_bot.plot(temps, fit_c[wid].to_numpy(dtype=float), linestyle="--", color=colors[idx], alpha=0.9)
            yd = np.gradient(yc, temps)
            ax2.plot(temps, yd, linestyle=":", color=colors[idx], alpha=0.9)
            tm_c = tm_lookup.get(wid)
            if tm_c is not None:
                ax_bot.axvline(tm_c, linestyle=":", color=colors[idx], alpha=0.5)
        ax_bot.set_xlabel("Temperature (°C)")
        ax_bot.set_ylabel("Baseline-corrected")
        ax2.set_ylabel("d Signal / dT")
        ax_bot.set_title(f"{cond} — Corrected + fits (solid/--), derivative (:)")
        handles1, labels1 = ax_bot.get_legend_handles_labels()
        ax_bot.legend(handles1, [f"{cond} {lab}" for lab in labels1], fontsize=7, loc="best")
        fig.tight_layout()
        fig.savefig(outdir / f"{_sanitize(cond)}.png")
        plt.close(fig)

# ------------------------ Output writer ------------------------
def write_analysis_with_platemap(analysis: dict, platemap_df: pd.DataFrame, outfile: Path, include_all_wells: bool, input_wide_c: pd.DataFrame | None = None, matrix_debug: dict | None = None):
    params = analysis["params"]
    params_stdev = analysis["params_stdev"]
    raw_wide = analysis["raw_wide"]
    preproc_wide = analysis["preproc_wide"]
    fit_wide = analysis["fit_wide"]
    raw_corr_wide = analysis["raw_corr_wide"]

    well_order = all_well_ids_384()
    if include_all_wells:
        raw_wide = ensure_complete_wells_wide(raw_wide, well_order)
        preproc_wide = ensure_complete_wells_wide(preproc_wide, well_order)
        fit_wide = ensure_complete_wells_wide(fit_wide, well_order)
        raw_corr_wide = ensure_complete_wells_wide(raw_corr_wide, well_order)

    raw_long = to_long_with_platemap(raw_wide, platemap_df, "Raw")
    rawcorr_long = to_long_with_platemap(raw_corr_wide, platemap_df, "BaselineCorrected")

    p = params.copy()
    if "ID" not in p.columns:
        p = p.reset_index().rename(columns={"index":"ID"})
    pm = platemap_df.reset_index()  # ID, Condition, Concentration
    merged = pm.merge(p, on="ID", how="left")

    with pd.ExcelWriter(outfile) as writer:
        if input_wide_c is not None:
            input_wide_c.to_excel(writer, sheet_name="Input (wide, C)")
        if matrix_debug:
            dbg = pd.DataFrame([matrix_debug])
            dbg.to_excel(writer, sheet_name="Matrix debug", index=False)

        merged.to_excel(writer, sheet_name="Fit parameters", index=False)
        params_stdev.to_excel(writer, sheet_name="Fit stddev", index=False)
        raw_wide.to_excel(writer, sheet_name="Raw (wide, K)")
        preproc_wide.to_excel(writer, sheet_name="Preproc (wide, K)")
        fit_wide.to_excel(writer, sheet_name="Fit (wide, K)")
        raw_corr_wide.to_excel(writer, sheet_name="Baseline-corr (wide, K)")
        raw_long.to_excel(writer, sheet_name="Raw+Map (long, C)", index=False)
        rawcorr_long.to_excel(writer, sheet_name="BaselineCorrected+Map (C)", index=False)

# ------------------------ Diagnostics ------------------------
def diagnose_well_coverage(plate_wide_c: pd.DataFrame, out_csv: Path | None):
    counts = plate_wide_c.notna().sum(axis=0).rename("non_null_points").reset_index().rename(columns={"index":"ID"})
    if out_csv is not None:
        counts.to_csv(out_csv, index=False)
    return counts

# ------------------------ CLI ------------------------
def main():
    parser = argparse.ArgumentParser(description="MoltenProt on 384-well plate (wider matrix auto-detect, dump input, plotting).")
    parser.add_argument("--platemap", default="platemap.xlsx", help="Path to platemap Excel file (with sample and conc sheets).")
    parser.add_argument("--pm-sample", default=None, help="Name of sample/ID sheet (auto-detect if omitted).")
    parser.add_argument("--pm-conc", default=None, help="Name of concentration sheet (auto-detect if omitted).")

    parser.add_argument("--plate", default="example_plate.xlsx", help="Path to plate Excel file (long or matrix).")
    parser.add_argument("--plate-matrix-sheet", default=None, help="If matrix-style, provide the sheet name (e.g., Sheet2). Omit for long-form input.")
    parser.add_argument("--tmin", type=float, default=37.0, help="Minimum temperature (°C).")
    parser.add_argument("--tmax", type=float, default=90.0, help="Maximum temperature (°C).")

    parser.add_argument("--model", default="santoro1988", help="Thermodynamic model name.")
    parser.add_argument("--out", default="analysis_384.xlsx", help="Output Excel path.")
    parser.add_argument("--include-all-wells", action="store_true", help="Include all 384 wells even if data is missing (values will be NaN).")

    parser.add_argument("--make-plots", action="store_true", help="Export per-well and per-compound plots.")
    parser.add_argument("--plots-outdir", default="plots", help="Directory to write plot PNGs.")
    parser.add_argument("--pos-label", default="control", help="Regex/text to identify positive control wells (Condition contains).")
    parser.add_argument("--neg-label", default="vehicle", help="Regex/text to identify negative control wells (Condition contains).")
    parser.add_argument("--cmap", default="viridis", help="Matplotlib colormap for concentration gradient.")
    parser.add_argument("--limit-wells", type=int, default=None, help="Limit number of wells for per-well plots (dev only).")
    parser.add_argument("--limit-compounds", type=int, default=None, help="Limit number of compound plots (dev only).")

    parser.add_argument("--diagnose", action="store_true", help="Write a CSV of non-null point counts per well (pre-analysis).")
    parser.add_argument("--diagnose-csv", default="well_coverage.csv", help="Path to write the diagnosis CSV.")
    parser.add_argument("--dump-input", action="store_true", help="Add a sheet 'Input (wide, C)' showing the exact data fed to MoltenProt.")

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    mp_core = _import_moltenprot(base_dir)

    platemap_df = load_platemap_384(Path(args.platemap), sample_sheet=args.pm_sample, conc_sheet=args.pm_conc)
    plate_wide_c, dbg = load_plate_auto(Path(args.plate), t_min_c=args.tmin, t_max_c=args.tmax, matrix_sheet=args.plate_matrix_sheet)
    plate_wide_c = plate_wide_c.reindex(columns=all_well_ids_384())

    # Quick A1 probe
    a1_non_null = int(plate_wide_c['A1'].notna().sum()) if 'A1' in plate_wide_c.columns else 0
    if a1_non_null == 0:
        print("WARNING: No A1 measurements found in the input plate. A1 will stay NaN in analysis unless the source file has A1 data.")

    if args.diagnose:
        counts = diagnose_well_coverage(plate_wide_c, Path(args.diagnose_csv))
        print(f"Diagnosis written to {args.diagnose_csv}. A1 non-null points: {a1_non_null}")

    analysis = run_analysis(plate_wide_c, platemap_df, model=args.model, mp_core=mp_core)
    write_analysis_with_platemap(analysis, platemap_df, Path(args.out), include_all_wells=True,
                                 input_wide_c=(plate_wide_c if args.dump_input else None),
                                 matrix_debug=(dbg if isinstance(dbg, dict) else None))
    print(f"Wrote Excel: {args.out}")

    if args.make_plots:
        outdir = Path(args.plots_outdir)
        export_well_plots(analysis["raw_wide"], analysis["raw_corr_wide"], analysis["fit_wide"],
                          analysis["params"], platemap_df, outdir / "wells",
                          pos_label=args.pos_label, neg_label=args.neg_label, limit_wells=args.limit_wells)
        export_compound_plots(analysis["raw_wide"], analysis["raw_corr_wide"], analysis["fit_wide"],
                              analysis["params"], platemap_df, outdir / "compounds",
                              cmap_name=args.cmap, pos_label=args.pos_label, neg_label=args.neg_label,
                              limit_compounds=args.limit_compounds)
        print(f"Wrote plots to: {outdir}")

if __name__ == "__main__":
    main()