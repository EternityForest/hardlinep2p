# This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivy.logger import Logger
import logging
logging.Logger.manager.root = Logger

import configparser

from kivy.uix.widget import Widget
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

from hardline import makeUserDatabase, uihelpers, drayerdb, cidict
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
    hardline.loadUserDatabases(None,forceProxy='127.0.0.1:7004')

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

                hardline.loadDrayerServerConfig()


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
        sm.add_widget(self.makeLogsPage())

        self.theme_cls.primary_palette = "Green"

        self.backStack = []

        self.screenManager = sm
        return sm

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

    def goToSettings(self, *a):
        self.screenManager.current = "Settings"

    def goToGlobalSettings(self, *a):
        globalConfig = configparser.ConfigParser(dict_type=CaseInsensitiveDict)
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

        self.localSettingsBox.add_widget(Label(size_hint=(1, 6), halign="center",
                                               text='Stream Server'))
        self.localSettingsBox.add_widget(Label(size_hint=(1, None),
                                              text='To allow others to sync to this node as a DrayerDB Stream server, set a server title to expose a service'))
        
        self.localSettingsBox.add_widget(
            self.settingButton(globalConfig, "DrayerDB", 'serverName'))

        btn1 = Button(text='Save',
                      size_hint=(1, None), font_size="14sp")

        def save(*a):
            with open(hardline.globalSettingsPath, 'w') as f:
                globalConfig.write(f)
            if platform == 'android':
                self.stop_service()
                self.start_service()
            else:
                hardline.loadDrayerServerConfig()

            self.screenManager.current = "Main"

        btn1.bind(on_press=save)
        self.localSettingsBox.add_widget(btn1)
        self.screenManager.current = "GlobalSettings"

    def makeBackButton(self):
        btn1 = Button(text='Back',
                size_hint=(1, None), font_size="14sp")

        def back(*a):
            #Get rid of the first one representing the current page
            if self.backStack:
                self.backStack.pop()

            #Go to the previous page, if that page left an instruction for how to get back to it
            if self.backStack:
                self.backStack.pop()()
            else:
                self.screenManager.current = "Main"
            
        btn1.bind(on_press=back)
        return btn1

    def makeGlobalSettingsPage(self):

        screen = Screen(name='GlobalSettings')
        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

  
        layout.add_widget(self.makeBackButton())

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

        layout = BoxLayout(orientation='vertical')
        page.add_widget(layout)
        label = MDToolbar(title="Settings and Tools")
        layout.add_widget(label)

        layout.add_widget(self.makeBackButton())



        log = Button(text='System Logs',
                      size_hint=(1, None), font_size="14sp")

        btn1 = Button(text='Local Services',
                      size_hint=(1, None), font_size="14sp")
        label1 = Label(size_hint=(1, None), halign="center",
                       text='Share a local webservice with the world')

        log.bind(on_release=self.gotoLogs)
        btn1.bind(on_press=self.goToLocalServices)
        layout.add_widget(log)

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

        layout.add_widget(Widget())

        return page

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
            import hardline
            s = hardline.userDatabases
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
                hardline.makeUserDatabase(None, v)
                self.editStream(v)

        self.askQuestion("New Stream Name?", cb=f)




    def makeLogsPage(self):
        screen = Screen(name='Logs')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)


        layout.add_widget(MDToolbar(title="System Logs"))

        layout.add_widget(self.makeBackButton())


        self.logsListBoxScroll = ScrollView(size_hint=(1, 1))

        self.logsListBox = BoxLayout(
            orientation='vertical', size_hint=(1, None), spacing=10)
        self.logsListBox.bind(
            minimum_height=self.logsListBox.setter('height'))

        self.logsListBoxScroll.add_widget(self.logsListBox)

        layout.add_widget(self.logsListBoxScroll)

        return screen

    def gotoLogs(self,*a):
        self.logsListBox.clear_widgets()
        try:
            from kivy.logger import LoggerHistory
            for i in LoggerHistory.history:
                self.logsListBox.add_widget(Label(text=str(i.getMessage()), size_hint=(1,None)))

            self.screenManager.current = "Logs"
        except Exception as e:
            logging.info(traceback.format_exc())


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



    def gotoNewStreamPost(self, stream,parent=''):
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(MDToolbar(title="New Post for "+stream))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoStreamPost(stream,parent)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        newtitle = MDTextField(text='',mode='fill', font_size='22sp')

        newp = MDTextField(text='',mode='rectangle', multiline=True)

        def post(*a):
            if newp.text:
                with hardline.userDatabases[stream]:
                    d = {'body': newp.text,'title':newtitle.text,'type':'post'}
                    if parent:
                        d['parent']=parent
                    hardline.userDatabases[stream].setDocument(d)
                    hardline.userDatabases[stream].commit()
                self.gotoStreamPosts(stream)

        btn1 = Button(text='Post!',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=post)

        self.streamEditPanel.add_widget(newtitle)

        self.streamEditPanel.add_widget(MDToolbar(title="Post Body"))

        self.streamEditPanel.add_widget(newp)
        self.streamEditPanel.add_widget(btn1)


    def gotoStreamPosts(self, stream, startTime=0, endTime=0, parent=''):
        "Handles both top level stream posts and comments"
        self.streamEditPanel.clear_widgets()
        s = hardline.userDatabases[stream]
        if not parent:
            self.streamEditPanel.add_widget(MDToolbar(title="Feed for "+stream))
        else:
            parentDoc=hardline.userDatabases[stream].getDocumentByID(parent)
            self.streamEditPanel.add_widget(self.makePostWidget(stream,parentDoc))
            self.streamEditPanel.add_widget((MDToolbar(title="Comments:")))
            

        topbar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)
        topbar.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoStreamPosts( stream, startTime, endTime, parent)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]


        def write(*a):
            self.gotoNewStreamPost(stream,parent)
        btn1 = Button(text='Write a post',
                size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=write)
        if s.writePassword:
            topbar.add_widget(btn1)

        self.streamEditPanel.add_widget(topbar)
        
        
        p = s.getDocumentsByType("post",startTime=startTime, endTime=endTime or 10**18, limit=100, parent=parent)
        if p:
            newest=p[-1]['time']
            oldest=p[0]['time']
        else:
            newest=endTime
            oldest=startTime

        #The calender interactions are based on the real oldest post in the set

        #Let the user see older posts by picking a start date to stat showing from.
        startdate = Button(text=time.strftime('(%a %b %d, %Y)',time.localtime(oldest/10**6)),
                      size_hint=(0.28, None), font_size="14sp")

      
        def f(*a):
            if oldest:
                d=time.localtime((oldest)/10**6)
            else:
                d=time.localtime()

            from kivymd.uix.picker import MDDatePicker

            def onAccept(date):
                t= datetime.datetime.combine(date,datetime.datetime.min.time()).timestamp()*10**6
                self.gotoStreamPosts(stream, t,parent=parent)            
            d =MDDatePicker(onAccept,year=d.tm_year, month=d.tm_mon, day=d.tm_mday)

            d.open()

        startdate.bind(on_release=f)



        pagebuttons = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)

        #Thids button advances to the next newer page of posts.
        newer = Button(text='Newer',
                      size_hint=(0.28, None), font_size="14sp")
        def f2(*a):
            self.gotoStreamPosts(stream, newest,parent=parent)            

        newer.bind(on_release=f2)

        #Thids button advances to the next newer page of posts.
        older = Button(text='Older',
                      size_hint=(0.28, None), font_size="14sp")
        def f3(*a):
            self.gotoStreamPosts(stream, endTime=oldest,parent=parent)            

        older.bind(on_release=f3)

        pagebuttons.add_widget(older)
        pagebuttons.add_widget(startdate)
        pagebuttons.add_widget(newer)


        self.streamEditPanel.add_widget(pagebuttons)

        self.streamEditPanel.add_widget(MDToolbar(title="Posts"))


       
        for i in reversed(p):
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i))
        self.screenManager.current = "EditStream"

    def makePostWidget(self,stream, post):
        def f(*a):
            self.gotoStreamPost(stream,post['id'])

        l = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(1,None))
        l.add_widget(Button(text=post.get('title',"?????") + " "+time.strftime('(%a %b %d, %Y)',time.localtime(post.get('time',0)/10**6)), size_hint=(1,None), on_release=f))
        l.add_widget(Label(text=post.get('body',"?????")[:140], size_hint=(1,None), font_size='22sp',halign='left'))

        return l

    def gotoStreamPost(self, stream,postID):
        "Editor/viewer for ONE specific post"
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text="Editing post in "+stream))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoStreamPost(stream, postID)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        document = hardline.userDatabases[stream].getDocumentByID(postID)

        newtitle = MDTextField(text=document.get("title",''),mode='fill', font_size='22sp')

        newp = MDTextField(text=document.get("body",''),mode='rectangle', multiline=True)

        date = Label(size_hint=(1,None), text="Last edited on: "+time.strftime('%Y %b %d (%a) @ %r',time.localtime(document.get('time',0)/10**6)))

        def post(*a):
            with hardline.userDatabases[stream]:
                document['title']=newtitle.text
                document['body']=newp.text
                hardline.userDatabases[stream].setDocument(document)
                hardline.userDatabases[stream].commit()
            self.gotoStreamPosts(stream)

        btn1 = Button(text='Save!',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=post)

        self.streamEditPanel.add_widget(date)

        self.streamEditPanel.add_widget(newtitle)
        self.streamEditPanel.add_widget(newp)
        if hardline.userDatabases[stream].writePassword:
            self.streamEditPanel.add_widget(btn1)

        def delete(*a):
            def reallyDelete(v):
                if v==postID:
                    with hardline.userDatabases[stream]:
                        hardline.userDatabases[stream].setDocument({'type':'null','id':postID})
                        hardline.userDatabases[stream].commit()
                    self.gotoStreamPosts(stream)
            self.askQuestion("Delete post permanently on all nodes?", postID, reallyDelete)

        btn1 = Button(text='Delete',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=delete)

        if hardline.userDatabases[stream].writePassword:
            self.streamEditPanel.add_widget(btn1)


        #This button takes you to the full comments manager
        def goToCommentsPage(*a):
            self.gotoStreamPosts(stream,parent=postID)

        btn1 = Button(text='Go to Comments and Reports',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=goToCommentsPage)
        self.streamEditPanel.add_widget(btn1)


        #This just shows you the most recent info
        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text="Recent Comments:"))

        s = hardline.userDatabases[stream]
        p = s.getDocumentsByType("post", limit=10,parent=postID)
        for i in reversed(p):
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i))

        
  
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


        self.screenManager.current = "EditStream"

    def editStreamSettings(self, name):
        db = hardline.userDatabases[name]
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
                    hardline.delDatabase(None, n)
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
                    import libnacl,base64
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



    def makeLocalServicesPage(self):

        screen = Screen(name='LocalServices')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)

      

        label = Label(size_hint=(1, None), halign="center",
                      text='WARNING: Running a local service may use a lot of data and battery.\nChanges may require service restart.')

        labelw = Label(size_hint=(1, None), halign="center",
                       text='WARNING 2: This app currently prefers the external SD card for almost everything including the keys.')

        layout.add_widget(self.makeBackButton())

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
            logging.info(traceback.format_exc())

        self.screenManager.current = "LocalServices"

    def makeLocalServiceEditPage(self):

        screen = Screen(name='EditLocalService')
        self.servicesScreen = screen

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)
        self.localServiceEditorName = Label(size_hint=(
            1, None), halign="center", text="??????????")

        layout.add_widget(self.makeBackButton())

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
            c = configparser.ConfigParser(dict_type=CaseInsensitiveDict)

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
            logging.info("SAVE BUTTON WAS PRESSED")
            # On android this is the bg service's job
            hardline.makeUserService(None, name, c['Info'].get("title", 'Untitled'), service=c['Service'].get("service", ""),
                                     port=c['Service'].get("port", ""), cacheInfo=c['Cache'], noStart=(platform == 'android'), useDHT=c['Access'].get("useDHT", "yes"))
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

       
        label = Label(size_hint=(1, None), halign="center",
                      text='Browsing your local network.\nWarning: anyone on your network\ncan advertise a site with any title they want.')


        layout.add_widget(self.makeBackButton())

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
            logging.info(traceback.format_exc())

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
