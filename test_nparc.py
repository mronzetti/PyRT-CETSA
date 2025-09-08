#!/usr/bin/env python
"""
External NPARC runner
- Loads your existing pyrt_cetsa.py by path
- Runs your normal analysis
- Computes NPARC (Raw + BaselineCorrected) externally
- Appends 'NPARC summary' and 'NPARC RSS (long)' to the Excel
- Optionally writes plots under ...\plots\nparc and ...\plots\nparc_raw
"""

import argparse
from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.stats import mannwhitneyu
from scipy.special import expit  # numerically stable sigmoid

# ---------------- NPARC core (self-contained) ----------------

def _four_pl_loglogistic(c, a, d, ec50, b):
    """
    Stable 4pLL:
      f(c) = d + (a-d) / (1 + (c/EC50)^b)
           = d + (a-d) * expit( - b * (ln c - ln EC50) )
    """
    c = np.asarray(c, dtype=float)
    # keep values in a sane numeric range and avoid log(0)
    c_safe = np.clip(c, 1e-12, 1e12)
    ec50_safe = float(np.clip(ec50, 1e-12, 1e12))
    # work in log space; clip z to prevent overflow in extreme tails
    z = b * (np.log(c_safe) - np.log(ec50_safe))
    z = np.clip(z, -500.0, 500.0)
    return d + (a - d) * expit(-z)

def _fit_null_const(x, y):
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return np.nan, np.array([]), np.array([])
    yv = np.asarray(y)[mask]
    yhat = np.full_like(yv, np.nanmean(yv))
    rss = np.nansum((yv - yhat) ** 2.0)
    return rss, yv, yhat

def _fit_4pl(x, y):
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return np.nan, np.array([]), np.array([]), None
    xv = np.asarray(x)[mask]
    yv = np.asarray(y)[mask]
    ymin, ymax = np.nanmin(yv), np.nanmax(yv)
    a0, d0 = ymax, ymin
    ec500 = np.nanmedian(xv[xv > 0]) if np.any(xv > 0) else 1.0
    b0 = 1.0  # or estimate sign from data if you like
    p0 = [float(a0), float(d0), float(ec500), float(b0)]
    bounds = ([-np.inf, -np.inf, 1e-12, -8.0],  # allow both up/down curves
              [np.inf, np.inf, 1e+12, 8.0])  # but keep slope magnitude reasonable
    try:
        popt, _ = curve_fit(_four_pl_loglogistic, xv, yv, p0=p0, bounds=bounds, maxfev=20000)
        yhat = _four_pl_loglogistic(xv, *popt)
        rss = np.nansum((yv - yhat) ** 2.0)
        return rss, yv, yhat, popt
    except Exception:
        return np.nan, np.array([]), np.array([]), None

def _temperatures_from_wide(wide_k: pd.DataFrame):
    idx = np.array(list(wide_k.index), dtype=float)
    return idx - 273.15 if np.nanmean(idx) > 150 else idx

def _condition_groups(platemap: pd.DataFrame):
    pm = platemap.copy()
    pm = pm[pm.get("Condition").notna() & (pm.get("Condition").astype(str).str.strip() != "")]
    pm = pm.reset_index().rename(columns={"index": "Well"})
    well_col = "ID" if "ID" in pm.columns else ("WellID" if "WellID" in pm.columns else "Well")
    groups = pm.groupby("Condition")[well_col].apply(list).to_dict()
    return groups

