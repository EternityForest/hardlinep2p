import configparser
from hardline import daemonconfig
from .. import daemonconfig, hardline


import configparser,logging

from kivy.uix.image import Image
from kivy.uix.widget import Widget

from typing import Sized, Text
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
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

# Terrible Hacc, because otherwise we cannot iumport hardline on android.
import os
import sys
import re
from .. daemonconfig import makeUserDatabase
from .. import  drayerdb, cidict, libnacl

from kivymd.uix.picker import MDDatePicker


class StreamsMixin():


    #Reuse the same panel for editStream, the main hub for accessing the stream,
    #and it's core settings
    def editStream(self, name):
        db = daemonconfig.userDatabases[name]
        c = db.config
        try:
            c.add_section("Service")
        except:
            pass
        try:
            c.add_section("Info")
        except:
            pass

        self.streamEditPanel.clear_widgets()

        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text=name))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.editStream( name)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]



        btn2 = Button(text='View Feed',
                size_hint=(1, None), font_size="14sp")
        def goPosts(*a):
            self.gotoStreamPosts(name)
        btn2.bind(on_press=goPosts)
        self.streamEditPanel.add_widget(btn2)



        btn2 = Button(text='Stream Settings',
                size_hint=(1, None), font_size="14sp")
        def goSettings(*a):
            self.editStreamSettings(name)
        btn2.bind(on_press=goSettings)
        self.streamEditPanel.add_widget(btn2)


        importData = Button(size_hint=(1,None), text="Import Data File")

        def promptSet(*a):
            from plyer import filechooser
            selection = filechooser.open_file(filters=["*.json"])
            if selection:
                import json
                with open(selection[0]) as f:
                    for i in json.loads(f.read()):
                        with  daemonconfig.userDatabases[name]:
                            daemonconfig.userDatabases[name].setDocument(i[0])
                        daemonconfig.userDatabases[name].commit()


            
        importData.bind(on_release=promptSet)
        self.streamEditPanel.add_widget(importData)


        self.screenManager.current = "EditStream"

    def editStreamSettings(self, name):
        db = daemonconfig.userDatabases[name]
        c = db.config


        self.streamEditPanel.clear_widgets()

        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text=name))

       
        self.streamEditPanel.add_widget(self.makeBackButton())

      

        def save(*a):
            logging.info("SAVE BUTTON WAS PRESSED")
            # On android this is the bg service's job
            db.saveConfig()

            if platform == 'android':
                self.stop_service()
                self.start_service()

        def delete(*a):
            def f(n):
                if n and n == name:
                    daemonconfig.delDatabase(None, n)
                    if platform == 'android':
                        self.stop_service()
                        self.start_service()
                    self.goToStreams()

            self.askQuestion("Really delete?", name, f)

        self.streamEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="24sp",
                                              text='Sync'))

        self.streamEditPanel.add_widget(
            keyBox :=self.settingButton(c, "Sync", "syncKey"))

        self.streamEditPanel.add_widget(
            pBox :=self.settingButton(c, "Sync", "writePassword"))

        self.streamEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="12sp",
                                              text='Keys have a special format, you must use the generator to change them.'))

        def promptNewKeys(*a,**k):
            def makeKeys(a):
                if a=='yes':
                    
                    vk, sk = libnacl.crypto_sign_keypair()
                    vk= base64.b64encode(vk).decode()
                    sk= base64.b64encode(sk).decode()
                    keyBox.text=vk
                    pBox.text=sk
            self.askQuestion("Overwrite with random keys?",'yes',makeKeys)
        
        keyButton = Button(text='Generate New Keys',
                      size_hint=(1, None), font_size="14sp")
        keyButton.bind(on_press=promptNewKeys)
        self.streamEditPanel.add_widget(keyButton)

        self.streamEditPanel.add_widget(
            self.settingButton(c, "Sync", "server"))

        self.streamEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="14sp",
                                              text='Do not include the http:// '))

        self.streamEditPanel.add_widget(
            self.settingButton(c, "Sync", "serve",'yes'))


        self.streamEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="14sp",
                                              text='Set serve=no to forbid clients to sync'))

        self.streamEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="24sp",
                                              text='Application'))

        self.streamEditPanel.add_widget(
            self.settingButton(c, "Application", "notifications",'no'))

        btn1 = Button(text='Save Changes',
                      size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=save)
        self.streamEditPanel.add_widget(btn1)

        btn2 = Button(text='Delete this stream',
                      size_hint=(1, None), font_size="14sp")

        btn2.bind(on_press=delete)
        self.streamEditPanel.add_widget(btn2)

        self.screenManager.current = "EditStream"

    def makeStreamsPage(self):
        screen = Screen(name='Streams')
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

    def goToStreams(self, *a):
        "Go to a page wherein we can list user-modifiable services."
        self.streamsListBox.clear_widgets()

        def goHere():
            self.screenManager.current = "Streams"
        self.backStack.append(goHere)
        self.backStack=self.backStack[-50:]

        try:
            s = daemonconfig.userDatabases
            time.sleep(0.5)
            for i in s:
                self.streamsListBox.add_widget(
                    self.makeButtonForStream(i))

        except Exception:
            logging.info(traceback.format_exc())

        self.screenManager.current = "Streams"

    def makeButtonForStream(self, name):
        "Make a button that, when pressed, edits the stream in the title"

        btn = Button(text=name,
                     font_size="14", size_hint=(1, None))

        def f(*a):
            self.editStream(name)
        btn.bind(on_press=f)
        return btn

    def promptAddStream(self, *a, **k):
        def f(v):
            if v:
                daemonconfig.makeUserDatabase(None, v)
                self.editStream(v)

        self.askQuestion("New Stream Name?", cb=f)



    def makeStreamEditPage(self):
        "Prettu much just an empty page filled in by the specific goto functions"

        screen = Screen(name='EditStream')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)


        self.streamEditPanelScroll = ScrollView(size_hint=(1, 1))

        self.streamEditPanel = BoxLayout(
            orientation='vertical',adaptive_height= True, spacing=5)
        self.streamEditPanel.bind(
            minimum_height=self.streamEditPanel.setter('height'))

        self.streamEditPanelScroll.add_widget(self.streamEditPanel)

        layout.add_widget(self.streamEditPanelScroll)

        return screen

