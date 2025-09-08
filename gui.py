# -*- coding: utf-8 -*-

# Copyright 2018-2021 Vadim Kotov, Thomas C. Marlovits
#
#   This file is part of MoltenProt.
#
#    MoltenProt is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#    MoltenProt is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#    along with MoltenProt.  If not, see <https://www.gnu.org/licenses/>.

# handling exceptions
import sys, os

# For platform description
import platform

# Data processing modules
import pandas as pd
import numpy as np

# core MoltenProt functions
from . import core

# Graphics module.
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import cm

# import PyQt5
try:
    from PyQt5.QtCore import (
        QThread,
        QThreadPool,
        QRunnable,
        QObject,
        pyqtSignal,
        pyqtSlot,
        QAbstractTableModel,
        Qt,
        QFile,
        # QTextStream,# for text logging, disabled
        QSettings,
        QEvent,
        QUrl,
        QFileInfo,
        QSize,
    )
    from PyQt5.QtGui import QColor, QIcon, QKeySequence, QPalette, QFont
    from PyQt5.QtWidgets import (
        QMainWindow,
        QDialog,
        QAction,
        QLabel,
        QComboBox,
        QToolBar,
        QWidget,
        QTableWidgetItem,
        QTextBrowser,
        QListView,
    )
    from PyQt5.QtWidgets import (
        QAbstractItemView,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QDialogButtonBox,
        QMessageBox,
        QFileDialog,
        QFontDialog,
    )
    from PyQt5.QtWidgets import QApplication, QDesktopWidget, QHeaderView, QItemDelegate
    from PyQt5.Qt import PYQT_VERSION_STR
    from PyQt5 import uic, QtWidgets
except ImportError:
    print(
        "Fatal: PyQt5 module not found or import of one or more modules from PyQt5 has failed."
    )
    sys.exit(1)

from .ui import resources  # detected as false-positive in pyflakes

# For printing line number and file name
from inspect import currentframe, getframeinfo

cf = currentframe()
cfFilename = getframeinfo(cf).filename

# check if core can do parallelization and set cpuCount
if core.parallelization:
    from multiprocessing import cpu_count

    cpuCount = cpu_count()
else:
    cpuCount = 1

# for passing clicked button ID's
from functools import partial

showVersionInformation = False
if showVersionInformation:
    core.showVersionInformation()
    print("PyQt5            : {}".format(PYQT_VERSION_STR))

# A cycler for color-safe 8-color palette from https://jfly.uni-koeln.de/color/
from cycler import cycler
import traceback

# Color-safe 8-color palette from https://jfly.uni-koeln.de/color/
colorsafe_cycler = cycler(
    color=[
        "#0077B8",
        "#F4640D",
        "#FAA200",
        "#00B7EC",
        "#00A077",
        "#F4E635",
        "#E37DAC",
        "#242424",
    ]
)


class ExportThread(QThread):
    exportThreadSignal = pyqtSignal(str)

    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        print(type(parent))

    def run(self):
        for i in range(1, 21):
            self.sleep(3)
            self.exportThreadSignal.emit("i = %s" % i)


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data
    
    error
        `tuple` (exctype, value, traceback.format_exc() )
    
    result
        `object` data returned from processing, anything

    progress
        `int` indicating % progress 

    """

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class ExportWorker(QRunnable):
    """
    Worker thread - runs data export in a separate thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and 
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, *args, **kwargs):
        super(ExportWorker, self).__init__()

        # Store constructor arguments (re-used for processing)
        # self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        # self.kwargs["progress_callback"] = self.signals.progress

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """

        # Retrieve args/kwargs here; and fire processing using them
        try:
            # result = self.fn(*self.args, **self.kwargs)
            # print(type(self.args),  self.args)
            # filename, xlsx, withReport, heatmaps, genpics, n_jobs
            moltenProtFitMultiple = self.args[0]
            # filename = self.args[1]
            # xlsx = self.args[2]
            # withReport = self.args[3]
            # heatmaps = self.args[3]
            # genpics = self.args[4]
            # n_jobs = self.args[5]
            # report_choice = self.args[6]
            print("Running export thread", type(self.signals.progress))
            moltenProtFitMultiple.WriteOutputAll(**self.kwargs)
            # No report done, follow the heatmaps/xlsx/genfigs settings
            """
            withReport = False
            if report_choice == 2:
                # HTML report
                withReport = True
            if report_choice == 1:
                filename = os.path.join(filename, "Summary.xlsx")
                # all filters and duplicate merging is skipped
                moltenProtFitMultiple.CombineResults(filename, -1, -1, False)
            else:
                moltenProtFitMultiple.WriteOutputAll(
                    outfolder=filename,
                    xlsx=xlsx,
                    report=withReport,
                    heatmaps=heatmaps,
                    genpics=genpics,
                    n_jobs=n_jobs,
                )
            """
            self.signals.progress.emit(1)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        # else:
        # self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


##  \brief This class implements Help Dialog of MoltenProt.
#     \details Simpliest help system. Help information should be placed in subdirectory with name "help".
class MoltenProtHelpDialog(QDialog):
    ##  \brief MoltenProtHelpDialog constructor.
    #     \details MoltenProtHelpDialog is created programmaticaly, not from ui file. Create simple text browser with two navgation buttons - Home and Back.
    #                   Information about Html help files location should be placed in resources.qrc
    #   <qresource>
    #       <file alias="editmenu.html">help/editmenu.html</file>
    #       <file alias="filemenu.html">help/filemenu.html</file>
    #       <file alias="index.html">help/index.html</file>
    #   </qresource>
    #    \param page - Initial html page.
    def __init__(self, page, parent=None):
        super(MoltenProtHelpDialog, self).__init__(parent)
        # self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_GroupLeader)
        self.setWindowTitle("MoltenProt Help")

        backAction = QAction(QIcon(":/back.svgz"), self.tr("&Back"), self)
        backAction.setShortcut(QKeySequence.Back)
        homeAction = QAction(QIcon(":/home.svgz"), self.tr("&Home"), self)
        homeAction.setShortcut(self.tr("Home"))
        self.pageLabel = QLabel()

        toolBar = QToolBar()
        toolBar.addAction(backAction)
        toolBar.addAction(homeAction)
        toolBar.addWidget(self.pageLabel)
        toolBar.setToolTip("toolBar.setToolTip")
        self.textBrowser = QTextBrowser()

        layout = QVBoxLayout()
        layout.addWidget(toolBar)
        layout.addWidget(self.textBrowser, 1)
        self.setLayout(layout)

        # self.connect(backAction, SIGNAL("triggered()"), self.textBrowser, SLOT("backward()"))
        # QtCore.QObject.connect(backAction, SIGNAL("triggered()"), self.textBrowser, SLOT("backward()"))
        backAction.triggered.connect(self.textBrowser.backward)
        # backAction.triggered.connect()
        # self.connect(homeAction, SIGNAL("triggered()"), self.textBrowser, SLOT("home()"))
        homeAction.triggered.connect(self.textBrowser.home)
        # self.connect(self.textBrowser, SIGNAL("sourceChanged(QUrl)"), self.updatePageTitle)
        self.textBrowser.sourceChanged.connect(self.updatePageTitle)

        self.textBrowser.setSearchPaths([":/"])
        self.textBrowser.setSource(QUrl(page))
        self.resize(400, 600)

    ##  \brief  Show page title according to selected help item.
    def updatePageTitle(self):
        self.pageLabel.setText(self.textBrowser.documentTitle())


# from ui_layout import Ui_layoutDialog
##  \brief This class implements Layout Dialog of MoltenProt.
#     \details Dialog description is located in layout-designer.ui file. This file can be edited in Qt designer. The following command should be issued after editing layout-designer.ui file :
#   - pyside-uic -o ui_layout.py      layout_designer.ui
class LayoutDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)

        # self.ui = Ui_layoutDialog()
        # self.ui.setupUi(self)
        uifile = QFile(":/layout.ui")
        uifile.open(QFile.ReadOnly)
        self.ui = uic.loadUi(uifile, self)
        uifile.close()
        # Method myAccept will be called when user pressed Ok button
        self.ui.buttonBox.accepted.connect(self.myAccept)
        # Method myReject will be called when user pressed Ok button
        self.ui.buttonBox.rejected.connect(self.myReject)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)

        blankAction = QAction("Blank", self)
        blankAction.triggered.connect(self.on_blankAction)
        self.addAction(blankAction)

        """
        #NOTE not implemented in main module, currently disabled
        referenceAction = QAction("Reference", self)
        referenceAction.triggered.connect(self.on_refAction)
        self.addAction(referenceAction)
        """

        ignoreAction = QAction("Ignore", self)
        ignoreAction.triggered.connect(self.on_ignoreAction)
        self.addAction(ignoreAction)

        clearSelectedAction = QAction("Clear selected cells", self)
        clearSelectedAction.triggered.connect(self.on_clearSelectedAction)
        self.addAction(clearSelectedAction)

    @pyqtSlot()
    def on_blankAction(self):
        for currentQTableWidgetItem in self.ui.tableWidget.selectedItems():
            currentQTableWidgetItem.setText("Blank")

    @pyqtSlot()
    def on_refAction(self):
        for currentQTableWidgetItem in self.ui.tableWidget.selectedItems():
            currentQTableWidgetItem.setText("Reference")

    @pyqtSlot()
    def on_ignoreAction(self):
        for currentQTableWidgetItem in self.ui.tableWidget.selectedItems():
            currentQTableWidgetItem.setText("Ignore")

    def on_clearSelectedAction(self):
        for currentQTableWidgetItem in self.ui.tableWidget.selectedItems():
            currentQTableWidgetItem.setText("")

    @pyqtSlot()
    def myAccept(self):
        if showVersionInformation:
            print("myAccept")
        # Hide dialog
        self.close()

    def myReject(self):
        if showVersionInformation:
            print("myReject")
        # Hide dialog
        self.close()


##  \brief This class implements export/import and the other settings toolbox dialog of MoltenProt.
class MoltenProtToolBox(QDialog):
    def __init__(self, parent=None):
        super(MoltenProtToolBox, self).__init__(parent)
        if parent == None:
            print("parent == None", cfFilename, currentframe().f_lineno)
        self.parent = parent
        uifile = QFile(":/settings.ui")
        uifile.open(QFile.ReadOnly)
        self.ui = uic.loadUi(uifile, self)
        uifile.close()
        self.ui.buttonBox.accepted.connect(self.myAccept)
        self.ui.buttonBox.rejected.connect(self.myReject)
        self.ui.buttonBox.clicked["QAbstractButton*"].connect(self.buttonClicked)
        self.ui.parallelSpinBox.setMaximum(cpuCount - 1)
        self.settings = QSettings()
        self.restoreSettingsValues()

    # @pyqtSlot()
    def buttonClicked(self, button):
        # print("buttonClicked")
        role = self.buttonBox.buttonRole(button)
        if role == QDialogButtonBox.ResetRole:
            self.resetToDefaults()

    @pyqtSlot()
    def myAccept(self):
        self.settings.setValue(
            "toolbox/importSettingsPage/separatorInputText",
            self.ui.separatorInput.text(),
        )
        self.settings.setValue(
            "toolbox/importSettingsPage/decimalSeparatorInputText",
            self.ui.decimalSeparatorInput.text(),
        )
        self.settings.setValue(
            "toolbox/importSettingsPage/denaturantComboBoxIndex",
            self.ui.denaturantComboBox.currentIndex(),
        )
        self.settings.setValue(
            "toolbox/importSettingsPage/scanRateSpinBoxValue",
            self.ui.scanRateSpinBox.value(),
        )

        self.settings.setValue(
            "toolbox/importSettingsPage/spectrumCsvCheckBox",
            int(self.ui.spectrumCsvCheckBox.isChecked()),
        )

        self.settings.setValue(
            "toolbox/importSettingsPage/refoldingCheckBox",
            int(self.ui.refoldingCheckBox.isChecked()),
        )

        self.settings.setValue(
            "toolbox/importSettingsPage/rawCheckBox",
            int(self.ui.rawCheckBox.isChecked()),
        )

        self.settings.setValue(
            "toolbox/exportSettingsPage/outputFormatComboBoxIndex",
            self.ui.outputFormatComboBox.currentIndex(),
        )
        self.settings.setValue(
            "toolbox/exportSettingsPage/outputReportComboBoxIndex",
            self.ui.outputReportComboBox.currentIndex(),
        )
        # self.settings.setValue(
        #    "toolbox/exportSettingsPage/genpicsCheckBox",
        #    int(self.ui.genpicsCheckBox.isChecked()),
        # )
        # self.settings.setValue(
        #    "toolbox/exportSettingsPage/heatmapCheckBox",
        #    int(self.ui.heatmapCheckBox.isChecked()),
        # )

        self.settings.setValue(
            "toolbox/miscSettingsPage/parallelSpinBox", self.ui.parallelSpinBox.value()
        )
        self.settings.setValue(
            "toolbox/miscSettingsPage/colormapForPlotComboBoxIndex",
            self.ui.colormapForPlotComboBox.currentIndex(),
        )

        self.settings.setValue(
            "toolbox/plotSettingsPage/curveVlinesCheckBox",
            int(self.ui.curveVlinesCheckBox.isChecked()),
        )
        self.settings.setValue(
            "toolbox/plotSettingsPage/curveBaselineCheckBox",
            int(self.ui.curveBaselineCheckBox.isChecked()),
        )
        self.settings.setValue(
            "toolbox/plotSettingsPage/curveDerivativeCheckBox",
            int(self.ui.curveDerivativeCheckBox.isChecked()),
        )

        self.settings.setValue(
            "toolbox/plotSettingsPage/curveHeatmapColorCheckBox",
            int(self.ui.curveHeatmapColorCheckBox.isChecked()),
        )

        # self.settings.setValue(
        #    "toolbox/plotSettingsPage/curveLegendCheckBox",
        #    int(self.ui.curveLegendCheckBox.isChecked()),
        # )
        self.settings.setValue(
            "toolbox/plotSettingsPage/curveLegendComboBox",
            self.ui.curveLegendComboBox.currentIndex(),
        )
        self.settings.setValue(
            "toolbox/plotSettingsPage/curveMarkEverySpinBoxValue",
            self.ui.curveMarkEverySpinBox.value(),
        )
        self.settings.setValue(
            "toolbox/plotSettingsPage/curveTypeComboboxIndex",
            self.ui.curveTypeComboBox.currentIndex(),
        )
        self.settings.setValue(
            "toolbox/plotSettingsPage/curveViewComboboxIndex",
            self.ui.curveViewComboBox.currentIndex(),
        )

        self.close()

    @pyqtSlot()
    def myReject(self):
        self.restoreSettingsValues()
        self.close()

    def restoreSettingsValues(self):
        index = int(
            self.settings.value("toolbox/importSettingsPage/denaturantComboBoxIndex", 0)
        )
        self.ui.denaturantComboBox.setCurrentIndex(index)
        text = self.settings.value("toolbox/importSettingsPage/separatorInputText", ",")
        self.ui.separatorInput.setText(text)
        text = self.settings.value(
            "toolbox/importSettingsPage/decimalSeparatorInputText", "."
        )
        self.ui.decimalSeparatorInput.setText(text)
        value = float(
            self.settings.value("toolbox/importSettingsPage/scanRateSpinBoxValue", 1.0)
        )
        self.ui.scanRateSpinBox.setValue(value)
        isChecked = int(
            self.settings.value("toolbox/importSettingsPage/refoldingCheckBox", 0)
        )
        self.ui.refoldingCheckBox.setChecked(isChecked)
        isChecked = int(
            self.settings.value("toolbox/importSettingsPage/rawCheckBox", 0)
        )
        self.ui.rawCheckBox.setChecked(isChecked)
        isChecked = int(
            self.settings.value("toolbox/importSettingsPage/spectrumCsvCheckBox", 0)
        )
        self.ui.spectrumCsvCheckBox.setChecked(isChecked)

        value = int(self.settings.value("toolbox/miscSettingsPage/parallelSpinBox", 1))
        self.ui.parallelSpinBox.setValue(value)
        index = int(
            self.settings.value(
                "toolbox/miscSettingsPage/colormapForPlotComboBoxIndex", 0
            )
        )
        self.ui.colormapForPlotComboBox.setCurrentIndex(index)

        index = int(
            self.settings.value(
                "toolbox/exportSettingsPage/outputFormatComboBoxIndex", 0
            )
        )
        self.ui.outputFormatComboBox.setCurrentIndex(index)
        index = int(
            self.settings.value(
                "toolbox/exportSettingsPage/outputReportComboBoxIndex", 0
            )
        )
        self.ui.outputReportComboBox.setCurrentIndex(index)
        # isChecked = int(
        #    self.settings.value("toolbox/exportSettingsPage/genpicsCheckBox", 0)
        # )
        # self.ui.genpicsCheckBox.setChecked(isChecked)
        # isChecked = int(
        #    self.settings.value("toolbox/exportSettingsPage/heatmapCheckBox", 0)
        # )
        # self.ui.heatmapCheckBox.setChecked(isChecked)

        isChecked = int(
            self.settings.value("toolbox/plotSettingsPage/curveVlinesCheckBox", 0)
        )
        self.ui.curveVlinesCheckBox.setChecked(isChecked)
        isChecked = int(
            self.settings.value("toolbox/plotSettingsPage/curveBaselineCheckBox", 0)
        )
        self.ui.curveBaselineCheckBox.setChecked(isChecked)
        isChecked = int(
            self.settings.value("toolbox/plotSettingsPage/curveHeatmapColorCheckBox", 0)
        )
        self.ui.curveHeatmapColorCheckBox.setChecked(isChecked)

        isChecked = int(
            self.settings.value("toolbox/plotSettingsPage/curveDerivativeCheckBox", 0)
        )
        self.ui.curveDerivativeCheckBox.setChecked(isChecked)
        # isChecked = int(
        # self.settings.value("toolbox/plotSettingsPage/curveLegendCheckBox", 0)
        # )
        # self.ui.curveLegendCheckBox.setChecked(isChecked)
        index = int(
            self.settings.value("toolbox/plotSettingsPage/curveLegendComboBox", 0)
        )
        self.ui.curveLegendComboBox.setCurrentIndex(index)

        value = int(
            self.settings.value(
                "toolbox/plotSettingsPage/curveMarkEverySpinBoxValue", 0
            )
        )
        self.ui.curveMarkEverySpinBox.setValue(value)

        index = int(
            self.settings.value("toolbox/exportSettingsPage/curveTypeComboboxIndex", 0)
        )
        self.ui.curveTypeComboBox.setCurrentIndex(index)
        index = int(
            self.settings.value("toolbox/exportSettingsPage/curveViewComboboxIndex", 0)
        )
        self.ui.curveViewComboBox.setCurrentIndex(index)

    def resetToDefaults(self):
        # print("resetToDefaults")
        index = 0  # int(self.settings.value('toolbox/importSettingsPage/denaturantComboBoxIndex',  0))
        self.ui.denaturantComboBox.setCurrentIndex(index)

        text = core.defaults[
            "sep"
        ]  # self.settings.value('toolbox/importSettingsPage/separatorInputText',  ',')
        self.ui.separatorInput.setText(text)

        text = core.defaults[
            "dec"
        ]  # self.settings.value('toolbox/importSettingsPage/decimalSeparatorInputText',  '.')
        self.ui.decimalSeparatorInput.setText(text)

        value = 1.0  # float(self.settings.value('toolbox/importSettingsPage/scanRateSpinBoxValue',  1.0))
        self.ui.scanRateSpinBox.setValue(value)

        isChecked = 0
        self.ui.spectrumCsvCheckBox.setChecked(isChecked)

        isChecked = 0  # int(self.settings.value('toolbox/importSettingsPage/refoldingCheckBox',  0))
        self.ui.refoldingCheckBox.setChecked(isChecked)

        isChecked = 0
        self.ui.rawCheckBox.setChecked(isChecked)

        value = 1  # int(self.settings.value('toolbox/miscSettingsPage/parallelSpinBox',  1))
        self.ui.parallelSpinBox.setValue(value)
        index = 0  # int(self.settings.value('toolbox/miscSettingsPage/colormapForPlotComboBoxIndex',  0))
        self.ui.colormapForPlotComboBox.setCurrentIndex(index)

        index = 0  # int(self.settings.value('toolbox/exportSettingsPage/outputFormatComboBoxIndex',  0))
        self.ui.outputFormatComboBox.setCurrentIndex(index)
        index = 0  # int(self.settings.value('toolbox/exportSettingsPage/outputReportComboBoxIndex',  0))
        self.ui.outputReportComboBox.setCurrentIndex(index)
        # isChecked = 0  # int(self.settings.value('toolbox/exportSettingsPage/genpicsCheckBox',  0))
        # self.ui.genpicsCheckBox.setChecked(isChecked)
        # isChecked = 0  # int(self.settings.value('toolbox/exportSettingsPage/heatmapCheckBox',  0))
        # self.ui.heatmapCheckBox.setChecked(isChecked)

        isChecked = 0  # int(self.settings.value('toolbox/plotSettingsPage/curveVlinesCheckBox',  0))
        self.ui.curveVlinesCheckBox.setChecked(isChecked)
        isChecked = 0  # int(self.settings.value('toolbox/plotSettingsPage/curveBaselineCheckBox',  0))
        self.ui.curveBaselineCheckBox.setChecked(isChecked)
        isChecked = 0  # int(self.settings.value('toolbox/plotSettingsPage/curveDerivativeCheckBox',  0))
        self.ui.curveDerivativeCheckBox.setChecked(isChecked)
        # isChecked = 0  # int(self.settings.value('toolbox/plotSettingsPage/curveLegendCheckBox',  0))
        # self.ui.curveLegendCheckBox.setChecked(isChecked)
        isChecked = 0
        self.ui.curveHeatmapColorCheckBox.setChecked(isChecked)

        index = 0
        self.ui.curveLegendComboBox.setCurrentIndex(index)
        value = 0  # int(self.settings.value('toolbox/plotSettingsPage/curveMarkEverySpinBoxValue',  0))
        self.ui.curveMarkEverySpinBox.setValue(value)
        if self.parent != None:
            self.parent.getPlotSettings()
            self.parent.manageSubplots()

        index = 0  # int(self.settings.value('toolbox/exportSettingsPage/curveTypeComboboxIndex',  0))
        self.ui.curveTypeComboBox.setCurrentIndex(index)
        index = 0  # int(self.settings.value('toolbox/exportSettingsPage/curveViewComboboxIndex',  0))
        self.ui.curveViewComboBox.setCurrentIndex(index)


class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])

            if orientation == Qt.Vertical:
                return str(self._data.index[section])

    def flags(self, index):
        if index.column() == 1:
            return Qt.ItemIsEditable | Qt.ItemIsEnabled
        else:
            return Qt.ItemIsEnabled

    def setData(self, index, value, role=Qt.DisplayRole):
        self._data.iloc[index.row(), index.column()] = value


class ComboDelegate(QItemDelegate):
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """

    def __init__(self, parent, items=[]):
        QItemDelegate.__init__(self, parent)
        self.li = items

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self.li)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        # editor.setCurrentIndex(int(index.model().data(index)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText())

    def currentIndexChanged(self):
        self.commitData.emit(self.sender())


