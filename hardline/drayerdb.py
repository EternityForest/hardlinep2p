

# This file manages kaithem's native SQLite document database.

# There is one table called Document

from hashlib import blake2b
import logging
import shutil
import websockets
import asyncio
import sqlite3
import time
import json
import uuid as uuidModule
import random
import configparser
import os
import libnacl
import base64
import struct
import uuid
import traceback

# from scullery import messagebus

# class DocumentView():
#     def __init__(self,database,uuid):
#         self.database = database
#         self.uuid = uuid

#     def __getitem__(self,key):

#         #Look for a prop record first, then look for an actual key in that document's table
#         cur = self.database.conn.cursor()
#         cur.execute("SELECT document FROM document WHERE parent=? AND type=? AND name=?", (self.uuid,".prop",key))
#         x= curr.fetchone()
#         if x:
#             return x[0]


#         cur = self.database.conn.cursor()
#         cur.execute("SELECT (document,type) FROM document WHERE uuid=?", (self.uuid,))
#         x= curr.fetchone()
#         if x:
#             if key in x[0]:
#                 return x[0][key]

import socket
import re
import threading
import weakref
import uuid
import time
import struct

from websockets import server

from .cidict import CaseInsensitiveDict

databaseBySyncKeyHash = weakref.WeakValueDictionary()


class Session():
    def __init__(self, isClientSide):
        self.alreadyDidInitialSync = False
        self.isClientSide = isClientSide
        # When you send the client all new changes
        # Set this flag to say what the most recent messaage is, so you can then
        # Get all more recent messages than that.
        self.lastResyncFlushTime = 0

        # We don't actually know who the other end is till we get a message.
        self.remoteNodeID = None


async def DBAPI(websocket, path):
    session = Session(False)
    try:
        a = await websocket.recv()

        databaseBySyncKeyHash[a[:16]].dbConnect()

        await websocket.send(databaseBySyncKeyHash[a[:16]].handleBinaryAPICall(a, session))
        session.socket = websocket
        databaseBySyncKeyHash[a[:16]].subscribers[time.time()] = session

        db = databaseBySyncKeyHash[a[:16]]

        while not websocket.closed:
            try:
                a = await asyncio.wait_for(websocket.recv(), timeout=5)
                await websocket.send(databaseBySyncKeyHash[a[:16]].handleBinaryAPICall(a, session))
            except (TimeoutError, asyncio.TimeoutError):
                pass

            if db.lastChange > session.lastResyncFlushTime:
                pass

    except websockets.exceptions.ConnectionClosedOK:
        pass


start_server = None

serverLocalPorts = [0]

slock = threading.RLock()

def stopServer():
    global start_server
    if start_server:
        try:
            start_server.close()
        except:
            logging.exception()
        start_server=None

wsloop = None
def startServer(port):
    if not port:
        port = int((random.random()*10000)+10000)
    global start_server,wsloop
    stopServer()

    #Icky hack, detect and restore the current event loop.
    #We want to make a custom loop just for the server so we have to set it as the main one.
    try:
        l = asyncio.get_event_loop()
    except:
        l=None

    wsloop = asyncio.new_event_loop()
    asyncio.set_event_loop(wsloop)
    s = websockets.serve(DBAPI, "localhost", port)
    serverLocalPorts[0] = port

    async def f():
        with slock:
            global start_server
            with slock:
                start_server = await s
            await start_server.wait_closed()
            #Stop when the server is closed.
            asyncio.get_event_loop().stop()
        
    def f2():
        #Pass off the loop to the new thread, we won't touch it after this
        asyncio.set_event_loop(wsloop)
        asyncio.get_event_loop().run_until_complete(f())
    

    # DB will eventually handle consistency by itself.
    t = threading.Thread(
        target=f2, daemon=True)
    t.start()

    for i in range(1000):
        if not start_server:
            time.sleep(0.01)
        else:
            break
    if not start_server.sockets:
        raise RuntimeError("Server not running")
    #Terrible stuff here. We are going to try to restore the event loop.

    if l:
        asyncio.set_event_loop(l)
    time.sleep(3)


