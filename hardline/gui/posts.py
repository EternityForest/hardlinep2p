import configparser
import json
from hardline import daemonconfig
from .. import daemonconfig, hardline

from kivy.metrics import cm

import configparser,logging,datetime

from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.textinput import TextInput
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




pinRankFilter = "IFNULL(json_extract(json,'$.pinRank'), 0) >0"


from kivymd.uix.stacklayout import MDStackLayout as StackLayout


class PostsMixin():


    def gotoStreamPost(self, stream,postID,noBack=False, indexAssumption=True):
        "Editor/viewer for ONE specific post"
        self.unsavedDataCallback=None

        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(MDToolbar(title="Post in "+stream+"(Autosave on)"))

        document = daemonconfig.userDatabases[stream].getDocumentByID(postID,allowOrphans=True)

        topbar = BoxLayout(size_hint=(1,None),adaptive_height=True,spacing=10)
        self.streamEditPanel.add_widget(topbar)

        def upOne(*a):
            if document and 'parent' in document:
                self.gotoStreamPost(stream,document['parent'])
            else:
                self.gotoStreamPosts(stream)

        btn1 = Button(text='Up')

        btn1.bind(on_press=upOne)
        topbar.add_widget(btn1)
        


        topbar.add_widget(self.makeBackButton())
        




        newtitle = MDTextField(text=document.get("title",''),mode='fill', multiline=False,font_size='22sp',hint_text='Title')
        newtitle.fill_color=(0.8,0.8,0.8,0.2)

                #I kinda hate that the way kivymd does colors.  I have no clue how to change
        #anything. I am using the Accent color as a sane text color
        newtitle.color_mode='accent'
        newtitle.fill_color=(.8,.8,.7,.5)
        newtitle.bold=True

        #Must set in correct order
        self.theme_cls.accent_pallete='Brown'
        self.theme_cls.accent_hue='900'

        titleBar = BoxLayout(adaptive_height=True,orientation='horizontal',size_hint=(0.99,None))
        innerTitleBar = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(0.68,None))
        date = MDFlatButton(text="Modified: "+time.strftime('%Y %b %d (%a) @ %r',time.localtime(document.get('time',0)/10**6)))
        innerTitleBar.add_widget(date)
        innerTitleBar.add_widget(newtitle)


        img = Image(size_hint=(0.28,1))
        titleBar.add_widget(img)
        titleBar.add_widget(innerTitleBar)



        src = os.path.join(directories.assetLibPath, document.get("icon","INVALID"))
        if os.path.exists(src):
            img.source= src

        self.currentlyViewedPostImage = img

        renderedText = tables.renderPostTemplate(daemonconfig.userDatabases[stream],postID, document.get("body",''))

        sourceText= [document.get("body",'')]
        

        newp = MDTextField(text=renderedText, multiline=True,size_hint=(1,None),mode='fill',color_mode='custom')        
        
        #I kinda hate that the way kivymd does colors.  I have no clue how to change
        #anything. I am using the Accent color as a sane text color
        newp.fill_color=(.8,.8,.7,.5)
        newp.line_color_normal=(0,0,0,1)
        newp.color_mode='accent'


        #Keeps android virtual keyboard from covering us up
        buffer = Widget(size_hint=(1,None),height=0)

        def f(instance, focus):
            
            if focus:
                buffer.height=640
                newp.text = sourceText[0]

                #Mark invalid because it can now change
                sourceText[0]=None
            else:
                buffer.height=0
                sourceText[0] =newp.text
                newp.text = tables.renderPostTemplate(daemonconfig.userDatabases[stream],postID, newp.text)
        newp.bind(focus=f)





        def post(*a,goBack=False):                    
            with daemonconfig.userDatabases[stream]:
                if self.unsavedDataCallback:            
                    self.unsavedDataCallback=None
                    document['title']=newtitle.text
                    document['body']=sourceText[0] or newp.text
                    #Make sure system knows this is not an old document
                    try:
                        del document['time']
                    except:
                        pass
                    daemonconfig.userDatabases[stream].setDocument(document)
                    daemonconfig.userDatabases[stream].commit()
                    if goBack:
                        self.goBack()

        def saveButtonHandler(*a):
            post(goBack=True)
        
        def setUnsaved(*a):
            self.unsavedDataCallback = post
        newtitle.bind(text=setUnsaved)
        newp.bind(text=setUnsaved)




        self.streamEditPanel.add_widget(titleBar)
        self.streamEditPanel.add_widget(newp)
        self.streamEditPanel.add_widget(buffer)

        
        
        buttons = StackLayout(spacing=10,adaptive_height=True,size_hint=(1,None))

        self.streamEditPanel.add_widget(buttons)  

        if daemonconfig.userDatabases[stream].writePassword:
            btn1 = Button(text='Save')
            btn1.bind(on_release=saveButtonHandler)
            buttons.add_widget(btn1)



        def delete(*a):
            def reallyDelete(v):
                if v==postID:
                    with daemonconfig.userDatabases[stream]:
                        daemonconfig.userDatabases[stream].setDocument({'type':'null','id':postID,'direct':True})
                        daemonconfig.userDatabases[stream].commit()
                        self.unsavedDataCallback=None
                        self.currentPageNewRecordHandler=None
                    self.gotoStreamPosts(stream)
            self.askQuestion("Delete post permanently on all nodes?", postID, reallyDelete)

       

        if daemonconfig.userDatabases[stream].writePassword:
            btn1 = Button(text='Delete')
            btn1.bind(on_release=delete)
            buttons.add_widget(btn1)






        #This button takes you to it
        def goToProperties(*a):
            self.gotoPostMetadata(stream,postID,document,post)
          
        

        btn1 = Button(text='Info')
        btn1.bind(on_release=goToProperties)
        buttons.add_widget(btn1)




        def tableview(*a):
            def f(x):
                if x:
                    self.unsavedDataCallback=None
                    self.currentPageNewRecordHandler=None
                    self.gotoTableView(stream,postID)
            if self.unsavedDataCallback:
                self.askQuestion("Discard changes?","yes",f)
            else:
                f('yes')


        btn1 = Button(text='Table')

        btn1.bind(on_press=tableview)
        buttons.add_widget(btn1)




        def archive(*a):
            def f(x):
                if x:
                    import uuid

                    #Save changes before we archive
                    document['title']=newtitle.text
                    document['body']=sourceText[0] or newp.text


                    #Special UUID standin for the "Root post", which does not really exist.
                    rootUUID = '1d4f7b28-0677-4245-a4e3-21a1376b0b3a'

                    #We use this UUID as the identifier for archives.
                    #We can't use a special name for fear of conflict, and because the user should have total freedom to
                    #Rename and customize the archive folder.
                    archiveUUID = 'f638dbb8-dc03-48f3-a644-9fe6ba4c13eb'

                    archiveID=str(uuid.uuid5(uuid.UUID(document.get('parent','') or rootUUID), archiveUUID))

                    with daemonconfig.userDatabases[stream]:
                        #Make the archive post.  It must be a sibling.
                        if not daemonconfig.userDatabases[stream].getDocumentByID(archiveID):
                            daemonconfig.userDatabases[stream].setDocument({
                                'id':archiveID,
                                'title':'Archive',
                                'specialPostType':'archive',
                                'parent':document.get('parent',''),
                                'type':'post',
                                'pinRank': 1,
                                'body':"This is where archived posts in this folder go",
                                "icon":"icons/CC0 Clipart/nicubunu/office/box_with_folders.jpg"
                            })
                        

                        #Now we make the document into a child of the archive
                        p=document.get('parent','')

                        document['parent']= archiveID
                        document['moveTime'] = int(time.time()*10**6)
                        try:
                            del document['time']
                        except KeyError:
                            pass
                        daemonconfig.userDatabases[stream].setDocument(document)

                    daemonconfig.userDatabases[stream].commit()


                    self.unsavedDataCallback=None
                    self.currentPageNewRecordHandler=None
                    self.gotoStreamPosts(stream, parent=p)


            self.askQuestion("Archive Post?","yes",f)



        btn1 = Button(text='Archive')

        btn1.bind(on_press=archive)
        buttons.add_widget(btn1)

        
        #This just shows you the most recent info
        self.streamEditPanel.add_widget(Label(size_hint=(
            1, None), halign="center", text="Recent Comments:"))

        s = daemonconfig.userDatabases[stream]

        pinnedIDs={}
        pinnedPosts = []

        #Get nonzero pin rank
        p1 = s.getDocumentsByType("post", limit=5,parent=postID,extraFilters=pinRankFilter)
        for i in p1:
            #The index assumption, jump straight to the index when we detect a very short post
            #with at least one child
            if indexAssumption and len(document.get('body',''))<140:
                self.gotoStreamPosts(stream,parent=postID,indexAssumptionWasUsed=True)
                return

            pinnedIDs[i['id']]=True
            pinnedPosts.append((i.get('pinRank',0),i['id'],i))

        for i in reversed(list(sorted(pinnedPosts))):
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i[2]))

        p = s.getDocumentsByType("post", limit=5,parent=postID)
        for i in p:
            #The index assumption, jump straight to the index when we detect a very short post
            #with at least one child
            if indexAssumption and len(document.get('body',''))<140:
                self.gotoStreamPosts(stream,parent=postID,indexAssumptionWasUsed=True)
                return

            #Avoid showing pinned twice
            if not i['id'] in pinnedIDs:
                self.streamEditPanel.add_widget(self.makePostWidget(stream,i))


        
        #Don't pollute history with timewaasters for every refresh
        #Do the adding to the back stack after the check for children so that
        #We don't create a back entry if we use the index assumption
        if not noBack:
            def goHere():
                self.gotoStreamPost(stream, postID)
            self.backStack.append(goHere)
            self.backStack = self.backStack[-50:]



        commentsbuttons = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True,size_hint=(1,None))
        
        #This button takes you to the full comments manager
        def goToCommentsPage(*a):
            def f(x):
                if x:
                    self.unsavedDataCallback=None
                    self.currentPageNewRecordHandler=None
                    self.gotoStreamPosts(stream,parent=postID)
            if self.unsavedDataCallback:
                self.askQuestion("Discard changes?","yes",f)
            else:
                f('yes')

        btn1 = Button(text='Comments')
        btn1.bind(on_release=goToCommentsPage)
        commentsbuttons.add_widget(btn1)




      #This button takes you to the full comments manager
        def writeComment(*a):
            def f(x):
                if x:
                    self.unsavedDataCallback=None
                    self.currentPageNewRecordHandler=None
                    self.gotoNewStreamPost(stream,postID)
            if self.unsavedDataCallback:
                self.askQuestion("Discard changes?","yes",f)
            else:
                f('yes')

        btn1 = Button(text='Add')
        btn1.bind(on_release=writeComment)
        commentsbuttons.add_widget(btn1)


        self.streamEditPanel.add_widget(commentsbuttons)
  
        self.screenManager.current = "EditStream"

        def onNewRecord(db,r,sig):
            if db is daemonconfig.userDatabases[stream]:
                if r.get('parent','')==document.get('parent','') and r['type']=="post":
                    if not self.unsavedDataCallback:
                        self.gotoStreamPost(stream,postID,noBack=True)

                #Not sourcetext==we check to make sure we have a static copy of the text and we are not
                #editing it at the momemt
                elif sourceText[0] and document['id'] in r.get("parent",''):
                    backup = newp.text
                    #Rerender on incoming table records 
                    newp.text = tables.renderPostTemplate(daemonconfig.userDatabases[stream],postID, sourceText[0])

                    #We could have started editing in that millisecond window. Restore the source text so we don't overwrite it with the rendered text
                    if not sourceText[0]:
                        newp.text=backup

        self.currentPageNewRecordHandler = onNewRecord

    def gotoStreamPosts(self, stream, startTime=0, endTime=0, parent='', search='',noBack=False,orphansMode=False,indexAssumptionWasUsed=False):
        "Handles both top level stream posts and comments, and searches.  So we can search comments if we want."

        #We MUST ensure we clear this when leaving the page. Pst widgets do ut for us.
        #If we do not, incomimg records may randomly take us back here.
        #We need a better way of handling this!!!!!
        self.currentPageNewRecordHandler=None
        self.streamEditPanel.clear_widgets()
       

        s = daemonconfig.userDatabases[stream]
        if not parent:
            if orphansMode:
                self.streamEditPanel.add_widget(MDToolbar(title="Unreachable Records in "+stream))
            else:
                self.streamEditPanel.add_widget(MDToolbar(title="Feed for "+stream))
        else:
            parentDoc=daemonconfig.userDatabases[stream].getDocumentByID(parent)
            self.streamEditPanel.add_widget(MDToolbar(title=stream))
            #Disable index assumption so we can always actually go to the parent post instead of getting stuck.
            self.streamEditPanel.add_widget(self.makePostWidget(stream,parentDoc,indexAssumption=False))


        topbar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True,size_hint=(1,None))

        def upOne(*a):
            if parent:
                #Treat as a 'view' of the parent doc so that up one level actually goes one abovet the parent for this comment
                #page
                if parentDoc.get('parent',''):
                    self.gotoStreamPost(stream,parentDoc.get('parent',''))
                    return
                self.gotoStreamPosts(stream)
            else:
                self.editStream(stream)

        btn1 = Button(text='Up')

        btn1.bind(on_press=upOne)
      
        topbar.add_widget(btn1)

        topbar.add_widget(self.makeBackButton(0.29))



        if not noBack:
            def goHere():
                self.gotoStreamPosts( stream, startTime, endTime, parent,search)
            self.backStack.append(goHere)
            self.backStack = self.backStack[-50:]


        def write(*a):
            self.currentPageNewRecordHandler=None
            self.gotoNewStreamPost(stream,parent)

        if s.writePassword and not orphansMode:
            btn1 = Button(text='Write')

            btn1.bind(on_press=write)
            
            topbar.add_widget(btn1)

        self.streamEditPanel.add_widget(topbar)





        if parent:
            parentPath=s.getDocumentByID(parent)['id']

        else:
            parentPath=''
        
        if orphansMode:
            parentPath=None

        if not search:
            if startTime:
                #If we have a start time the initial search has to be ascending or we will just always get the very latest.
                #So then we have to reverse it to give a consistent ordering
                p = list(reversed(list(s.getDocumentsByType("post",startTime=startTime, endTime=endTime or 10**18, limit=20,descending=False,orphansOnly=orphansMode,parent=parentPath))))
            else:
                p = list(s.getDocumentsByType("post",startTime=startTime, endTime=endTime or 10**18, limit=20,orphansOnly=orphansMode,parent=parentPath))
        else:
            #Search always global
            p=list(s.searchDocuments(search,"post",startTime=startTime, endTime=endTime or 10**18, limit=20))

        if p:
            newest=p[0]['time']
            oldest=p[-1]['time']
        else:
            newest=endTime
            oldest=startTime

        
        #If everything fits on one page we do not need to have the nav buttons
        if len(p)>=20 or startTime or endTime:
            #The calender interactions are based on the real oldest post in the set

            #Let the user see older posts by picking a start date to stat showing from.
            startdate = Button(text=time.strftime("(%a %b %d, '%y)",time.localtime(oldest/10**6)))

        
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

            pagebuttons = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True,size_hint=(1,None))

            #Thids button advances to the next newer page of posts.
            newer = Button(text='>>')
            def f2(*a):
                self.gotoStreamPosts(stream, newest,parent=parent)            

            newer.bind(on_release=f2)

            #Thids button advances to the next newer page of posts.
            older = Button(text='<<')
            def f3(*a):
                self.gotoStreamPosts(stream, endTime=oldest,parent=parent)            

            older.bind(on_release=f3)

            pagebuttons.add_widget(older)
            pagebuttons.add_widget(startdate)
            pagebuttons.add_widget(newer)      
            self.streamEditPanel.add_widget(pagebuttons)



        if not orphansMode and ((not parent) or search):

            searchBar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True,size_hint=(1,None))

            searchQuery = MDTextField(size_hint=(0.68,None),multiline=False, text=search)
            searchButton = MDRoundFlatButton(text="Search")
    

            searchBar.add_widget(searchQuery)
            searchBar.add_widget(searchButton)



            def doSearch(*a):
                self.gotoStreamPosts(stream, startTime, endTime, parent,searchQuery.text.strip())
            searchButton.bind(on_release=doSearch)


            self.streamEditPanel.add_widget(searchBar)


                
     




        pinnedIDs={}
        pinnedPosts = []

        #Get nonzero pin rank
        p1 = s.getDocumentsByType("post",parent=parentPath,extraFilters=pinRankFilter)
        for i in p1:
            pinnedIDs[i['id']]=True
            pinnedPosts.append((i.get('pinRank',0),i['id'],i))

        for i in reversed(list(sorted(pinnedPosts))):
            self.streamEditPanel.add_widget(self.makePostWidget(stream,i[2]))

        for i in p:
            #Avoid showing pinned twice
            if not i['id'] in pinnedIDs:
                self.streamEditPanel.add_widget(self.makePostWidget(stream,i))
                pass

        
        def onNewRecord(db,r,sig):
            if db is daemonconfig.userDatabases[stream]:
                if r.get('parent','')==parent and r['type']=="post":
                   self.gotoStreamPosts(stream,startTime,endTime,parent, search,noBack=True)
        if not orphansMode:
            self.currentPageNewRecordHandler = onNewRecord

        self.screenManager.current = "EditStream"

    def makePostWidget(self,stream, post,indexAssumption=True):
        "Index assumption allows treating very short posts as indexes that gfo straight to the comment page"
        def f(*a):
            def f2(d):
                if d:
                    self.currentPageNewRecordHandler=None
                    self.unsavedDataCallback = False
                    self.gotoStreamPost(stream,post['id'],indexAssumption=indexAssumption)

            # If they have an unsaved post, ask them if they really want to leave.
            if self.unsavedDataCallback:
                self.askQuestion("Discard unsaved data?", 'yes', cb=f2)
            else:
                f2(True)

        #Chop to a shorter length, then rechop to even shorter, to avoid cutting off part of a long template and being real ugly.
        body=post.get('body',"?????")[:240].strip()
        body = tables.renderPostTemplate(daemonconfig.userDatabases[stream], post['id'], body, 4096)
        body=body[:140].replace("\r",'').replace("\n",'_NEWLINE',2).replace("\n","").replace("_NEWLINE","\r\n")

        #Split on blank line
        body=body.split('\r\n\r\n')[0].split('\n#')[0]

        btn=Button(text=post.get('title',"?????") + " "+time.strftime('(%a %b %d, %Y)',time.localtime(post.get('time',0)/10**6)), on_release=f)
        
        if (not post.get('body','').strip()) and ((not post.get('icon','')) or not post['icon'].strip()):
            return btn

        l = BoxLayout(adaptive_height=True,orientation='vertical',size_hint=(1,None))

        
        l.add_widget(btn)
        l2 = BoxLayout(adaptive_height=True,orientation='horizontal',size_hint=(1,None))
        

        src = os.path.join(directories.assetLibPath, post.get("icon","INVALID"))
        useIcon=False
        img = Image(size_hint=(0.18,1))
        img.size_hint_min_y=cm(1.5)   
        img.source= src
        l2.add_widget(img)
        l.image = img
        bodyText =Label(text=body.strip(),size_hint=(0.78,1),valign="top")
        l.body = bodyText
    
        def setWidth(obj,w):
            bodyText.text_size=(w-(img.width+4)),None
            bodyText.texture_update()
            bodyText.size = (bodyText.texture_size[0],max(bodyText.texture_size[1],cm(1.5)))
            l2.minimum_height=max(bodyText.texture_size[1],cm(1.5))
            l.minimum_height=l2.height+btn.height+4

        l2.bind(width=setWidth)

        #w = MDTextField(text=body, multiline=True,size_hint=(1,0.5),mode="rectangle",readonly=True)
        w=bodyText
        
        l2.add_widget(w)
        l.add_widget(l2)

    

        return l

    def gotoNewStreamPost(self, stream,parent=''):
        self.currentPageNewRecordHandler=None
        self.streamEditPanel.clear_widgets()
        self.streamEditPanel.add_widget(MDToolbar(title="Posting in: "+stream+"(Autosave on)"))

        self.streamEditPanel.add_widget(self.makeBackButton())
        
        def goHere():
            self.gotoNewStreamPost(stream,parent)
        self.backStack.append(goHere)
        self.backStack = self.backStack[-50:]

        newtitle = MDTextField(text='',mode='fill', font_size='22sp')

        newp = MDTextFieldRect(text='', multiline=True,size_hint=(0.68,None))

        def savepost(*a,goto=False):
            if newp.text:
                with daemonconfig.userDatabases[stream]:
                    import uuid
                    id = str(uuid.uuid4())
                    d = {'body': newp.text,'title':newtitle.text,'type':'post','documentTime':int(time.time()*10**6)}
                    if parent:
                        d['parent'] = parent

                    daemonconfig.userDatabases[stream].setDocument(d)
                    daemonconfig.userDatabases[stream].commit()

                self.unsavedDataCallback=None
                if goto:
                    try:
                        if parent:
                            self.gotoStreamPost(stream,parent)
                        else:
                            self.gotoStreamPost(stream,id)
                    except:
                        logging.exception("Error going to root of where we just put comment")
                        self.goBack()

        def post(*a):
            savepost(goto=True)

        self.unsavedDataCallback=post

        btn1 = Button(text='Post!')
        btn1.bind(on_release=post)

        self.streamEditPanel.add_widget(newtitle)

        self.streamEditPanel.add_widget(MDToolbar(title="Post Body"))

        self.streamEditPanel.add_widget(newp)
        self.streamEditPanel.add_widget(btn1)



    def gotoBookmark(self,b):
        bm = daemonconfig.getBookmarks()[b]
        for i in daemonconfig.userDatabases:
            if bm[0]==daemonconfig.userDatabases[i].filename:
                self.gotoStreamPost(i,bm[1])


    def makePostMetaDataPage(self):
        "Prettu much just an empty page filled in by the specific goto functions"

        screen = Screen(name='PostMeta')

        layout = BoxLayout(orientation='vertical', spacing=10,size_hint=(1, 1),adaptive_height= True)
        screen.add_widget(layout)


        self.postMetaPanelScroll = ScrollView(size_hint=(1, 1))
        self.postMetaPanel = BoxLayout(
            orientation='vertical', spacing=5,adaptive_height= True,size_hint=(1, 1))
        self.postMetaPanel.bind(
            minimum_height=self.postMetaPanel.setter('height'))

        self.postMetaPanelScroll.add_widget(self.postMetaPanel)

        layout.add_widget(self.postMetaPanelScroll)


        return screen

    def gotoPostMetadata(self, stream, docID, document, autosavecallback):
        "Handles both top level stream posts and comments"
        self.postMetaPanel.clear_widgets()
        s = document

        self.postMetaPanel.add_widget((MDToolbar(title=s.get('title','Untitled'))))

        topbar = BoxLayout(orientation="horizontal",spacing=10,adaptive_height=True,size_hint=(1, None))
        
        def goBack(*a):
            self.screenManager.current= "EditStream"
        btn =  Button( text="Go Back")
        btn.bind(on_release=goBack)
        self.postMetaPanel.add_widget(btn)
    
     
        location = Button( text="Location: "+str(s.get("lat",0))+','+str(s.get('lon',0)) )

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
                            self.unsavedDataCallback=autosavecallback
                    
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

        icon = Button( text="Icon: "+os.path.basename(s.get("icon",'')) )
        def promptSet(*a):
            from .kivymdfmfork import MDFileManager
          
            def f(selection):
                s['icon'] = selection[len(directories.assetLibPath)+1:] if selection else ''
                s['time']=None
                self.unsavedDataCallback=autosavecallback
                icon.text = "Icon: "+os.path.basename(s.get("icon",''))

                #Immediately update the image as seen in the post editor window

                src = os.path.join(directories.assetLibPath, s.get("icon","INVALID"))
                if os.path.exists(src):
                    self.currentlyViewedPostImage.source = src
                self.openFM.close()
            
            def e(*a):
                self.openFM.close()

            #Autocorrect had some fun with the kivymd devs
            try:
                self.openFM= MDFileManager(select_path=f,preview=True,exit_manager=e)
            except:
                try:
                    self.openFM= MDFileManager(select_path=f,previous=True,exit_manager=e)
                except:
                    self.openFM= MDFileManager(select_path=f,exit_manager=e)

            self.openFM.show(os.path.join(directories.assetLibPath,'icons'))

            
        icon.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(icon)





        clearicon = Button( text="Clear Icon")
        def promptSet(*a):
            from .kivymdfmfork import MDFileManager
          
            def f(x):
                if x=='yes':
                    s['icon'] = selection[len(directories.assetLibPath)+1:] if selection else ''
                    s['time']=None
                    self.unsavedDataCallback=autosavecallback
                    icon.text = "Icon: "+os.path.basename(s.get("icon",''))

            self.askQuestion("Remove Icon?",'yes',f)
            
        clearicon.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(clearicon)


        idButton = Button( text="Show Post ID")
        def promptSet(*a):
            self.askQuestion("You can't change this",docID)
            
        idButton.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(idButton)



        parentButton = Button( text="Set post parent")
        def promptSet(*a):
            def f(p):
                if not p is None:
                    #Stop the obvious case of the loops
                    if p.strip()==docID:
                        parentButton.text="Parent:cannot be self"
                        return

                    if p:
                        r, a =daemonconfig.userDatabases[stream].getDocumentByID(p.strip(), returnAllAncestors=True)

                        #Detect common scenarios where one does not want to move a post.
                        if not r:
                            parentButton.text="Parent:nonexistent"
                            return
                        if not r['type']=='post':
                            parentButton.text="Parent:is not valid post"
                            return
                        if r.get('leafNode',False):
                            parentButton.text="Parent:Post does not allow children"
                            return
                        if 'autoclean' in r:
                            parentButton.text="Parent:Parent post volatile, refusing to move"
                            return
                        if docID in a:
                            parentButton.text="Parent:Cannot be own ancestor"
                            return

                    parentButton.text="Set post parent"

                    s['parent']=p.strip()
                    #Mark as intentional move, else it would unintentionally snap back.
                    s['moveTime']= int(time.time()*10**6)
                    self.unsavedDataCallback=autosavecallback

            self.askQuestion("Move record to this post ID?",s.get('parent',''),f)
            
        parentButton.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(parentButton)


        bmButton = Button( text="Bookmark")
        def promptSet(*a):
            def f(p):
                if not p is None:
                    daemonconfig.setBookmark(p,daemonconfig.userDatabases[stream].filename, docID )
            self.askQuestion("Bookmark Name?",s['title'],f)
            
        bmButton.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(bmButton)


        #Used to set the pin rank of a post
        prButton = Button( text="Pin Rank:"+str(s.get('pinRank') or 0))
        def promptSet(*a):
            def f(p):
                if not p is None:
                    try:
                        s['pinRank']=int(p)
                        self.unsavedDataCallback=autosavecallback
                    except:
                        pass

                    prButton.text="Pin Rank:"+str(s.get('pinRank') or 0)
            self.askQuestion("Pin Rank?",str(s.get('pinRank') or 0),f)
            
        prButton.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(prButton)



        export = Button( text="Export Raw Data")

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
                    logging.info("Exporting data to:"+selection)
                    with open(selection,'w') as f:
                        f.write(json.dumps(l, sort_keys=True,indent=2))
                    self.openFM.close()

             #Autocorrect had some fun with the kivymd devs
            self.openFM= MDFileManager(select_path=f,save_mode=((s.get('title','') or 'UntitledPost')+'.json'))
            self.openFM.show(directories.externalStorageDir or directories.settings_path)


            
        export.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(export)
        self.postMetaPanel.add_widget(Label(text="Exports this post, all descendants,\nand all ancestors in JSON format\nthat can be imported into\nanother stream.",size_hint=(1,None)))



        export = Button( text="Export TOML")

        def promptSet(*a):
            from .kivymdfmfork import MDFileManager


            def f(selection):
                if selection:
                    if not selection.endswith(".toml"):
                        selection=selection+".toml"
                
                    try:
                        #Needed for android
                        if not "com.eternityforest" in selection:
                            self.getPermission('files')
                    except:
                        logging.exception("cant ask permission")
                    data = daemonconfig.userDatabases[stream].exportRecordSetToTOML([docID])

                    logging.info("Exporting data to:"+selection)
                    with open(selection,'w') as f:
                        f.write(data)
                    self.openFM.close()

             #Autocorrect had some fun with the kivymd devs
            self.openFM= MDFileManager(select_path=f,save_mode=((s.get('title','') or 'UntitledPost')+'.toml'))
            self.openFM.show(directories.externalStorageDir or directories.settings_path)


            
        export.bind(on_release=promptSet)
        self.postMetaPanel.add_widget(export)


        





        def burn(*a):
            def reallyBurn(v):
                if v==docID:
                    with daemonconfig.userDatabases[stream]:
                        daemonconfig.userDatabases[stream].setDocument({'type':'null','id':docID,'direct':True,'burn':True})
                        daemonconfig.userDatabases[stream].commit()
                        self.unsavedDataCallback=None
                        self.currentPageNewRecordHandler=None
                    self.gotoStreamPosts(stream)
            self.askQuestion("BURN post permanently on all nodes?", docID, reallyBurn)


        if daemonconfig.userDatabases[stream].writePassword:
            btn1 = Button(text='Burn')
            btn1.bind(on_release=burn)
            self.postMetaPanel.add_widget(btn1)
            self.postMetaPanel.add_widget(self.saneLabel("Burning a post is less\n likely to leave behind recoverable\nchild comments for spies than just deleting.\nHowever it has a chance of also\nremoving child posts that *used*\nto be stored under the post\nbut were moved.",  self.postMetaPanel))
            self.postMetaPanel.add_widget(self.saneLabel("Both methods reliably delete this specific post.",  self.postMetaPanel))