##  \brief This class implements AnalysisDialog of MoltenProt.
#     \details
class AnalysisDialog(QDialog):
    ##  \brief AnalysisDialog constructor.
    def __init__(self, parent=None):
        # QDialog.__init__(self)
        super(AnalysisDialog, self).__init__(parent)
        if parent == None:
            print("parent == None", cfFilename, currentframe().f_lineno)
        self.parent = parent
        uifile = QFile(":/analysis.ui")
        uifile.open(QFile.ReadOnly)
        self.ui = uic.loadUi(uifile, self)
        uifile.close()
        self.ui.buttonBox.accepted.connect(self.myAccept)
        self.ui.buttonBox.rejected.connect(self.myReject)
        self.ui.medianFilterCheckBox.clicked.connect(
            self.on_medianFilterCheckBoxChecked
        )
        self.ui.shrinkCheckBox.clicked.connect(self.on_shrinkCheckBoxChecked)
        self.ui.buttonBox.clicked["QAbstractButton*"].connect(self.buttonClicked)

        self.ui.filterWindowSizeLabel.hide()
        self.ui.shrinkNewdTValueLabel.hide()
        self.settings = QSettings()
        self.restoreSettingsValues()

        self.ui.analysisTableView.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

    @pyqtSlot()
    def myAccept(self):
        self.settings.setValue(
            "analysisSettings/dCpSpinBoxValue", self.ui.dCpSpinBox.value()
        )
        self.settings.setValue(
            "analysisSettings/medianFilterCheckBox",
            int(self.ui.medianFilterCheckBox.isChecked()),
        )
        self.settings.setValue(
            "analysisSettings/medianFilterSpinBox", self.ui.medianFilterSpinBox.value()
        )
        self.settings.setValue(
            "analysisSettings/shrinkCheckBox", int(self.ui.shrinkCheckBox.isChecked())
        )
        self.settings.setValue(
            "analysisSettings/shrinkDoubleSpinBox", self.ui.shrinkDoubleSpinBox.value()
        )
        self.close()

    @pyqtSlot()
    def myReject(self):
        self.restoreSettingsValues()
        self.close()

    def buttonClicked(self, button):
        role = self.buttonBox.buttonRole(button)
        if role == QDialogButtonBox.ResetRole:
            self.resetToDefaults()

    def resetToDefaults(self):
        # print("self.resetToDefaults()")
        # default analysis approach - this is the first one in the list of available models
        # index = 0
        # default dCp value
        value = core.analysis_defaults["dCp"]
        self.ui.dCpSpinBox.setValue(value)
        # median filter - disabled by default, but set the default value in the spinbox
        self.ui.medianFilterCheckBox.setChecked(False)
        value = 5
        self.ui.medianFilterSpinBox.setValue(value)
        self.on_medianFilterCheckBoxChecked()
        # shrinking - the same as with mfilt, good starting value is 1
        self.ui.shrinkCheckBox.setChecked(False)
        value = 1.0
        self.ui.shrinkDoubleSpinBox.setValue(value)
        self.on_shrinkCheckBoxChecked()
        # trimming - no trimming
        self.ui.tempRangeMinSpinBox.setValue(core.prep_defaults["trim_min"])
        self.ui.tempRangeMaxSpinBox.setValue(core.prep_defaults["trim_max"])
        # savgol, baselines, baseline bounds
        self.ui.savgolSpinBox.setValue(core.analysis_defaults["savgol"])
        self.ui.baselineFitSpinBox.setValue(core.analysis_defaults["baseline_fit"])
        self.ui.baselineBoundsSpinbox.setValue(
            core.analysis_defaults["baseline_bounds"]
        )
        # prepare the analysis table view
        if self.parent != None:
            self.parent.prepareAnalysisTableView()

    def setCheckBox(self, checkBoxSettingValue, checkBox):
        value = self.settings.value(checkBoxSettingValue)
        if value == None:
            value = False
        else:
            value = int(value)
        if value == 1:
            value = True
        else:
            value = False
        checkBox.setChecked(value)

    def restoreSettingsValues(self):
        value = int(self.settings.value("analysisSettings/dCpSpinBoxValue", 0))
        self.ui.dCpSpinBox.setValue(value)

        self.setCheckBox(
            "analysisSettings/medianFilterCheckBox", self.ui.medianFilterCheckBox
        )
        value = self.settings.value("analysisSettings/medianFilterSpinBox", 5)
        value = int(value)
        self.ui.medianFilterSpinBox.setValue(value)
        self.on_medianFilterCheckBoxChecked()

        self.setCheckBox("analysisSettings/shrinkCheckBox", self.ui.shrinkCheckBox)
        value = self.settings.value("analysisSettings/shrinkDoubleSpinBox", 5)
        value = float(value)
        self.ui.shrinkDoubleSpinBox.setValue(value)
        self.on_shrinkCheckBoxChecked()

    ##  \brief Show/hide medianFilterSpinBox,filterWindowSizeLabel  GUI elements according to medianFilterCheckBox state.
    @pyqtSlot()
    def on_medianFilterCheckBoxChecked(self):
        if self.ui.medianFilterCheckBox.isChecked():
            self.ui.medianFilterSpinBox.show()
            self.ui.filterWindowSizeLabel.show()
        else:
            self.ui.medianFilterSpinBox.hide()
            self.ui.filterWindowSizeLabel.hide()

    ##  \brief Show/hide snrDoubleSpinBox GUI element according to snrCheckBoxChecked state.
    @pyqtSlot()
    def on_snrCheckBoxChecked(self):
        if self.ui.snrCheckBox.isChecked():
            self.ui.snrDoubleSpinBox.show()
        else:
            self.ui.snrDoubleSpinBox.hide()

    ##  \brief Show/hide shrinkDoubleSpinBox,shrinkNewdTValueLabel  GUI elements according to shrinkCheckBox state.
    @pyqtSlot()
    def on_shrinkCheckBoxChecked(self):
        if self.ui.shrinkCheckBox.isChecked():
            self.ui.shrinkDoubleSpinBox.show()
            self.ui.shrinkNewdTValueLabel.show()
        else:
            self.ui.shrinkDoubleSpinBox.hide()
            self.ui.shrinkNewdTValueLabel.hide()