def run_nparc_external(raw_wide_k: pd.DataFrame,
                       raw_corr_wide_k: pd.DataFrame,
                       platemap: pd.DataFrame,
                       value: str = "BaselineCorrected"):
    assert value in ("Raw", "BaselineCorrected")
    wide_k = raw_corr_wide_k if value == "BaselineCorrected" else raw_wide_k
    temps_c = _temperatures_from_wide(wide_k)
    groups = _condition_groups(platemap)
    rows, summaries = [], []

    for cond, wells in groups.items():
        sub = platemap.loc[platemap.index.intersection(wells)].copy()
        if "Concentration" not in sub.columns:
            continue
        conc_map = sub["Concentration"].astype(float).to_dict()
        conc_vals = pd.Series(conc_map, dtype=float).dropna().values
        if len(np.unique(np.round(conc_vals, 12))) < 3:
            continue  # need ≥3 distinct concentrations

        rss_null_list, rss_alt_list = [], []

        for ti, tC in enumerate(temps_c):
            x, y = [], []
            for w in wells:
                yv = wide_k.iloc[ti][w] if w in wide_k.columns else np.nan
                xv = conc_map.get(w, np.nan)
                x.append(xv); y.append(yv)
            x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
            m = np.isfinite(x) & np.isfinite(y)
            x, y = x[m], y[m]
            if len(x) < 3 or len(np.unique(np.round(x, 12))) < 2:
                continue
            rss0, yv0, _ = _fit_null_const(x, y)
            rss1, yv1, _, _ = _fit_4pl(x, y)
            if np.isfinite(rss0) and np.isfinite(rss1):
                rows.append({
                    "Condition": cond,
                    "Temperature_C": float(tC),
                    "RSS_null": float(rss0),
                    "RSS_alt": float(rss1),
                    "N_points": int(len(yv0)),
                    "value_type": value
                })
                rss_null_list.append(rss0); rss_alt_list.append(rss1)

        rss0 = np.asarray(rss_null_list, dtype=float)
        rss1 = np.asarray(rss_alt_list, dtype=float)
        m = np.isfinite(rss0) & np.isfinite(rss1)
        rss0, rss1 = rss0[m], rss1[m]
        if len(rss0) >= 5:
            try:
                U, p = mannwhitneyu(rss1, rss0, alternative="less", method="auto")
            except Exception:
                U, p = np.nan, np.nan
            summaries.append({
                "Condition": cond,
                "n_temperatures": int(len(rss0)),
                "U_stat": float(U) if np.isfinite(U) else np.nan,
                "p_value": float(p) if np.isfinite(p) else np.nan,
                "median_RSS_null": float(np.nanmedian(rss0)) if len(rss0) else np.nan,
                "median_RSS_alt": float(np.nanmedian(rss1)) if len(rss1) else np.nan,
                "frac_alt_better": float(np.mean(rss1 < rss0)) if len(rss1) else np.nan,
                "value_type": value
            })

    rss_long = pd.DataFrame(rows)
    summary = pd.DataFrame(summaries)
    # BH-FDR within each value_type
    if not summary.empty and summary["p_value"].notna().any():
        out = []
        for vt, subdf in summary.groupby("value_type", dropna=False):
            pv = subdf["p_value"].to_numpy()
            m = len(pv)
            order = np.argsort(pv)
            ranks = np.empty_like(order); ranks[order] = np.arange(1, m+1)
            q = pv * m / ranks
            q_sorted = np.minimum.accumulate(q[order][::-1])[::-1]
            q_adj = np.empty_like(q); q_adj[order] = q_sorted
            s2 = subdf.copy(); s2["p_adj_BH"] = q_adj
            out.append(s2)
        summary = pd.concat(out, ignore_index=True)
    else:
        summary["p_adj_BH"] = np.nan

    return {"rss_long": rss_long, "summary": summary}

def export_nparc_plots(nparc_rss_long: pd.DataFrame,
                       raw_wide_k: pd.DataFrame,
                       raw_corr_wide_k: pd.DataFrame,
                       platemap: pd.DataFrame,
                       outdir: Path,
                       value: str = "BaselineCorrected"):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    wide_k = raw_corr_wide_k if value == "BaselineCorrected" else raw_wide_k
    temps_c = _temperatures_from_wide(wide_k)
    groups = _condition_groups(platemap)

    for cond, wells in groups.items():
        dfc = nparc_rss_long[nparc_rss_long["Condition"] == cond]
        if dfc.empty:
            continue
        # RSS vs T
        fig, ax = plt.subplots(figsize=(6,4), dpi=150)
        dfc_sorted = dfc.sort_values("Temperature_C")
        ax.plot(dfc_sorted["Temperature_C"], dfc_sorted["RSS_null"], label="RSS null")
        ax.plot(dfc_sorted["Temperature_C"], dfc_sorted["RSS_alt"], label="RSS alt (4pLL)")
        ax.set_xlabel("Temperature (°C)"); ax.set_ylabel("Residual sum of squares")
        ax.set_title(f"NPARC RSS — {cond} [{value}]"); ax.legend(loc="best", fontsize=8)
        fig.tight_layout(); fig.savefig(outdir / f"{cond.replace('/','-')}__RSS_vs_T.png"); plt.close(fig)

        # Representative temperatures
        used_T = dfc_sorted["Temperature_C"].to_numpy()
        if used_T.size == 0:
            continue
        for q in [0.25, 0.5, 0.75]:
            Tsel = float(np.quantile(used_T, q))
            ti = int(np.argmin(np.abs(temps_c - Tsel)))
            Tactual = float(temps_c[ti])
            # dose-response data at Tactual
            concs, ys = [], []
            for w in wells:
                c = platemap.loc[w, "Concentration"] if w in platemap.index else np.nan
                y = wide_k.iloc[ti][w] if w in wide_k.columns else np.nan
                concs.append(float(c) if pd.notna(c) else np.nan)
                ys.append(float(y) if pd.notna(y) else np.nan)
            concs = np.asarray(concs, dtype=float); ys = np.asarray(ys, dtype=float)
            m = np.isfinite(concs) & np.isfinite(ys)
            concs, ys = concs[m], ys[m]
            if concs.size < 3 or len(np.unique(np.round(concs,12))) < 2:
                continue
            _, _, _ = _fit_null_const(concs, ys)
            _, _, _, popt = _fit_4pl(concs, ys)
            xgrid = np.linspace(max(1e-12, np.nanmin(concs[concs>0]) if np.any(concs>0) else 1e-12),
                                max(np.nanmax(concs), 1.0), 200)
            fig, ax = plt.subplots(figsize=(6,4), dpi=150)
            ax.scatter(concs, ys, s=12, label="data")
            ax.hlines(np.nanmean(ys), xmin=np.nanmin(concs), xmax=np.nanmax(concs), linestyles="--", label="null const")
            if popt is not None:
                ax.plot(xgrid, _four_pl_loglogistic(xgrid, *popt), label="4pLL fit")
            ax.set_xscale("log")
            ax.set_xlabel("Concentration"); ax.set_ylabel(f"Signal ({value})")
            ax.set_title(f"{cond} — {value} @ {Tactual:.1f} °C")
            ax.legend(loc="best", fontsize=8)
            fig.tight_layout()
            outname = f"{cond.replace('/','-')}__DR_at_{Tactual:.1f}C.png".replace(".", "p")
            fig.savefig(outdir / outname); plt.close(fig)

