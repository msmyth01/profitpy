#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2007 Troy Melhase
# Distributed under the terms of the GNU General Public License v2
# Author: Troy Melhase <troy@gci.net>

from os import getpid
from os.path import abspath, dirname, join, pardir
from subprocess import Popen, PIPE
from sys import platform
from time import time

from PyQt4.QtCore import Qt, pyqtSignature
from PyQt4.QtGui import QFrame, QMessageBox, QFileDialog

# workaround for code generated by pyuic4
from PyQt4 import QtCore, QtGui
from PyQt4.Qwt5 import QwtThermo; QtGui.QwtThermo = QwtThermo

from profit.lib import defaults, logging
from profit.lib.core import SessionHandler, Settings, Signals
from profit.workbench.widgets.ui_connectionwidget import Ui_ConnectionWidget


def hasTerm():
    try:
        return Popen(['which', 'xterm'], stdout=PIPE, stderr=PIPE).communicate()[0].strip()
    except (Exception, ):
        pass


def commandStrings():
    binDir = abspath(join(dirname(abspath(__file__)), pardir, 'bin'))
    keyCmd =  join(binDir, 'login_helper') + ' -v'
    brokerCmd = join(binDir, 'ib_tws')
    if hasTerm():
        commandFs = 'xterm -title %s -e %s'
        keyCmd = commandFs % ('helper', keyCmd, )
        brokerCmd = commandFs % ('ibtws', brokerCmd, )
    return keyCmd, brokerCmd


def saveMethod(sig, key):
    @pyqtSignature(sig)
    def method(self, value):
        self.settings.setValue(key, value)
    return method


class ConnectionDisplay(QFrame, Ui_ConnectionWidget, SessionHandler):
    def __init__(self, parent=None):
        QFrame.__init__(self, parent)
        self.setupUi(self)
        self.setupControls()
        self.startTimer(500)
        self.requestSession()

    def setSession(self, session):
        self.session = session
        connected = session.isConnected()
        self.setControlsEnabled(not connected, connected)
        session.registerMeta(self)
        session.registerAll(self.updateLastMessage)
        if session.connection:
            self.serverVersionEdit.setText(
                str(session.connection.serverVersion()))
            self.connectionTimeEdit.setText(
                session.connection.TwsConnectionTime())
        self.connect(session, Signals.connectedTWS, self.on_connectedTWS)

    def unsetSession(self):
        session = self.session
        session.deregisterAll(self.updateLastMessage)
        self.disconnect(session, Signals.connectedTWS, self.on_connectedTWS)

    def on_session_ConnectionClosed(self, message):
        self.setControlsEnabled(True, False)
        self.serverVersionEdit.setText('')
        self.connectionTimeEdit.setText('')
        self.rateThermo.setValue(0.0)
        self.lastMessageEdit.setText('')

    def on_connectedTWS(self):
        session = self.session
        if session.isConnected():
            self.setControlsEnabled(False, True)
            try:
                if self.requestAccount.isChecked():
                    session.requestAccount()
                if self.requestTickers.isChecked():
                    session.requestTickers()
                if self.requestOrders.isChecked():
                    session.requestOrders()
            except (Exception, ), exc:
                QMessageBox.critical(self, 'Session Error', str(exc))
            else:
                self.serverVersionEdit.setText(
                    str(session.connection.serverVersion()))
                self.connectionTimeEdit.setText(
                    session.connection.TwsConnectionTime())
        else:
            logging.warn('Exception during connect')
            QMessageBox.critical(
                self, 'Connection Error', 'Unable to connect.')
            self.setControlsEnabled(True, False)

    @pyqtSignature('')
    def on_connectButton_clicked(self):
        try:
            self.session.connectTWS(
                self.hostNameEdit.text(),
                self.portNumberSpin.value(),
                self.clientIdSpin.value())
        except (Exception, ), exc:
            QMessageBox.critical(self, 'Connection Error', str(exc))

    @pyqtSignature('')
    def on_disconnectButton_clicked(self):
        if self.session and self.session.isConnected():
            self.session.disconnectTWS()
            self.setControlsEnabled(True, False)

    @pyqtSignature('')
    def on_keyHelperCommandRunButton_clicked(self):
        args = str(self.keyHelperCommandEdit.text()).split()
        try:
            proc = Popen(args)
        except (OSError, ), exc:
            QMessageBox.critical(self, 'Key Helper Command Error', str(exc))

    @pyqtSignature('')
    def on_keyHelperCommandSelectButton_clicked(self):
        filename = QFileDialog.getOpenFileName(
            self, 'Select Helper Command', '')
        if filename:
            self.keyHelperCommandEdit.setText(filename)

    @pyqtSignature('')
    def on_brokerCommandRunButton_clicked(self):
        args = str(self.brokerCommandEdit.text()).split()
        if not args:
            return
        try:
            proc = Popen(args)
        except (OSError, ), exc:
            QMessageBox.critical(self, 'Broker Command Error', str(exc))
        else:
            self.brokerPids.append(proc.pid)

    @pyqtSignature('')
    def on_brokerCommandSelectButton_clicked(self):
        filename = QFileDialog.getOpenFileName(
            self, 'Select Broker Command', '')
        if filename:
            self.brokerCommandEdit.setText(filename)

    ## saveMethod stopped working so these methods will have to do for
    ## now.

    @pyqtSignature('QString')
    def on_brokerCommandEdit_textEdited(self, text):
        self.settings.setValue('brokercommand', text)

    @pyqtSignature('QString')
    def on_keyHelperCommandEdit_textEdited(self, text):
        self.settings.setValue('keycommand', text)

    @pyqtSignature('QString')
    def on_hostNameEdit_textEdited(self, text):
        self.settings.setValue('host', text)

    @pyqtSignature('int')
    def on_portNumberSpin_valueChanged(self, value):
        self.settings.setValue('port', value)

    @pyqtSignature('int')
    def on_clientIdSpin_valueChanged(self, value):
        self.settings.setValue('clientid', value)

    def setupControls(self):
        self.brokerPids = []
        self.settings = settings = Settings()
        settings.beginGroup(settings.keys.connection)
        self.hostNameEdit.setText(
            settings.value('host', defaults.connection.host).toString())
        self.portNumberSpin.setValue(
            settings.value('port', defaults.connection.port).toInt()[0])
        self.clientIdSpin.setValue(
            settings.value('clientid', defaults.connection.client).toInt()[0])
        keyHelperCommand, brokerCommand = commandStrings()
        self.keyHelperCommandEdit.setText(
            settings.value('keycommand', keyHelperCommand).toString())
        self.brokerCommandEdit.setText(
            settings.value('brokercommand', brokerCommand).toString())
        self.rateThermo.setValue(0.0)
        self.rateThermo.setOrientation(Qt.Horizontal, self.rateThermo.BottomScale)

    def setControlsEnabled(self, connect, disconnect):
        self.connectButton.setEnabled(connect)
        self.disconnectButton.setEnabled(disconnect)
        self.connectParamWidgets.setEnabled(connect)

    def timerEvent(self, event):
        try:
            last = self.session.messages[-30:]
        except (AttributeError, ):
            return
        try:
            rate = len(last) / (time() - last[0][0])
            self.rateThermo.setValue(rate)
        except (IndexError, ZeroDivisionError, ):
            pass

    def updateLastMessage(self, message):
        name = message.typeName
        items = str.join(', ', ['%s=%s' % item for item in message.items()])
        text = '%s%s' % (name, ' ' + items if items else '')
        self.lastMessageEdit.setText(text)
        self.lastMessageEdit.setCursorPosition(0)
