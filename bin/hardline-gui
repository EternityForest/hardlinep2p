#This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.button import Button
from kivy.uix.label import Label

from kivy.uix.boxlayout import BoxLayout
import threading
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

class ServiceApp(App):

    def stop_service(self,foo=None):
        if self.service:
            self.service.stop()
            self.service = None
        else:
            import hardline
            hardline.stop()

    def start_service(self,foo=None):
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
            t = threading.Thread(target=f,daemon=True)
            t.start()

    def build(self):
        self.service=None

        self.start_service()

        # Create the manager
        sm = ScreenManager()
        sm.add_widget(self.makeMainScreen())
        sm.add_widget(self.makeDiscoveryPage())

        self.screenManager = sm
        return sm

    

    def makeMainScreen(self):
        mainScreen = Screen(name='Main')

    
        layout = BoxLayout(orientation='vertical')
        mainScreen.add_widget(layout)
        label = Label(halign='center',text='HardlineP2P: The open source way to find\n and connect to servers\nwith no fees or registration')
        layout.add_widget(label)


        btn1 = Button(text='Discover services on your network')
       
        btn1.bind(on_press=self.goToDiscovery)


        btn3 = Button(halign='center',text='Stop the service\n(Service must be running to use hardlines)')
        btn3.bind(on_press=self.stop_service)

        btn4 = Button(text='Start or restart.')
        btn4.bind(on_press=self.start_service)

        layout.add_widget(btn1)
        layout.add_widget(btn3)
        layout.add_widget(btn4)

        return mainScreen

    def makeDiscoveryPage(self):

        # Discovery Page

        screen = Screen(name='Discovery')

    
        layout = BoxLayout(orientation='vertical')
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page')
        label = Label( halign='center', text='Browsing your local network.\nWarning: anyone on your network\ncan advertise a site with any title.\nVerify the actual URL before\nentering sensitive data into any site.')

        def goMain(*a):
            self.screenManager.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        layout.add_widget(label)


        self.discoveryListbox =  BoxLayout(orientation='vertical')
        layout.add_widget(self.discoveryListbox)


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
        btn = Button(text=str(info['title'])+"\n"+info['hash'], halign='center')
        def f(*a):
            self.openInBrowser("http://"+info['hash']+".localhost:7009")
        btn.bind(on_press=f)

        return btn

    



    def openInBrowser(self,link):
        "Opens a link in the browser"
        if platform == 'android':
            from jnius import autoclass,cast
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
            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivity(intent)
        else:
            import webbrowser
            webbrowser.open(link)


if __name__ == '__main__':
    ServiceApp().run()
