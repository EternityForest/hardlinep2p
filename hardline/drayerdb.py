

# This file manages kaithem's native SQLite document database.

# There is one table called Document

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


def stopServer():
    global start_server
    if start_server:
        start_server.close()


def startServer(port):
    global start_server
    stopServer()
    start_server = websockets.serve(DBAPI, "localhost", port)
    asyncio.get_event_loop().run_until_complete(start_server)
    # DB will eventually handle consistency by itself.
    t = threading.Thread(
        target=asyncio.get_event_loop().run_forever, daemon=True)
    t.start()
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
MESSAGE_TYPE_READONLY = 2


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

       

        self.config = configparser.ConfigParser()

        if os.path.exists(filename+".ini"):
            self.config.read(filename+".ini")

        self.threadLocal.conn.row_factory = sqlite3.Row
        # self.threadLocal.conn.execute("PRAGMA wal_checkpoint=FULL")
        self.threadLocal.conn.execute("PRAGMA secure_delete = off")

        # Yep, we're really just gonna use it as a document store like this.
        self.threadLocal.conn.execute(
            '''CREATE TABLE IF NOT EXISTS document (rowid integer primary key, json text, signature text, localinfo text)''')

        self.threadLocal.conn.execute('''CREATE TABLE IF NOT EXISTS meta
             (key text primary key, value  text)''')

        self.threadLocal.conn.execute('''CREATE TABLE IF NOT EXISTS peers
             (peerID text primary key, lastArrival integer, info text)''')

        # To keep indexing simple and universal, it only works on three properties.  _tags, _description and _body.
        self.threadLocal.conn.execute('''
             CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(tags, description, body, content='')''')

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
            """
            CREATE TRIGGER IF NOT EXISTS search_index AFTER INSERT ON document BEGIN
            INSERT INTO search(rowid, tags, description, body) VALUES (new.rowid, IFNULL(json_extract(new.json,"$.tags"), ""), IFNULL(json_extract(new.json,"$.description"), ""), IFNULL(json_extract(new.json,"$.body"), ""));
            END;
            """)

        self.threadLocal.conn.execute(
            """   CREATE TRIGGER IF NOT EXISTS search_delete AFTER DELETE ON document BEGIN
            INSERT INTO search(search, rowid, tags, description, body) VALUES ('delete', old.rowid, IFNULL(json_extract(old.json,"$.tags"), ""), IFNULL(json_extract(old.json,"$.description"), ""), IFNULL(json_extract(old.json,"$.body"), ""));
            END;""")

        self.threadLocal.conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS search_update AFTER UPDATE ON document BEGIN
            INSERT INTO search(search, rowid, tags, description, body) VALUES ('delete', old.rowid, IFNULL(json_extract(old.json,"$.tags"), ""), IFNULL(json_extract(old.json,"$.description"), ""), IFNULL(json_extract(old.json,"$.body"), ""));
            INSERT INTO search(rowid, tags, description, body) VALUES (new.rowid, IFNULL(json_extract(new.json,"$.tags"), ""), IFNULL(json_extract(new.json,"$.description"), ""), IFNULL(json_extract(new.json,"$.body"), ""));
            END;
            """
        )


        # If a db is deleted and recreated at the same file path, this means we have a chance of
        # detecting that in the remote node by making the localNodeVK different.

        # The point of this is to uniquiely identify a DB instance so that we always know what records we have or don't have.
        self.nodeIDSeed = self.getMeta("nodeIDSeed")
        if not self.nodeIDSeed:
            self.nodeIDSeed = os.urandom(24).hex()

        # Deterministically generate a keypair that we will use to sign all correspondance
        self.localNodeVK, self.localNodeSK = libnacl.crypto_sign_seed_keypair(
            libnacl.crypto_generichash((os.path.basename(filename)+self.nodeIDSeed).encode("utf8"), readNodeID()))


        if not keypair:
            if 'sync' not in self.config:
                vk, sk = libnacl.crypto_sign_keypair()
                self.config.add_section('sync')
                self.config.set('sync', 'syncKey',
                                base64.b64encode(vk).decode('utf8'))
                self.config.set('sync', 'writePassword',
                                base64.b64encode(sk).decode('utf8'))
                self.saveConfig()

            self.syncKey = self.config.get('sync', 'syncKey', fallback=None)
            self.writePassword = self.config.get(
                'sync', 'writePassword', fallback='')

        else:
            self.syncKey = keypair[0]
            self.writePassword = keypair[1]

        self.serverURL = self.config.get('sync', 'server', fallback=None)

        if self.syncKey and servable:
            databaseBySyncKeyHash[libnacl.crypto_generichash(
                libnacl.crypto_generichash(base64.b64decode(self.syncKey)))[:16]] = self

        self.useSyncServer(self.serverURL)

    def useSyncServer(self, server, permanent=False):
        with self.lock:
            if server == self.serverURL:
                return
            if permanent:
                self.config.set('sync', 'serverURL', server)

            self.serverURL = server
            if not server:
                return

            t = threading.Thread(target=self.serverManagerThread, daemon=True)
            t.start()

    def serverManagerThread(self):
        oldServerURL = self.serverURL
        loop = asyncio.new_event_loop()
        backoff = 1

        while oldServerURL == self.serverURL:
            try:
                if loop.run_until_complete(self.openSessionAsClient()):
                    backoff = 1
            except:
                logging.exception("Error in DB Client")
                print(traceback.format_exc())

            backoff *= 2
            backoff = max(backoff, 5*60)
            time.sleep(backoff)

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
                                "SELECT lastArrival FROM peers WHERE peerID=?", (session.remoteNodeID,))

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
                print(f"> {name}")

                greeting = await websocket.recv()
                print(f"< {greeting}")

        asyncio.create_task(f)

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
        elif innerMessageType == MESSAGE_TYPE_READONLY:
            # These don't have the extra inner encryption.
            pass

        d = json.loads(d)

        r = {'records': []}

        if sessionObject and not sessionObject.alreadyDidInitialSync:
            cur = self.threadLocal.conn.cursor()
            cur.execute(
                "SELECT lastArrival FROM peers WHERE peerID=?", (remoteNodeID,))

            c = cur.fetchone()
            if c:
                c = c[0]
            else:
                c = 0
            # No falsy value allowed, that would mean don't get new arrivals
            r['getNewArrivals'] = c or 1
            sessionObject.alreadyDidInitialSync = True

        # Can't send records if we don't have the send key
        if self.writePassword:
            if "getNewArrivals" in d:
                cur = self.threadLocal.conn.cursor()
                # Avoid dumping way too much at once
                cur.execute(
                    "SELECT json,signature FROM document WHERE json_extract(json,'$.arrival')>? LIMIT 100", (d['getNewArrivals'],))

                # Declares that there are no records left out in between this time and the first time we actually send
                r['recordsStartFrom'] = d['getNewArrivals']

                for i in cur:
                    if not 'records' in r:
                        r['records'] = []
                    print(i)
                    r['records'].append([i[0], ''])

                    sessionObject.lastResyncFlushTime = max(
                        sessionObject.lastResyncFlushTime, json.loads(i[0])['arrival'])

        if innerMessageType == MESSAGE_TYPE_AUTHORIZED:
            if "records" in d and d['records']:
                for i in d['records']:

                    # The client side trusts the server(Because the user has presumably explicitly configured the server),
                    # and only requires the correct sync key.
                    # The server side does not trust the client to write, unless it has the write password.

                    self.setDocument(i[0])
                    r['getNewArrivals'] = latest = json.loads(i[0])['arrival']

                # Set a flag saying that
                cur = self.threadLocal.conn.cursor()
                # If the recorded lastArrival is less than the incoming recordsStartFrom, it would mean that there is a gap in which records
                # That we don't know about could be hiding.   Don't update the timestamp in that case, as the chain is broken.
                # We can still accept new records, but we will need to request everything all over again starting at the breakpoint to fix this.
                cur.execute("UPDATE peers SET lastArrival=? WHERE peerID=? AND lastArrival !=? AND lastArrival>=?",
                            (latest, remoteNodeID, latest, d["recordsStartFrom"]))
                self.threadLocal.conn.commit()

        return self.encodeMessage(r)

    def getUpdatesForSession(self, session):
        # Don't send anything till they have requested something, ohterwise we will just be sending nonsense they already have
        if session.lastResyncFlushTime:
            r = {}
            cur = self.threadLocal.conn.cursor()
            # Avoid dumping way too much at once
            cur.execute(
                "SELECT json,signature FROM document WHERE json_extract(json,'$.arrival')>? LIMIT 100", (session.lastResyncFlushTime,))

            # Let the client know that there are no records left out in between the start of this message and the end of what they have
            r['recordsStartFrom'] = session.lastResyncFlushTime

            for i in cur:
                if not 'records' in r:
                    r['records'] = []
                r['records'].append([i[0], base64.b64encode(i[1]).decode()])

                session.lastResyncFlushTime = max(
                    session.lastResyncFlushTime, json.loads(i[0])['arrival'])

            # We can of course just send nothing if there are no changes to flush.
            if r:
                return self.encodeMessage(r)

    def createBinaryWriteCall(self, r, sig=None):
        "Creates a binary command representing a request to insert a record."
        p = self.config.get('sync', 'writePassword', fallback=None)
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

        if self.writePassword:
            data = bytes([1]) + libnacl.crypto_sign(r,
                                                    base64.b64decode(self.writePassword))
        else:
            data = bytes([2]) + r

        signed = libnacl.crypto_sign(timeAsBytes+data, self.localNodeSK)
        data = self.localNodeVK+signed

        r = libnacl.crypto_secretbox(data, timeAsBytes+b'\0'*16, symKey)

        return keyHint + timeAsBytes + r

    def createBinaryWriteCall(self, r, sig=None):
        "Creates a binary command representing arequest to insert a record."
        p = self.config.get('sync', 'writePassword', fallback=None)
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
        with open(self.filename+".conf", 'w') as configfile:
            self.config.write(configfile)

    def __enter__(self):
        self.threadLocal.conn.__enter__
        return self

    def __exit__(self, *a):
        self.threadLocal.conn.__exit__

        ts = int((time.time())*10**6)

    def setDocument(self, doc):
        if isinstance(doc, str):
            doc = json.loads(doc)

        doc['time'] = doc.get('time', time.time()*1000000)
        doc['arrival'] = doc.get('arrival', time.time()*1000000)
        doc['id'] = doc.get('id', str(uuid.uuid4()))
        doc['name'] = doc.get('name', doc['id'])
        doc['type'] = doc.get('type', '')

        # If a UUID has been supplied, we want to erase any old record bearing that name.
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            'SELECT json_extract(json,"$.time") FROM document WHERE  json_extract(json,"$.id")=?', (doc['id'],))
        x = cur.fetchone()

        d = jsonEncode(doc)
        signature = ''

        if x:
            # Check that record we are trying to insert is newer, else ignore
            if x[0] < doc['time']:
                self.threadLocal.conn.execute(
                    "UPDATE document SET json=?, signature=? WHERE json_extract(json,'$.id')=?", (d, signature,  doc['id']))

                # If we are marking this as deleted, we can ditch everything that depends on it.
                # We don't even have to just set them as deleted, we can relly delete them, the deleted parent record
                # is enough for other nodes to know this shouldn't exist anymore.
                if doc['type'] == "null":
                    self.threadLocal.conn.execute(
                        "DELETE FROM document WHERE json_extract(json,'$.id')=?", (doc['id'],))

                return doc['id']
            else:
                return doc['id']

        self.threadLocal.conn.execute(
            "INSERT INTO document VALUES (null,?,?,?)", (d, signature, ''))
        self.lastChange = time.time()

        for i in self.subscribers:
            try:
                asyncio.get_event_loop().run_until_complete(
                    self.subscribers[i].socket.send(self.getUpdatesForSession(self.subscribers[i])))
            except:
                print(traceback.format_exc())

        return doc['id']

    def getDocumentByID(self, key):
        cur = self.threadLocal.conn.cursor()
        cur.execute(
            "SELECT json from document WHERE json_extract(json,'$.id')=?", (key,))
        x = cur.fetchone()
        if x:
            return x[0]
