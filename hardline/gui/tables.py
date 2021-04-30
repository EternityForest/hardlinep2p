import configparser
from hardline import daemonconfig
from .. import daemonconfig, hardline


import configparser,logging

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
from .. import drayerdb, cidict

from kivymd.uix.picker import MDDatePicker


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
                import simpleeval
                simpleeval.POWER_MAX = 512
                replacements[i.group()] = simple_eval(i.group(1), names= ctx, functions=makePostRenderingFuncs(limit))
            except Exception as e:
                logging.exception("Error in template expression in a post")
                replacements[i.group()] = e
    
    for i in replacements:
        text = text.replace(i, str(replacements[i]))
    
    return text



class TablesMixin():

    def gotoTableView(self, stream, parent='', search=''):
        "Data records can be attatched to a post."
        self.streamEditPanel.clear_widgets()
        s = daemonconfig.userDatabases[stream]
        parentDoc=daemonconfig.userDatabases[stream].getDocumentByID(parent)
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
                if daemonconfig.userDatabases[stream].getDocumentByID(id):
                    self.gotoStreamRow(stream, id)
                    return
            else:
                import uuid
                id=str(uuid.uuid4())
            
            x = daemonconfig.userDatabases[stream].getDocumentsByType("row.template", parent=parent,limit=1) 
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

        document = document or daemonconfig.userDatabases[stream].getDocumentByID(postID)
        if 'type' in document and not document['type'] == 'row':
            raise RuntimeError("Document is not a row")
        document['type']='row'

        title = Label(text=document.get("name",''),font_size='22sp')

        #Our default template if none exists
        #Give it a name because eventually we may want to have multiple templates.
        #Give it an ID so it can override any existing children of that template. 
        oldTemplate= {'type':"row.template",'parent':document['parent'], 'name': 'default', 'id':document['parent']+".rowtemplate.default"}

        for i in daemonconfig.userDatabases[stream].getDocumentsByType("row.template", parent=document['parent'],limit=1):
            oldTemplate=i

        template= template or oldTemplate


        def post(*a):
            with daemonconfig.userDatabases[stream]:
                #Make sure system knows this is not an old document
                try:
                    del document['time']
                except:
                    pass
                daemonconfig.userDatabases[stream].setDocument(document)

                #If the template has changed, that is how we know we need to save template changes at the same time as data changes
                if not template.get('time',0)==oldTemplate.get('time',1):
                    daemonconfig.userDatabases[stream].setDocument(template)
                daemonconfig.userDatabases[stream].commit()
                self.unsavedDataCallback=None

            self.gotoStreamPosts(stream)
      
        btn1 = Button(text='Save Changes',
                      size_hint=(0.48, None), font_size="14sp")
        btn1.bind(on_release=post)


        self.streamEditPanel.add_widget(title)
        
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
            self.askQuestion("Delete table row permanently on all nodes?", postID, reallyDelete)

        btn1 = Button(text='Delete',
                      size_hint=(0.48, None), font_size="14sp")
        btn1.bind(on_release=delete)

        if daemonconfig.userDatabases[stream].writePassword:
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