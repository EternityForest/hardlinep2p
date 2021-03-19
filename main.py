# This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

import configparser
import hardline
import service
from typing import Text
from kivymd.app import MDApp
from kivy.utils import platform
from kivymd.uix.button import MDFillRoundFlatButton as Button
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel as Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.checkbox import CheckBox


from kivymd.uix.boxlayout import MDBoxLayout as BoxLayout
import threading
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

# Terrible Hacc, because otherwise we cannot iumport hardline on android.
import os
import sys





class ServiceApp(MDApp):

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
                    hardline.user_services_dir)
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

        self.theme_cls.primary_palette = "Green"

        self.screenManager = sm
        return sm

    def askQuestion(self, question, answer='', cb=None):
        "As a text box based question, with optional  default answer.  If user confirm, call cb."

        t = MDTextField(text='')

        def cbr_yes(*a):
            cb(t.text)
            self.dialog.dismiss()

        def cbr_no(*a):
            cb(None)
            self.dialog.dismiss()

        self.dialog = MDDialog(
            type="custom",
            title=question,
            content_cls=t,
            buttons=[
                Button(
                    text="Accept", text_color=self.theme_cls.primary_color, on_press=cbr_yes
                ),
                Button(
                    text="Cancel", text_color=self.theme_cls.primary_color, on_press=cbr_no
                ),
            ],
        )
        t.text = answer
        self.dialog.open()

    def checkboxPrompt(self, question, answer=False, cb=None):
        "As a text box based question, with optional  default answer.  If user confirm, call cb."

        t = CheckBox(active=True)

        def cbr_yes(*a):
            cb(t.active)
            self.dialog.dismiss()

        def cbr_no(*a):
            cb(None)
            self.dialog.dismiss()

        self.dialog = MDDialog(
            type="custom",
            title=question,
            content_cls=t,
            buttons=[
                Button(
                    text="Accept", text_color=self.theme_cls.primary_color, on_press=cbr_yes
                ),
                Button(
                    text="Cancel", text_color=self.theme_cls.primary_color, on_press=cbr_no
                ),
            ],
        )
        t.active = answer
        self.dialog.open()


    def settingButton(self, configObj, section, key):
        "Return a button representing a setting in a configparser obj which you can press to edit."

        try:
            configObj.add_section(section)
        except:
            pass

        x = MDFlatButton(text=key+":"+configObj[section].get(key, "")[:25])

        def f(*a):
            def g(r):
                if r:
                    configObj[section][key] = r
                    x.text = key+":"+configObj[section].get(key, "")[:25]
            self.askQuestion(
                section+":"+key, configObj[section].get(key, ""), g)

        x.bind(on_press=f)

        return x

    def makeMainScreen(self):
        mainScreen = Screen(name='Main')

        layout = BoxLayout(orientation='vertical', spacing=10)
        mainScreen.add_widget(layout)
        label = Label(size_hint=(1, 6), halign="center", valign="top",
                      text='HardlineP2P: The open source way to find\n and connect to servers\nwith no fees or registration')
        layout.add_widget(label)

        btn1 = Button(text='Discover Services',
                      size_hint=(1, None), font_size="20sp")
        label2 = Label(size_hint=(1, None), halign="center",
                       text='Find Hardline sites on your local network')

        btn1.bind(on_press=self.goToDiscovery)
        layout.add_widget(btn1)
        layout.add_widget(label2)

        btn5 = Button(text='Settings+Tools',
                      size_hint=(1, None), font_size="20sp")

        btn5.bind(on_press=self.goToSettings)

        layout.add_widget(btn5)

        return mainScreen

    def goToSettings(self, *a):
        self.screenManager.current = "Settings"

    def makeSettingsPage(self):
        page = Screen(name='Settings')

        layout = BoxLayout(orientation='vertical', spacing=10)
        page.add_widget(layout)
        label = Label(size_hint=(1, 6), halign="center", valign="top",
                      text='HardlineP2P Settings')
        layout.add_widget(label)

        btn = Button(text='Back to main page',
                      size_hint=(1, None), font_size="20sp")
    
        def goMain(*a):
            self.screenManager.current = "Main"
        btn.bind(on_press=goMain)
        layout.add_widget(btn)


        btn1 = Button(text='Local Services',
                      size_hint=(1, None), font_size="20sp")
        label1 = Label(size_hint=(1, None), halign="center",
                       text='Share a local webservice with the world')

        btn1.bind(on_press=self.goToLocalServices)
        layout.add_widget(btn1)
        layout.add_widget(label1)

        # Start/Stop
        btn3 = Button(text='Stop', size_hint=(1, None), font_size="22sp")
        btn3.bind(on_press=self.stop_service)
        label3 = Label(size_hint=(1, None), halign="center",
                       text='Stop the background process.  It must be running to acess hardline sites.  Starting may take a few seconds.')
        layout.add_widget(btn3)
        layout.add_widget(label3)

        btn4 = Button(text='Start or Restart.',
                      size_hint=(1, None), font_size="20sp")
        btn4.bind(on_press=self.start_service)
        label4 = Label(size_hint=(1, None), halign="center",
                       text='Restart the process. It will show in your notifications.')
        layout.add_widget(btn4)
        layout.add_widget(label4)

        return page

    def makeLocalServicesPage(self):

        screen = Screen(name='LocalServices')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="20sp")

        label = Label(size_hint=(1, None), halign="center",
                      text='WARNING: Running a local service may use a lot of data and battery.\nChanges may require service restart.')

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        layout.add_widget(label)

        btn2 = Button(text='Create a service',
                      size_hint=(1, None), font_size="20sp")

        btn2.bind(on_press=self.promptAddService)
        layout.add_widget(btn2)

        self.localServicesListBoxScroll = ScrollView(size_hint=(1, 1))

        self.localServicesListBox = BoxLayout(
            orientation='vertical', size_hint=(1, None))
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
            s = hardline.listServices(hardline.user_services_dir)
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
                      size_hint=(1, None), font_size="20sp")

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
            hardline.makeUserService(hardline.user_services_dir, name, c['Info'].get("title", 'Untitled'), service=c['Service'].get("service", ""),
                                 port=c['Service'].get("port", ""), cacheInfo=c['Cache'])
            self.goToLocalServices()

        def delete(*a):
            def f(n):
                if n and n == name:
                    hardline.delUserService(hardline.user_services_dir, n)
                    self.goToLocalServices()

            self.askQuestion("Really delete?", name, f)

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Service", "service"))
        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Service", "port"))
        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Info", "title"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Cache Settings(Cache mode only works for static content)'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "directory"))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "maxAge"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Try to refresh after maxAge seconds(default 1 week)'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "maxSize"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Max size to use for the cache(default 256MB)'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "downloadRateLimit"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Max MB per hour to download(Default: 1200)'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "dynamicContent"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Allow executing code in protected @mako files in the cache dir. yes to enable. Do not use with untrusted @mako'))

        self.localServiceEditPanel.add_widget(
            self.settingButton(c, "Cache", "allowListing"))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Allow directory listing'))

        self.localServiceEditPanel.add_widget(Label(size_hint=(1, None), halign="center",
                       text='Directory names are subfolders within the HardlineP2P cache folder,\nand can also be used to share\nstatic files by leaving the service blank.'))    

        btn1 = Button(text='Save Changes',
                      size_hint=(1, None), font_size="20sp")

        btn1.bind(on_press=save)
        self.localServiceEditPanel.add_widget(btn1)

        btn2 = Button(text='Delete this service',
                      size_hint=(1, None), font_size="20sp")

        btn2.bind(on_press=delete)
        self.localServiceEditPanel.add_widget(btn2)

        self.screenManager.current = "EditLocalService"

    def makeButtonForLocalService(self, name, c=None):
        "Make a button that, when pressed, edits the local service in the title"
        layout = BoxLayout(orientation='vertical')

        btn = Button(text=name,
                     font_size="26sp", size_hint=(1, None))

        def f(*a):
            self.editLocalService(name, c)
        btn.bind(on_press=f)
        layout.add_widget(btn)

        return layout

    def makeDiscoveryPage(self):

        # Discovery Page

        screen = Screen(name='Discovery')
        self.discoveryScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="20sp")
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
            hardline.discoveryPeer.search('')
            time.sleep(0.5)
            for i in hardline.getAllDiscoveries():
                self.discoveryListbox.add_widget(self.makeButtonForPeer(i))

        except Exception:
            print(traceback.format_exc())

        self.screenManager.current = "Discovery"

    def makeButtonForPeer(self, info):
        "Make a button that, when pressed, opens a link to the service denoted by the hash"
        layout = BoxLayout(orientation='vertical')

        btn = Button(text=str(info['title']),
                     font_size="26sp", size_hint=(1, None))

        def f(*a):
            self.openInBrowser("http://"+info['hash']+".localhost:7009")
        btn.bind(on_press=f)

        layout.add_widget(btn)
        layout.add_widget(
            Label(text="Hosted By: "+info.get("from_ip", ""), font_size="14sp"))

        layout.add_widget(Label(text="ID: "+info['hash'], font_size="14sp"))

        return layout

    def openInBrowser(self, link):
        "Opens a link in the browser"
        if platform == 'android':
            from jnius import autoclass, cast
            # import the needed Java class
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')

            # create the intent
            intent = Intent()
            intent.setAction(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(link))

            # PythonActivity.mActivity is the instance of the current Activity
            # BUT, startActivity is a method from the Activity class, not from our
            # PythonActivity.
            # We need to cast our class into an activity and use it
            currentActivity = cast(
                'android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivity(intent)
        else:
            import webbrowser
            webbrowser.open(link)


if __name__ == '__main__':
    ServiceApp().run()
