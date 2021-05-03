# This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivy.logger import Logger
import logging

from hardline import daemonconfig
logging.Logger.manager.root = Logger

import configparser
import libnacl,base64
from kivy.clock import mainthread,Clock

from .. import directories
from .. import simpleeval
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from .. import hardline

from typing import Sized, Text
from kivymd.app import MDApp
from kivy.utils import platform
from kivymd.uix.button import MDFillRoundFlatButton as Button, MDRoundFlatButton
from kivymd.uix.button import MDFlatButton

from kivymd.uix.textfield import MDTextFieldRect,MDTextField
from kivymd.uix.label import MDLabel as Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivymd.uix.toolbar import MDToolbar

from kivymd.uix.card import MDCard

from kivymd.uix.boxlayout import MDBoxLayout as BoxLayout
import threading
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

# Terrible Hacc, because otherwise we cannot iumport hardline on android.
import os
import sys
import re
from .. daemonconfig import makeUserDatabase
from .. import  drayerdb, cidict

from kivymd.uix.picker import MDDatePicker

import datetime

from hardline.cidict import CaseInsensitiveDict

from kivy.logger import Logger, LOG_LEVELS
Logger.setLevel(LOG_LEVELS["info"])










#On android the service that will actually be handling these databases is in the background in a totally separate
#process.  So we open an SECOND drayer database object for each, with the same physical storage, using the first as the server.
#just for use in the foreground app.

#Because of this, two connections to the same DB file is a completetely supported use case that drayerDB has optimizations for.
if platform=='android':
    daemonconfig.loadUserDatabases(None,forceProxy='127.0.0.1:7004')


from . import tools,servicesUI,discovery,tables,posts,streams,uihelpers



#In this mode, we are just acting as a viewer for a file
oneFileMode = False


#Horrible hacc
try:
    import plyer.platforms.linux.filechooser
    from distutils.spawn import find_executable as which

    class KDialogFileChooser(plyer.platforms.linux.filechooser.SubprocessFileChooser):
        '''A FileChooser implementation using KDialog (on GNU/Linux).
        Not implemented features:
        * show_hidden
        * preview
        '''

        executable = "kdialog"
        separator = "\n"
        successretcode = 0

        def _gen_cmdline(self):
            cmdline = [which(self.executable)]

            filt = []

            for f in self.filters:
                if type(f) == str:
                    filt += [f]
                else:
                    filt += list(f[1:])

            if self.mode == "dir":
                cmdline += [
                    "--getexistingdirectory",
                    (self.path if self.path else os.path.expanduser("~"))
                ]
            elif self.mode == "save":
                cmdline += [
                    "--getsavefilename",
                    (self.path if self.path else os.path.expanduser("~")),
                    " ".join(filt)
                ]
            else:
                cmdline += [
                    "--getopenfilename",
                    (self.path if self.path else os.path.expanduser("~")),
                    " ".join(filt)
                ]
            if self.multiple:
                cmdline += ["--multiple", "--separate-output"]
            if self.title:
                cmdline += ["--title", self.title]
            if self.icon:
                cmdline += ["--icon", self.icon]
            return cmdline
    plyer.platforms.linux.filechooser.KDialogFileChooser=KDialogFileChooser
    plyer.platforms.linux.filechooser.CHOOSERS['kde']=KDialogFileChooser
except:
    pass

