

from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDFlatButton

from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel as Label
from kivymd.uix.button import MDFillRoundFlatButton as Button
from kivymd.uix.dialog import MDDialog
from kivy.uix.checkbox import CheckBox

from kivy.utils import platform

class AppHelpers():
    def showText(self, text,title="QR"):
        from kivy_garden.qrcode import QRCodeWidget
       
        t= MDTextField(text=text, multiline=True,size_hint=(1,None),mode="rectangle")
        
        def cbr_yes(*a):
            print("Accept Button")
            self.dialog.dismiss()

        self.dialog = MDDialog(
            type="custom",
            title=title,
            content_cls=t,
            buttons=[
                Button(
                    text="Close", text_color=self.theme_cls.primary_color, on_press=cbr_yes
                )
            ],
        )
        self.dialog.set_normal_height()
        self.dialog.open()

    def showQR(self, text,title="QR"):
        from kivy_garden.qrcode import QRCodeWidget
        t =QRCodeWidget(data=text, size_hint=(1,None))
        
        def cbr_yes(*a):
            print("Accept Button")
            self.dialog.dismiss()

    
        def cbr_txt(*a):
            print("Accept Button")
            self.dialog.dismiss()
            self.showText(text,title)

        self.dialog = MDDialog(
            type="custom",
            title=title,
            content_cls=t,
            buttons=[
                Button(
                    text="Close", text_color=self.theme_cls.primary_color, on_press=cbr_yes
                ),
                Button(
                    text="Show Text", text_color=self.theme_cls.primary_color, on_press=cbr_txt
                )
            ],
        )
        self.dialog.set_normal_height()
        self.dialog.open()

    def askQuestion(self, question, answer='', cb=None,multiline=False):
        "As a text box based question, with optional  default answer.  If user confirm, call cb."

        t = MDTextField(text='', size_hint=(1,None),multiline=multiline,mode="rectangle")

        def cbr_yes(*a):
            print("Accept Button")
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
        self.dialog.set_normal_height()

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
        self.dialog.set_normal_height()
        t.active = answer
        self.dialog.open()


    def settingButton(self, configObj, section, key,default=''):
        "Return a button representing a setting in a configparser obj which you can press to edit."

        try:
            configObj.add_section(section)
        except:
            pass

        configObj[section][key]= configObj[section].get(key,default) or default

        x = MDFlatButton(text=key+":"+configObj[section].get(key, "")[:25])

        def f(*a):
            def g(r):
                if not r is None:
                    configObj[section][key] = r
                    x.text = key+":"+configObj[section].get(key, "")[:25]
            self.askQuestion(
                section+":"+key, configObj[section].get(key, ""), g)

        x.bind(on_press=f)

        return x

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