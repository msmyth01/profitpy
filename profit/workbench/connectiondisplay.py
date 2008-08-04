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

from profit.lib import BasicHandler, Signals, defaults, logging
from profit.workbench.widgets.ui_connectionwidget import Ui_ConnectionWidget


def hasTerm():
    """ Runs an external process (which) to find xterm.  Returns True if found.

    """
    try:
        proc = Popen(['which', 'xterm'], stdout=PIPE, stderr=PIPE)
        return proc.communicate()[0].strip()
    except (Exception, ):
        pass


def commandStrings():
    """ Returns keystroke helper and TWS command strings.

    """
    binDir = abspath(join(dirname(abspath(__file__)), pardir, 'bin'))
    keyCmd =  join(binDir, 'login_helper') + ' -v'
    brokerCmd = join(binDir, 'ib_tws')
    if hasTerm():
        commandFs = 'xterm -title %s -e %s'
        keyCmd = commandFs % ('helper', keyCmd, )
        brokerCmd = commandFs % ('ibtws', brokerCmd, )
    return keyCmd, brokerCmd


class ConnectionDisplay(QFrame, Ui_ConnectionWidget, BasicHandler):
    """ ConnectionDisplay -> widgets for managing broker connection.

    """
    def __init__(self, parent=None):
        """ Initializer.

        @param parent ancestor of this object
        @return None
        """
        QFrame.__init__(self, parent)
        self.setupUi(self)
        self.setupControls()
        self.startTimer(500)
        self.requestSession()

    def setSession(self, session):
        """ Configures this instance for a session.

        @param session Session instance
        @return None
        """
        self.session = session
        connected = session.isConnected()
        self.setConnectControlsEnabled(not connected, connected)
        session.registerMeta(self)
        session.registerAll(self.updateLastMessage)
        if session.connection:
            ver = session.connection.serverVersion()
            contime = session.connection.TwsConnectionTime()
            self.serverVersionEdit.setText(str(ver))
            self.connectionTimeEdit.setText(contime)

    def unsetSession(self):
        """ Removes association between this instance and it's session object.

        """
        session = self.session
        session.deregisterAll(self.updateLastMessage)
        self.disconnect(session, Signals.tws.connected, self.on_connectedTWS)

    def on_session_ConnectionClosed(self, message):
        """ Resets various widgets after a connection closed message.

        """
        self.setConnectControlsEnabled(True, False)
        self.serverVersionEdit.setText('')
        self.connectionTimeEdit.setText('')
        self.rateThermo.setValue(0.0)
        self.lastMessageEdit.setText('Connection closed.')

    def on_session_connectedTWS(self):
        """ Called after a connection to the broker is established.

        """
        session = self.session
        if session.isConnected():
            self.setConnectControlsEnabled(False, True)
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
            port = self.portNumberSpin.value()
            if port == session.specialPortNo:
                port = 7496
            host = self.hostNameEdit.text()
            text = 'Unable to connect.\n\nEnsure TWS is running'
            text += ' on %s and is configured to accept socket ' % host
            text += 'connections on port %s.' % port
            QMessageBox.critical(self, 'Connection Error', text)
            self.setConnectControlsEnabled(True, False)

    @pyqtSignature('')
    def on_connectButton_clicked(self):
        """ Connects the session to the broker.

        """
        host = self.hostNameEdit.text()
        port = self.portNumberSpin.value()
        clientId = self.clientIdSpin.value()
        try:
            self.session.connectTWS(host, port, clientId)
        except (Exception, ), exc:
            QMessageBox.critical(self, 'Connection Error', str(exc))

    @pyqtSignature('')
    def on_disconnectButton_clicked(self):
        """ Disconnects the session from the broker.

        """
        if self.session and self.session.isConnected():
            self.session.disconnectTWS()
            self.setConnectControlsEnabled(True, False)

    @pyqtSignature('')
    def on_keyHelperCommandRunButton_clicked(self):
        """ Runs the keystroke helper command.

        """
        args = str(self.keyHelperCommandEdit.text()).split()
        if not args:
            return
        try:
            proc = Popen(args)
        except (OSError, ), exc:
            QMessageBox.critical(self, 'Key Helper Command Error', str(exc))

    @pyqtSignature('')
    def on_keyHelperCommandSelectButton_clicked(self):
        """ Prompts user with dialog box to select keystroke helper.

        """
        filename = QFileDialog.getOpenFileName(
            self, 'Select Helper Command', '')
        if filename:
            self.keyHelperCommandEdit.setText(filename)

    @pyqtSignature('')
    def on_brokerCommandRunButton_clicked(self):
        """ Runs the broker application command.

        """
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
        """ Prompts user with dialog box to select broker application.

        """
        filename = QFileDialog.getOpenFileName(
            self, 'Select Broker Application', '')
        if filename:
            self.brokerCommandEdit.setText(filename)

    @pyqtSignature('QString')
    def on_brokerCommandEdit_textEdited(self, text):
        """ Saves the broker command string when edited.

        """
        self.settings.setValue('brokercommand', text)

    @pyqtSignature('QString')
    def on_keyHelperCommandEdit_textEdited(self, text):
        """ Saves the keystroke helper command string when edited.

        """
        self.settings.setValue('keycommand', text)

    @pyqtSignature('QString')
    def on_hostNameEdit_textEdited(self, text):
        """ Saves the hostname string when edited.

        """
        self.settings.setValue('host', text)

    @pyqtSignature('int')
    def on_portNumberSpin_valueChanged(self, value):
        """ Saves the port number when changed.

        """
        self.settings.setValue('port', value)

    @pyqtSignature('int')
    def on_clientIdSpin_valueChanged(self, value):
        """ Saves the client id number when changed.

        """
        self.settings.setValue('clientid', value)

    def setupControls(self):
        """ Configures controls on this display.

        """
        self.brokerPids = []
        settings = self.settings
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

    def setConnectControlsEnabled(self, connect, disconnect):
        """ Enables or disables connection buttons and parameter widgets.

        """
        self.connectButton.setEnabled(connect)
        self.disconnectButton.setEnabled(disconnect)
        self.connectParamWidgets.setEnabled(connect)

    def timerEvent(self, event):
        """ Updates the rate thermometer widget.

        """
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
        """ Updates the last message label.

        """
        self.lastMessageEdit.setText(str(message)[1:-1])
        self.lastMessageEdit.setCursorPosition(0)
