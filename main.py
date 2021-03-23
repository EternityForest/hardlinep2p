# This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

import configparser
import hardline
import service
from typing import Text
from kivymd.app import MDApp
from kivy.utils import platform
from kivymd.uix.button import MDFillRoundFlatButton as Button
from kivymd.uix.button import MDFlatButton

from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel as Label
from kivy.uix.scrollview import ScrollView


from kivymd.uix.boxlayout import MDBoxLayout as BoxLayout
import threading
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

# Terrible Hacc, because otherwise we cannot iumport hardline on android.
import os
import sys

from hardline import makeUserDatabase, uihelpers, drayerdb


class ServiceApp(MDApp, uihelpers.AppHelpers):

    def stop_service(self, foo=None):
        if self.service:
            self.service.stop()
            self.service = None
        else:
            import hardline
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
                import hardline
                # Ensure stopped
                hardline.stop()

                loadedServices = hardline.loadUserServices(
                    None)
                db = hardline.loadUserDatabases(
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

        self.theme_cls.primary_palette = "Green"

        self.screenManager = sm
        return sm

    def makeMainScreen(self):
        mainScreen = Screen(name='Main')

        layout = BoxLayout(orientation='vertical', spacing=10)
        mainScreen.add_widget(layout)
        label = Label(size_hint=(1, 6), halign="center",
                      text='HardlineP2P: The open source way to find\n and connect to servers\nwith no fees or registration')
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

    def goToSettings(self, *a):
        self.screenManager.current = "Settings"

    def goToGlobalSettings(self, *a):
        globalConfig = configparser.ConfigParser()
        globalConfig.read(hardline.globalSettingsPath)
        self.localSettingsBox.clear_widgets()

        self.localSettingsBox.add_widget(Label(size_hint=(1, 6), halign="center",
                                               text='OpenDHT Proxies'))
        self.localSettingsBox.add_widget(Label(size_hint=(1, None),
                                               text='Proxies are tried in order from 1-3'))

        self.localSettingsBox.add_widget(
            self.settingButton(globalConfig, "DHTProxy", 'server1'))
        self.localSettingsBox.add_widget(
            self.settingButton(globalConfig, "DHTProxy", 'server2'))
        self.localSettingsBox.add_widget(
            self.settingButton(globalConfig, "DHTProxy", 'server3'))

        btn1 = Button(text='Save',
                      size_hint=(1, None), font_size="14sp")

        def save(*a):
            with open(hardline.globalSettingsPath, 'w') as f:
                globalConfig.write(f)

            self.screenManager.current = "Main"

        btn1.bind(on_press=save)
        self.localSettingsBox.add_widget(btn1)
        self.screenManager.current = "GlobalSettings"

    def makeGlobalSettingsPage(self):

        screen = Screen(name='GlobalSettings')
        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="14sp")

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        self.localSettingsScroll = ScrollView(size_hint=(1, 1))
        self.localSettingsBox = BoxLayout(
            orientation='vertical', size_hint=(1, None), spacing=10)
        self.localSettingsBox.bind(
            minimum_height=self.localSettingsBox.setter('height'))

        self.localSettingsScroll.add_widget(self.localSettingsBox)

        layout.add_widget(self.localSettingsScroll)

        return screen

    def makeSettingsPage(self):
        page = Screen(name='Settings')

        layout = BoxLayout(orientation='vertical', spacing=10)
        page.add_widget(layout)
        label = Label(size_hint=(1, 6), halign="center",
                      text='HardlineP2P Settings')
        layout.add_widget(label)

        btn = Button(text='Back to main page',
                     size_hint=(1, None), font_size="14sp")

        def goMain(*a):
            self.screenManager.current = "Main"
        btn.bind(on_press=goMain)
        layout.add_widget(btn)

        btn1 = Button(text='Local Services',
                      size_hint=(1, None), font_size="14sp")
        label1 = Label(size_hint=(1, None), halign="center",
                       text='Share a local webservice with the world')

        btn1.bind(on_press=self.goToLocalServices)
        layout.add_widget(btn1)
        layout.add_widget(label1)

        btn = Button(text='Global Settings',
                     size_hint=(1, None), font_size="14sp")

        btn.bind(on_press=self.goToGlobalSettings)
        layout.add_widget(btn)

        # Start/Stop
        btn3 = Button(text='Stop', size_hint=(1, None), font_size="14sp")
        btn3.bind(on_press=self.stop_service)
        label3 = Label(size_hint=(1, None), halign="center",
                       text='Stop the background process.  It must be running to acess hardline sites.  Starting may take a few seconds.')
        layout.add_widget(btn3)
        layout.add_widget(label3)

        btn4 = Button(text='Start or Restart.',
                      size_hint=(1, None), font_size="14sp")
        btn4.bind(on_press=self.start_service)
        label4 = Label(size_hint=(1, None), halign="center",
                       text='Restart the process. It will show in your notifications.')
        layout.add_widget(btn4)
        layout.add_widget(label4)

        return page

    def makeStreamsPage(self):
        screen = Screen(name='Streams')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="14sp")

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

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

        try:
            import hardline
            s = hardline.userDatabases
            time.sleep(0.5)
            for i in s:
                self.streamsListBox.add_widget(
                    self.makeButtonForStream(i))

        except Exception:
            print(traceback.format_exc())

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
                hardline.makeUserDatabase(None, v)
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
            orientation='vertical', size_hint=(1, None))
        self.streamEditPanel.bind(
            minimum_height=self.streamEditPanel.setter('height'))

        self.streamEditPanelScroll.add_widget(self.streamEditPanel)

        layout.add_widget(self.streamEditPanelScroll)

        return screen



    def gotoStreamPosts(self, stream):
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text=stream))



        def back(*a):
            self.editStream(stream)
        btn1 = Button(text='Back',
                size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=back)
        self.streamEditPanel.add_widget(btn1)


        newp = MDTextField(text='')

        def post(*a):
            if newp.text:
                with hardline.userDatabases[stream]:
                    hardline.userDatabases[stream].setDocument({'body': newp.text,'type':'post'})
                self.gotoStreamPosts(stream)

        btn1 = Button(text='Post!',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=post)

        self.streamEditPanel.add_widget(newp)
        self.streamEditPanel.add_widget(btn1)

        s = hardline.userDatabases[stream]
        p = s.getDocumentsByType("post")
        for i in p:
            self.streamEditPanel.add_widget(Label(text=i.get('body',"?????"), size_hint=(1,None)))
        self.screenManager.current = "EditStream"



    #Reuse the same panel for editStream, the main hub for accessing the stream,
    #and it's core settings
    def editStream(self, name):
        db = hardline.userDatabases[name]
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

        btn1 = Button(text='Back',
                      size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=self.goToStreams)
        self.streamEditPanel.add_widget(btn1)


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


        self.screenManager.current = "EditStream"

    def editStreamSettings(self, name):
        db = hardline.userDatabases[name]
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

        def back(*a):
            self.editStream(name)
        btn1 = Button(text='Back',
                size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=back)
        self.streamEditPanel.add_widget(btn1)

      

        def save(*a):
            print("SAVE BUTTON WAS PRESSED")
            # On android this is the bg service's job
            db.saveConfig()

            if platform == 'android':
                self.stop_service()
                self.start_service()

        def delete(*a):
            def f(n):
                if n and n == name:
                    hardline.delDatabase(None, n)
                    if platform == 'android':
                        self.stop_service()
                        self.start_service()
                    self.goToStreams()

            self.askQuestion("Really delete?", name, f)

        self.streamEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="24sp",
                                              text='Service'))

        self.streamEditPanel.add_widget(
            self.settingButton(c, "Sync", "syncKey"))

        self.streamEditPanel.add_widget(
            self.settingButton(c, "Sync", "writePassword"))

        self.streamEditPanel.add_widget(
            self.settingButton(c, "Sync", "server"))

        btn1 = Button(text='Save Changes',
                      size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=save)
        self.streamEditPanel.add_widget(btn1)

        btn2 = Button(text='Delete this stream',
                      size_hint=(1, None), font_size="14sp")

        btn2.bind(on_press=delete)
        self.streamEditPanel.add_widget(btn2)

        self.screenManager.current = "EditStream"



    def makeLocalServicesPage(self):

        screen = Screen(name='LocalServices')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="14sp")

        label = Label(size_hint=(1, None), halign="center",
                      text='WARNING: Running a local service may use a lot of data and battery.\nChanges may require service restart.')

        labelw = Label(size_hint=(1, None), halign="center",
                       text='WARNING 2: This app currently prefers the external SD card for almost everything including the keys.')

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        layout.add_widget(label)
        layout.add_widget(labelw)

        btn2 = Button(text='Create a service',
                      size_hint=(1, None), font_size="14sp")

        btn2.bind(on_press=self.promptAddService)
        layout.add_widget(btn2)

        self.localServicesListBoxScroll = ScrollView(size_hint=(1, 1))

        self.localServicesListBox = BoxLayout(
            orientation='vertical', size_hint=(1, None), spacing=10)
        self.localServicesListBox.bind(
            minimum_height=self.localServicesListBox.setter('height'))

        self.localServicesListBoxScroll.add_widget(self.localServicesListBox)

        layout.add_widget(self.localServicesListBoxScroll)

        return screen

    def promptAddService(self, *a, **k):

        def f(v):
            if v:
                self.editLocalService(v)
        self.askQuestion("New Service filename?", cb=f)

    def goToLocalServices(self, *a):
        "Go to a page wherein we can list user-modifiable services."
        self.localServicesListBox.clear_widgets()

        try:
            import hardline
            s = hardline.listServices(None)
            time.sleep(0.5)
            for i in s:
                self.localServicesListBox.add_widget(
                    self.makeButtonForLocalService(i, s[i]))

        except Exception:
            print(traceback.format_exc())

        self.screenManager.current = "LocalServices"

    def makeLocalServiceEditPage(self):

        screen = Screen(name='EditLocalService')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)
        self.localServiceEditorName = Label(size_hint=(
            1, None), halign="center", text="??????????")
        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="14sp")

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        self.localServiceEditPanelScroll = ScrollView(size_hint=(1, 1))

        self.localServiceEditPanel = BoxLayout(
            orientation='vertical', size_hint=(1, None))
        self.localServiceEditPanel.bind(
            minimum_height=self.localServiceEditPanel.setter('height'))

        self.localServiceEditPanelScroll.add_widget(self.localServiceEditPanel)

        layout.add_widget(self.localServiceEditPanelScroll)

        return screen

    def editLocalService(self, name, c=None):
        if not c:
            c = configparser.ConfigParser()

        try:
            c.add_section("Service")
        except:
            pass
        try:
            c.add_section("Info")
        except:
            pass

        self.localServiceEditPanel.clear_widgets()

        self.localServiceEditorName.text = name

        def save(*a):
            print("SAVE BUTTON WAS PRESSED")
            # On android this is the bg service's job
            hardline.makeUserService(None, name, c['Info'].get("title", 'Untitled'), service=c['Service'].get("service", ""),
                                     port=c['Service'].get("port", ""), cacheInfo=c['Cache'], noStart=(platform == 'android'))
            if platform == 'android':
                self.stop_service()
                self.start_service()

            self.goToLocalServices()

        def delete(*a):
            def f(n):
                if n and n == name:
                    hardline.delUserService(None, n)
                    if platform == 'android':
                        self.stop_service()
                        self.start_service()
                    self.goToLocalServices()

            self.askQuestion("Really delete?", name, f)

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="24sp",
                                                    text='Service'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Service", "service"))
        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Service", "port"))
        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Info", "title"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="24sp",
                                                    text='Cache'))
        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), font_size="14sp",
                                                    text='Cache mode only works for static content'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "directory"))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "maxAge"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), font_size="14sp",
                                                    text='Try to refresh after maxAge seconds(default 1 week)'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "maxSize", '256'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None),  font_size="14sp",
                                                    text='Max size to use for the cache in MB'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "downloadRateLimit", '1200'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None),  font_size="14sp",
                                                    text='Max MB per hour to download'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "dynamicContent", 'no'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None),  font_size="14sp",
                                                    text='Allow executing code in protected @mako files in the cache dir. yes to enable. Do not use with untrusted @mako'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "allowListing", 'no'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None),  font_size="14sp",
                                                    text='Allow directory listing of cached content'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None),  font_size="14sp",
                                                    text='Directory names are subfolders within the HardlineP2P cache folder,\nand can also be used to share\nstatic files by leaving the service blank.'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center", font_size="24sp",
                                                    text='Access Settings'))
        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None),  font_size="14sp",
                                                    text='Cache mode only works for static content'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Access", "useDHT", 'yes'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), font_size="14sp",
                                                    text='DHT Discovery uses a proxy server on Android. \nDisabling this saves bandwidth but makes access from outside your network\nunreliable.'))

        btn1 = Button(text='Save Changes',
                      size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=save)
        self.localServiceEditPanel.add_widget(btn1)

        btn2 = Button(text='Delete this service',
                      size_hint=(1, None), font_size="14sp")

        btn2.bind(on_press=delete)
        self.localServiceEditPanel.add_widget(btn2)

        self.screenManager.current = "EditLocalService"

    def makeButtonForLocalService(self, name, c=None):
        "Make a button that, when pressed, edits the local service in the title"

        btn = Button(text=name,
                     font_size="14", size_hint=(1, None))

        def f(*a):
            self.editLocalService(name, c)
        btn.bind(on_press=f)

        return btn

    def makeDiscoveryPage(self):

        # Discovery Page

        screen = Screen(name='Discovery')
        self.discoveryScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="16sp")
        label = Label(size_hint=(1, None), halign="center",
                      text='Browsing your local network.\nWarning: anyone on your network\ncan advertise a site with any title they want.')

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        layout.add_widget(label)

        self.discoveryScroll = ScrollView(size_hint=(1, 1))

        self.discoveryListbox = BoxLayout(
            orientation='vertical', size_hint=(1, None))
        self.discoveryListbox.bind(
            minimum_height=self.discoveryListbox.setter('height'))

        self.discoveryScroll.add_widget(self.discoveryListbox)
        layout.add_widget(self.discoveryScroll)

        return screen

    def goToDiscovery(self, *a):
        "Go to the local network discovery page"
        self.discoveryListbox.clear_widgets()

        try:
            import hardline
            hardline.discoveryPeer.search('', n=5)
            time.sleep(0.5)
            for i in hardline.getAllDiscoveries():
                for j in self.makeButtonForPeer(i):
                    self.discoveryListbox.add_widget(j)

        except Exception:
            print(traceback.format_exc())

        self.screenManager.current = "Discovery"

    def makeButtonForPeer(self, info):
        "Make a button that, when pressed, opens a link to the service denoted by the hash"

        btn = Button(text=str(info['title']),
                     font_size="26sp", size_hint=(1, None))

        def f(*a):
            self.openInBrowser("http://"+info['hash']+".localhost:7009")
        btn.bind(on_press=f)

        return(btn, Label(text="Hosted By: "+info.get("from_ip", ""), font_size="14sp", size_hint=(1, None)),

               Label(text="ID: "+info['hash'], font_size="14sp", size_hint=(1, None)))


if __name__ == '__main__':
    ServiceApp().run()