##  \brief This class implements QMainWindow of MoltenProt.
#     \details
class MoltenProtMainWindow(QMainWindow):
    NextId = 1
    Instances = set()
    ##  \brief MoltenProtMainWindow constructor.
    #     \details
    #   - Set analysis defaults. \sa setAnalysisDefaults
    #   - Init class members.
    #   - Parse application arguments. \sa parseArgs
    #   - Read settings.
    #   - Create standard GUI elements of QMainWindow for MoltenProt application and set their visibility. \sa createMainWindow createStatusBar initDialogs.
    def __init__(self, filename=None, parent=None):
        super(MoltenProtMainWindow, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        MoltenProtMainWindow.Instances.add(self)

        self.layout = None
        self.canvas = None
        ## \brief  This attribute holds the filename of the data.
        self.filename = filename
        if self.filename == None:
            MoltenProtMainWindow.NextId += 1

        self.setAnalysisDefaults()
        ## \brief  This attribute holds the instance of MoltenProtFit object. \sa core.MoltenProtFit
        self.moltenProtFit = None
        ## \brief  This attribute holds the instance of MoltenProtFitMultiple object. \sa core.MoltenProtFitMultiple
        self.moltenProtFitMultiple = None
        # the initial state is that data is not processed
        self.dataProcessed = False
        ## \brief  This attribute holds the instance of AxesDerivative object.
        #   \details AxesDerivative object depicts derevative data plot under the main plot and is created in addDerivativeSublot method.
        #   \sa addDerivativeSublot
        self.axesDerivative = None
        self.axesLegend = None
        ## \brief  This attribute holds the instance of sortScoreCombBoxAction object.
        #    \details This attribute is created in populateAndShowSortScoreComboBox method. \sa populateAndShowSortScoreComboBox
        self.sortScoreCombBoxAction = None
        ## \brief This attribute holds user personal settings.
        #   \details At present moment this object holds last working directory. \sa lastDir
        self.settings = QSettings()
        ## \brief  This attribute holds last working directory.
        self.lastDir = self.settings.value("settings/lastDir", ".")
        # print type(self.lastDir), self.lastDir, cfFilename, currentframe().f_lineno
        ## \brief  This attribute holds the number of analysis runs.
        self.analysisRunsCounter = int(
            self.settings.value("settings/analysisRunsCounter", 0)
        )
        # set analysisRunsCounter threshold to display the survey request (the default starting value is 1000)
        self.analysisRunsThresh = int(
            self.settings.value("settings/analysisRunsThresh", 1000)
        )

        ## Plotting-related constants
        ## \brief  This attribute controls the legend placement on the main plot.
        self.legendLocation = (
            "best"  # legend is now in a separate axes, is this needed?
        )

        self.setWindowTitle("MoltenProt Main Window")

        # Set dimensions of experimental and layout data. Those dimensions are used in createButtonArray, editLayout methods.
        ## \brief  This attribute sets the row dimension of the experimental and the layout data. \sa createButtonArray editLayout
        self.rowsCount = 8
        ## \brief  This attribute sets the column dimension of the experimental and the layout data. \sa createButtonArray editLayout
        self.colsCount = 12
        # default button style
        self.buttonStyleString = "QPushButton {  border-width: 2px; border-color: black; background-color: gray } QPushButton:checked { border-color: green; border-style: inset;}"
        # default gray colour for buttons make part of HeatmapButton?
        self.buttonGray = QColor.fromRgbF(0.501961, 0.501961, 0.501961, 1.000000)

        ## \brief This attribute holds the name of edited layout file
        # self.layoutFileName = None
        ## \brief This attribute holds the instance of MoltenProtFit.hm_dic attribute. \sa core.MoltenProtFit.hm_dic
        self.hm_dic = core.MoltenProtFit.hm_dic

        # create cycler for colors and set the starting color
        self.resetColorCycler()

        ## \brief This attribute holds the name of default sort.
        # self.heatMapName = "Sort_score"
        ## \brief This attribute holds the export as spreadsheet flag.
        self.exportXlsx = False
        ## \brief This attribute holds the name of default analysis.
        self.analysisMode = "santoro1988"
        self.n_jobs = 1
        self.parseArgs()
        ## \brief This attribute holds the namelist of MoltenProt colormap names.
        self.colorMapNames = [
            "RdYlGn",
            "RdYlGn_r",
            "coolwarm",
            "coolwarm_r",
            "Greys",
            "Greys_r",
            "plasma",
            "plasma_r",
        ]
        ## \brief This attribute holds the current palette index.
        self.currentColorMapIndex = 0
        ## \brief This attribute holds the current palette.
        self.currentColorMap = self.colorMapNames[self.currentColorMapIndex]
        self.colorMapComboBoxAction = None
        self.createMainWindow()
        self.createStatusBar()

        self.initDialogs()
        # NOTE some dialogs must be visible only when a file is loaded
        self.actionsSetVisible(False)

        self.setRunAnalysisCounterLabel()

        self.threadpool = QThreadPool()
        print(
            "Multithreading with maximum %d threads" % self.threadpool.maxThreadCount()
        )
        self.threadIsWorking = False

        self.closeWithoutQuestion = False

        self.iconSize = 12
        self.readFontFromSettings()

    def createExportThread(self):
        self.exportThread = ExportThread(self)  # make a class instance
        self.exportThread.started.connect(self.on_started)
        self.exportThread.finished.connect(self.on_finished)
        self.exportThread.exportThreadSignal.connect(
            self.on_change, Qt.QueuedConnection
        )

    def resetColorCycler(self):
        """
        Creates a fresh iterator through colors and sets the initial color
        """
        self.curveColorCycler = colorsafe_cycler()
        self.currentCurveColor = next(self.curveColorCycler)["color"]

    def on_started(self):  # called when thread is started
        if showVersionInformation:
            print("on_started")

    def on_finished(self):  # called when thread is finished
        if showVersionInformation:
            print("on_finished")

    def on_change(self, s):
        # self.label.setText(s)
        if showVersionInformation:
            print("on_change", s)

    def threadComplete(self):
        self.threadIsWorking = False
        QMessageBox.information(
            self, "Info", "Export complete",
        )
        self.status_text.setText("Results exported!")

    ## \brief  This method sets the analysis data, which has been loaded from json file, to analysis options data in the Analysis Dialog.
    def setAnalysisOptionsFromJSON(self):
        if self.moltenProtFit == None:
            print("self.moltenProtFit == None", cfFilename, currentframe().f_lineno)
        elif self.moltenProtFit.analysisHasBeenDone():
            # read the information from the MPFM instance
            (
                analysis_settings,
                model_settings,
            ) = self.moltenProtFitMultiple.GetAnalysisSettings()

            # set GUI elements
            self.setDoubleSpinBoxAccording2CheckBox(
                analysis_settings["shrink"],
                self.analysisDialog.ui.shrinkCheckBox,
                self.analysisDialog.ui.shrinkDoubleSpinBox,
            )
            self.setDoubleSpinBoxAccording2CheckBox(
                analysis_settings["mfilt"],
                self.analysisDialog.ui.medianFilterCheckBox,
                self.analysisDialog.ui.medianFilterSpinBox,
            )
            # NOTE trim settings are relative, but at the start of analysis the very original (plate_raw)
            # dataset is loaded, so extra chopping should not occur
            self.setAnalysisDialogTrimData()
            self.analysisDialog.ui.dCpSpinBox.setValue(analysis_settings["dCp"])
            self.analysisDialog.ui.baselineFitSpinBox.setValue(
                analysis_settings["baseline_fit"]
            )
            self.analysisDialog.ui.baselineBoundsSpinbox.setValue(
                analysis_settings["baseline_bounds"]
            )
            if analysis_settings["savgol"] != None:
                self.analysisDialog.ui.savgolSpinBox.setValue(
                    analysis_settings["savgol"]
                )

            # update the dataset/model table
            self.prepareAnalysisTableView(data=model_settings)

    ## \brief  This method is used to show/hide doubleSpinBox and set checkBox state according to analysisParameter.
    def setDoubleSpinBoxAccording2CheckBox(
        self, analysisParameter, checkBox, doubleSpinBox
    ):
        if analysisParameter == None:
            checkBox.setChecked(False)
            doubleSpinBox.hide()
        else:
            checkBox.setChecked(True)
            doubleSpinBox.setValue(analysisParameter)
            doubleSpinBox.show()

    ## \brief  This method is used to show/hide tempRangeMaxSpinBox and set its range in the Analysis Dialog according to moltenProtFit.trim_min and moltenProtFit.trim_max values.
    def setAnalysisDialogTrimData(self):
        if self.moltenProtFit == None:
            print("self.moltenProtFit == None", cfFilename, currentframe().f_lineno)
        else:
            if self.moltenProtFit.trim_max == None:
                self.moltenProtFit.trim_max = 0
            self.analysisDialog.ui.tempRangeMaxSpinBox.setValue(
                self.moltenProtFit.trim_max
            )
            if self.moltenProtFit.trim_min == None:
                self.moltenProtFit.trim_min = 0
            self.analysisDialog.ui.tempRangeMinSpinBox.setValue(
                self.moltenProtFit.trim_min
            )
            self.analysisDialog.ui.tempRangeMaxSpinBox.show()
            self.analysisDialog.ui.tempRangeMinSpinBox.show()

    ## \brief  This method set analysis defaults from core data.
    def setAnalysisDefaults(self):
        # there are now 3 dicts with options in core:
        # analysis_defaults - options related to analysis
        # prep_defaults - options related to data preprocessing
        # defaults - uncategorized options
        # TODO Is it necessary to copy all values here??
        self.model = core.analysis_defaults["model"]
        self.baseline_fit = core.analysis_defaults["baseline_fit"]
        self.baseline_bounds = core.analysis_defaults["baseline_bounds"]
        self.exclude = core.prep_defaults["exclude"]
        self.blanks = core.prep_defaults["blanks"]
        self.mfilt = core.prep_defaults["mfilt"]
        self.shrink = core.prep_defaults["shrink"]
        self.invert = core.prep_defaults["invert"]
        self.layout = core.defaults["layout"]
        self.savgol = core.analysis_defaults["savgol"]
        self.trim_min = core.prep_defaults["trim_min"]
        self.trim_max = core.prep_defaults["trim_max"]
        self.layout_input_type = "csv"
        self.dCp = core.analysis_defaults["dCp"]

    ## \brief  This method prints analysis settings for debug.
    def printAnalysisSettings(self):
        print("\033[91m" + "\nAnalysisSettings:")
        print(
            "model=",
            self.model,
            "exclude=",
            self.exclude,
            "blanks=",
            self.blanks,
            "mfilt=",
            self.mfilt,
        )
        print(
            "shrink=",
            self.shrink,
            type(self.shrink),
            "invert=",
            self.invert,
            "layout=",
            self.layout,
            "trim_min=",
            self.trim_min,
            "trim_max=",
            self.trim_max,
        )
        print(
            "savgol=", self.savgol, "baseline_fit", self.baseline_fit, "dCp=", self.dCp
        )
        print("\033[0m" + "\n")

    ## \brief This method shows run analysis counter for paricular user.
    #    \details In Linux QSettings data (self.analysisRunsCounter is saved using QSettings object) are stored in $HOME/.config/MoltenProt/moltenprot.conf
    #                   In MS Windows this data is stored in MS Windows registry.
    def setRunAnalysisCounterLabel(self):
        self.mainWindow.runAnalysisCounterLabel.setText(
            "Global curve counter: {}".format(self.analysisRunsCounter)
        )

    ## \brief This method implements analysis according to parameters entered by user from the corresponding GUI elements.
    # \todo We have here debug print, which should be excluded from the production version.
    def acceptAnalysis(self):

        # step 1: construct analysis_kwargs from GUI elements
        if self.analysisDialog.ui.medianFilterCheckBox.isChecked():
            self.mfilt = self.analysisDialog.ui.medianFilterSpinBox.value()
        else:
            self.mfilt = None

        if self.analysisDialog.ui.shrinkCheckBox.isChecked():
            self.shrink = self.analysisDialog.ui.shrinkDoubleSpinBox.value()
        else:
            self.shrink = None

        self.trim_min = self.analysisDialog.ui.tempRangeMinSpinBox.value()
        self.trim_max = self.analysisDialog.ui.tempRangeMaxSpinBox.value()

        self.dCp = self.analysisDialog.ui.dCpSpinBox.value()
        self.baseline_fit = self.analysisDialog.ui.baselineFitSpinBox.value()
        self.baseline_bounds = self.analysisDialog.ui.baselineBoundsSpinbox.value()
        self.savgol = self.analysisDialog.ui.savgolSpinBox.value()

        analysis_kwargs = dict(
            baseline_fit=self.baseline_fit,
            baseline_bounds=self.baseline_bounds,
            mfilt=self.mfilt,
            shrink=self.shrink,
            invert=self.invert,
            # layout=self.layout, # ever used in GUI?
            trim_min=self.trim_min,
            trim_max=self.trim_max,
            savgol=self.savgol,
            dCp=self.dCp,
        )

        analysis_kwargs = core.analysis_kwargs(analysis_kwargs)

        # step 2: cycle through datasets/models table and apply analysis options
        # read a pandas df representing the table of dataset/model (dm_table)
        dm_table = self.analysisDialog.ui.analysisTableView.model()._data

        # cycle through available datasets and set analysis options as in analysis_kwargs
        for i in dm_table.index:
            # HACK change class type if lumry_eyring model was selected in at least one dataset
            if dm_table.Model[i] == "lumry_eyring":
                self.moltenProtFitMultiple.__class__ = core.MoltenProtFitMultipleLE

            analysis_kwargs["model"] = dm_table.Model[i]

            self.moltenProtFitMultiple.SetAnalysisOptions(
                which=dm_table.Dataset[i], **analysis_kwargs
            )

        # step 3: prepare the canvas
        self.axisClear()
        self.on_deselectAll()
        self.canvas.draw()

        # step 4: run analysis
        QApplication.setOverrideCursor(Qt.WaitCursor)
        if showVersionInformation:
            self.printAnalysisSettings()

        # show error message if sth fails during analysis (only MoltenProt errors)
        try:
            self.runAnalysis()
            self.dataProcessed = True
        except (ValueError, TypeError) as e:
            QApplication.restoreOverrideCursor()
            print(e, cfFilename, currentframe().f_lineno)
            errMsg = (
                "Error occured during analysis: change analysis settings and try again."
            )
            QMessageBox.warning(self, "MoltenProt Error", str(e))
            self.status_text.setText(errMsg)
            self.dataProcessed = False

        # actions done regardless of analysis success/failure
        QApplication.restoreOverrideCursor()

        # actions done only if analysis was successful
        if self.dataProcessed:
            self.mainWindow.protocolPlainTextEdit.setPlainText(
                self.moltenProtFit.protocolString
            )
            self.populateAndShowSortScoreComboBox()
            self.setButtonsStyleAccordingToNormalizedData()

            self.settings.setValue(
                "settings/analysisRunsCounter", self.analysisRunsCounter
            )
            # check if analysisRunsCounter is above the threshold, show survey request and increase thershold
            if self.analysisRunsCounter > self.analysisRunsThresh:
                QMessageBox.information(
                    self,
                    "We need your feedback!",
                    """<p>You have processed {} curves with MoltenProt! Would you like to complete a survey?</p> 
            <p>Follow the link provided on the <a href="http://marlovitslab.org/lab/Download.html">download page</a> or click <a href="https://forms.gle/EacRgkQXfad4JnZx7">here</a>. </p>""".format(
                        self.analysisRunsCounter
                    ),
                    buttons=QMessageBox.Close,
                )
                self.analysisRunsThresh *= 10
                self.settings.setValue(
                    "settings/analysisRunsThresh", self.analysisRunsThresh
                )

            self.settings.sync()
            self.status_text.setText("Data analysis complete.")
            self.mainWindow.actionExport.setVisible(True)
            # adjust subplots
            self.manageSubplots()

    ## \brief This method implements analysis according to parameters entered by user from the corresponding GUI elements.
    def runAnalysis(self):
        n_jobs = self.moltenProtToolBox.ui.parallelSpinBox.value()

        self.moltenProtFitMultiple.PrepareAndAnalyseAll(n_jobs=n_jobs)

        # once the analysis is done, only show non-skipped datasets in the HeatmapMultipleComboBox
        available_datasets = self.moltenProtFitMultiple.GetDatasets(no_skip=True)
        # if the user decides to skip all datasets, then analysis is impossible
        if len(available_datasets) < 1:
            raise ValueError("No datasets selected for analysis")
        self.moltenProtFit = self.moltenProtFitMultiple.datasets[available_datasets[0]]
        self.populateDatasetComboBox(available_datasets)

        # count the total number of curves processed and add to the global counter
        for dataset in self.moltenProtFitMultiple.GetDatasets():
            if self.moltenProtFitMultiple.datasets[dataset].analysisHasBeenDone():
                self.analysisRunsCounter += len(
                    self.moltenProtFitMultiple.datasets[dataset].plate_results
                )

        self.setRunAnalysisCounterLabel()
        self.moltenProtToolBox.ui.colormapForPlotComboBox.show()
        self.moltenProtToolBox.ui.colormapForPlotLabel.show()

        self.showHideSelectDeselectAll(True)

    def createPlotSettings(self):
        self.curveVlinesCheckBoxIsChecked = None
        self.curveHeatmapColorCheckBoxIsChecked = None
        self.curveBaselineCheckBoxIsChecked = None
        self.curveDerivativeCheckBoxIsChecked = None
        self.curveLegendComboboxCurrentText = None
        self.curveMarkEverySpinBoxValue = None
        self.curveTypeComboboxCurrentText = None
        self.curveViewComboboxCurrentText = None

    ## \brief This method connects signals for Plot tab in Settings dialog data GUI elements.
    def connectPlotSettingsSignals(self):
        # new code: for all actions just update values in the main window attributes
        self.moltenProtToolBox.ui.curveVlinesCheckBox.clicked.connect(
            self.getPlotSettings
        )
        self.moltenProtToolBox.ui.curveBaselineCheckBox.clicked.connect(
            self.getPlotSettings
        )
        self.moltenProtToolBox.ui.curveHeatmapColorCheckBox.clicked.connect(
            self.getPlotSettings
        )

        # legend and derivative subplots require dedicated methods
        self.moltenProtToolBox.ui.curveLegendComboBox.currentIndexChanged.connect(
            self.manageSubplots
        )
        # self.moltenProtToolBox.ui.curveDerivativeCheckBox.clicked.connect(self.getPlotSettings)
        self.moltenProtToolBox.ui.curveDerivativeCheckBox.clicked.connect(
            self.manageSubplots
        )

        # Get data from spinbox.
        self.moltenProtToolBox.ui.curveMarkEverySpinBox.valueChanged[int].connect(
            self.on_curveMarkEverySpinBoxValueChanged
        )
        # Get data from comboboxes.
        self.moltenProtToolBox.ui.curveTypeComboBox.currentIndexChanged.connect(
            self.on_curveTypeComboBoxCurrentIndexChanged
        )
        self.moltenProtToolBox.ui.curveViewComboBox.currentIndexChanged.connect(
            self.on_curveViewComboBoxCurrentIndexChanged
        )

    @pyqtSlot()
    def on_curveTypeComboBoxCurrentIndexChanged(self):
        # print 'on_curveTypeComboBoxCurrentTextChanged',  cfFilename, currentframe().f_lineno
        self.curveTypeComboboxCurrentText = (
            self.moltenProtToolBox.ui.curveTypeComboBox.currentText()
        )
        # print self.curveTypeComboboxCurrentText,  cfFilename, currentframe().f_lineno

    @pyqtSlot()
    def on_curveViewComboBoxCurrentIndexChanged(self):
        # print 'on_curveTypeComboBoxCurrentTextChanged',  cfFilename, currentframe().f_lineno
        self.curveViewComboboxCurrentText = (
            self.moltenProtToolBox.ui.curveViewComboBox.currentText()
        )

    @pyqtSlot()
    def on_curveMarkEverySpinBoxValueChanged(self):  # ,  value_as_int):
        # print 'int value changed:',  value_as_int,  cfFilename, currentframe().f_lineno
        self.curveMarkEverySpinBoxValue = (
            self.moltenProtToolBox.ui.curveMarkEverySpinBox.value()
        )

    ## \brief This method gets Plot tab in Settings dialog data from its GUI elements.
    def getPlotSettings(self):
        self.curveHeatmapColorCheckBoxIsChecked = (
            self.moltenProtToolBox.ui.curveHeatmapColorCheckBox.isChecked()
        )
        self.curveVlinesCheckBoxIsChecked = (
            self.moltenProtToolBox.ui.curveVlinesCheckBox.isChecked()
        )
        self.curveBaselineCheckBoxIsChecked = (
            self.moltenProtToolBox.ui.curveBaselineCheckBox.isChecked()
        )
        self.curveDerivativeCheckBoxIsChecked = (
            self.moltenProtToolBox.ui.curveDerivativeCheckBox.isChecked()
        )
        self.curveLegendComboboxCurrentText = (
            self.moltenProtToolBox.ui.curveLegendComboBox.currentText()
        )
        self.curveMarkEverySpinBoxValue = (
            self.moltenProtToolBox.ui.curveMarkEverySpinBox.value()
        )
        self.curveTypeComboboxCurrentText = (
            self.moltenProtToolBox.ui.curveTypeComboBox.currentText()
        )
        self.curveViewComboboxCurrentText = (
            self.moltenProtToolBox.ui.curveViewComboBox.currentText()
        )
        # clean up the axes after plot settings are changed
        self.axisClear()
        self.on_deselectAll()
        self.canvas.draw()

    ## \brief This method  creates toolbox dialog.
    #   \todo When toolbox appearence will be fixed, we should set fixed width and height for this dialog.
    def createToolBox(self):
        self.moltenProtToolBox = MoltenProtToolBox(self)
        self.allItemsInCurveTypeComboBox = [
            self.moltenProtToolBox.ui.curveTypeComboBox.itemText(i)
            for i in range(self.moltenProtToolBox.ui.curveTypeComboBox.count())
        ]
        self.createPlotSettings()
        self.getPlotSettings()
        self.connectPlotSettingsSignals()

        width = self.moltenProtToolBox.width()
        height = self.moltenProtToolBox.height()
        wid = QDesktopWidget()
        screenWidth = wid.screen().width()
        screenHeight = wid.screen().height()
        self.moltenProtToolBox.setGeometry(
            (screenWidth / 2) - (width / 2),
            (screenHeight / 2) - (height / 2),
            width,
            height,
        )

    ## \brief This method  creates analysis dialog
    def createAnalysisDialog(self):
        self.analysisDialog = AnalysisDialog(self)
        self.analysisDialog.ui.buttonBox.accepted.connect(self.acceptAnalysis)

    ## \brief This method creates the following dialogs: Preferences, Analysis and Layout.
    #   \sa AnalysisDialog, moltenProtToolBox, LayoutDialog and HelpDialog.
    def initDialogs(self):
        self.createToolBox()
        self.createColorMapComboBox()
        self.createAnalysisDialog()

        # Create layout dialog
        self.layoutDialog = LayoutDialog()
        self.connectButtonsFromLayoutDialog()
        # Create help dialog
        self.helpDialog = MoltenProtHelpDialog("index.html")

        # set tooltips for dialogs
        self.setTooltips()

    ## \brief This method shows the Analysis Dialog.
    @pyqtSlot()
    def on_analysisPushButtonClicked(self):
        self.analysisDialog.show()

    ## \brief This method is dummy and should be implemented.
    #   \todo This method is dummy and should be implemented.
    @pyqtSlot()
    def on_kelvinsCheckBoxChecked(self):
        if showVersionInformation:
            print("on_kelvinsCheckBoxChecked")

    ## \brief This method is not used.
    #   \todo This method is not used.
    def analysisModeBoxSelectionChange(self, i):
        self.analysisMode = self.importDialog.ui.analysisModeBox.currentText()

    ## \brief This method is dummy and should be implemented.
    #   \todo This method is dummy and should be implemented.
    def parseArgs(self):
        self.sepValue = ","
        self.decValue = "."
        self.exclude = []
        self.blanks = []

    @pyqtSlot()
    def on_exportResults(self):
        """
        Actions performed when the export data button is clicked
        """
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.Directory)
        filenames = None

        if dlg.exec_():
            filenames = dlg.selectedFiles()
            filename = filenames[0]
            # get export settings from the ui elements and convert them into kwargs for MP.WriteOutput
            data_out = self.moltenProtToolBox.ui.outputFormatComboBox.currentIndex()
            report_out = self.moltenProtToolBox.ui.outputReportComboBox.currentIndex()

            out_kwargs = {}
            out_kwargs["outfolder"] = filename

            if data_out == 0:
                # 0 no data output
                # 1 CSV output
                # 2 XLSX output
                out_kwargs["no_data"] = True
            elif data_out == 1:
                out_kwargs["xlsx"] = False
            elif data_out == 2:
                out_kwargs["xlsx"] = True
            
            # NOTE matplotlib is not thread-safe, so threading is disabled for some options
            use_threads = True
            if report_out == 0:
                # 0 no report
                # 1 pdf
                # 2 XLSX summary
                # HTML
                out_kwargs["report_format"] = None
            elif report_out == 1:
                out_kwargs["report_format"] = "pdf"
                use_threads = False
            elif report_out == 2:
                out_kwargs["report_format"] = "xlsx"
            elif report_out == 3:
                out_kwargs["report_format"] = "html"
                use_threads = False

            out_kwargs["n_jobs"] = self.moltenProtToolBox.ui.parallelSpinBox.value()

            QApplication.setOverrideCursor(Qt.WaitCursor)

            if use_threads:
                worker = ExportWorker(
                    self.moltenProtFitMultiple,
                    **out_kwargs
                )
                worker.signals.finished.connect(self.threadComplete)
                worker.signals.progress.connect(self.progressFn)
                self.threadIsWorking = True
                # Execute
                self.threadpool.start(worker)
            else:
                self.moltenProtFitMultiple.WriteOutputAll(**out_kwargs)

            QApplication.restoreOverrideCursor()
            self.status_text.setText(
                "Results exported to folder {}".format(filename)
            )


    def executeThisFn(self, progress_callback):
        if showVersionInformation:
            print("executeThisFn")
        return "Done."

    def progressFn(self):
        if showVersionInformation:
            print("progressFn")

    ## \brief This SLOT is called when user clicks <b>New</b> button and  runs another instance of MoltenProt GUI application.
    @pyqtSlot()
    def on_actionNewTriggered(self):
        MoltenProtMainWindow().show()

    @pyqtSlot()
    def on_actionFontTriggered(self):
        fontDialog = QFontDialog(self)
        fontDialog.setFont(self.font)
        font, ok = fontDialog.getFont()
        if ok:
            self.font = font
            self.settings.setValue("fontSettings/currentFont", self.font.toString())
            self.setNewFont(self.font)

    def setIconSize(self):
        self.iconSize = self.font.pointSize() * 3
        iconSize = QSize(self.iconSize, self.iconSize)
        self.mainWindow.fileToolBar.setIconSize(iconSize)
        self.mainWindow.actionToolBar.setIconSize(iconSize)
        self.mainWindow.miscToolBar.setIconSize(iconSize)

    def setNewFont(self, newFont):
        self.font = newFont
        self.setApplicationMenuFont()
        self.setIconSize()

    def readFontFromSettings(self):
        newFontString = self.settings.value("fontSettings/currentFont")
        newFont = QFont()
        ok = newFont.fromString(newFontString)
        if ok:
            self.setNewFont(newFont)
        else:
            print("Failed to set font", newFont, cfFilename, currentframe().f_lineno)

    def setApplicationMenuFont(self):
        QtWidgets.QApplication.setFont(self.font, "QFileDialog")
        QtWidgets.QApplication.setFont(self.font, "QPushButton")
        QtWidgets.QApplication.setFont(self.font, "QAction")
        QtWidgets.QApplication.setFont(self.font, "QFontDialog")
        QtWidgets.QApplication.setFont(self.font, "QToolBar")
        QtWidgets.QApplication.setFont(self.font, "QMainWindow")
        QtWidgets.QApplication.setFont(self.font, "QWidget")
        QtWidgets.QApplication.setFont(self.font, "QTextEdit")
        QtWidgets.QApplication.setFont(self.font, "QDialogButtonBox")
        if self.canvas != None:
            self.canvas.setFont(self.font)

    ## \brief This SLOT is called when user clicks <b>About</b> button and shows some information about used python modules and Qt version.
    @pyqtSlot()
    def on_actionAbout(self):
        mp_version = str(core.__version__)
        # check if running from PyInstaller bundle and add info to version
        if core.from_pyinstaller:
            mp_version += " (PyInstaller bundle)"
        QMessageBox.about(
            self,
            "About MoltenProt",
            """<b>MoltenProt</b> v. %s
        <p>Copyright &copy; 2018-2021 Vadim Kotov, Thomas C. Marlovits
        <p>A robust toolkit for assessment and optimization of protein (thermo)stability.
        <p>Python %s - PyQt5 %s - Matplotlib %s on %s"""
            % (
                core.__version__,
                platform.python_version(),
                PYQT_VERSION_STR,
                matplotlib.__version__,
                platform.system(),
            ),
        )

    ## \brief This SLOT is called when user clicks <b>Cite</b> menu item.
    @pyqtSlot()
    def on_actionCite_MoltenProt(self):
        QMessageBox.about(
            self, "Cite MoltenProt", core.citation["html"],
        )

    ## \brief This SLOT is called when user clicks <b>Help</b> menu item and shows the MoltenProt help system main window.
    @pyqtSlot()
    def on_actionHelp(self):
        self.helpDialog.show()

    ## \brief This SLOT is called when user clicks File>Load sample data
    @pyqtSlot()
    def on_actionLoad_sample_data(self):
        # opens the folder where demo data is stored
        self.on_loadFile(directory=os.path.join(core.__location__, "demo_data"))

    ## \brief Save the current case as JSON.
    @pyqtSlot()
    def on_actionSave_as_JSONTriggered(self):
        filename = QFileDialog.getSaveFileName(
            self,
            caption=self.tr(
                "Save MoltenProt session in *.json format"
            ),  # the title of the dialog window
            directory=self.lastDir,  # the starting directory, use "." for cwd
            filter="JSON Files (*.json)",  # file type filter
        )

        if filename[0] != "":
            # convert returned filname value to string and add .json if necessary
            filename = str(filename[0])
            if filename[-5:] != ".json":
                filename += ".json"
            core.mp_to_json(self.moltenProtFitMultiple, filename)

    def prepareAnalysisTableView(self, data=None):
        # if data is None generate the table freshly
        # otherwise populate using the values from supplied dataframe

        analysisModeComboBoxItemsList = list(core.avail_models.keys())

        if data is None:
            # analysisModeComboBoxItemsList = list( core.avail_models.keys() )
            # analysisModeComboBoxItemsList.append('skip') # skip is now a "model", too
            defaultModel = analysisModeComboBoxItemsList[0]
            # self.analysisDialog.ui.analysisModeComboBox.clear()
            # self.analysisDialog.ui.analysisModeComboBox.insertItems(1,  analysisModeComboBoxItemsList)

            currentDataSetsList = list(self.moltenProtFitMultiple.GetDatasets())
            data = pd.DataFrame(columns=("Dataset", "Model"))
            for i in range(len(currentDataSetsList)):
                data.loc[i] = [currentDataSetsList[i], defaultModel]

        tableModel = TableModel(data)
        self.analysisDialog.ui.analysisTableView.setModel(tableModel)
        comboDelegate = ComboDelegate(self, analysisModeComboBoxItemsList)
        self.analysisDialog.ui.analysisTableView.setItemDelegateForColumn(
            1, comboDelegate
        )

    def showHideSelectDeselectAll(self, show):
        self.mainWindow.actionSelectAll.setVisible(show)
        self.mainWindow.actionDeselectAll.setVisible(show)

    ## \brief Load the input data in xlsx, JSON or csv format for analysis.
    @pyqtSlot()
    def on_loadFile(self, directory=None):
        """
        Parameters
        ----------
        directory
            a folder where to open the file dialog
        """
        if directory is None:
            directory = self.lastDir

        self.on_deselectAll()
        filename = QFileDialog.getOpenFileName(
            # self,
            caption=self.tr("Open JSON session or import data"),
            directory=directory,
            filter="XLSX Files (*.xlsx);;JSON Files (*.json);;CSV files (*.csv)",
        )
        # returns a tuple with file path, and the mode of QFileDialog used (XLSX Files, JSON Files, etc)
        filename = filename[0]
        fileInfo = QFileInfo(filename)
        if fileInfo.isReadable():
            self.lastDir = fileInfo.canonicalPath()
            self.settings.setValue("settings/lastDir", self.lastDir)
            self.settings.sync()
            self.resetButtons()
            if self.sortScoreCombBoxAction != None:  # TODO is this really needed here?
                self.sortScoreCombBoxAction.setVisible(False)
            self.dataProcessed = False

            if self.fileLoaded == False:
                # print("self.createMatplotlibContextMenu() has been commented.")
                pass
            else:
                # print("Clear previous data", cfFilename, currentframe().f_lineno)
                self.on_deselectAll()
                self.axisClear()
                self.mainWindow.actionExport.setVisible(False)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                if filename.endswith(".csv"):
                    self.processCsv(filename)
                elif filename.endswith(".json"):
                    self.processJSON(filename)
                elif filename.endswith(".xlsx"):
                    self.processXLSX(filename)
                self.status_text.setText("Loaded " + filename)
                self.fileLoaded = True
            except ValueError as e:
                # TODO currently the previous data/layout is left around even though the file could not open
                QMessageBox.warning(self, "MoltenProt Open File Error", str(e))
                self.status_text.setText("Requested file could not be opened.")
                # reset the GUI
                self.resetGUI()
                self.fileLoaded = False

            # done regarless of file loading success
            QApplication.restoreOverrideCursor()
            # done only when opening succeeded
            if self.fileLoaded:
                self.actionsSetVisible(True)

                self.setAllButtons("enable", True)
                self.showOnlyValidButtons()
                self.prepareAnalysisTableView()

                # Overwrite default analysis settings if input file was JSON and was processed
                # for any other file type reset to defaults
                if filename.endswith(".json"):
                    self.setAnalysisOptionsFromJSON()
                else:
                    ###TODO restore default analysis settings
                    pass

                # actions in case the data was processed (JSON only)
                if self.dataProcessed:
                    if showVersionInformation:
                        print(
                            "Analysis has been done",
                            cfFilename,
                            currentframe().f_lineno,
                        )
                    # self.showHideSelectDeselectAll(True)
                    self.moltenProtToolBox.ui.colormapForPlotComboBox.show()
                    self.moltenProtToolBox.ui.colormapForPlotLabel.show()
                    self.populateAndShowSortScoreComboBox()
                    self.setButtonsStyleAccordingToNormalizedData()
                    self.sortScoreComboBox.clear()
                    self.sortScoreComboBox.insertItems(
                        1, self.moltenProtFit.getResultsColumns()
                    )
                else:
                    self.moltenProtToolBox.ui.colormapForPlotComboBox.hide()
                    self.moltenProtToolBox.ui.colormapForPlotLabel.hide()
        elif filename != "":
            # empty string is returned when Cancel is pressed in QFileDialog
            QMessageBox.warning(
                self, "MoltenProt Open File Error", "Input file not readable"
            )
            self.resetGUI()

    def populateDatasetComboBox(self, available_datasets):
        # Adds datasets from the list to the respective combobox
        # if there is one or no datasets, the combobox is hidden
        self.datasetComboBox.clear()
        if len(available_datasets) <= 1:
            self.datasetComboBoxAction.setVisible(False)
        else:
            self.datasetComboBox.insertItems(1, available_datasets)
            width = self.datasetComboBox.minimumSizeHint().width()
            self.datasetComboBox.setMinimumWidth(width)
            self.datasetComboBoxAction.setVisible(True)

    ## \brief This method is used to process CSV file named filename
    #   \param filename - CSV file to process.
    #   \todo Debug print is used here.
    def processCsv(self, filename):
        if showVersionInformation:
            print("processCsv", filename, cfFilename, currentframe().f_lineno)
        self.sepValue = self.moltenProtToolBox.ui.separatorInput.text()
        self.decValue = self.moltenProtToolBox.ui.decimalSeparatorInput.text()
        self.scanRateValue = self.moltenProtToolBox.ui.scanRateSpinBox.value()

        if self.moltenProtToolBox.ui.spectrumCsvCheckBox.isChecked():
            self.moltenProtFitMultiple = core.parse_spectrum_csv(
                filename,
                sep=self.sepValue,
                dec=self.decValue,
                scan_rate=self.scanRateValue,
            )
        else:
            self.moltenProtFitMultiple = core.parse_plain_csv(
                filename,
                sep=self.sepValue,
                dec=self.decValue,
                scan_rate=self.scanRateValue,
            )
        available_datasets = self.moltenProtFitMultiple.GetDatasets()
        self.moltenProtFit = self.moltenProtFitMultiple.datasets[available_datasets[0]]
        self.populateDatasetComboBox(available_datasets)

    ## \brief This method is used to process JSON file named filename
    #   \param filename - JSON file to process.
    #   \todo Debug print is used here.
    def processJSON(self, filename):
        # print("processJSON", filename, cfFilename, currentframe().f_lineno)
        jsonData = core.mp_from_json(filename)
        if isinstance(jsonData, core.MoltenProtFitMultiple):
            self.moltenProtFitMultiple = jsonData

            # do not show datasets that were marked as skipped in the combobox
            available_datasets = self.moltenProtFitMultiple.GetDatasets(no_skip=True)
            self.moltenProtFit = self.moltenProtFitMultiple.datasets[
                available_datasets[0]
            ]

            # MPF2 dynamically populate heatmap combobox
            self.populateDatasetComboBox(available_datasets)

            # TODO currently this only checks analysis completion only in one of MoltenProtFit instances
            if self.moltenProtFit.analysisHasBeenDone():
                self.dataProcessed = True
                # make the export button visible
                self.mainWindow.actionExport.setVisible(True)
                # update plot view
                self.manageSubplots()
            else:
                if showVersionInformation:
                    print(
                        "Analysis has not been done",
                        cfFilename,
                        currentframe().f_lineno,
                    )
        else:
            if showVersionInformation:
                print(
                    "Unknown object has been created from json file",
                    filename,
                    cfFilename,
                    currentframe().f_lineno,
                )

    ## \brief This method is used to process XLSX file named filename.
    #   \param filename - XLSX file to process.
    #   \todo Debug print is used here.
    def processXLSX(self, filename):
        refolding = self.moltenProtToolBox.ui.refoldingCheckBox.isChecked()
        is_raw = self.moltenProtToolBox.ui.rawCheckBox.isChecked()
        self.moltenProtFitMultiple = core.parse_prom_xlsx(
            filename, raw=is_raw, refold=refolding
        )
        available_datasets = self.moltenProtFitMultiple.GetDatasets()
        self.moltenProtFit = self.moltenProtFitMultiple.datasets[available_datasets[0]]
        # MPF2 dynamically populate heatmap combobox
        self.populateDatasetComboBox(available_datasets)
        # NOTE XLSX is always unprocessed, however, dataProcessed attribute
        # and the view of the plots must be reset from the previous run
        self.dataProcessed = False
        self.manageSubplots()

    ## \brief This method set tooltips for GUI elements using core.MoltenProtFit.defaults dictionary.
    #   \sa core.defaults dicts
    def setTooltips(self):
        # data prep defaults
        self.analysisDialog.ui.shrinkCheckBox.setToolTip(core.prep_defaults["shrink_h"])
        self.analysisDialog.ui.shrinkDoubleSpinBox.setToolTip(
            core.prep_defaults["shrink_h"]
        )
        self.analysisDialog.ui.medianFilterCheckBox.setToolTip(
            core.prep_defaults["mfilt_h"]
        )
        self.analysisDialog.ui.medianFilterSpinBox.setToolTip(
            core.prep_defaults["mfilt_h"]
        )
        self.analysisDialog.ui.tempRangeMaxSpinBox.setToolTip(
            core.prep_defaults["trim_max_h"]
        )
        self.analysisDialog.ui.tempRangeMinSpinBox.setToolTip(
            core.prep_defaults["trim_min_h"]
        )
        # analysis defaults
        self.analysisDialog.ui.dCpSpinBox.setToolTip(core.analysis_defaults["dCp_h"])
        self.analysisDialog.ui.baselineFitSpinBox.setToolTip(
            core.analysis_defaults["baseline_fit_h"]
        )
        self.analysisDialog.ui.baselineBoundsSpinbox.setToolTip(
            core.analysis_defaults["baseline_bounds_h"]
        )
        self.analysisDialog.ui.savgolSpinBox.setToolTip(
            core.analysis_defaults["savgol_h"]
        )

    ## \brief This method shows the Preferences Dialog.
    #   \sa moltenProtToolBox
    @pyqtSlot()
    def on_showmoltenProtToolBox(self):
        self.moltenProtToolBox.show()

    ## \brief This metod creates QMessageBox with messageKind icon and shows message.
    def showMessage(self, message, messageKind):
        msg = QMessageBox()
        msg.setIcon(messageKind)
        msg.setText(message)
        """
        msg.setInformativeText("This is additional information")
        msg.setWindowTitle("MessageBox demo")
        msg.setDetailedText("The details are as follows:")  
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.buttonClicked.connect(msgbtn)
        retval = msg.exec_()
        """
        msg.exec_()

    def __layout2widget(self, input_series):
        """
        Helper function to convert a single row of layout DataFrame into
        a QTableWidget entry
        NOTE to avoid Overflow errors, the respective DataFrame must have np.nan etc changed to 'None' string
        """
        # Convert alphanumeric index to numeric indices:
        # A1 -> (0, 0)
        # H12 -> (7, 11)
        row = "ABCDEFGH".index(input_series.name[0])
        column = int(input_series.name[1:]) - 1

        if input_series["Condition"] != "None":
            item_value = input_series["Condition"]
        else:
            # default value for layout is ""
            item_value = ""
        self.layoutDialog.ui.tableWidget.setItem(
            row, column, QTableWidgetItem(str(item_value))
        )

    ## \brief This method shows the layout from MoltenProtFitMultiple.layout in QTableWidget in LayoutDialog.
    #   \sa LayoutDialog
    def editLayout(self):
        layout = self.moltenProtFitMultiple.layout.fillna("None")
        layout.apply(self.__layout2widget, axis=1)
        self.layoutDialog.ui.tableWidget.resizeColumnsToContents()
        self.layoutDialog.ui.tableWidget.alternatingRowColors()
        self.layoutDialog.show()

    def openLayout(self):
        """
        Load a layout from a specially formatted CSV file to QTableWidget
        """
        layoutFileName = QFileDialog.getOpenFileName(
            self,
            caption=self.tr("Open layout from CSV file"),
            directory=self.lastDir,
            filter="CSV files (*.csv)",
        )
        layoutFileName = layoutFileName[0]
        if layoutFileName != "":
            fileInfo = QFileInfo(layoutFileName)
            if showVersionInformation:
                print(fileInfo.fileName(), currentframe().f_lineno, cfFilename)
            if fileInfo.isReadable():
                layout = pd.read_csv(
                    layoutFileName, index_col="ID", encoding="utf_8"
                ).fillna("None")
                layout.apply(self.__layout2widget, axis=1)
                self.layoutDialog.ui.tableWidget.resizeColumnsToContents()
                self.layoutDialog.ui.tableWidget.alternatingRowColors()
                self.layoutDialog.show()
            else:
                print(
                    layoutFileName + " can not be processed. Check your permissions!",
                    currentframe().f_lineno,
                    cfFilename,
                )

    def updateLayout(self):
        # NOTE can also use tableWidget.rowCount()/columnCount()
        # print self.layoutDialog.ui.tableWidget.rowCount()
        # print self.layoutDialog.ui.tableWidget.columnCount()
        # edit the layout of MPFM instance
        for column in range(0, 12):
            for row in range(0, 8):
                item = self.layoutDialog.ui.tableWidget.item(row, column)
                alphanumeric_index = "ABCDEFGH"[row] + str(column + 1)

                # NOTE the layout is always 12x8, however, the data may have less samples
                # do not assign layout to the data that is not present in plate_raw
                if self.moltenProtFit.testWellID(
                    alphanumeric_index, ignore_results=True
                ):
                    if item.text() != "":
                        self.moltenProtFitMultiple.layout.loc[
                            alphanumeric_index, "Condition"
                        ] = item.text()
                    else:
                        self.moltenProtFitMultiple.layout.loc[
                            alphanumeric_index, "Condition"
                        ] = None
        # apply edited layout to all datasets inside MPFM
        self.moltenProtFitMultiple.UpdateLayout()

    def resetLayout(self):
        """
        Action to be performed when reset button in Layout dialog is pressed.
        Restore the original layout from layout_raw if this is available
        """
        self.moltenProtFitMultiple.ResetLayout()
        self.layoutDialog.close()

    ## \brief This SLOT (in Qt terms) is called when user changes heatmap table name.
    #   \sa createComboBoxesForActionToolBar
    @pyqtSlot()
    def on_changeInputTable(self):
        if self.moltenProtFit != None:
            self.on_deselectAll()
            inputTableName = self.datasetComboBox.currentText()
            if inputTableName in self.moltenProtFitMultiple.GetDatasets():
                inputTableNameIsValid = True
                self.moltenProtFit = self.moltenProtFitMultiple.datasets[inputTableName]
                newProtocolString = self.moltenProtFitMultiple.datasets[
                    inputTableName
                ].protocolString
                self.mainWindow.protocolPlainTextEdit.setPlainText(newProtocolString)
            else:
                print(
                    "Unknown table name",
                    inputTableName,
                    currentframe().f_lineno,
                    cfFilename,
                )
                inputTableNameIsValid = False
            if inputTableNameIsValid:
                if self.dataProcessed:
                    # NOTE before this is done, we must ensure that the combobox contains valid items
                    self.populateAndShowSortScoreComboBox()
                    self.setButtonsStyleAccordingToNormalizedData()
                else:
                    self.resetButtons()
        else:
            if showVersionInformation:
                print("self.moltenProtFit == None", currentframe().f_lineno, cfFilename)

    def __genTooltip(self, input_series, heatMapName):
        """
        Helper function that converts a single row of MPF.plate_results to a tooltip string
        """

        output = "{} {} {} = {}".format(
            input_series.name,
            input_series.Condition,
            heatMapName,
            round(input_series[heatMapName], 2,),
        )
        return output

    def setButtonsStyleAccordingToNormalizedData(self):
        if self.moltenProtFit != None:
            heatMapName = self.sortScoreComboBox.currentText()
            # NOTE during startup the values of the drop-down list
            # can be empty which would result in a crash
            if heatMapName in self.moltenProtFit.getResultsColumns():
                # normalize the data in selected column and create colors (rgba tuples) with the current colormap
                cmap = cm.get_cmap(self.currentColorMap)
                button_colors = core.normalize(
                    self.moltenProtFit.plate_results[heatMapName]
                ).apply(cmap)
                # update the Color column in the Buttons df with existing colors
                # NOTE buttons without a color will have None
                button_colors.name = "Color"
                self.buttons.Color = None  # resets all colors to None
                self.buttons.update(button_colors)

                # generate tooltips
                self.buttons.Tooltip = None  # reset all tooltips
                tooltips = self.moltenProtFit.plate_results.apply(
                    self.__genTooltip, heatMapName=heatMapName, axis=1
                )
                tooltips.name = "Tooltip"
                self.buttons.update(tooltips)

                # apply changes to the buttons
                self.buttons.apply(self.__setOneButtonStyle, axis=1)
        else:
            print("self.moltenProtFit == None", currentframe().f_lineno, cfFilename)

    def setAllButtons(self, action, flag):
        """
        Applies a certain boolean action to all buttons in self.buttons
        
        Possible actions:
        check - whether the button was clicked or not
        enable - whether the button is enabled
        
        flag (bool) - true or false for action
        
        """
        for button_id in core.alphanumeric_index:
            if action == "check":
                # TODO add skipping of gray buttons
                self.buttons.at[button_id, "Button"].setChecked(flag)
            elif action == "enable":
                self.buttons.at[button_id, "Button"].setEnabled(flag)
            else:
                raise ValueError("Unknown action: {}".format(action))

    def resetButtons(self):
        for button_id in core.alphanumeric_index:
            self.buttons.at[button_id, "Button"].setStyleSheet(self.buttonStyleString)

    @pyqtSlot()
    def on_selectAll(self):
        """
        Cycles through all buttons, checks valid buttons and updates plots and table
        """
        QApplication.setOverrideCursor(Qt.WaitCursor)
        for button_id in self.buttons.index:
            if self.moltenProtFit.testWellID(button_id):
                self.buttons.at[button_id, "Button"].setChecked(True)
                self.updateTable(button_id)
                self.plotFigAny(button_id)
                self.currentCurveColor = next(self.curveColorCycler)["color"]
        # re-initialize colors
        self.resetColorCycler()
        self.canvas.draw()
        QApplication.restoreOverrideCursor()

    @pyqtSlot()
    def on_deselectAll(self):
        # clear axes
        self.axisClear()
        self.setAllButtons("check", False)
        self.resetTable()
        for button_id in core.alphanumeric_index:
            # NOTE draw_canvas=False makes the removal faster
            self.removeButtonLine2D(button_id, draw_canvas=False)
        # re-initialize colors
        self.resetColorCycler()
        self.canvas.draw()

    @pyqtSlot()
    def on_show(self, button_id):
        """
        The main action on button click
        This method is also called:
        1) when GUI is initialized
        2) when all buttons are selected/deselected
        
        checks for the validity of the button id are in respective methods (plotfig and updateTable)
        
        if button clicked
            upd table
            plot the curve
        else -> button unclicked
            remove plotted curve
            remove table entry
        
        Parameters
        ----------
        button_id
            alphanumeric code (e.g. A1) of the button that was clicked
        
        Known issues
        ------------
        * if a button that was already clicked is unclicked, the color cycle doesn't go back. This means that upon unclicking the color used in the line of the unclicked button will not become the current color. Visually, it is somewhat inconsistent, however, one would need to somehow track the previous color and check if the button was previously clicked or not. For instance, one can keep two copies of curve cyclers, where one is one step ahead of the other
        """
        btn = self.buttons.at[button_id, "Button"]
        if btn.isChecked():
            self.updateTable(button_id)
            # line has already been already plotted by the hover function, but need to change the color for plotting
            self.currentCurveColor = next(self.curveColorCycler)["color"]
        else:
            self.removeButtonLine2D(button_id)
            # remove respective entry from the table - scan all rows of the first column to find the button_id
            for row in range(self.tableWidget.rowCount()):
                # id in the table
                item = self.tableWidget.item(row, 0)
                if item is not None:
                    table_id = self.tableWidget.item(row, 0).text()
                    if table_id == button_id:
                        self.tableWidget.removeRow(row)
                        # only one table_id should exist, stop the cycle when found
                        break
        self.canvas.draw()

    def removeButtonLine2D(self, button_id, draw_canvas=True):
        """
        Removes lines associated with a button
        """
        lines = self.buttons.at[button_id, "Line2D"]
        if lines is not np.nan:
            for line in lines:
                line.remove()
            self.buttons.at[button_id, "Line2D"] = np.nan  # deregisters the line list
        if draw_canvas:
            # NOTE this updates the plot and may be a slow step
            # if this step is omitted then the changes to the plot will not be updated on the screen
            self.canvas.draw()

    def resetTable(self):
        """
        Cleans, but does not hide the table widget
        """
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(0)

    def updateTable(self, button_id):
        """
        Reads information from self.moltenProtFit and creates a table under the heatmap
        
        Notes
        -----
        * Table widget will be made visible when the method is called for the first time
        """

        if self.dataProcessed:
            plateResults = self.moltenProtFit.plate_results
            # create a dictionary to map column ID's in GUI to column names from getResultsColumns
            column_labels = ["ID", "Condition"] + self.moltenProtFit.getResultsColumns()
            column_dict = {}
            for i in range(len(column_labels)):
                column_dict[i] = column_labels[i]
            # set the number of columns in the table
            self.tableWidget.setColumnCount(len(column_dict))

            if self.tableWidget.isVisible() == False:
                self.tableWidget.show()
                self.tableDockWidget.show()

            # temporarily disable sorting to allow proper insertion of new rows (see QTableWidget docs)
            self.tableWidget.setSortingEnabled(False)

            rowPosition = self.tableWidget.rowCount()
            self.tableWidget.insertRow(rowPosition)
            for column_pos, column_name in column_dict.items():
                if column_name == "ID":
                    table_string = button_id
                elif column_name == "Condition":
                    table_string = plateResults.loc[button_id, column_name]
                    if table_string is np.nan:
                        # NOTE prevents QTableWidgetItem Overflow error
                        table_string = "n/a"
                    else:
                        table_string = str(table_string)
                elif column_name == "S":
                    # NOTE for S formatting to two last decimals is not always working
                    table_string = str(plateResults.loc[button_id, column_name])
                else:
                    table_string = "{:10.2f}".format(
                        plateResults.loc[button_id, column_name]
                    )
                item = QTableWidgetItem(table_string)
                item.setTextAlignment(Qt.AlignCenter)
                self.tableWidget.setItem(rowPosition, column_pos, item)
            # set table widget titles accordingly
            self.tableWidget.setHorizontalHeaderLabels(column_labels)
            # restore sorting functionality
            self.tableWidget.setSortingEnabled(True)
        else:
            # TODO can use this section to show sample information before analysis
            # print("Warning: cannot create table because data is not processed")
            pass

    def axisClear(self, draw_canvas=True):
        """
        Clears all available axes.
        
        Parameters
        ----------
        draw_canvas: bool
            force redraw of the plot window
            
        Notes
        -----
        This is not equivalent to self.fig.clear, which would remove everything from the plot window
        """
        # NOTE the very last ax is reserved for legend and nothing should be cleared here
        self.axes.clear()
        self.axes.grid(True)
        if self.axesDerivative != None:
            self.axesDerivative.clear()
            self.axesDerivative.grid(True)
        if draw_canvas:
            self.canvas.draw()

    def __setOneButtonStyle(self, input_series):
        """
        Helper function that applies a color and state to one button
        To be used in setButtonsStyle/setButtonsStyleAccordingToNormalizedData
        """
        button = input_series["Button"]
        color = input_series["Color"]
        tooltip = input_series["Tooltip"]
        if color is not None:
            styleString = (
                "QPushButton {  border-width: 2px; border-color: white; background-color: "
                + matplotlib.colors.to_hex(color, keep_alpha=False)
                + "} QPushButton:checked { border-color:  black; border-style: inset;}"
            )
            enabled = True
        else:
            styleString = "QPushButton {  border-width: 2px; border-color: white; background-color: gray } QPushButton:checked { border-color:  black; border-style: inset;}"
            enabled = False
        button.setEnabled(enabled)
        button.setStyleSheet(styleString)
        if tooltip is not None:
            button.setToolTip(tooltip)

    def createButtonArray(self, hbox):
        ## \brief self.buttons attribute contains all information related to samples selected in the GUI heatmap and their plots
        # index is alphanumeric ID's (similar to mp.MoltenProtFit.plate_results), but columns contain the info on the state of the GUI:
        # Visible (bool) - whether the button should be displayed at all - can be fetched from the button object
        # Selected (bool) - whether the user clicked on the button - can be fetched from the button object
        # Color (str) - matplotlib-compatible color for the curve
        # Button - reference to the respective GUI button
        # Tooltip - information displayed when mouse is over a button
        # Line2D - reference to the matplotlib object of the experimental line; if None, then the curve was not plotted!
        # LineColor - the color used for the line (e.g. from colorsafe list, or the same color as the button)
        self.buttons = pd.DataFrame(
            index=core.alphanumeric_index,
            columns=("Button", "Color", "Tooltip", "Line2D", "LineColor",),
        )
        self.buttons.index.name = "ID"

        # constants for the button generation
        buttonSize = 40
        letters = ["A", "B", "C", "D", "E", "F", "G", "H"]

        # populate the buttons DataFrame with actual buttons
        for j in range(self.colsCount):
            right_vbox = QVBoxLayout()
            for i in range(self.rowsCount):
                button_name = letters[i] + str(j + 1)
                button = QPushButton(button_name)
                button.setObjectName(button_name)
                button.setCheckable(True)
                button.setChecked(False)
                button.setEnabled(False)
                button.setFixedWidth(buttonSize)
                button.setFixedHeight(buttonSize)
                button.setStyleSheet(self.buttonStyleString)
                button.installEventFilter(self)
                # pass the button name to the slot:
                # borrowed [here](https://eli.thegreenplace.net/2011/04/25/passing-extra-arguments-to-pyqt-slot)
                button.clicked.connect(partial(self.on_show, button_name))
                right_vbox.addWidget(button)
                # add button to buttons df
                self.buttons.at[button_name, "Button"] = button
            right_vbox.addStretch(1)
            hbox.addLayout(right_vbox)
        hbox.addStretch(1)

    def showOnlyValidButtons(self):
        # shows a button only if it is found in the raw data
        for button_id in core.alphanumeric_index:
            if self.moltenProtFit.testWellID(button_id, ignore_results=True):
                self.buttons.at[button_id, "Button"].show()
            else:
                self.buttons.at[button_id, "Button"].hide()

    def actionsSetVisible(self, show):
        # show/hide buttons that require a dataset to be loaded
        self.showHideSelectDeselectAll(show)
        self.mainWindow.actionAnalysis.setVisible(show)
        self.mainWindow.actionEdit_layout.setVisible(show)
        self.mainWindow.actionSave_as_JSON.setVisible(show)
        self.mainWindow.actionToolBar.setVisible(show)
        self.mainWindow.actionToolBar.setEnabled(show)
        self.mainWindow.actionShowHideProtocol.setVisible(show)

    def resetGUI(self):
        # Make the GUI look like it was just opened:
        # analysis options, layout etc are hidden, all buttons are not clickable
        # This method is used when a file could not be opened
        self.actionsSetVisible(False)
        self.resetButtons()
        self.setAllButtons("enable", False)
        self.populateDatasetComboBox(
            []
        )  # with an empty list as argument the combobox will be hidden

    def eventFilter(self, object, event):
        """
        Event filter to handle additional button events (clicks are handled via method on_show)
        """
        button_id = object.objectName()  # get button ID
        if event.type() == QEvent.HoverMove or event.type()==QEvent.Enter:
            # NOTE handling non-existing/gray samples is in method plotFigAny
            if self.fileLoaded:
                # plot new lines only if not registered
                if self.buttons.at[button_id, "Line2D"] is np.nan:
                    self.plotFigAny(button_id)
                    self.canvas.draw()
            # TODO highlight the curve if it has already been selected
            if object.isChecked():
                pass

        if event.type() == QEvent.HoverLeave or event.type()==QEvent.Leave:
            if not object.isChecked():
                if self.buttons.at[button_id, "Line2D"] is not np.nan:
                    # NOTE when draw_canvas is false, then the curve will be only removed when a new one is plotted, this makes hovering more smooth, however, creates "undeletable" plots
                    self.removeButtonLine2D(button_id)

        return False

    ## \brief This method plots a curve from a single well on the axes using the curve* set of settings and the processing status (raw or after analysis)
    def plotFigAny(self, wellID):
        """
        Plot a curve from a single well on the axes
        using the curve* set of settings and the processing status (raw or after analysis)
        
        Parameters
        ----------
        wellID
            a string with the alphanumeric well id; non-existent ID's are also handled
        """
        # some starting settings
        # NOTE MoltenProt internally uses K, but in future chemical denaturants can be here, too
        xlabel = "Temperature, K"
        ylabel = self.moltenProtFit.readout_type
        # variable to have only one legend entry for exp/fit plots
        sample_label = False

        # set the color of all curves to be plotted
        if self.curveHeatmapColorCheckBoxIsChecked:
            current_color = self.buttons.at[wellID, "Color"]
        else:
            current_color = self.currentCurveColor

        # a list of all plotted lines
        lines = []

        # check if the well exists anywhere in the data
        if self.moltenProtFit.testWellID(wellID, ignore_results=True):
            # a flag to request raw data plotting
            # will only be false when processed data is available and plotted
            plot_raw = True

            # the well is definitely recorded, but the fit might have failed or not even performed
            if self.dataProcessed:
                # main plotting part
                if self.moltenProtFit.testWellID(wellID, ignore_results=False):
                    # sample was successfully fit
                    # the displayable elements primarily depend on curve type
                    # applicable to all types:
                    # curveLegendComboboxCurrentText - either show ID in legend or annotation, or no legend at all
                    # curveMarkEverySpinBoxValue - density of datapoints
                    # curveViewComboboxCurrentText - Datapoints, Fit, Datapoints + Fit - also for van 't Hoff?
                    # applicable to exp and funf
                    # applicable to exp only
                    # curveDerivativeCheckBoxIsChecked - yes/no derivative plot
                    # curveBaselineCheckBoxIsChecked - yes/no baselines

                    # sample label is taken from the layout or well ID
                    if self.curveLegendComboboxCurrentText == "Annotation":
                        label = self.moltenProtFit.plate_results.at[wellID, "Condition"]
                    else:
                        label = wellID

                    if self.curveTypeComboboxCurrentText == "Experimental signal":
                        if (
                            self.curveViewComboboxCurrentText == "Datapoints"
                            or self.curveViewComboboxCurrentText == "Datapoints + Fit"
                        ):
                            lines += self.axes.plot(
                                self.moltenProtFit.plate[wellID].index.values,
                                self.moltenProtFit.plate[wellID],
                                lw=0,
                                marker=".",
                                markevery=self.curveMarkEverySpinBoxValue,
                                label=label,
                                color=current_color,
                            )
                            sample_label = True
                        if (
                            self.curveViewComboboxCurrentText == "Fit"
                            or self.curveViewComboboxCurrentText == "Datapoints + Fit"
                        ):
                            # if exp signal was plotted, do not add label to fit
                            if sample_label:
                                lines += self.axes.plot(
                                    self.moltenProtFit.plate_fit[wellID].index.values,
                                    self.moltenProtFit.plate_fit[wellID],
                                    color=current_color,
                                )
                            else:
                                lines += self.axes.plot(
                                    self.moltenProtFit.plate_fit[wellID].index.values,
                                    self.moltenProtFit.plate_fit[wellID],
                                    color=current_color,
                                    label=label,
                                )
                            # if current_color is None:
                            #    current_color = self.axes.get_lines()[-1].get_color()

                        # draw Tm/Tagg or Tons
                        lines += self.plotVlines(wellID, current_color)

                        if self.curveBaselineCheckBoxIsChecked:
                            # draw baselines
                            # calculate polynomials
                            poly_pre = np.poly1d(
                                *self.moltenProtFit.plate_results.loc[
                                    [wellID], ["kN_fit", "bN_fit"]
                                ].values
                            )
                            poly_post = np.poly1d(
                                *self.moltenProtFit.plate_results.loc[
                                    [wellID], ["kU_fit", "bU_fit"]
                                ].values
                            )
                            xmin_xmax = (
                                self.moltenProtFit.plate[wellID].index.min(),
                                self.moltenProtFit.plate[wellID].index.max(),
                            )
                            lines += self.axes.plot(
                                xmin_xmax,
                                poly_pre(xmin_xmax),
                                linestyle="--",
                                color=current_color,
                            )
                            lines += self.axes.plot(
                                xmin_xmax,
                                poly_post(xmin_xmax),
                                linestyle="--",
                                color=current_color,
                            )
                    elif self.curveTypeComboboxCurrentText == "Baseline-corrected":
                        if "plate_raw_corr" in self.moltenProtFit.__dict__:
                            """
                            NOTE In this plotting mode no fit data exists
                            """
                            if (
                                self.curveViewComboboxCurrentText == "Datapoints"
                                or self.curveViewComboboxCurrentText
                                == "Datapoints + Fit"
                            ):
                                lines += self.axes.plot(
                                    self.moltenProtFit.plate_raw_corr[
                                        wellID
                                    ].index.values,
                                    self.moltenProtFit.plate_raw_corr[wellID],
                                    lw=0,
                                    # linestyle=":",
                                    marker=".",
                                    markevery=self.curveMarkEverySpinBoxValue,
                                    label=label,
                                    color=current_color,
                                )
                                self.axes.set_ylim([-0.2, 1.2])
                                # current_color = self.axes.get_lines()[-1].get_color()
                                # draw Tm/Tagg or Tons
                                lines += self.plotVlines(wellID, current_color)

                            if (
                                self.curveViewComboboxCurrentText == "Fit"
                                or self.curveViewComboboxCurrentText
                                == "Datapoints + Fit"
                            ):
                                # show warning in the status bar that the fit is not available here
                                self.status_text.setText(
                                    "Fit data are not available in this plotting mode"
                                )
                                # show the derivative on the extra plot
                    if (
                        self.curveDerivativeCheckBoxIsChecked
                        and self.axesDerivative is not None
                    ):
                        if self.curveTypeComboboxCurrentText == "Experimental signal":
                            lines += self.axesDerivative.plot(
                                self.moltenProtFit.plate_derivative[
                                    wellID
                                ].index.values,
                                self.moltenProtFit.plate_derivative[wellID],
                                color=current_color,
                            )
                        else:
                            # derivative only available for exp signal
                            lines.append(
                                self.axesDerivative.text(
                                    0.5,
                                    0.5,
                                    "n/a",
                                    horizontalalignment="center",
                                    verticalalignment="center",
                                    transform=self.axesDerivative.transAxes,
                                )
                            )
                        self.axesDerivative.set_xlabel("Temperature")
                        self.axesDerivative.set_ylabel("1st Deriv.")
                        # rescale axes
                        self.axesDerivative.relim()
                        self.axesDerivative.autoscale_view()
                    # skip raw data plotting
                    plot_raw = False

            if plot_raw:
                # this is run in two cases: when then there are gray wells after analysis, or when no processing done yet
                # NOTE this mode ignores the curveLegendComboBox and curveHeatmapColorCheckBox
                sourcedf = self.moltenProtFit.plate_raw
                lines += self.axes.plot(
                    sourcedf[wellID].index.values,
                    sourcedf[wellID],
                    label=wellID,
                    color=self.currentCurveColor,
                )
        else:
            print("Debug: non-existent well ID called: {}".format(wellID))

        # set labels for axes
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        # set xlim for axes based on the respective MoltenProt instance
        self.axes.set(xlim=self.moltenProtFit.xlim)
        # rescale axes
        self.axes.relim()
        self.axes.autoscale_view()

        # create legend (if respective axes already exists)
        if (
            self.curveLegendComboboxCurrentText != "None"
            and self.axesLegend is not None
        ):
            # select column number based on the legend display mode
            if self.curveLegendComboboxCurrentText == "ID":
                ncol = 8
            if self.curveLegendComboboxCurrentText == "Annotation":
                ncol = 2

            self.legend = self.axes.legend(
                bbox_to_anchor=(0.0, 0.8, 1.0, 0.0),
                bbox_transform=self.axesLegend.transAxes,
                ncol=ncol,
                mode="expand",
            )
        # if plotting was successful, record the line color and line list for future reference
        self.buttons.at[wellID, "LineColor"] = current_color
        self.buttons.at[wellID, "Line2D"] = lines

    def plotVlines(self, wellID, current_color):
        """
        Adds a Tm/Tagg or Tonset vertical line for wellID with color current_color based on the settings
        
        Arguments
        ---------
        wellID
            ID of the sample to plot
        current_color
            which color to use
        
        Returns
        -------
        A list of plotted Line2D objects
        
        Notes
        -----
        Lines may have different names from different models; just use the contents of MPFit.plotlines
        """
        out = []
        if self.curveVlinesCheckBoxIsChecked:
            for parameter_name in self.moltenProtFit.plotlines:
                # NOTE lines are not labeled so that they are not listed in the legend
                out.append(
                    self.axes.axvline(
                        self.moltenProtFit.plate_results[parameter_name][wellID],
                        ls="dotted",
                        c=current_color,
                        lw=3,
                    )
                )
                # add text with the parameter used to generate the line
                out.append(
                    self.axes.text(
                        self.moltenProtFit.plate_results[parameter_name][wellID],
                        self.axes.get_ylim()[0]
                        + 0.05 * (self.axes.get_ylim()[1] - self.axes.get_ylim()[0]),
                        " " + parameter_name,
                    )
                )
        return out

    ## \brief this method creates subplots for derivative and/or legend
    def manageSubplots(self):
        if self.dataProcessed:
            self.getPlotSettings()
            self.fig.clear()
            if (
                self.curveDerivativeCheckBoxIsChecked
                and self.curveLegendComboboxCurrentText != "None"
            ):
                self.axes = self.fig.add_subplot(3, 1, 1)
                # TODO hide ticks for main plot when deriv plot is on
                self.axesDerivative = self.fig.add_subplot(3, 1, 2, sharex=self.axes)
                self.axesLegend = self.fig.add_subplot(3, 1, 3)
            elif self.curveDerivativeCheckBoxIsChecked:
                self.axes = self.fig.add_subplot(2, 1, 1)
                self.axesDerivative = self.fig.add_subplot(2, 1, 2, sharex=self.axes)
                self.axesLegend = None
            elif self.curveLegendComboboxCurrentText != "None":
                self.axes = self.fig.add_subplot(2, 1, 1)
                self.axesDerivative = None
                self.axesLegend = self.fig.add_subplot(2, 1, 2)
            else:
                # nothing checked - just keep the main plot
                self.axes = self.fig.add_subplot(1, 1, 1)
                self.axesDerivative = None
                self.axesLegend = None
            # remove spines from legend subplot
            if self.axesLegend != None:
                self.axesLegend.axis("off")
            # set axes grids
            self.axes.grid(True)
            if self.axesDerivative is not None:
                self.axesDerivative.grid(True)
        else:
            # without complete analysis most visualizations are not possible
            self.status_text.setText(
                "Run analysis to enable additional plotting options"
            )

    ## \brief This method shows or hides the legend.
    @pyqtSlot()
    def on_legendChecked(self):
        self.getPlotSettings()
        self.fig.clear()
        if self.curveLegendComboboxCurrentText != "None":
            # create a dedicated subplot for holding the legend
            if self.axesDerivative != None:
                self.axes = self.fig.add_subplot(3, 1, 1)
                self.axesDerivative = self.fig.add_subplot(3, 1, 2)
                self.axesLegend = self.fig.add_subplot(3, 1, 3)
            else:
                self.axes = self.fig.add_subplot(2, 1, 1)
                # self.axesDerivative = self.fig.add_subplot(2,1,2)
                self.axesLegend = self.fig.add_subplot(2, 1, 2)
        else:
            # remove existing legend
            if self.axesLegend is not None:
                if self.axesDerivative != None:
                    self.axes = self.fig.add_subplot(2, 1, 1)
                    self.axesDerivative = self.fig.add_subplot(2, 1, 2)
                else:
                    self.axes = self.fig.add_subplot(1, 1, 1)

    @pyqtSlot()
    def on_curveBaselineCheckBoxChecked(self):
        if showVersionInformation:
            print(
                "on_curveBaselineCheckBoxChecked",
                self.moltenProtToolBox.ui.curveBaselineCheckBox.isChecked(),
                cfFilename,
                currentframe().f_lineno,
            )

    def createMatplotlibStuff(self):
        self.main_frame = QWidget()
        self.fig = Figure()
        self.axes = self.fig.add_subplot()
        self.axes.grid(True)
        self.canvas = FigureCanvas(self.fig)
        # print(type(self.canvas),  currentframe().f_lineno,  cfFilename)
        self.canvas.setParent(self.main_frame)
        # Create matplolib toolbar as a Qt object
        # self.mpl_toolbar = NavigationToolbar(self.canvas, self.main_frame)

        left_vbox = QVBoxLayout()
        left_vbox.addWidget(self.canvas)
        self.main_frame.setLayout(left_vbox)

    def addDerivativeSublot(self):
        self.axesDerivative = self.fig.add_subplot(2, 1, 2)

    ## \brief This method is no unused.
    def createMatplotlibContextMenu(self):
        # show context menu of matplolib window, show/hide legend, show/hide derivative plot
        self.main_frame.setContextMenuPolicy(Qt.ActionsContextMenu)

        # show/hide legend
        # self.showLegendAction = QAction("Show legend",  self.main_frame)
        # self.showLegendAction.setCheckable(True)
        # Show or hide the legend.
        # self.showLegendAction.triggered.connect(self.on_legendChecked)
        # Create matplotlib - show/hide the derivative.
        # self.showDerivativeSubplotAction = QAction("Show derivative subplot",  self.main_frame)
        # self.showDerivativeSubplotAction.setCheckable(True)
        # Hide the derivative window.
        # self.showDerivativeSubplotAction.setVisible(False)
        # actions after using the checkbox
        # add matplolib actions to Qt context menu
        # self.main_frame.addAction(self.showLegendAction)
        # self.main_frame.addAction(self.showDerivativeSubplotAction)

    ## \brief This method assignes to  the stackable window heatmap.
    def createHeatmapDockWidget(self, heatmapTitle="Heatmap"):
        """
        heatmapDockWidget = QDockWidget(self)
        heatmapDockWidget.setWindowTitle(heatmapTitle)
        heatmapDockWidget.setAllowedAreas(Qt.LeftDockWidgetArea|Qt.RightDockWidgetArea)
        heatmapDockWidget.setObjectName("heatmapDockWidget")
        self.addDockWidget(Qt.DockWidgetArea(1), heatmapDockWidget)
        """
        heatmapDockWidget = self.mainWindow.heatmapDockWidget
        return heatmapDockWidget

    def createHeatmapButtons(self):
        # Create buttons in the dockable heatmap widget
        self.dockButtonsFrame = QWidget(self.heatmapDockWidgetContents)
        hbox = QHBoxLayout()
        self.createButtonArray(hbox)
        self.dockButtonsFrame.setLayout(hbox)

    ## \brief This method creates sortScoreComboBox and datasetComboBox, sets tooltips for them
    def createComboBoxesForActionToolBar(self):
        ## \brief  This attribute holds the sortScoreComboBox.
        self.sortScoreComboBox = QComboBox()
        self.sortScoreComboBox.setToolTip("Select sort score")
        self.sortScoreComboBox.currentIndexChanged.connect(
            self.setButtonsStyleAccordingToNormalizedData
        )
        ## \brief  This attribute holds the datasetComboBox.
        self.datasetComboBox = QComboBox()
        self.datasetComboBox.setToolTip("Select a dataset for viewing")
        self.datasetComboBox.currentIndexChanged.connect(self.on_changeInputTable)
        self.heatmapMultipleListView = QListView(self.datasetComboBox)
        self.datasetComboBox.setView(self.heatmapMultipleListView)
        self.datasetComboBoxAction = self.mainWindow.actionToolBar.addWidget(
            self.datasetComboBox
        )

    def createColorMapComboBox(self):
        self.colorMapComboBox = self.moltenProtToolBox.ui.colormapForPlotComboBox
        self.moltenProtToolBox.ui.colormapForPlotLabel.hide()
        self.colorMapComboBox.hide()
        self.colorMapComboBox.insertItems(1, self.colorMapNames)
        index = int(
            self.settings.value(
                "toolbox/miscSettingsPage/colormapForPlotComboBoxIndex", 0
            )
        )
        self.colorMapComboBox.currentIndexChanged.connect(self.on_changeColorMap)
        self.moltenProtToolBox.ui.colormapForPlotComboBox.setCurrentIndex(index)

    @pyqtSlot()
    def on_changeColorMap(self):
        self.currentColorMapIndex = self.colorMapComboBox.currentIndex()
        self.currentColorMap = self.colorMapNames[self.currentColorMapIndex]
        self.on_deselectAll()  # TODO can this be avoided?
        if self.moltenProtFit != None:
            self.setButtonsStyleAccordingToNormalizedData()

    ## \brief This method adds  self.sortScoreComboBox to self.mainWindow.actionToolBar if it was not already added. Then clears items in it, populates self.sortScoreComboBox by
    #   self.moltenProtFit.getResultsColumns() method and shows it. \sa core.MoltenProtFit.getResultsColumns() \sa sortScoreComboBox
    def populateAndShowSortScoreComboBox(self):
        if self.sortScoreCombBoxAction == None:
            self.sortScoreCombBoxAction = self.mainWindow.actionToolBar.addWidget(
                self.sortScoreComboBox
            )
        self.sortScoreComboBox.clear()
        self.sortScoreComboBox.insertItems(1, self.moltenProtFit.getResultsColumns())
        width = self.sortScoreComboBox.minimumSizeHint().width()
        self.sortScoreComboBox.setMinimumWidth(width)
        self.sortScoreCombBoxAction.setVisible(True)

    ## \brief This method creates MoltenProt GUI application main window.
    #   \details
    #   This method:
    #   - Creates Matplotlib GUI elements.
    #   - Creates MoltenProt MainWindow and set Matplotlib main_frame as CentralWidget.
    #   - Creates ComboBoxes for ActionToolBar via createComboBoxesForActionToolBar method. \sa createComboBoxesForActionToolBar
    def createMainWindow(self):
        self.fileLoaded = False
        self.dataProcessed = False
        self.createMatplotlibStuff()
        uifile = QFile(":/main.ui")
        uifile.open(QFile.ReadOnly)
        self.mainWindow = uic.loadUi(uifile, self)
        uifile.close()
        self.setCentralWidget(self.main_frame)
        self.createComboBoxesForActionToolBar()
        self.mainWindow.actionToolBar.setVisible(False)
        self.mainWindow.actionToolBar.setEnabled(False)

        self.heatmapDockWidgetContents = QWidget(self.mainWindow.heatmapDockWidget)
        self.heatmapDockWidgetContents.setObjectName("heatmapDockWidgetContents")
        self.mainWindow.heatmapDockWidget.setWidget(self.heatmapDockWidgetContents)

        self.mainWindow.tableDockWidget.hide()
        self.tableDockWidget = self.mainWindow.tableDockWidget
        tableWidget = self.mainWindow.tableWidget
        tableWidget.setColumnCount(5)  # ATTENTION has to be set dynamically
        header = tableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        tableWidget.setSortingEnabled(True)
        tableWidget.setAlternatingRowColors(True)
        tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tableWidget.hide()
        self.tableWidget = tableWidget
        self.mainWindow.heatmapDockWidget.setMinimumWidth(560)
        # Hide the Protocol DockWidget
        self.mainWindow.protocolDockWidget.setVisible(False)

        # self.createColormap()
        self.createHeatmapButtons()
        self.connectSignals2Actions()
        self.mainWindow.actionSave_as_JSON.setVisible(False)

        self.font = QFont("Arial", 10)

    def connectSignals2Actions(self):
        self.mainWindow.actionNew.triggered.connect(self.on_actionNewTriggered)
        self.mainWindow.actionLoad.triggered.connect(self.on_loadFile)
        self.mainWindow.actionLoad_sample_data.triggered.connect(
            self.on_actionLoad_sample_data
        )
        self.mainWindow.actionSave_as_JSON.triggered.connect(
            self.on_actionSave_as_JSONTriggered
        )
        self.mainWindow.actionQuit.triggered.connect(self.on_closeMoltenProtMainWindow)
        self.mainWindow.actionAbout.triggered.connect(self.on_actionAbout)
        self.mainWindow.actionCite_MoltenProt.triggered.connect(
            self.on_actionCite_MoltenProt
        )
        self.mainWindow.actionHelp.triggered.connect(self.on_actionHelp)
        self.mainWindow.actionAnalysis.triggered.connect(
            self.on_analysisPushButtonClicked
        )
        self.mainWindow.actionActions.triggered.connect(self.on_showmoltenProtToolBox)
        self.mainWindow.actionExport.triggered.connect(self.on_exportResults)
        self.mainWindow.actionDeselectAll.triggered.connect(self.on_deselectAll)
        self.mainWindow.actionSelectAll.triggered.connect(self.on_selectAll)
        self.mainWindow.actionEdit_layout.triggered.connect(self.editLayout)
        self.mainWindow.actionPrtSc.triggered.connect(self.on_saveMainWindowAsPng)
        self.mainWindow.actionShowHideProtocol.triggered.connect(
            self.on_actionShowHideProtocol
        )
        self.mainWindow.actionFont.triggered.connect(self.on_actionFontTriggered)

    @pyqtSlot()
    def on_closeMoltenProtMainWindow(self):
        msg = QMessageBox(self)
        msg.setFont(self.font)
        msg.setWindowTitle("MoltenProt")
        if self.threadIsWorking == True:
            msg.setIcon(QMessageBox.Information)
            msg.setText("Some thread is still running. Please try later.")
            msg.setStandardButtons(QMessageBox.Ok)
        else:
            msg.setIcon(QMessageBox.Question)
            msg.setText("Are you sure that you want to close MoltenProt?")
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            retval = msg.exec_()
            if retval == QMessageBox.Ok:
                self.closeWithoutQuestion = True
                self.close()

    def closeEvent(self, event):
        msg = QMessageBox()
        msg.setFont(self.font)
        msg.setWindowTitle("MoltenProt")
        if self.threadIsWorking == True:
            msg.setIcon(QMessageBox.Information)
            msg.setText("Some thread is still running. Please try later.")
            msg.setStandardButtons(QMessageBox.Ok)
            event.ignore()
        else:
            if self.closeWithoutQuestion:
                event.accept()
            else:
                msg.setIcon(QMessageBox.Question)
                msg.setText("Are you sure that you want to close MoltenProt?")
                msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                retval = msg.exec_()
                if retval == QMessageBox.Ok:
                    event.accept()
                else:
                    event.ignore()

    @pyqtSlot()
    def on_actionShowHideProtocol(self):
        self.mainWindow.protocolDockWidget.setVisible(
            self.mainWindow.actionShowHideProtocol.isChecked()
        )
        # read protocol from the currently viewed MoltenProtFit instance
        if self.moltenProtFit is not None:
            self.mainWindow.protocolPlainTextEdit.setPlainText(
                self.moltenProtFit.protocolString
            )

    def connectButtonsFromLayoutDialog(self):
        # if OK clicked - update layout as it is
        self.layoutDialog.ui.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(
            self.updateLayout
        )
        # NOTE Save button is redundant
        # self.layoutDialog.ui.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.saveLayout)
        # Open button allow loading an external layout file and applying it to the MPFM instance
        self.layoutDialog.ui.buttonBox.button(QDialogButtonBox.Open).clicked.connect(
            self.openLayout
        )
        # a button to restore original layout
        self.layoutDialog.ui.buttonBox.button(QDialogButtonBox.Reset).clicked.connect(
            self.resetLayout
        )

    def layoutTableCellClicked(self, row, column):
        if showVersionInformation:
            print(row, column, currentframe().f_lineno, cfFilename)

    def createStatusBar(self):
        self.status_text = QLabel("Please load a data file")
        self.statusBar().addWidget(self.status_text, 1)

    @pyqtSlot()
    def on_saveMainWindowAsPng(self):
        pixMap = QApplication.primaryScreen().grabWindow(self.winId())
        filename = QFileDialog.getSaveFileName(
            self,
            caption=self.tr("Enter png file name "),
            directory=self.lastDir,
            filter="png Files (*.png)",
        )[0]
        # add PNG suffix if needed
        if filename[-4:] != ".png":
            filename += ".png"
        pixMap.save(filename, "PNG")

    def setExpertMode(self):
        if showVersionInformation:
            print("setExpertMode")