def jsonEncode(d):
    return json.dumps(d, sort_keys=True, indent=0, separators=(',', ':'))


nodeIDSecretPath = "~/.drayerdb/config/nodeid-secret"


def readNodeID():
    # # Using challenge response, nodes can identify
    if not os.path.exists(os.path.expanduser(nodeIDSecretPath)):
        os.makedirs(os.path.dirname(os.path.expanduser(
            nodeIDSecretPath)), 0o700, exist_ok=True)
        with open(os.path.expanduser(nodeIDSecretPath), 'w') as f:
            f.write(base64.b64encode(os.urandom(32)).decode("utf8"))

    with open(os.path.expanduser(nodeIDSecretPath)) as f:
        return base64.b64decode(f.read().strip())


# unauthorized messageds cannot contain new records or updates to them.
# Authorized messages must be signed with the stream's current private key.
MESSAGE_TYPE_AUTHORIZED = 1
MESSAGE_TYPE_NORMAL = 2


class DocumentDatabase():
    def __init__(self, filename, keypair=None, servable=True):

        self.filename = os.path.abspath(filename)
        self.threadLocal = threading.local()

        # A hint to know when to do real rescan
        self.lastChange = 0

        self.lock = threading.RLock()

        # Websockets that are subscribing to us.
        self.subscribers = weakref.WeakValueDictionary()

        self.dbConnect()

        self.inTransaction=0
       

        self.config = configparser.ConfigParser(dict_type=CaseInsensitiveDict)

        if os.path.exists(filename+".ini"):
            self.config.read(filename+".ini")

        self.threadLocal.conn.row_factory = sqlite3.Row
        with self:
            # self.threadLocal.conn.execute("PRAGMA wal_checkpoint=FULL")
            self.threadLocal.conn.execute("PRAGMA secure_delete = off")

            # Yep, we're really just gonna use it as a document store like this.
            self.threadLocal.conn.execute(
                '''CREATE TABLE IF NOT EXISTS document (rowid integer primary key, json text, signature text, arrival integer, localinfo text)''')

            self.threadLocal.conn.execute('''CREATE TABLE IF NOT EXISTS meta
                (key text primary key, value  text)''')

            self.threadLocal.conn.execute('''CREATE TABLE IF NOT EXISTS peers
                (peerID text primary key, lastArrival integer, horizon integer, info text)''')

            # To keep indexing simple and universal, it only works on four standard properties. tags, title, descripion, body
            self.threadLocal.conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(tags, title, description, body, content='')''')

            self.threadLocal.conn.execute(
                '''CREATE INDEX IF NOT EXISTS document_parent ON document(json_extract(json,"$.parent")) WHERE json_extract(json,"$.parent") IS NOT null ''')
            self.threadLocal.conn.execute(
                '''CREATE INDEX IF NOT EXISTS document_link ON document(json_extract(json,"$.link")) WHERE json_extract(json,"$.link") IS NOT null''')
            self.threadLocal.conn.execute(
                '''CREATE INDEX IF NOT EXISTS document_name ON document(json_extract(json,"$.name"))''')
            self.threadLocal.conn.execute(
                '''CREATE INDEX IF NOT EXISTS document_id ON document(json_extract(json,"$.id"))''')
            self.threadLocal.conn.execute(
                '''CREATE INDEX IF NOT EXISTS document_type ON document(json_extract(json,"$.type"))''')
            self.threadLocal.conn.execute(
                '''CREATE INDEX IF NOT EXISTS document_arrival ON document(arrival)''')

            self.threadLocal.conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS search_index AFTER INSERT ON document BEGIN
                INSERT INTO search(rowid, tags,title, description, body) VALUES (new.rowid, IFNULL(json_extract(new.json,"$.tags"), ""), IFNULL(json_extract(new.json,"$.title"), ""), IFNULL(json_extract(new.json,"$.description"), "") , IFNULL(json_extract(new.json,"$.body"), ""));
                END;
                """)

            self.threadLocal.conn.execute(
                """   CREATE TRIGGER IF NOT EXISTS search_delete AFTER DELETE ON document BEGIN
                INSERT INTO search(search, rowid, tags, title,description, body) VALUES ('delete', old.rowid, IFNULL(json_extract(old.json,"$.tags"), ""), IFNULL(json_extract(old.json,"$.title"), ""), IFNULL(json_extract(old.json,"$.description"), ""), IFNULL(json_extract(old.json,"$.body"), ""));
                END;""")

            self.threadLocal.conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS search_update AFTER UPDATE ON document BEGIN
                INSERT INTO search(search, rowid, tags, title,description, body) VALUES ('delete', old.rowid, IFNULL(json_extract(old.json,"$.tags"), ""),IFNULL(json_extract(old.json,"$.title"), ""), IFNULL(json_extract(old.json,"$.description"), ""), IFNULL(json_extract(old.json,"$.body"), ""));
                INSERT INTO search(rowid, tags, title,description, body) VALUES (new.rowid, IFNULL(json_extract(new.json,"$.tags"), ""), IFNULL(json_extract(new.json,"$.title"), ""), IFNULL(json_extract(new.json,"$.description"), ""), IFNULL(json_extract(new.json,"$.body"), ""));
                END;
                """
            )




        # If a db is deleted and recreated at the same file path, this means we have a chance of
        # detecting that in the remote node by making the localNodeVK different.

        # The point of this is to uniquiely identify a DB instance so that we always know what records we have or don't have.
        self.nodeIDSeed = self.getMeta("nodeIDSeed")
        if not self.nodeIDSeed:
            self.nodeIDSeed = os.urandom(24).hex()
            self.setMeta("nodeIDSeed",self.nodeIDSeed)

        

        if not keypair:
            if 'Sync' not in self.config:
                vk, sk = libnacl.crypto_sign_keypair()
                self.config.add_section('Sync')
                self.config.set('Sync', 'syncKey',
                                base64.b64encode(vk).decode('utf8'))
                self.config.set('Sync', 'writePassword',
                                base64.b64encode(sk).decode('utf8'))
                self.saveConfig()

            self.syncKey = self.config.get('Sync', 'syncKey', fallback=None)
            self.writePassword = self.config.get(
                'Sync', 'writePassword', fallback='')

        else:
            self.syncKey = base64.b64encode(keypair[0]).decode()
            self.writePassword = base64.b64encode(keypair[1]).decode()
        
        # Deterministically generate a keypair that we will use to sign all correspondance
        # writePassword has to be a part of it because nodes that have it are special and we want it
        #to be harder to fake one, plus adding one should effectively make it a new node so we know
        #to check things we couldn't trust before.
        self.localNodeVK, self.localNodeSK = libnacl.crypto_sign_seed_keypair(
            libnacl.crypto_generichash((os.path.basename(filename)+self.nodeIDSeed+self.writePassword).encode("utf8"), readNodeID()))


        if self.syncKey and servable:
            databaseBySyncKeyHash[libnacl.crypto_generichash(
                libnacl.crypto_generichash(base64.b64decode(self.syncKey)))[:16]] = self
        self.serverURL=None
        self.syncFailBackoff =1
        self.useSyncServer(self.config.get('Sync', 'server', fallback=None))

    def useSyncServer(self, server, permanent=False):
        with self.lock:
            if server == self.serverURL:
                return
            if permanent:
                self.config.set('Sync', 'serverURL', server)

            self.serverURL = server
            if not server:
                return

            t = threading.Thread(target=self.serverManagerThread, daemon=True)
            t.start()

    def serverManagerThread(self):
        oldServerURL = self.serverURL
        loop = asyncio.new_event_loop()


        while oldServerURL == self.serverURL:
            try:
                if loop.run_until_complete(self.openSessionAsClient()):
                    self.syncFailBackoff = 1
            except:
                logging.exception("Error in DB Client")
                logging.info(traceback.format_exc())

            self.syncFailBackoff *= 2
            self.syncFailBackoff = min(self.syncFailBackoff, 5*60)

            #Small increments so we can interrupt it
            for i in range(5*60):
                if i> self.syncFailBackoff:
                    break
                time.sleep(1)

        loop.stop()
        loop.close()

    async def openSessionAsClient(self):

        if not self.serverURL:
            return 1

        session = Session(True)

        oldServerURL = self.serverURL

        async with websockets.connect(self.serverURL) as websocket:
            try:

                self.dbConnect()

                # Empty message so they know who we are
                await websocket.send(self.encodeMessage({}))

                while not websocket.closed:
                    try:
                        a = await asyncio.wait_for(websocket.recv(), timeout=5)
                        await websocket.send(self.handleBinaryAPICall(a, session))

                        # The initial request happens after we know who they are
                        if session.remoteNodeID and not session.alreadyDidInitialSync:
                            r = {}
                            cur = self.threadLocal.conn.cursor()
                            cur.execute(
                                "SELECT lastArrival FROM peers WHERE peerID=?", (base64.b64encode(session.remoteNodeID),))

                            c = cur.fetchone()
                            if c:
                                c = c[0]
                            else:
                                c = 0
                            # No falsy value allowed, that would mean don't get new arrivals
                            r['getNewArrivals'] = c or 1

                            session.alreadyDidInitialSync = True
                            await websocket.send(self.encodeMessage(r))

                    except (TimeoutError, asyncio.TimeoutError):
                        pass

                    if self.lastChange > session.lastResyncFlushTime:
                        pass

                    if not oldServerURL == self.serverURL:
                        return

            except websockets.exceptions.ConnectionClosedOK:
                pass
            except:
                return 0

    def dbConnect(self):
        if not hasattr(self.threadLocal, 'conn'):
            self.threadLocal.conn = sqlite3.connect(self.filename)

    def connectToServer(self, uri):
        "Open a new sync connection to a server."
        async def f(self):
            async with websockets.connect(uri) as websocket:
                name = input("What's your name? ")

                await websocket.send(name)
                logging.info(f"> {name}")

                greeting = await websocket.recv()
                logging.info(f"< {greeting}")

        asyncio.create_task(f)

    def _checkIfNeedsResign(self,i):
        "Check if we need to redo the sig on a record,sig pair because the key has changed.  Return sig, old sig if no correction needed"
        if not base64.b64decode(i[1])[24:].startswith(kdg):
            if self.writePassword:
                mdg = libnacl.crypto_generichash(i[0].encode())[:24]
                kdg = libnacl.crypto_generichash(base64.b64decode(self.syncKey))[:8]
                sig = libnacl.crypto_sign_detached(mdg, base64.b64decode(self.writePassword))
                signature = base64.b64encode(mdg+kdg+sig).decode()
                id = json.loads(i[0])['id']
                c2 = self.threadLocal.conn.execute('UPDATE document SET signature=? WHERE json_extract(json,"$.id")=?',(signature,id))

                return signature
            else:
                raise RuntimeError("Record needs resign but no key to do so is present")

        return i[1]

    def handleBinaryAPICall(self, a, sessionObject=None):
        # Process one incoming binary API message.  If part of a sesson, using a sesson objert enables certain features.

        # Get the key hint
        k = a[:16]
        a = a[16:]
        binTimestamp = a[:8]

        protectedData = a[8:]

        # The "public key" in this protocol is actually secret which means signed messages have to be
        # encrypted with an outer layer symmetric key derived from the public key,
        openingKey = libnacl.crypto_generichash(base64.b64decode(self.syncKey))
        keyHint = libnacl.crypto_generichash(openingKey)[:16]

        if k == keyHint:
            pass
        else:
            raise RuntimeError("Bad Key Hint")

        # First we decrypt the outer layer symmetric coding
        # Pad the timestamp to get the bytes.
        d = libnacl.crypto_secretbox_open(
            protectedData, binTimestamp+b'\0'*16, openingKey)

        remoteNodeID = d[:32]
        if sessionObject and sessionObject.remoteNodeID:
            if not remoteNodeID == sessionObject.remoteNodeID:
                raise RuntimeError("Remote ID changed in same session")
        d = d[32:]

        # Verify that it is from who it claims to be from
        a = libnacl.crypto_sign_open(d, remoteNodeID)

        # Timestamp bytes are repeated within the signed portion,
        # So we know when they generated the message
        tbytes = a[:8]
        t = struct.unpack("<Q", tbytes)[0]

        # reject very old stuff
        if t < (time.time()-3600)*1000000:
            return {}
        if sessionObject:
            sessionObject.remoteNodeID = remoteNodeID

        # Get the data
        d = a[8:]

        innerMessageType = d[0]
        d = d[1:]

        if innerMessageType == MESSAGE_TYPE_AUTHORIZED:
            # Now finally we decrypt the inner message.  By making this the inner,
            # We can perhaps have anonymizing servers that repackage it without knowing the write password.

            d = libnacl.crypto_sign_open(d, base64.b64decode(self.syncKey))
        elif innerMessageType == MESSAGE_TYPE_NORMAL:
            # These don't have the extra inner encryption and are currently the only type used for everything
            pass

        d = json.loads(d)

        r = {'records': []}

        cur = self.threadLocal.conn.cursor()
        cur.execute(
            "SELECT lastArrival,horizon FROM peers WHERE peerID=?", (base64.b64encode(remoteNodeID).decode(),))

        peerinfo = cur.fetchone()
        #How far back do we have knowledge of ther peer's records
        peerHorizon = time.time()*1000000
        isNewPeer = False
        if peerinfo:
            c = peerinfo[0]               
            peerHorizon=peerinfo[1]
        else:
            isNewPeer=True
            c = 0

        if sessionObject and not sessionObject.alreadyDidInitialSync:
           
            # No falsy value allowed, that would mean don't get new arrivals
            r['getNewArrivals'] = c or 1
            sessionObject.alreadyDidInitialSync = True


        if "getNewArrivals" in d:
            kdg = libnacl.crypto_generichash(base64.b64decode(self.syncKey))[:8]
            cur = self.threadLocal.conn.cursor()
            # Avoid dumping way too much at once
            cur.execute(
                "SELECT json,signature,arrival FROM document WHERE arrival>? LIMIT 100", (d['getNewArrivals'],))

            # Declares that there are no records left out in between this time and the first time we actually send
            r['recordsStartFrom'] = d['getNewArrivals']

            needCommit =False

            for i in cur:
                sig = i[1]
                #Detect if the record was signed with an old key and needs to be resigned
                if not base64.b64decode(i[1])[24:].startswith(kdg):
                    if self.writePassword:
                        sig = self._checkIfNeedsResign(i)
                        needCommit=True
                    else:
                        #Can't send stuff sent with old keys if we can't re sign, they will have to get from a source that can.
                        continue
                else:
                    signature = i[1]

                if not 'records' in r:
                    r['records'] = []
                logging.info(i)
                r['records'].append([i[0],sig,i[2]])

                sessionObject.lastResyncFlushTime = max(
                    sessionObject.lastResyncFlushTime, i[2])
            
            if needCommit:
                self.commit()

        needUpdatePeerTimestamp = False
        if "records" in d and d['records']:
            with self:
                for i in d['records']:
                
                    self.setDocument(i[0],i[1])
                    r['getNewArrivals'] = latest = i[2]
                    needUpdatePeerTimestamp = True

                if needUpdatePeerTimestamp:
                    # Set a flag saying that
                    cur = self.threadLocal.conn.cursor()

                    if not isNewPeer:
                        # If the recorded lastArrival is less than the incoming recordsStartFrom, it would mean that there is a gap in which records
                        # That we don't know about could be hiding.   Don't update the timestamp in that case, as the chain is broken.
                        # We can still accept new records, but we will need to request everything all over again starting at the breakpoint to fix this.
                        cur.execute("UPDATE peers SET lastArrival=? WHERE peerID=? AND lastArrival !=? AND lastArrival>=?",
                                    (latest,base64.b64encode(remoteNodeID).decode(), latest, d["recordsStartFrom"]))

                        #Now we do the same thing, but for the horizon.  If the tip of the new block pf records is later than or equal to the current
                        #horizon, we have a complete chain and we can set the horizon to recordsStartFrom, knowing that we have all records up to that point.
                        cur.execute("UPDATE peers SET horizon=? WHERE peerID=? AND horizon !=? AND horizon<=?",
                                    (d["recordsStartFrom"],base64.b64encode(remoteNodeID).decode(), d["recordsStartFrom"],  latest))
                    else:
                        # If the recorded lastArrival is less than the incoming recordsStartFrom, it would mean that there is a gap in which records
                        # That we don't know about could be hiding.   Don't update the timestamp in that case, as the chain is broken.
                        # We can still accept new records, but we will need to request everything all over again starting at the breakpoint to fix this.
                        cur.execute("INSERT INTO peers VALUES(?,?,?,?)",
                                    (base64.b64encode(remoteNodeID).decode(), latest, d["recordsStartFrom"],'{}'))


        return self.encodeMessage(r)

    def getUpdatesForSession(self, session):
        # Don't send anything till they have requested something, ohterwise we will just be sending nonsense they already have
        if session.lastResyncFlushTime:
            r = {}
            cur = self.threadLocal.conn.cursor()
            # Avoid dumping way too much at once
            cur.execute(
                "SELECT json,signature,arrival FROM document WHERE arrival>? LIMIT 100", (session.lastResyncFlushTime,))

            # Let the client know that there are no records left out in between the start of this message and the end of what they have
            r['recordsStartFrom'] = session.lastResyncFlushTime

            for i in cur:
                if not 'records' in r:
                    r['records'] = []
                r['records'].append([i[0], i[1]])

                session.lastResyncFlushTime = max(
                    session.lastResyncFlushTime, i[2])

            # We can of course just send nothing if there are no changes to flush.
            if r:
                return self.encodeMessage(r)

    def createBinaryWriteCall(self, r, sig=None):
        "Creates a binary command representing a request to insert a record."
        p = self.config.get('Sync', 'writePassword', fallback=None)
        if not p:
            if not sig:
                raise RuntimeError(
                    "You do not have the writePassword and this record is unsigned")

        d = {
            "writePassword": libnacl.crypto_generichash(p),
            "insertDocuments": [r, sig]
        }

        return self.encodeMessage(d, True)

    def encodeMessage(self, d, needWritePassword=False):
        "Given a JSON message, encode it so as to be suitable to send to another node"
        if needWritePassword and not self.writePassword:
            raise RuntimeError("You don't have a write password")

        pk = self.syncKey
        pk = base64.b64decode(pk)
        symKey = libnacl.crypto_generichash(pk)
        keyHint = libnacl.crypto_generichash(symKey)[:16]

        r = jsonEncode(d).encode('utf8')

        timeAsBytes = struct.pack("<Q", int(time.time()*1000000))


        #Currently we do not use the special authorized messages, relying on record-level sigs only.
        # if self.writePassword:
        #     data = bytes([MESSAGE_TYPE_AUTHORIZED]) + libnacl.crypto_sign(r,
        #                                             base64.b64decode(self.writePassword))
        # else:
        #     data = bytes([MESSAGE_TYPE_NORMAL]) + r

        data = bytes([MESSAGE_TYPE_NORMAL]) + r

        signed = libnacl.crypto_sign(timeAsBytes+data, self.localNodeSK)
        data = self.localNodeVK+signed

        r = libnacl.crypto_secretbox(data, timeAsBytes+b'\0'*16, symKey)

        return keyHint + timeAsBytes + r

    def createBinaryWriteCall(self, r, sig=None):
        "Creates a binary command representing arequest to insert a record."
        p = self.config.get('Sync', 'writePassword', fallback=None)
        if not p:
            if not sig:
                raise RuntimeError(
                    "You do not have the writePassword and this record is unsigned")

        d = {
            "writePassword": libnacl.crypto_generichash(p),
            "insertDocuments": [r, sig]
        }

        return self.encodeMessage(d)

    def getMeta(self, key):
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            "SELECT value FROM meta WHERE key=?", (key,))
        x = cur.fetchone()
        if x:
            return x[0]

    def setMeta(self, key, value):
        self.threadLocal.conn.execute(
            "INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?", (key, value, value))
        self.commit()

    def getPeerSyncTime(self, key):
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            "SELECT lastArrival FROM peers WHERE peerID=?", (key,))
        x = cur.fetchone()
        if x:
            return x[0]
        return 0

    def setConfig(self, section, key, value):
        try:
            self.config.addSection(section)
        except:
            pass
        self.config.set(section, key, value)

    def commit(self):
        self.dbConnect()
        self.threadLocal.conn.commit()

    def saveConfig(self):
        with open(self.filename+".ini", 'w') as configfile:
            self.config.write(configfile)
        self.syncFailBackoff=1

    def __enter__(self):
        self.dbConnect()
        self.threadLocal.conn.__enter__()
        return self

    def __exit__(self, *a):
        self.threadLocal.conn.__exit__(*a)

        ts = int((time.time())*10**6)

    def setDocument(self, doc, signature=None):
        "Two modes: Locally generate a signature, or use the existing sig data"
        arrival = time.time()*1000000

        if signature:
            libnacl.crypto_generichash(doc)[:24]
            kdg = libnacl.crypto_generichash(base64.b64decode(self.syncKey))[:8]
            sig = base64.b64decode(signature)
            mdg = sig[:24]
            sig = sig[24:]
            recievedKeyDigest = sig[:8]
            sig = sig[8:]

            recievedMessageDigest = libnacl.crypto_generichash(doc)[:24]
            if not recievedMessageDigest==mdg:
                raise ValueError("Bad message digest in supplied record")
            if not kdg==recievedKeyDigest:
                raise ValueError("This message was signed with the wrong key")

            libnacl.crypto_sign_verify_detached(sig,mdg, base64.b64decode(self.syncKey))
            d= doc
        
        else:
            if not self.writePassword:
                raise RuntimeError("Cannot modify records without the writePassword")
            #Handling a locally created document
            
            doc['time'] = doc.get('time', time.time()*1000000)
            
            doc['id'] = doc.get('id', str(uuid.uuid4()))
            doc['name'] = doc.get('name', doc['id'])
            doc['type'] = doc.get('type', '')

            d = jsonEncode(doc)

            # This is a bit of a tricky part here.  We want to allow repeaters that
            # do not have full write privilidges in the future. So We sign with the
            # write password.  However that key is not permanently linked to
            # the database.  It could change, which would mean that older signed records
            # would not be accepted.  However, this is unavoidable really.  If the key
            # is compromised, it is essential that we obviously don't accept new records that were signed
            # with it.
            mdg = libnacl.crypto_generichash(d)[:24]


            #Only 8 bytes because it's not meant to be cryptographically strong, just a hint
            #to aid lookup of the real key
            kdg = libnacl.crypto_generichash(base64.b64decode(self.syncKey))[:8]
            sig = libnacl.crypto_sign_detached(mdg, base64.b64decode(self.writePassword))
            signature = base64.b64encode(mdg+kdg+sig).decode()

        if isinstance(doc, str):
            doc = json.loads(doc)

        # If a UUID has been supplied, we want to erase any old record bearing that name.
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            'SELECT json_extract(json,"$.time") FROM document WHERE  json_extract(json,"$.id")=?', (doc['id'],))
        oldVersion = cur.fetchone()

        if oldVersion:
            # Check that record we are trying to insert is newer, else ignore
            if oldVersion[0] < doc['time']:
                self.threadLocal.conn.execute(
                    "UPDATE document SET json=?, signature=?,arrival=? WHERE json_extract(json,'$.id')=?", (d, signature,  arrival, doc['id']))

                # If we are marking this as deleted, we can ditch everything that depends on it.
                # We don't even have to just set them as deleted, we can relly delete them, the deleted parent record
                # is enough for other nodes to know this shouldn't exist anymore.
                if doc['type'] == "null":
                    self.threadLocal.conn.execute(
                        "DELETE FROM document WHERE json_extract(json,'$.parent')=?", (doc['id'],))

                self.onRecordChange(doc,signature)

                return doc['id']
            else:
                return doc['id']

        self.threadLocal.conn.execute(
            "INSERT INTO document VALUES (null,?,?,?,?)", (d, signature,arrival,signature))
        self.onRecordChange(doc,signature)

        self.lastChange = time.time()

        for i in self.subscribers:
            try:
                x = self.getUpdatesForSession(self.subscribers[i])
                if x:
                
                    asyncio.run_coroutine_threadsafe(
                        self.subscribers[i].socket.send(x),wsloop)
            except:
                logging.info(traceback.format_exc())

        return doc['id']

    def onRecordChange(self,record, signature):
        pass

    def getDocumentByID(self, key):
        self.dbConnect()
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            "SELECT json from document WHERE json_extract(json,'$.id')=?", (key,))
        x = cur.fetchone()
        if x:
            x= json.loads(x[0])
            if x.get("type",'')=='null':
                return None
            return x

    def getDocumentsByType(self, key, startTime=0, endTime=10**18, limit=100):
        self.dbConnect()
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            "SELECT json from document WHERE json_extract(json,'$.type')=? AND json_extract(json,'$.time')>=? AND json_extract(json,'$.time')<=? ORDER BY json_extract(json,'$.time') desc LIMIT ?", (key,startTime,endTime, limit))
        
        return list(reversed([i for i in [json.loads(i[0]) for i in cur] if not i.get('type','')=='null']))

    
    def searchDocuments(self, key, startTime=0, limit=100):
        self.dbConnect()
        cur = self.threadLocal.conn.cursor()
        l = []
        r=[]
        with self:
            cur.execute(
                "SELECT rowid from search WHERE tags MATCH ? or title MATCH ? or body MATCH ? or description MATCH ? LIMIT ?", (key,key,key,limit))
            for i in cur:
                l.append[i[0]]

            for i in l:
                cur.execute("SELECT json FROM document WHERE rowid=?",(i,))
                x = cur.fetchone()
                if x:
                    r.append(x)
            
        return list(reversed([i for i in [json.loads(i[0]) for i in r] if not i.get('type','')=='null']))


if __name__=="__main__":

    kp = libnacl.crypto_sign_seed_keypair(b'TEST'*int(32/4))
    db1 = DocumentDatabase("test1.db",keypair=kp)
    db2 = DocumentDatabase("test2.db",keypair=kp,servable=False)

    startServer(7004)
    with db1:
        db1.setDocument({'body':"From Db1"})
    with db2:
        db2.setDocument({'body':"From Db2"})

    db2.useSyncServer("ws://localhost:7004")

    with db1:
        db1.setDocument({'body':"From Db1 after connect"})
    with db2:
        db2.setDocument({'body':"From Db2  after connect"})
        

    time.sleep(2)
    db1.commit()
    db2.commit()

    time.sleep(2000)

