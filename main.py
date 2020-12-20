#This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
import threading


class ServiceApp(App):

    #Buttons only work on the android
    def stop_service(self,foo=None):
        if self.service:
            self.service.stop()
            self.service = None

    def start_service(self,foo=None):
        if self.service:
            self.service.stop()
            self.service = None

        if platform == 'android':
                from android import AndroidService
                service = AndroidService('HardlineP2P Service', 'running')
                service.start('service started')
                self.service = service


    def build(self):
        self.service=None



        if platform == 'android':
            from android import AndroidService
            service = AndroidService('HardlineP2P Service', 'running')
            service.start('service started')
            self.service = service

        else:
            def f():
                from service import main
            t = threading.Thread(target=f,daemon=True)
            t.start()

        layout = BoxLayout(orientation='vertical')
        btn1 = Button(text='HardlineP2P shuld be running')
        btn2 = Button(text='Enjoy! (Start/stop only works on android)')

        btn3 = Button(text='Pls Stahp!')

        btn3.bind(on_press=self.stop_service)

        btn4 = Button(text='Pls (re?)Start!')
        btn4.bind(on_press=self.start_service)

        layout.add_widget(btn1)
        layout.add_widget(btn2)
        layout.add_widget(btn3)
        layout.add_widget(btn4)

        return layout

if __name__ == '__main__':
    ServiceApp().run()
