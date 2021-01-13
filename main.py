# This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivymd.app import MDApp
from kivy.utils import platform
from kivymd.uix.button import MDFillRoundFlatButton as Button
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


for i in os.listdir(os.path.dirname(os.path.abspath(__file__))):
    print(i)
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
                hardline.start(7009)
            t = threading.Thread(target=f, daemon=True)
            t.start()

    def build(self):
        self.service = None

        self.start_service()

        # Create the manager
        sm = ScreenManager()
        sm.add_widget(self.makeMainScreen())
        sm.add_widget(self.makeDiscoveryPage())
        self.theme_cls.primary_palette = "Green"

        self.screenManager = sm
        return sm

    def makeMainScreen(self):
        mainScreen = Screen(name='Main')

        layout = BoxLayout(orientation='vertical', spacing=10)
        mainScreen.add_widget(layout)
        label = Label(size_hint=(1, None), halign="center", valign="center",
                      text='HardlineP2P: The open source way to find\n and connect to servers\nwith no fees or registration')
        layout.add_widget(label)

        btn1 = Button(text='Discover Services',
                      size_hint=(1, None), font_size="26sp")
        label2 = Label(size_hint=(1, None), halign="center",
                       text='Find Hardline sites on your local network')

        btn1.bind(on_press=self.goToDiscovery)
        layout.add_widget(btn1)
        layout.add_widget(label2)

        btn3 = Button(text='Stop', size_hint=(1, None), font_size="26sp")
        btn3.bind(on_press=self.stop_service)
        label3 = Label(size_hint=(1, None), halign="center",
                       text='Stop the background process.  It must be running to acess hardline sites.  Starting may take a few seconds.')
        layout.add_widget(btn3)
        layout.add_widget(label3)

        btn4 = Button(text='Start or Restart.',
                      size_hint=(1, None), font_size="26sp")
        btn4.bind(on_press=self.start_service)
        label4 = Label(size_hint=(1, None), halign="center",
                       text='Restart the process. It will show in your notifications.')

        layout.add_widget(btn4)
        layout.add_widget(label4)

        return mainScreen

    def makeDiscoveryPage(self):

        # Discovery Page

        screen = Screen(name='Discovery')
        self.discoveryScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page',
                      size_hint=(1, None), font_size="26sp")
        label = Label(size_hint=(1, None), halign="center",
                      text='Browsing your local network.\nWarning: anyone on your network\ncan advertise a site with any title.\nVerify the actual URL before\nentering sensitive data into any site.')

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
