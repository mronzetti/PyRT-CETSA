#!/usr/bin/env python3

"""
Copyright 2018-2021 Vadim Kotov, Thomas C. Marlovits

    This file is part of MoltenProt.

    MoltenProt is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    MoltenProt is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with MoltenProt.  If not, see <https://www.gnu.org/licenses/>.
"""

# CLI interface
import argparse

# creating folders
import os
import sys

# deleting folders
from shutil import rmtree

# get the current date and time (GUI progressbar)
import time

# running git queries
# import subprocess
# HACK this allows to test the module without proper installation:
# python moltenprot --help
path = os.path.dirname(sys.modules[__name__].__file__)
path = os.path.join(path, "..")
sys.path.insert(0, path)
from moltenprot import core

### Parser for CLI options
def CLIparser():
    """
    Creates the command-line argument parser object
    
    Returns
    -------
    parser
        arparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="A robust toolkit for assessment and optimization of  protein thermostability.",
        # required to print default values in the help
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # argument groups
    gen_grp = parser.add_argument_group("General options")
    smp_grp = parser.add_argument_group("Sample annotation")
    pre_grp = parser.add_argument_group("Pre-processing")
    ana_grp = parser.add_argument_group("Analysis options")
    csv_grp = parser.add_argument_group("CSV-specific settings")
    xls_grp = parser.add_argument_group("XLSX-specific settings")
    out_grp = parser.add_argument_group("Output options")

    # most default values and option descriptions are stored in protefitmod.MoltenProtFit.defaults attribute

    # TODO for some options add "choices=[a,b,c]" argument, which would specify allowed values
    # NOTE set help=argparse.SUPPRESS to hide the option from the help message
    # TODO in each group arrange options in order of their usefulness

    ## General options

    # argument for GUI mode
    gen_grp.add_argument(
        "--gui",
        action="store_true",
        help="Start the GUI version, all other command-line options will be ignored",
    )

    # new filename argument, required for CLI version
    gen_grp.add_argument(
        "--input",
        "-i",
        nargs="+",
        help="Specify one or more *.csv or *.xlsx files with data; this option is required in CLI mode",
    )

    # prefix for the output
    gen_grp.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output folder name; if nothing is supplied, output folder has the same name as the input file; for multiple file input each file gets a subfolder in the output folder",
    )

    # overwrite output folder if it exists
    # -o is more expected for output, so rename option to "force"
    gen_grp.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing results"
    )

    # option to run the code in parallel
    gen_grp.add_argument(
        "-j",
        "--n_jobs",
        default=core.defaults["j"],
        type=int,
        help=core.defaults["j_h"],
    )

    # a switch to enable "verbose" version of the script
    gen_grp.add_argument(
        "-v", "--verbose", action="store_true", help="Print additional information"
    )

    # citation
    gen_grp.add_argument(
        "--citation", action="store_true", help="Print the current MoltenProt reference"
    )

    ## Sample annotation

    # show available readouts
    smp_grp.add_argument(
        "--print_readouts",
        action="store_true",
        help="For XLSX input: show available readouts stored in the file; use these names to exclude readouts from analysis; NOTE: exclusion of F330 and F350 from XLSX file does not affect calculation of deltaF",
    )

    # exlude the whole readout
    smp_grp.add_argument(
        "--exclude_readout",
        nargs="+",
        type=str,
        help="Skip processing of one or more readouts; use --print_readouts to get available readout names",
    )

    # specify layout file
    smp_grp.add_argument(
        "--layout",
        type=str,
        help="Select layout file for the plate; if multiple input files are supplied, the same layout will be used for all of them; for *.xlsx input the layout is read from the annotations sheet",
    )

    # argument for excluding wells (e.g. some outliers or just empty ones); currently only individual names are supported
    smp_grp.add_argument(
        "--exclude",
        nargs="+",
        type=str,
        default=core.prep_defaults["exclude"],
        help=core.prep_defaults["exclude_h"],
    )

    # argument for blank wells (can accept multiple parameters, but they're all averaged)
    smp_grp.add_argument(
        "--blank",
        nargs="+",
        type=str,
        default=core.prep_defaults["blanks"],
        help=core.prep_defaults["blanks_h"],
    )

    ## Pre-processing options

    # remove parts of curves
    pre_grp.add_argument(
        "--trim_min",
        type=float,
        default=core.prep_defaults["trim_min"],
        help=core.prep_defaults["trim_min_h"],
    )
    pre_grp.add_argument(
        "--trim_max",
        type=float,
        default=core.prep_defaults["trim_max"],
        help=core.prep_defaults["trim_max_h"],
    )
    # set if the the post-transition baseline is lower than the pre-transition baseline
    pre_grp.add_argument(
        "--invert",
        default=core.prep_defaults["invert"],
        action="store_true",
        help=core.prep_defaults["invert_h"],
    )
    # shrinking/binning of the data
    pre_grp.add_argument("--shrink", type=float, help=core.prep_defaults["shrink_h"])
    # median filtering
    pre_grp.add_argument(
        "--mfilt",
        default=core.prep_defaults["mfilt"],
        type=float,
        help=core.prep_defaults["mfilt_h"],
    )
    # SavGol filter for the derivative (only newer scipy versions)
    pre_grp.add_argument(
        "--savgol",
        type=float,
        default=core.analysis_defaults["savgol"],
        help=core.analysis_defaults["savgol_h"],
    )

    ## Analysis options

    # select the fitting equation/data processing approach
    ana_grp.add_argument(
        "--model",
        default=core.analysis_defaults["model"],
        choices=core.avail_models.keys(),
        help=core.analysis_defaults["model_h"],
    )

    # specify separate scattering options for multi-data inputs
    # TODO ideally, if nothing is specified then use the normal analysis/sort options
    ana_grp.add_argument(
        "--model_sct",
        default="santoro1988d",
        help="XLSX input only: supply a different model for scattering analysis",
    )

    # pre-evaluation of the baselines
    ana_grp.add_argument(
        "--baseline_fit",
        type=float,
        default=core.analysis_defaults["baseline_fit"],
        help=core.analysis_defaults["baseline_fit_h"],
    )
    # parameter bounds for baselines (computed from the pre-fitting routine)
    ana_grp.add_argument(
        "--baseline_bounds",
        type=int,
        default=core.analysis_defaults["baseline_bounds"],
        help=core.analysis_defaults["baseline_bounds_h"],
    )

    # heat capacity change of unfolding for all samples (per-sample heat-capacity can be specfied in the layout)
    # NOTE this setting is overridden by the layout
    ana_grp.add_argument(
        "--dCp",
        type=float,
        default=core.analysis_defaults["dCp"],
        help=core.analysis_defaults["dCp_h"],
    )

    ## CSV-specific options

    # separator argument
    csv_grp.add_argument(
        "--sep", default=core.defaults["sep"], type=str, help=core.defaults["sep_h"]
    )

    # decimal separator argument
    csv_grp.add_argument(
        "--dec", default=core.defaults["dec"], type=str, help=core.defaults["dec_h"]
    )

    csv_grp.add_argument(
        "--spectrum", action="store_true", help=core.defaults["spectrum_h"]
    )

    # for CSV input - specify with denaturant is used and type of readout
    csv_grp.add_argument(
        "-d",
        "--denaturant",
        default=core.defaults["denaturant"],
        help=core.defaults["denaturant_h"],
    )
    csv_grp.add_argument(
        "--readout", default=core.defaults["readout"], help=core.defaults["readout_h"]
    )

    # no default entry needed, because it will be set to None if not a float
    csv_grp.add_argument(
        "--scan_rate",
        type=float,
        help="Set scan rate in degrees per minute; this option is only relevant for kinetic models applied to data from CSV files",
    )

    ## XLSX-specific settings
    # refolding ramp
    xls_grp.add_argument(
        "--refold",
        action="store_true",
        help="For XLSX input: indicate if refolding ramp was used",
    )

    # raw data
    xls_grp.add_argument(
        "--raw",
        action="store_true",
        help='For XLSX input: indicate if "raw" rather than "processed" file is provided',
    )

    ## Output options

    # heatmap colormap
    out_grp.add_argument(
        "--hm_cmap",
        type=str,
        default=core.defaults["heatmap_cmap"],
        help=core.defaults["heatmap_cmap_h"],
    )

    # report argument
    out_grp.add_argument(
        "-r",
        "--report_format",
        default=None,
        choices=["pdf", "xlsx", "html"],
        help="Make a report in PDF, XLSX or HTML format",
    )

    # argument for *.xlsx export
    out_grp.add_argument(
        "-x",
        "--xlsx",
        action="store_true",
        help="Output a single *.xlsx file instead of several *.csv",
    )

    # only save a MoltenProt session
    out_grp.add_argument(
        "--json",
        action="store_true",
        help="Only save a MoltenProt session file (in *.json format); this option overrides any other output options",
    )

    # argument for specifying if generating images is needed
    out_grp.add_argument(
        "--genpics",
        action="store_true",
        help="Generate plots of experimental data, fits and derivatives",
    )

    # argument for creating heatmaps
    out_grp.add_argument(
        "--heatmaps",
        nargs="+",
        type=str,
        help='Specify this option to generate heatmaps; valid arguments are "all" or any column name(s) from plate_results.csv ',
    )

    # argument for heatmaps' reference
    out_grp.add_argument(
        "--hm_ref", type=str, help=argparse.SUPPRESS
    )  #'Specify the reference for heatmaps (doesn\'t work without --heatmap option)')

    return parser


### Main functions CLI and GUI
def MoltenprotCLI(args):
    """
    
    Run MoltenProt analysis in command-line mode

    Parameters
    ----------
    args : namespace
        CLI paramater namespace
    """
    # print citation and exit
    if args.citation:
        print(core.citation["long"])
        sys.exit(0)

    # print version info from core
    if args.verbose:
        core.showVersionInformation()

    # check if --input option is provided and the file exists
    if args.input is None:
        # NOTE this part is only required when neither --gui nor --input are supplied, but at least one other option is supplied
        print("Fatal: Please supply at least one input file or start the GUI mode")
        sys.exit(1)

    # check if the user requested too many jobs:
    if args.n_jobs > 1:
        from multiprocessing import cpu_count

        if args.n_jobs > cpu_count():
            print(
                "Warning: the amount of requested jobs ({}) is higher than the amount of CPU's available ({})\nprogram execution may be slow!".format(
                    args.n_jobs, cpu_count()
                )
            )

    # if something is provided, than we have to cycle through it
    for input_file in args.input:
        print("Information: processing file {}".format(input_file))
        # check file existence
        if not os.path.exists(input_file):
            # check if file exists, if not then break the loop
            # and continue to the next file
            print("Fatal: {} does not exist!".format(input_file))
            continue

        # generate output folder and file extension
        resultfolder, file_ext = os.path.splitext(input_file)

        # if -o is not supplied, create the output folder in the same folder as input file
        # otherwise create a requested folder and dump all outputs there
        if args.output is not None:
            resultfolder = os.path.join(args.output, os.path.basename(resultfolder))

        # check if the output folder exists and delete if necessary
        if os.path.exists(resultfolder):
            if args.force:
                print("Information: Removing previously calculated results...")
                try:
                    rmtree(resultfolder)
                except OSError:
                    print(
                        "Fatal: cannot remove results file, because some other program is using it"
                    )
                    continue
            else:
                print(
                    "Fatal: cannot create result folder, because a folder with the same name already exists!"
                )
                print(
                    "Information: You can specify --force option to override this error"
                )
                continue

        # after all checks are done, the folder can be created
        os.makedirs(resultfolder)

        if file_ext == ".csv":
            if args.spectrum:
                data = core.parse_spectrum_csv(
                    input_file,
                    scan_rate=args.scan_rate,
                    sep=args.sep,
                    dec=args.dec,
                    denaturant=args.denaturant,
                    readout=args.readout,
                )
            else:
                data = core.parse_plain_csv(
                    input_file,
                    scan_rate=args.scan_rate,
                    sep=args.sep,
                    dec=args.dec,
                    layout=args.layout,
                    denaturant=args.denaturant,
                    readout=args.readout,
                )
        elif file_ext == ".xlsx":
            if args.model == "lumry_eyring":
                LE = True
            else:
                LE = False

            data = core.parse_prom_xlsx(
                input_file, raw=args.raw, refold=args.refold, LE=LE
            )

        elif file_ext == ".json":
            # NOTE currently this would mean that the previous JSON session is re-analysed with new settings
            # TODO how to auto-set the outfolder here?
            data = core.mp_from_json(input_file)
        else:
            print('Fatal: unsupported file format "{}"'.format(file_ext))
            continue

        if args.print_readouts:
            print("These readouts are available in the input file:")
            print(" ".join(data.GetDatasets()))
            continue

        # extract analysis-related settings in a separate dict
        analysis_kwargs = core.analysis_kwargs(args.__dict__)
        data.SetAnalysisOptions("all", **analysis_kwargs)

        # HACK if the instance was made from JSON, let it know that LE analysis will be run
        if file_ext == ".json" and args.model == "lumry_eyring":
            data.__class__ = core.MoltenProtFitMultipleLE

        # special settings for scattering (this give a second set-analysis message to the log)
        # NOTE this will not affect LE mode, because the Scattering settings are hard-coded in method
        # PrepareAndAnalyseAll
        if "Scattering" in data.GetDatasets():
            if args.model_sct:
                analysis_kwargs["model"] = args.model_sct
            data.SetAnalysisOptions("Scattering", **analysis_kwargs)

        # set model to "skip" for readouts that should not be processed (the data will be still available)
        if args.exclude_readout is not None:
            for readout in args.exclude_readout:
                if data.datasets.get(readout):
                    data.datasets[readout].model = "skip"
                    cont = False
                else:
                    print(
                        "Fatal: readout {} not found in the input file; use --print_readouts to get available readouts".format(
                            readout
                        )
                    )
                    # terminate this loop and signal to the file loop that the next file must be processed
                    cont = True
                    break
            if cont:
                continue

        data.PrepareAndAnalyseAll(n_jobs=args.n_jobs)

        if args.json:
            core.mp_to_json(data, os.path.join(resultfolder, "MP_session.json"))
        else:
            data.WriteOutputAll(
                outfolder=resultfolder,
                report_format=args.report_format,
                xlsx=args.xlsx,
                genpics=args.genpics,
                heatmaps=args.heatmaps,
                n_jobs=args.n_jobs,
                session=True,
                heatmap_cmap=args.hm_cmap,
            )


# ATTENTION!
# Below is doxygen documentation code.
##  \brief Start up the GUI of MoltenProt
#     \details
#   - Import necessary PyQt modules and show information about PyQt and Qt versions used in current python environment.
#   - Create Qt GUI application.
#   - Create and show splashscreen.
#   - Create MoltenProtMainWindow class instance and set it size and placement.
#   - Run GUI MoltenProt application.
#    \sa moltenprotgui.MoltenProtMainWindow
#     \param localizationStuffFlag - If True use Qt internationalization facilities.
#     \todo TODO list for MoltenprotGUI.
def MoltenprotGUI(localizationStuffFlag=False):
    import PyQt5.QtCore as QtCore
    from PyQt5.QtCore import QTranslator, QLocale, Qt
    from PyQt5.QtWidgets import (
        QApplication,
        QSplashScreen,
        QDesktopWidget,
        QProgressBar,
    )
    from PyQt5.QtGui import QPixmap, QIcon

    from moltenprot import gui

    """
    Some tricks for the GUI to supprot Hi-DPI displays, see below for more info:
    https://stackoverflow.com/questions/41331201/pyqt-5-and-4k-screen
    https://doc.qt.io/qt-5/highdpi.html
    """
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)

    splashPixmap = QPixmap(":/splash.png")
    # splash = QSplashScreen(QDesktopWidget().screen(), splashPixmap, Qt.WindowStaysOnTopHint)
    splash = QSplashScreen(splashPixmap)
    splash.setEnabled(False)
    # adding progress bar
    progressBar = QProgressBar(splash)
    progressBar.setMaximum(10)
    progressBar.setGeometry(0, splashPixmap.height() - 50, splashPixmap.width(), 20)
    splash.show()
    for i in range(1, 11):
        progressBar.setValue(i)
        t = time.time()
        while time.time() < t + 0.1:
            app.processEvents()

    if localizationStuffFlag:
        # Localization stuff
        locale = QLocale.system().name()
        print(locale)
        qtTranslator = QTranslator()
        # if qtTranslator.load("qt_" + locale, ":/"):
        if qtTranslator.load("qt_ru", ":/"):
            app.installTranslator(qtTranslator)
        else:
            print("Failed to load locale")
        appTranslator = QTranslator()
        if appTranslator.load("moltenprot_ru", ":/"):
            app.installTranslator(appTranslator)
        else:
            print("Failed to load application locale.")
    else:
        pass  # Localization not implemented
    app.setOrganizationName("MoltenProt")
    app.setApplicationName("moltenprot")
    app.setWindowIcon(QIcon(":/MP_icon.png"))
    # print app.arguments()
    moltenProtMainWindow = gui.MoltenProtMainWindow()
    width = int(moltenProtMainWindow.width())
    height = int(moltenProtMainWindow.height())
    wid = QDesktopWidget()
    screenWidth = int(wid.screen().width())
    screenHeight = int(wid.screen().height())
    moltenProtMainWindow.setGeometry(
        int((screenWidth / 2) - (width / 2)),
        int((screenHeight / 2) - (height / 2)),
        width,
        height,
    )
    # forces main window decorator on Windows
    moltenProtMainWindow.setWindowFlags(Qt.Window)
    moltenProtMainWindow.show()
    # Hide splashscreen
    splash.finish(moltenProtMainWindow)
    app.exec_()


##  \brief Main function for the startup script
def main():
    """Main function for the startup script"""
    # create the parser object
    parser = CLIparser()
    # put the args in variables
    args = parser.parse_args()

    # check if any arguments were supplied
    if len(sys.argv[1:]) == 0:
        # if running in PyInstaller bundle, start the GUI
        if core.from_pyinstaller:
            args.gui = True
        else:
            parser.print_help()
            sys.exit(0)

    if args.gui:
        MoltenprotGUI()
    else:
        MoltenprotCLI(args)


if __name__ == "__main__":
    main()
