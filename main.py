from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
import threading

kv = '''
Button:
    text: 'Yippy kai ay!  Hardline should be running.'
'''

class ServiceApp(App):
    def build(self):
        if platform == 'android':
            service = autoclass('com.eternityforest.hardlinep2p.ServiceHardlineService')
            mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
            argument = ''
            service.start(mActivity, argument)

        else:
            def f():
                import hardline_android_service
            t = threading.Thread(target=f,daemon=True)
            t.start()

        return Builder.load_string(kv)

if __name__ == '__main__':
    ServiceApp().run()