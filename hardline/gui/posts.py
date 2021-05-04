import configparser
import json
from hardline import daemonconfig
from .. import daemonconfig, hardline


import configparser,logging,datetime

from kivy.uix.image import Image
from kivy.uix.widget import Widget

from typing import Sized, Text
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
from kivy.uix.screenmanager import ScreenManager, Screen

import time
import traceback

# Terrible Hacc, because otherwise we cannot iumport hardline on android.
import os
import sys
import re
from .. daemonconfig import makeUserDatabase
from .. import   drayerdb, cidict,directories

from kivymd.uix.picker import MDDatePicker

from . import tables

class PostsMixin():


    def gotoStreamPost(self, stream,postID):
        "Editor/viewer for ONE specific post"
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(MDToolbar(title="Post in "+stream+"(Autosave on)"))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoStreamPost(stream, postID)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        document = daemonconfig.userDatabases[stream].getDocumentByID(postID)

        newtitle = MDTextField(text=document.get("title",''),mode='fill', multiline=False,font_size='22sp')

        titleBar = BoxLayout(adaptive_height=True,orientation='horizontal',size_hint=(1,None))
        innerTitleBar = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(0.7,None))
        date = MDFlatButton(size_hint=(1,None), text="Modified: "+time.strftime('%Y %b %d (%a) @ %r',time.localtime(document.get('time',0)/10**6)), )
        innerTitleBar.add_widget(date)
        innerTitleBar.add_widget(newtitle)


        img = Image(size_hint=(0.3,1))
        titleBar.add_widget(img)
        titleBar.add_widget(innerTitleBar)



        src = os.path.join(directories.assetLibPath, document.get("icon","INVALID"))
        if os.path.exists(src):
            img.source= src

        self.currentlyViewedPostImage = img

        renderedText = tables.renderPostTemplate(daemonconfig.userDatabases[stream],postID, document.get("body",''))

        sourceText= [document.get("body",'')]

        newp = MDTextFieldRect(text=renderedText, multiline=True,size_hint=(1,None))


        def f(instance, focus):
            if focus:
                newp.text = sourceText[0]

                #Mark invalid because it can now change
                sourceText[0]=None
            else:
                sourceText[0] =newp.text
                newp.text = tables.renderPostTemplate(daemonconfig.userDatabases[stream],postID, newp.text)
        newp.bind(focus=f)



        def post(*a):
            with daemonconfig.userDatabases[stream]:
                document['title']=newtitle.text
                document['body']=sourceText[0] or newp.text
                #Make sure system knows this is not an old document
                try:
                    del document['time']
                except:
                    pass
                daemonconfig.userDatabases[stream].setDocument(document)
                daemonconfig.userDatabases[stream].commit()
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


        if daemonconfig.userDatabases[stream].writePassword:
            self.streamEditPanel.add_widget(buttons)  
            buttons.add_widget(btn1)



        def delete(*a):
            def reallyDelete(v):
                if v==postID:
                    with daemonconfig.userDatabases[stream]:
                        daemonconfig.userDatabases[stream].setDocument({'type':'null','id':postID})
                        daemonconfig.userDatabases[stream].commit()
                    self.gotoStreamPosts(stream)
            self.askQuestion("Delete post permanently on all nodes?", postID, reallyDelete)

        btn1 = Button(text='Delete',
                      size_hint=(0.28, None), font_size="14sp")
        btn1.bind(on_release=delete)

        if daemonconfig.userDatabases[stream].writePassword:
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

        s = daemonconfig.userDatabases[stream]
        p = s.getDocumentsByType("post", limit=5,parent=postID)
        for i in p:
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i))

        btn1 = Button(text='Go to Comments and Reports',
                      size_hint=(1, None), font_size="14sp")
        btn1.bind(on_release=goToCommentsPage)
        self.streamEditPanel.add_widget(btn1)
  
        self.screenManager.current = "EditStream"

    def gotoStreamPosts(self, stream, startTime=0, endTime=0, parent='', search=''):
        "Handles both top level stream posts and comments, and searches.  So we can search comments if we want."
        self.streamEditPanel.clear_widgets()
        s = daemonconfig.userDatabases[stream]
        if not parent:
            self.streamEditPanel.add_widget(MDToolbar(title="Feed for "+stream))
        else:
            parentDoc=daemonconfig.userDatabases[stream].getDocumentByID(parent)
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
                      size_hint=(1, None), font_size="14sp")

      
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
        pagebuttons.add_widget(newer)


        self.streamEditPanel.add_widget(pagebuttons)
        self.streamEditPanel.add_widget(startdate)

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
        body = tables.renderPostTemplate(daemonconfig.userDatabases[stream], post, body, 4096)
        body=body[:140]

        l = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(1,None))
        l.add_widget(Button(text=post.get('title',"?????") + " "+time.strftime('(%a %b %d, %Y)',time.localtime(post.get('time',0)/10**6)), size_hint=(1,None), on_release=f))
        l2 = BoxLayout(adaptive_height=True,orientation='horizontal',size_hint=(1,None))
        img = Image(size_hint=(0.3,1))
        l2.add_widget(img)
        
        src = os.path.join(directories.assetLibPath, post.get("icon","INVALID"))
        if os.path.exists(src):
            img.source= src


        l2.add_widget(Label(text=body, size_hint=(0.7,None), font_size='22sp',halign='left'))
        l.add_widget(l2)

        l.image = img

        return l

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
                with daemonconfig.userDatabases[stream]:
                    d = {'body': newp.text,'title':newtitle.text,'type':'post'}
                    if parent:
                        d['parent']=parent
                    daemonconfig.userDatabases[stream].setDocument(d)
                    daemonconfig.userDatabases[stream].commit()

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

    def gotoPostMetadata(self, stream, docID, document):
        "Handles both top level stream posts and comments"
        self.postMetaPanel.clear_widgets()
        s = document

        self.postMetaPanel.add_widget((MDToolbar(title=s.get('title','Untitled'))))

        topbar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True)
        
        def goBack(*a):
            self.screenManager.current= "EditStream"
        btn =  Button(size_hint=(1,None), text="Go Back")
        btn.bind(on_release=goBack)
        self.postMetaPanel.add_widget(btn)
    
     
        location = Button(size_hint=(1,None), text="Location: "+str(s.get("lat",0))+','+str(s.get('lon',0)) )

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
                            location.text="Location: "+str(s.get("lat",0))+','+str(s.get('lon',0))
                    
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
                    location.text="Location: "+str(s.get("lat",0))+','+str(s.get('lon',0))
                    s['time']=None


            self.askQuestion("Enter location",str(s.get("lat",0))+','+str(s.get('lon',0)),onEnter)

        location.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(location)

        self.screenManager.current="PostMeta"

        self.postMetaPanel.add_widget(Label(text="Icon Asset Lib:"+ directories.assetLibPath, size_hint=(1,None)))

        icon = Button(size_hint=(1,None), text="Icon: "+os.path.basename(s.get("icon",'')) )
        def promptSet(*a):
            from .kivymdfmfork import MDFileManager
          
            def f(selection):
                s['icon'] = selection[len(directories.assetLibPath)+1:] if selection else ''
                s['time']=None
                icon.text = "Icon: "+os.path.basename(s.get("icon",''))

                #Immediately update the image as seen in the post editor window

                src = os.path.join(directories.assetLibPath, s.get("icon","INVALID"))
                if os.path.exists(src):
                    self.currentlyViewedPostImage.source = src
                self.openFM.close()
            
            def e(selection):
                self.openFM.close()

            #Autocorrect had some fun with the kivymd devs
            try:
                self.openFM= MDFileManager(select_path=f,preview=True)
            except:
                try:
                    self.openFM= MDFileManager(select_path=f,previous=True)
                except:
                    self.openFM= MDFileManager(select_path=f)

            self.openFM.show(os.path.join(directories.assetLibPath,'icons'))

            
        icon.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(icon)



        export = Button(size_hint=(1,None), text="Export Raw Data")

        def promptSet(*a):
            from .kivymdfmfork import MDFileManager


            def f(selection):
                if selection:
                    if not selection.endswith(".json"):
                        selection=selection+".json"
                
                    try:
                        #Needed for android
                        if not "com.eternityforest" in selection:
                            self.getPermission('files')
                    except:
                        logging.exception("cant ask permission")
                    data = daemonconfig.userDatabases[stream].getAllRelatedRecords(docID)


                    #Get the records as a list, sorted by time for consistency.
                    l = []
                    import json
                    for i in data:
                        d=json.loads(data[i][0])
                        l.append((d['id'],d))
                    l = sorted(l)

                    l = [ [i[1]] for i in l]

                    with open(selection,'w') as f:
                        f.write(json.dumps(l, sort_keys=True,indent=2))
                    self.openFM.close()

             #Autocorrect had some fun with the kivymd devs
            self.openFM= MDFileManager(select_path=f,save_mode=((s.get('title','') or 'UntitledPost')+'.json'))
            self.openFM.show(directories.settings_path)


            
        export.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(export)
        self.postMetaPanel.add_widget(Label(text="Exports this post, all descendants,\nand all ancestors in JSON format\nthat can be imported into\nanother stream.",size_hint=(1,None)))

