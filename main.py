# This is the kivy android app.  Maybe ignore it on ither platforms, the code the support them is only for testing.

from kivy.logger import Logger
import logging
logging.Logger.manager.root = Logger

import configparser
from kivy.clock import mainthread,Clock

from hardline import directories, simpleeval
from kivy.uix.image import Image
from kivy.uix.widget import Widget
import hardline
import service
from typing import Sized, Text
from kivymd.app import MDApp
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
import threading
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

# Terrible Hacc, because otherwise we cannot iumport hardline on android.
import os
import sys
import re
from hardline import makeUserDatabase, uihelpers, drayerdb, cidict
from kivymd.uix.picker import MDDatePicker

import datetime

from hardline.cidict import CaseInsensitiveDict

from kivy.logger import Logger, LOG_LEVELS
Logger.setLevel(LOG_LEVELS["info"])






def makePostRenderingFuncs(limit=1024*1024):
    def spreadsheetSum(p):
        t=0
        n=0
        for i in p:
            try:
                i=float(i)
                n+=1
            except:
                continue
            if n>limit:
                return float('nan')
            t+=i
        return t
    
    def spreadsheetLatest(p):
        for i in p:
            return t


    def spreadsheetAvg(p):
        t=0
        n =0
        for i in p:
            try:
                i=float(i)
                n+=1
            except:
                continue

            if n>limit:
                return float('nan')
            t+=i
        return t/n
    
    funcs = {'SUM':spreadsheetSum, 'AVG':spreadsheetAvg,'LATEST':spreadsheetLatest}
    return funcs


class ColumnIterator():
    def __init__(self, db,postID, col):
        self.col = col
        self.db = db
        self.postID= postID

    def __iter__(self):
        self.cur = self.db.getDocumentsByType("row", parent=self.postID, limit=10240000000)
        return self

    def __next__(self):
        for i in self.cur:
            if self.col in i:
                return i[self.col]
        raise StopIteration