class ServiceApp(MDApp, uihelpers.AppHelpers,tools.ToolsAndSettingsMixin,servicesUI.ServicesMixin,discovery.DiscoveryMixin,tables.TablesMixin,posts.PostsMixin,streams.StreamsMixin):

    def stop_service(self, foo=None):
        if self.service:
            self.service.stop()
            self.service = None
        else:
            hardline.stop()

    def start_service(self, foo=None):
        if self.service:
            self.service.stop()
            self.service = None

        if platform == 'android':
            from android import AndroidService
            service = AndroidService('HardlineP2P Service', 'running')
            service.start('service started')
            self.service = service
        else:
            def f():
                # Ensure stopped
                hardline.stop()

                loadedServices = daemonconfig.loadUserServices(
                    None)

                daemonconfig.loadDrayerServerConfig()


                db = daemonconfig.loadUserDatabases(
                    None)
                hardline.start(7009)
                # Unload them at exit because we will be loading them again on restart
                for i in loadedServices:
                    loadedServices[i].close()
            t = threading.Thread(target=f, daemon=True)
            t.start()

    def build(self):
        self.service = None

        self.start_service()

        # Create the manager
        sm = ScreenManager()
        sm.add_widget(self.makeMainScreen())
        sm.add_widget(self.makeDiscoveryPage())
        sm.add_widget(self.makeSettingsPage())

        sm.add_widget(self.makeLocalServiceEditPage())
        sm.add_widget(self.makeLocalServicesPage())
        sm.add_widget(self.makeGlobalSettingsPage())
        sm.add_widget(self.makeStreamsPage())
        sm.add_widget(self.makeStreamEditPage())
        sm.add_widget(self.makeLogsPage())
        sm.add_widget(self.makePostMetaDataPage())

        self.theme_cls.primary_palette = "Green"

        self.backStack = []

        #Call this to save whatever unsaved data. Also acts as a flag.
        self.unsavedDataCallback = None

        self.screenManager = sm

        Clock.schedule_interval(self.flushUnsaved, 60*5)

        return sm

    #Here is our autosave
    def on_pause(self):
        self.flushUnsaved()
        return True

    def on_stop(self):
        self.flushUnsaved()

    def on_destroy(self):
        self.flushUnsaved()

    def flushUnsaved(self,*a):
        if self.unsavedDataCallback:
            self.unsavedDataCallback()
            self.unsavedDataCallback=None


    def makeMainScreen(self):
        mainScreen = Screen(name='Main')

        layout = BoxLayout(orientation='vertical', spacing=10,size_hint=(1,1))
        mainScreen.add_widget(layout)
        label = MDToolbar(title="HardlineP2P")
        layout.add_widget(label)

        btn1 = Button(text='My Streams',
                      size_hint=(1, None), font_size="14sp")
        label2 = Label(size_hint=(1, None), halign="center",
                       text='Notetaking, microblogging, and more!')
        layout.add_widget(btn1)
        layout.add_widget(label2)

        btn1.bind(on_press=self.goToStreams)

        btn1 = Button(text='Discover Services',
                      size_hint=(1, None), font_size="14sp")
        label2 = Label(size_hint=(1, None), halign="center",
                       text='Find Hardline sites on your local network')

        btn1.bind(on_press=self.goToDiscovery)
        layout.add_widget(btn1)
        layout.add_widget(label2)

        btn5 = Button(text='Settings+Tools',
                      size_hint=(1, None), font_size="14sp")

        btn5.bind(on_press=self.goToSettings)

        layout.add_widget(btn5)

        return mainScreen



    def makeBackButton(self):
        btn1 = Button(text='Back',
                size_hint=(1, None), font_size="14sp")

        def back(*a):
            def f(d):
                if d:
                    self.unsavedDataCallback=False
                    #Get rid of the first one representing the current page
                    if self.backStack:
                        self.backStack.pop()

                    #Go to the previous page, if that page left an instruction for how to get back to it
                    if self.backStack:
                        self.backStack.pop()()
                    else:
                        self.screenManager.current = "Main"

            #If they have an unsaved post, ask them if they really want to leave.
            if self.unsavedDataCallback:
                self.askQuestion("Discard unsaved data?",'yes',cb=f)
            else:
                f(True)
            
        btn1.bind(on_press=back)
        return btn1

    



    def makeDataTablePage(self):
        screen = Screen(name='TableView')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        layout.add_widget(MDToolbar(title="My Streams"))
        def goMain(*a):
            self.screenManager.current = "Main"

        layout.add_widget(self.makeBackButton())

        btn2 = Button(text='Create a Stream',
                      size_hint=(1, None), font_size="14sp")

        btn2.bind(on_press=self.promptAddStream)
        layout.add_widget(btn2)

        self.streamsListBoxScroll = ScrollView(size_hint=(1, 1))

        self.streamsListBox = BoxLayout(
            orientation='vertical', size_hint=(1, None), spacing=10)
        self.streamsListBox.bind(
            minimum_height=self.streamsListBox.setter('height'))

        self.streamsListBoxScroll.add_widget(self.streamsListBox)

        layout.add_widget(self.streamsListBoxScroll)

        return screen


    def getPermission(self,type='all'):
        """
        Since API 23, Android requires permission to be requested at runtime.
        This function requests permission and handles the response via a
        callback.
        The request will produce a popup if permissions have not already been
        been granted, otherwise it will do nothing.
        """
        if platform=="android":
            from android.permissions import request_permissions, Permission

            if type=='all':
                plist = [Permission.ACCESS_COARSE_LOCATION,
                                Permission.ACCESS_FINE_LOCATION, Permission.MANAGE_EXTERNAL_STORAGE]
            if type=='location':
                plist =[Permission.ACCESS_COARSE_LOCATION,
                                Permission.ACCESS_FINE_LOCATION]
            if type=='files':
                plist=[Permission.MANAGE_EXTERNAL_STORAGE]


            def callback(permissions, results):
                """
                Defines the callback to be fired when runtime permission
                has been granted or denied. This is not strictly required,
                but added for the sake of completeness.
                """
                if all([res for res in results]):
                    print("callback. All permissions granted.")
                else:
                    print("callback. Some permissions refused.")

            request_permissions(plist, callback)






                    









   


ServiceApp().run()
