import sys
import os
import logging
from PyQt5.QtWidgets import (QMainWindow, QMessageBox, QFileDialog, QTableWidgetItem)
from PyQt5.QtCore import (QThread, QSize, pyqtSignal, pyqtSlot)
import design
from types import MethodType
from visa import *
from telcommands import *
import telhacks

class GPIBTesterWindow(QMainWindow, design.Ui_MainWindow):
    def __init__(self, cfg, parent=None):
        super(GPIBTesterWindow, self).__init__(parent)
        self.setupUi(self)
        self.queryButton.clicked.connect(lambda: self.cmdButtonClicked('query'))
        self.writeButton.clicked.connect(lambda: self.cmdButtonClicked('write'))
        self.readButton.clicked.connect(lambda: self.cmdButtonClicked('read'))
        self.serialPollButton.clicked.connect(lambda: self.cmdButtonClicked('serial_poll'))
        self.clearButton.clicked.connect(lambda: self.cmdButtonClicked('clear'))
        self.runButton.clicked.connect(self.runButtonClicked)
        self.sidePanelButton.clicked.connect(self.sidePanelButtonClicked)
        self.saveAsButton.clicked.connect(self.saveAsButtonClicked)
        self.saveButton.clicked.connect(self.saveButtonClicked)
        self.sequenceBox.setCurrentIndex(-1)
        self.sequenceBox.currentIndexChanged.connect(self.sequenceBoxChanged)


        # start with a hidden right panel
        self.sidePanel.setHidden(True)

        # these are GUI widgets to disable while performing a command
        self.itemsToXable = (self.queryButton, self.writeButton, self.readButton, self.clearButton, self.runButton,
                             self.serialPollButton)

        # connect to the device
        self.rm, self.instr = self.connect(cfg)
    def save(self, filename):
        # compute a list with all the lines in the sequence table
        lines = []
        for i in range(self.tableWidget.rowCount() - 1):
            lines.append(self.tableWidget.item(i, 0).text())

        # dump the list contents to the selected file
        with open(filename, 'w') as f:
            for line in lines:
                f.write("{}\n".format(line))

    def saveAsButtonClicked(self):
        # select a file to save to using the dialog
        fname = QFileDialog.getSaveFileName(None, 'Save As', '.seq', filter='GPIB Sequence (*.seq)')
        if fname[0] == '':
            return

        # save to the selected file
        self.save(fname[0])

        # add this file to the combobox
        self.sequenceBox.blockSignals(True)
        last = self.sequenceBox.count() - 1
        self.sequenceBox.insertItem(last, fname[0])
        self.sequenceBox.setCurrentIndex(last)
        self.sequenceBox.blockSignals(False)

    def saveButtonClicked(self):
        filename = self.sequenceBox.currentText()
        self.save(filename)

    def sequenceBoxChanged(self):
        current = self.sequenceBox.currentIndex()
        last = self.sequenceBox.count() - 1
        if current == last:
            self.sequenceBox.blockSignals(True)
            fname = QFileDialog.getOpenFileName(filter='GPIB Sequence (*.seq);;All Files (*)')
            if fname[0] == '':
                return

            self.sequenceBox.insertItem(last, fname[0])
            self.sequenceBox.setCurrentIndex(last)
            self.sequenceBox.blockSignals(False)

            # delete all rows in sequence table
            self.tableWidget.setRowCount(0)

            # read selected file to a list
            with open(fname[0]) as f:
                lines = f.readlines()

            # add each line to the sequence table
            for line in lines:
                i = self.tableWidget.rowCount()
                self.tableWidget.insertRow(i)
                item = QTableWidgetItem(line.rstrip('\r\n'))
                self.tableWidget.setItem(i, 0, item)

    def sidePanelButtonClicked(self):
        h = self.sidePanel.isHidden()
        sw = self.size()
        sp = self.sidePanel.size()
        if h:
            self.resize(QSize(sw.width() + sp.width() + self.sidePanelLayout.spacing(), sw.height()))
            self.sidePanel.setHidden(False)
            self.sidePanelButton.setText('<\n<\n<\n')
        else:
            self.resize(QSize(sw.width() - sp.width() - self.sidePanelLayout.spacing(), sw.height()))
            self.sidePanel.setHidden(True)
            self.sidePanelButton.setText('>\n>\n>\n')

    def runButtonClicked(self):
        # t = GpibSequenceThread(self.instr, sequence)
        for row in range(self.tableWidget.rowCount()):
            command = self.tableWidget.item(row, 0).text()
            if command == 'A':
                self.thread = TELCommandThread(self.instr, 'query', command)
            elif command == 'O':
                self.thread = TELCommandThread(self.instr, 'query', command)
            elif command == '':
                continue
            else:
                logging.error('Unknown (not implemented?) command ' + command)
                continue

            self.thread.finished.connect(self.onFinished)
            self.thread.info.connect(self.info)
            self.thread.warning.connect(self.warning)
            self.thread.error.connect(self.error)
            self.thread.critical.connect(self.critical)
            self.thread.start()
            self.thread.wait()


    def cmdButtonClicked(self, cmd):
        for item in self.itemsToXable:
            item.setDisabled(True)

        self.thread = TELCommandThread(self.instr, cmd, self.commandEdit.text())
        self.thread.finished.connect(self.onFinished)
        self.thread.info.connect(self.info)
        self.thread.warning.connect(self.warning)
        self.thread.error.connect(self.error)
        self.thread.critical.connect(self.critical)
        self.thread.start()

    def showCriticalDialog(self, text):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText(text)
        msg.setWindowTitle("Critical")
        msg.setStandardButtons(QMessageBox.Close)
        msg.exec_()
        self.close()
        sys.exit()

    def connect(self, cfg):
        rm = None
        instr = None

        if(os.name == 'posix'):
            rm = ResourceManager('@py')
        else:
            rm = ResourceManager()

        i = cfg['gpibDevice']
        r = None
        try:
            r = rm.list_resources()
        except:
            logging.critical(i + ' is not connected')
            self.showCriticalDialog(i + ' is not connected')

        if i not in r:
            logging.critical(i + ' is not connected')
            self.showCriticalDialog(i + ' is not connected')

        instr = rm.open_resource(i)

        instr.read_stb = MethodType(telhacks.read_stb_with_previous, instr)
        instr.timeout = 1000 # in miliseconds

        return rm, instr

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.instr.close()
        self.rm.close()


    @pyqtSlot(str)
    def info(self, message):
        logging.info(message)

    @pyqtSlot(str)
    def error(self, message):
        logging.error(message)

    @pyqtSlot(str)
    def warning(self, message):
        logging.warning(message)

    @pyqtSlot(str)
    def critical(self, message):
        logging.critical(message)

    @pyqtSlot()
    def onFinished(self):
        for item in self.itemsToXable:
            item.setDisabled(False)
        # logging.info('...')
        self.thread.quit()