def renderPostTemplate(db, postID,text, limit=100000000):
    "Render any {{expressions}} in a post based on that post's child data row objects"

    search=list(re.finditer(r'\{\{(.*?)\}\}',text))
    if not search:
        return text

    #Need to be able to go slightly 
    rows = db.getDocumentsByType('row',parent=postID)

    ctx = {}
    
    n = 0
    for i in rows:
        n+=1
        if n>limit:
            return text
        for j in i:
            if j.startswith("row."):
                ctx[j[4:]]=ColumnIterator(db,postID, j)
                
    replacements ={}
    for i in search:
        if not i.group() in replacements:
            try:
                from simpleeval import simple_eval
                simpleeval.POWER_MAX = 512
                replacements[i.group()] = simple_eval(i.group(1), names= ctx, functions=makePostRenderingFuncs(limit))
            except Exception as e:
                logging.exception("Error in template expression in a post")
                replacements[i.group()] = e
    
    for i in replacements:
        text = text.replace(i, str(replacements[i]))
    
    return text





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
        sm.add_widget(self.makePostMetaDataPage())

        self.theme_cls.primary_palette = "Green"

        self.backStack = []

        #Call this to save whatever unsaved data. Also acts as a flag.
        self.unsavedDataCallback = None

        self.screenManager = sm

        Clock.schedule_interval(self.flushUnsaved, 60*5)

        return sm

    #Here is our autosave
    def on_pause(self):
        self.flushUnsaved()
        return True

    def on_stop(self):
        self.flushUnsaved()

    def on_destroy(self):
        self.flushUnsaved()

    def flushUnsaved(self,*a):
        if self.unsavedDataCallback:
            self.unsavedDataCallback()
            self.unsavedDataCallback=None


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
            def f(d):
                if d:
                    self.unsavedDataCallback=False
                    #Get rid of the first one representing the current page
                    if self.backStack:
                        self.backStack.pop()

                    #Go to the previous page, if that page left an instruction for how to get back to it
                    if self.backStack:
                        self.backStack.pop()()
                    else:
                        self.screenManager.current = "Main"

            #If they have an unsaved post, ask them if they really want to leave.
            if self.unsavedDataCallback:
                self.askQuestion("Discard unsaved data?",'yes',cb=f)
            else:
                f(True)
            
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




    def makeDataTablePage(self):
        screen = Screen(name='TableView')
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
        self.streamEditPanel.add_widget(MDToolbar(title="Posting in: "+stream+"(Autosave on)"))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoStreamPost(stream,parent)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        newtitle = MDTextField(text='',mode='fill', font_size='22sp')

        newp = MDTextFieldRect(text='', multiline=True,size_hint=(0.68,None))

        def post(*a):
            if newp.text:
                with hardline.userDatabases[stream]:
                    d = {'body': newp.text,'title':newtitle.text,'type':'post'}
                    if parent:
                        d['parent']=parent
                    hardline.userDatabases[stream].setDocument(d)
                    hardline.userDatabases[stream].commit()

                self.unsavedDataCallback=None
                #Done with this, don't need it in back history
                if self.backStack:
                    self.backStack.pop()
                self.gotoStreamPosts(stream)

        self.unsavedDataCallback=post

        btn1 = Button(text='Post!',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=post)

        self.streamEditPanel.add_widget(newtitle)

        self.streamEditPanel.add_widget(MDToolbar(title="Post Body"))

        self.streamEditPanel.add_widget(newp)
        self.streamEditPanel.add_widget(btn1)



    def makePostsListingPage(self):
        "Generic posts listing"

        screen = Screen(name='PostList')

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)


        self.postListScroll = ScrollView(size_hint=(1, 1))

        self.postListPanel = BoxLayout(
            orientation='vertical',adaptive_height= True, spacing=5)
        self.postListPanel.bind(
            minimum_height=self.postListPanel.setter('height'))

        self.postListPanelScroll.add_widget(self.postListPanel)

        layout.add_widget(self.postListPanelScroll)

        return screen





    def makePostMetaDataPage(self):
        "Prettu much just an empty page filled in by the specific goto functions"

        screen = Screen(name='PostMeta')

        layout = BoxLayout(orientation='vertical', spacing=10)
        screen.add_widget(layout)


        self.postMetaPanelScroll = ScrollView(size_hint=(1, 1))

        self.postMetaPanel = BoxLayout(
            orientation='vertical',adaptive_height= True, spacing=5)
        self.postMetaPanel.bind(
            minimum_height=self.postMetaPanel.setter('height'))

        self.postMetaPanelScroll.add_widget(self.postMetaPanel)

        layout.add_widget(self.postMetaPanelScroll)


        return screen



    def request_android_permissions(self):
        """
        Since API 23, Android requires permission to be requested at runtime.
        This function requests permission and handles the response via a
        callback.
        The request will produce a popup if permissions have not already been
        been granted, otherwise it will do nothing.
        """
        from android.permissions import request_permissions, Permission

        def callback(permissions, results):
            """
            Defines the callback to be fired when runtime permission
            has been granted or denied. This is not strictly required,
            but added for the sake of completeness.
            """
            if all([res for res in results]):
                print("callback. All permissions granted.")
            else:
                print("callback. Some permissions refused.")

        request_permissions([Permission.ACCESS_COARSE_LOCATION,
                             Permission.ACCESS_FINE_LOCATION], callback)


    def gotoPostMetadata(self, stream, docID, document):
        "Handles both top level stream posts and comments"
        self.postMetaPanel.clear_widgets()
        s = document

        self.postMetaPanel.add_widget((MDToolbar(title=s.get('title','Untitled'))))

        topbar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)
        
        def goBack(*a):
            self.screenManager.current= "EditStream"
        btn =  MDRoundFlatButton(size_hint=(1,None), text="Go Back")
        btn.bind(on_release=goBack)
        self.postMetaPanel.add_widget(btn)
    
     
        location = MDRoundFlatButton(size_hint=(1,None), text="Location: "+s.get("lat",'')+','+s.get('lon','') )

        def promptSet(*a):
            def onEnter(d):
                if d is None:
                    return
                if d:
                    l=[i.strip() for i in d.split(",")]
                    if len(l)==2:
                        try:
                            lat = float(l[0])
                            lon=float(l[1])
                            s['time']=None
                            s['lat']=lat
                            s['lon']=lon
                            location.text="Location: "+s.get("lat",'')+','+s.get('lon','')
                    
                            return
                        except:
                            logging.exception("Parse Error")
                else:
                    try:
                        del s['lat']
                    except:
                        pass
                    try:
                        del s['lon']
                    except:
                        pass
                    location.text="Location: "+s.get("lat",'')+','+s.get('lon','')
                    s['time']=None


            self.askQuestion("Enter location",s.get("lat",0)+','+s.get('lon',0),onEnter)

        location.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(location)

        self.screenManager.current="PostMeta"


        icon = MDRoundFlatButton(size_hint=(1,None), text="Icon: "+os.path.basename(s.get("icon",'')) )
        def promptSet(*a):
            from plyer import filechooser
            selection = filechooser.open_file(path=os.path.join(directories.assetLibPath,'icons'))
            s['icon'] = selection[0][len(directories.assetLibPath)+1:] if selection else ''
            s['time']=None
            icon.text = "Icon: "+os.path.basename(s.get("icon",''))

            
        icon.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(icon)






                    





    def gotoTableView(self, stream, parent='', search=''):
        "Data records can be attatched to a post."
        self.streamEditPanel.clear_widgets()
        s = hardline.userDatabases[stream]
        parentDoc=hardline.userDatabases[stream].getDocumentByID(parent)
        self.streamEditPanel.add_widget(self.makeBackButton())
        self.streamEditPanel.add_widget(self.makePostWidget(stream,parentDoc))
        self.streamEditPanel.add_widget((MDToolbar(title="Data Table View")))
            

        topbar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)

        searchBar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)

        searchQuery = MDTextField(size_hint=(0.68,None),multiline=False, text=search)
        searchButton = MDRoundFlatButton(text="Search", size_hint=(0.3,None))
        searchBar.add_widget(searchQuery)
        searchBar.add_widget(searchButton)

        def doSearch(*a):
            self.gotoTableView(stream, parent,searchQuery.text.strip())
        searchButton.bind(on_release=doSearch)

        def goHere():
            self.gotoTableView( stream, parent,search)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        newEntryBar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)


        newRowName = MDTextField(size_hint=(0.68,None),multiline=False, text=search)
        def write(*a):
            for i in  newRowName.text:
                if i in "[]{}:,./\\":
                    return

            if newRowName.text.strip():
                id = parent+'-'+newRowName.text.strip().lower().replace(' ',"")[:48]
                #That name already exists, jump to it
                if hardline.userDatabases[stream].getDocumentByID(id):
                    self.gotoStreamRow(stream, id)
                    return
            else:
                import uuid
                id=str(uuid.uuid4())
            
            x = hardline.userDatabases[stream].getDocumentsByType("row.template", parent=parent,limit=1) 
            newDoc = {'parent': parent,'id':id, 'name':newRowName.text.strip() or id, 'type':'row'}

            #Use the previously created or modified row as the template
            for i in x:
                for j in i:
                    if j.startswith('row.'):
                        newDoc[j]= ''


           
            self.gotoStreamRow(stream, id, newDoc)

        btn1 = Button(text='New Entry',
                size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=write)
        newEntryBar.add_widget(newRowName)
        newEntryBar.add_widget(btn1)

        if s.writePassword:
            topbar.add_widget(newEntryBar)

        self.streamEditPanel.add_widget(topbar)
        
        if not search:
            p = s.getDocumentsByType("row", limit=1000, parent=parent)
        else:
            p = s.searchDocuments(search,"row", limit=1000, parent=parent)



     

        self.streamEditPanel.add_widget(MDToolbar(title="Data Rows"))
        self.streamEditPanel.add_widget(searchBar)


       
        for i in p:
            self.streamEditPanel.add_widget(self.makeRowWidget(stream,i))
        self.screenManager.current = "EditStream"





    def gotoStreamPosts(self, stream, startTime=0, endTime=0, parent='', search=''):
        "Handles both top level stream posts and comments, and searches.  So we can search comments if we want."
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

        searchBar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)

        searchQuery = MDTextField(size_hint=(0.68,None),multiline=False, text=search)
        searchButton = MDRoundFlatButton(text="Search", size_hint=(0.3,None))
        searchBar.add_widget(searchQuery)
        searchBar.add_widget(searchButton)

        def doSearch(*a):
            self.gotoStreamPosts(stream, startTime, endTime, parent,searchQuery.text.strip())
        searchButton.bind(on_release=doSearch)

        def goHere():
            self.gotoStreamPosts( stream, startTime, endTime, parent,search)
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



        
        if not search:
            p = list(s.getDocumentsByType("post",startTime=startTime, endTime=endTime or 10**18, limit=100, parent=parent))
        else:
            p=list(s.searchDocuments(search,"post",startTime=startTime, endTime=endTime or 10**18, limit=100, parent=parent))

        if p:
            newest=p[0]['time']
            oldest=p[-1]['time']
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
        self.streamEditPanel.add_widget(searchBar)


        self.streamEditPanel.add_widget(MDToolbar(title="Posts"))


       
        for i in p:
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i))
        self.screenManager.current = "EditStream"

    def makePostWidget(self,stream, post):
        def f(*a):
            self.gotoStreamPost(stream,post['id'])

        #Chop to a shorter length, then rechop to even shorter, to avoid cutting off part of a long template and being real ugly.
        body=post.get('body',"?????")[:240]
        body = renderPostTemplate(hardline.userDatabases[stream], post, body, 4096)
        body=body[:140]

        l = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(1,None))
        l.add_widget(Button(text=post.get('title',"?????") + " "+time.strftime('(%a %b %d, %Y)',time.localtime(post.get('time',0)/10**6)), size_hint=(1,None), on_release=f))
        l2 = BoxLayout(adaptive_height=True,orientation='horizontal',size_hint=(1,None))
        img = Image(size_hint=(0.3,None))
        l2.add_widget(img)
        
        src = os.path.join(directories.assetLibPath, post.get("icon","INVALID"))
        if os.path.exists(src):
            img.source= src


        l2.add_widget(Label(text=body, size_hint=(0.7,None), font_size='22sp',halign='left'))
        l.add_widget(l2)

        return l

    
    def makeRowWidget(self,stream, post):
        def f(*a):
            self.gotoStreamRow(stream,post['id'])

        l = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(1,None))
        l.add_widget(Button(text=post.get('name',"?????"), size_hint=(1,None), on_release=f))
        #l.add_widget(Label(text=post.get('body',"?????")[:140], size_hint=(1,None), font_size='22sp',halign='left'))
        return l

    def gotoStreamRow(self, stream, postID, document=None, noBack=False,template=None):
        "Editor/viewer for ONE specific row"
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(MDToolbar(title="Table Row in "+stream))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        if not noBack:
            def goHere():
                self.gotoStreamRow(stream, postID)
            self.backStack.append(goHere)
            self.backStack = self.backStack[-50:]

        document = document or hardline.userDatabases[stream].getDocumentByID(postID)
        if 'type' in document and not document['type'] == 'row':
            raise RuntimeError("Document is not a row")
        document['type']='row'

        title = Label(text=document.get("name",''),font_size='22sp')

        #Our default template if none exists
        #Give it a name because eventually we may want to have multiple templates.
        #Give it an ID so it can override any existing children of that template. 
        oldTemplate= {'type':"row.template",'parent':document['parent'], 'name': 'default', 'id':document['parent']+".rowtemplate.default"}

        for i in hardline.userDatabases[stream].getDocumentsByType("row.template", parent=document['parent'],limit=1):
            oldTemplate=i

        template= template or oldTemplate


        def post(*a):
            with hardline.userDatabases[stream]:
                #Make sure system knows this is not an old document
                try:
                    del document['time']
                except:
                    pass
                hardline.userDatabases[stream].setDocument(document)

                #If the template has changed, that is how we know we need to save template changes at the same time as data changes
                if not template.get('time',0)==oldTemplate.get('time',1):
                    hardline.userDatabases[stream].setDocument(template)
                hardline.userDatabases[stream].commit()
                self.unsavedDataCallback=None

            self.gotoStreamPosts(stream)
      
        btn1 = Button(text='Save Changes',
                      size_hint=(0.48, None), font_size="14sp")
        btn1.bind(on_release=post)


        self.streamEditPanel.add_widget(title)
        
        buttons = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)
              

        if hardline.userDatabases[stream].writePassword:
            self.streamEditPanel.add_widget(buttons)  
            buttons.add_widget(btn1)



        def delete(*a):
            def reallyDelete(v):
                if v==postID:
                    with hardline.userDatabases[stream]:
                        hardline.userDatabases[stream].setDocument({'type':'null','id':postID})
                        hardline.userDatabases[stream].commit()
                    self.gotoStreamPosts(stream)
            self.askQuestion("Delete table row permanently on all nodes?", postID, reallyDelete)

        btn1 = Button(text='Delete',
                      size_hint=(0.48, None), font_size="14sp")
        btn1.bind(on_release=delete)

        if hardline.userDatabases[stream].writePassword:
            buttons.add_widget(btn1)
            
        names ={}

        self.streamEditPanel.add_widget(MDToolbar(title="Data Columns:"))

        for i in template:
            if i.startswith('row.'):
                names[i]=''
               
        for i in document:
            if i.startswith('row.'):
                if i in template:
                    names[i]=''
                else:
                    #In the document but not the template, it is an old/obsolete column, show that to user.
                    names[i]='(removed)'
        
        for i in names:
            self.streamEditPanel.add_widget( Button(size_hint=(1,None), text=i[4:]))
            d = document.get(i,'')
            try:
                d=float(d)
            except:
                pass
                
            x = MDTextField(text=str(d)+names[i],mode='fill', multiline=False,font_size='22sp')
            def oc(*a,i=i):
                d=x.text.strip()
                if isinstance(d,str):
                    d=d.strip()
                try:
                    d=float(d or 0)
                except:
                    pass
                document[i]=d
            x.bind(text=oc)
            self.streamEditPanel.add_widget(x)

            if isinstance(d,float) or not d.strip():
                l = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)
                b = MDRoundFlatButton(text="--", size_hint=(0.48,None))
                def f(*a, i=i, x=x):
                    d=document.get(i,'')
                    if isinstance(d,str):
                        d=d.strip()
                    try:
                        d=float(d or 0)
                    except:
                        return
                    document[i]=d-1
                    x.text=str(d-1)
                b.bind(on_release=f)

                b2 = MDRoundFlatButton(text="++", size_hint=(0.48,None))
                def f(*a, i=i, x=x):
                    d=document.get(i,'')
                    if isinstance(d,str):
                        d=d.strip()
                    try:
                        d=float(d or 0)
                    except:
                        return
                    document[i]=d+1
                    x.text=str(document[i])

                b2.bind(on_release=f)

                l.add_widget(b)
                l.add_widget(b2)
                self.streamEditPanel.add_widget(l)


        b = MDRoundFlatButton(text="Add Column", size_hint=(0.48,None))
        def f(*a):
            def f2(r):
                if r:
                    template['row.'+r]=''
                    #Remove time field which marks it as a new record that will get a new timestamp rather than
                    #being ignored when we go to save it, for being old.
                    template.pop('time',None)
                    #Redraw the whole page, it is lightweight, no DB operation needed.
                    self.gotoStreamRow(stream, postID, document=document, noBack=True,template=template)
            self.askQuestion("Name of new column?",cb=f2)

        b.bind(on_release=f)
        self.streamEditPanel.add_widget(b)

        b = MDRoundFlatButton(text="Del Column", size_hint=(0.48,None))
        def f(*a):
            def f2(r):
                if r:
                    try:
                       del template['row.'+r]
                       template.pop('time',None)
                    except:
                        pass
                    #Redraw the whole page, it is lightweight, no DB operation needed.
                    self.gotoStreamRow(stream, postID, document=document, noBack=True,template=template)
            self.askQuestion("Column to delete?",cb=f2)
                
        b.bind(on_release=f)
        self.streamEditPanel.add_widget(b)


        self.screenManager.current = "EditStream"


    def gotoStreamPost(self, stream,postID):
        "Editor/viewer for ONE specific post"
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(MDToolbar(title="Post in "+stream+"(Autosave on)"))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoStreamPost(stream, postID)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        document = hardline.userDatabases[stream].getDocumentByID(postID)

        newtitle = MDTextField(text=document.get("title",''),mode='fill', multiline=False,font_size='22sp')

        titleBar = BoxLayout(adaptive_height=True,orientation='horizontal',size_hint=(1,None))
        img = Image(size_hint=(0.3,None))
        titleBar.add_widget(img)
        titleBar.add_widget(newtitle)

        src = os.path.join(directories.assetLibPath, document.get("icon","INVALID"))
        if os.path.exists(src):
            img.source= src

        renderedText = renderPostTemplate(hardline.userDatabases[stream],postID, document.get("body",''))

        sourceText= [document.get("body",'')]

        newp = MDTextFieldRect(text=renderedText, multiline=True,size_hint=(1,None))


        def f(instance, focus):
            if focus:
                newp.text = sourceText[0]

                #Mark invalid because it can now change
                sourceText[0]=None
            else:
                sourceText[0] =newp.text
                newp.text = renderPostTemplate(hardline.userDatabases[stream],postID, newp.text)
        newp.bind(focus=f)

        date = Label(size_hint=(1,None), text="Last edited on: "+time.strftime('%Y %b %d (%a) @ %r',time.localtime(document.get('time',0)/10**6)))


        def post(*a):
            with hardline.userDatabases[stream]:
                document['title']=newtitle.text
                document['body']=sourceText[0] or newp.text
                #Make sure system knows this is not an old document
                try:
                    del document['time']
                except:
                    pass
                hardline.userDatabases[stream].setDocument(document)
                hardline.userDatabases[stream].commit()
                self.unsavedDataCallback=None

            self.gotoStreamPosts(stream)
        
        def setUnsaved(*a):
            self.unsavedDataCallback = post
        newtitle.bind(text=setUnsaved)
        newp.bind(text=setUnsaved)

        btn1 = Button(text='Save',
                      size_hint=(0.28, None), font_size="14sp")
        btn1.bind(on_release=post)


        self.streamEditPanel.add_widget(titleBar)
        self.streamEditPanel.add_widget(newp)        
        
        buttons = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)


        if hardline.userDatabases[stream].writePassword:
            self.streamEditPanel.add_widget(buttons)  
            buttons.add_widget(btn1)

        self.streamEditPanel.add_widget(date)


        def delete(*a):
            def reallyDelete(v):
                if v==postID:
                    with hardline.userDatabases[stream]:
                        hardline.userDatabases[stream].setDocument({'type':'null','id':postID})
                        hardline.userDatabases[stream].commit()
                    self.gotoStreamPosts(stream)
            self.askQuestion("Delete post permanently on all nodes?", postID, reallyDelete)

        btn1 = Button(text='Delete',
                      size_hint=(0.28, None), font_size="14sp")
        btn1.bind(on_release=delete)

        if hardline.userDatabases[stream].writePassword:
            buttons.add_widget(btn1)


        #This button takes you to it
        def goToProperties(*a):
            self.gotoPostMetadata(stream,postID,document)
          
        

        btn1 = Button(text='Info',
                      size_hint=(0.28, None), font_size="14sp")
        btn1.bind(on_release=goToProperties)
        buttons.add_widget(btn1)


        #This button takes you to the full comments manager
        def goToCommentsPage(*a):
            def f(x):
                if x:
                    self.unsavedDataCallback=None
                    self.gotoStreamPosts(stream,parent=postID)
            if self.unsavedDataCallback:
                self.askQuestion("Discard changes?","yes",f)
            else:
                f('yes')

     

        def tableview(*a):
            self.gotoTableView(stream,postID)
        btn1 = Button(text='Data Table',
                size_hint=(1, None), font_size="14sp")

        btn1.bind(on_press=tableview)
        self.streamEditPanel.add_widget(btn1)

        #This just shows you the most recent info
        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text="Recent Comments:"))

        s = hardline.userDatabases[stream]
        p = s.getDocumentsByType("post", limit=5,parent=postID)
        for i in p:
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i))

        btn1 = Button(text='Go to Comments and Reports',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=goToCommentsPage)
        self.streamEditPanel.add_widget(btn1)
  
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
