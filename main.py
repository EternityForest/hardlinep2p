#This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
import threading
from kivy.uix.screenmanager import ScreenManager, Screen

import time

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

        #Main Page
        mainScreen = Screen(name='Main')
        sm.add_widget(mainScreen)

    
        layout = BoxLayout(orientation='vertical')
        mainScreen.add_widget(layout)

        btn1 = Button(text='Discover')
        def goToDiscovery(*a):
            #We are going to refresh the list of discovered remote peers
            self.discoveryListbox.clear_widgets()
            import hardline
            hardline.discoveryPeer.search('')
            time.sleep(0.5)

            for i in hardline.getAllDiscoveries():
                btn = Button(text=str(i['title']))
                self.discoveryListbox.add_widget(btn)

            sm.current = "Discovery"
        btn1.bind(on_press=goToDiscovery)


        btn3 = Button(text='Pls Stahp!')
        btn3.bind(on_press=self.stop_service)

        btn4 = Button(text='Pls (re?)Start!')
        btn4.bind(on_press=self.start_service)

        layout.add_widget(btn1)
        layout.add_widget(btn3)
        layout.add_widget(btn4)




        # Discovery Page

        screen = Screen(name='Discovery')
        sm.add_widget(screen)

    
        layout = BoxLayout(orientation='vertical')
        screen.add_widget(layout)

        btn1 = Button(text='Back to main page')
        def goMain(*a):
            sm.current = "Main"
        btn1.bind(on_press=goMain)
        layout.add_widget(btn1)

        self.discoveryListbox =  BoxLayout(orientation='vertical')
        layout.add_widget(self.discoveryListbox)


        return sm

if __name__ == '__main__':
    ServiceApp().run()