# ---------------- Runner ----------------

def main():
    ap = argparse.ArgumentParser(description="External NPARC runner (no edits to your code).")
    ap.add_argument("--pyrt", required=True, help="Path to your pyrt_cetsa.py")
    ap.add_argument("--platemap", required=True)
    ap.add_argument("--plate", required=True)
    ap.add_argument("--tmin", type=float, default=37.0)
    ap.add_argument("--tmax", type=float, default=90.0)
    ap.add_argument("--out", required=True, help="Excel output path (NPARC sheets will be (re)written)")
    ap.add_argument("--plots", help="Directory for NPARC plots (optional)")
    args = ap.parse_args()

    PYRT = Path(args.pyrt)
    spec = importlib.util.spec_from_file_location("pc", str(PYRT))
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    print("Loaded:", pc.__file__)

    # Load inputs with your helpers
    platemap_df = pc.load_platemap_384(Path(args.platemap), sample_sheet=None, conc_sheet=None)
    plate_wide_c, dbg = pc.load_plate_auto(Path(args.plate), t_min_c=args.tmin, t_max_c=args.tmax, matrix_sheet=None)

    # Run original pipeline
    mp_core = pc._import_moltenprot(Path(args.pyrt).parent)
    analysis = pc.run_analysis(plate_wide_c, platemap_df, model="santoro1988", mp_core=mp_core)

    # Compute NPARC (Raw + BaselineCorrected)
    nparc_bc = run_nparc_external(analysis["raw_wide"], analysis["raw_corr_wide"], platemap_df, value="BaselineCorrected")
    nparc_raw = run_nparc_external(analysis["raw_wide"], analysis["raw_corr_wide"], platemap_df, value="Raw")
    summary = pd.concat([nparc_bc["summary"], nparc_raw["summary"]], ignore_index=True, sort=False)
    rss_long = pd.concat([nparc_bc["rss_long"], nparc_raw["rss_long"]], ignore_index=True, sort=False)

    # Ensure base workbook exists (write it if not)
    out_xlsx = Path(args.out)
    if not out_xlsx.exists():
        pc.write_analysis_with_platemap(
            analysis, platemap_df, out_xlsx,
            include_all_wells=True,
            input_wide_c=plate_wide_c,
            matrix_debug=(dbg if isinstance(dbg, dict) else None),
        )

    # Append/replace NPARC sheets
    with pd.ExcelWriter(out_xlsx, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        summary.to_excel(writer, sheet_name="NPARC summary", index=False)
        rss_long.to_excel(writer, sheet_name="NPARC RSS (long)", index=False)

    print(f"Wrote NPARC sheets to {out_xlsx}")
    print(f"NPARC summary rows: {len(summary)}; RSS rows: {len(rss_long)}")

    # Optional plots
    if args.plots:
        plots = Path(args.plots)
        export_nparc_plots(rss_long.query("value_type == 'BaselineCorrected'"), analysis["raw_wide"], analysis["raw_corr_wide"], platemap_df, plots / "nparc", value="BaselineCorrected")
        export_nparc_plots(rss_long.query("value_type == 'Raw'"), analysis["raw_wide"], analysis["raw_corr_wide"], platemap_df, plots / "nparc_raw", value="Raw")
        print(f"NPARC plots written to {plots}")

if __name__ == "__main__":
    main()
