
import libnacl,select,threading,re, weakref,os,socket,libnacl,time,ssl,collections,binascii,traceback,random, sqlite3,json

from . import util, upnpwrapper

from OpenSSL import crypto, SSL

services = weakref.WeakValueDictionary()

#TODO LPD bootstrap attempt
# dht = btdht.DHT()


# dht.start()
# time.sleep(15)

P2P_PORT=7009

# dhtlock=threading.RLock()


#Mutable containers we can pass to services
WANPortContainer = [0]
ExternalAddrs=['']

try:
    os.makedirs(os.path.expanduser("~/.hardlinep2p/"))
except:
    pass

DB_PATH = os.path.expanduser("~/.hardlinep2p/peers.db")

discoveryDB  = sqlite3.connect(DB_PATH)
c=discoveryDB.cursor()

# Create table which we will use to store our peers.
c.execute('''CREATE TABLE IF NOT EXISTS peers
             (serviceID text, info text)''')



dbLock = threading.RLock()



dbLocal =threading.local()

def getDB():
    try:
        return dbLocal.db
    except:
        dbLocal.db = sqlite3.connect(DB_PATH)
        return dbLocal.db


class DiscoveryCache(util.LPDPeer):
    def __init__(self,hash):
        util.LPDPeer.__init__(self,"HARDLINE-SERVICE","HARDLINE-SEARCH")
        self.infohash = hash
        self.cacheRecord=(None,0,10)

    def doLookup(self):
        self.search(self.infohash)
        def cb(l):
            for i in l:
                #Priority
                if self.cacheRecord[2]>=1:
                    self.cacheRecord= (i,time.time(),1)

        # with dhtlock:
        #     dht.get_peers(binascii.a2b_hex(self.infohash), block=False, callback=cb, limit=1)
       

    def onDiscovery(self,hash, host,port):
        #Local discovery has priority zero
        self.cacheRecord = ((host,port),time.time(),0)

     


    def get(self,invalidate=False):

      
        #Try a local serach
        for i in range(0,3):
          
            #Look in the cache first
            x = self.cacheRecord    
            if x[1]> (time.time()- 60):
                return x[0]

            self.doLookup()
            #Wait a bit for replies, waiting a little longer every time
            time.sleep(i*0.07 + 0.025)
    
        #Local search failed, we haven't seen a packet from them, so we are probably not on their network.
        # lets try a stored WAN address search, maybe we have a record we can use?
        with dbLock:
            discoveryDB  = getDB()
            c=discoveryDB.cursor()
            c = discoveryDB.cursor()
            d = c.execute("select info from peers where serviceID=?",(self.infohash,)).fetchone()
            if d:
                p = json.loads(d[0])['WANHosts'].split(":")
                return (p[0],int(p[1]))
                



discoveries = collections.OrderedDict()

#Not threadsafe, but we rely on the application anyway, to handle the unreliable network
def discover(key,refresh=False):
    if len(discoveries)> 32:
        discoveries.popitem(True)
        discoveries.popitem(True)
        discoveries.popitem(True)
        discoveries.popitem(True)

    if not key in discoveries:
        discoveries[key]= DiscoveryCache(key)

    return discoveries[key].get(refresh)





def writeWanInfoToDatabase(infohash, hosts):
    #The device can tell us how to later find it even when we leave the WAN
    #TODO: People can give us fake values, which we will then save. Solution: digitally sign.
    if hosts:
        with dbLock:
            #Todo don't just reopen a new connection like this
            discoveryDB  = getDB()
            cur = discoveryDB.cursor()
            d = cur.execute("select info from peers where serviceid=?",(infohash,)).fetchone()
            if d:
                #No change has been made
                try:
                    d=json.loads(d[1])['WANHosts']
                    if d==hosts:
                        return
                except:
                    print(traceback.format_exc())
                cur.execute("update peers set info=? where serviceid=?",(json.dumps({"WANHosts": hosts}),infohash))
            else:
                cur.execute("insert into peers values (?,?)",(infohash, json.dumps({"WANHosts": hosts})))
            discoveryDB.commit()


class Service():
    def __init__(self,cert, destination,port=80):
        global P2P_PORT

        self.certfile = cert
        self.dest = destination+":"+str(port)

     
        
        if os.path.exists(cert+'.hash'):
            with open(cert+'.hash', "r") as f:
                self.keyhash = bytes.fromhex(f.read())
        else:
            self.cert_gen(cert)

    

        services[self.keyhash.hex()]=self
        
        self.lpd = util.LPDPeer("HARDLINE-SERVICE","HARDLINE-SEARCH")

        self.lpd.advertise(self.keyhash.hex(),destination,P2P_PORT)

       
        # self.dhtPush()

                
    def dhtPush(self):
        with dhtlock:
            def f(peers):
                global P2P_PORT

                with dhtlock:
                    dht.announce_peer(self.keyhash,P2P_PORT, delay=0, block=False)

            dht.get_peers(self.keyhash, limit=5,callback=f,block=False)


    def handleConnection(self,sock):
        "Handle incoming encrypted connection from another hardline instance.  The root server code has alreadt recieved the SNI and has dispatched it to us"
        #Swap out the contetx,  now that we know the service they want, we need to serve the right certificate
        p2p_server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if not os.path.exists(self.certfile):
            raise RuntimeError("No cert")
        if not os.path.exists(self.certfile+".private"):
            raise RuntimeError("No key")
        p2p_server_context.load_cert_chain(certfile=self.certfile, keyfile=self.certfile+".private")
        sock.context =p2p_server_context

    

    def handleConnectionReady(self,sock):
        def f():
            conn = socket.socket(socket.AF_INET)
            h,p =self.dest.split(":")
            conn.connect((h,int(p)))
        
            #Wait for ready
            for i in range(50):
                r,w,x = select.select([],[sock],[],0.1)
                if w:
                    break



            sendOOB =  {
               
            }

            #Using a list as an easy mutable global.
            #Should there be an external addr we can tell them about, we stuff it in our header so they can memorize it.
            #Note that this is secured via the same SSH tunnel, only the real server can send this.
            if ExternalAddrs[0]:
                 sendOOB['WANHosts']= (ExternalAddrs[0]+":"+str(WANPortContainer[0]))

            #Send our oob data header
            sock.send(json.dumps(sendOOB, separators=(',', ':')).encode()+b"\n")



            oob= b''

            #The first part of the data is reserved for an OOB header
            while(1):
                r,w,x = select.select([sock,],[],[],1)
                if r:
                    oob += sock.recv(4096)
                    if b"\n" in oob:
                        break

            oob, overflow = oob.split(b"\n")

            #Send any data that was after the newline
            conn.send(overflow)




            while(1):
                r,w,x = select.select([sock,conn],[],[],1)
                try:
                   
                    #Whichever one has data, shove it down the other one
                    for i in r:
                        try:
                            if i==sock:
                                conn.send(i.recv(4096))
                            else:
                                sock.send(i.recv(4096))
                        except:
                            print(traceback.format_exc())
                            x=True

                    if x:
                        print("socket closing")

                        sock.close()
                        conn.close()
                        return
                except:
                    pass
                            
        t=threading.Thread(target=f, daemon=True)
        t.start()
            
            
    def cert_gen(self,fn):
        #None of these parameters matter.  We will be using the hash directly, comparing
        #exact certificate identity
        emailAddress="emailAddress"
        commonName="commonName"
        countryName="NT"
        localityName="localityName"
        stateOrProvinceName="stateOrProvinceName"
        organizationName="organizationName"
        organizationUnitName="organizationUnitName"
        serialNumber=0
        validityStartInSeconds=0
        validityEndInSeconds=100*365*24*60*60
        KEY_FILE = fn+".private"
        CERT_FILE=fn
        #can look at generated file using openssl:
        #openssl x509 -inform pem -in selfsigned.crt -noout -text
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 4096)
        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = countryName
        cert.get_subject().ST = stateOrProvinceName
        cert.get_subject().L = localityName
        cert.get_subject().O = organizationName
        cert.get_subject().OU = organizationUnitName
        cert.get_subject().CN = commonName
        cert.get_subject().emailAddress = emailAddress
        cert.set_serial_number(serialNumber)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(validityEndInSeconds)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha512')
        
        with open(CERT_FILE, "wt") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
            
        with open(KEY_FILE, "wt") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))
        
        with open(CERT_FILE+'.hash', "wt") as f:
            f.write(libnacl.crypto_generichash(crypto.dump_certificate(crypto.FILETYPE_ASN1, cert))[:20].hex())
            self.keyhash = libnacl.crypto_generichash(crypto.dump_certificate(crypto.FILETYPE_ASN1, cert))[:20]

def server_thread(sock):
    "Spawns a thread for the server that is meant to be accessed via localhost, and create the backend P2P"
    #In a thread, we are going to 
    def f():
        rb = b''

        t=time.time()
        #Sniff for an HTTP host so we know who to connect to.
        #Normally we would use the SSL SNI, but the localhost conection doesn't have that.
        while time.time()-t < 5:
            r,w,x = select.select([sock],[],[],1)
            if r:
                rb+= sock.recv(4096)
                
                #Found it!
                x = re.search(b"^Host: *(.*?)$",rb,re.MULTILINE)
                if x:
                    destination = x.groups(1)[0].replace(b"\r",b'')
                    break
                if len(rb)>10000:
                    raise RuntimeError("HTTP sniffing fail")

        x = destination.split(b".")
        
        #This is the service we want, identified by hex key hash
        service =x[0]

        #This is the location at which we actually find it.
        #We need to pack an entire hostname which could actually be an IP address, into a single subdomain level component
        host = discover(service.decode())
        
        #We do our own verification
        sk = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        sk.check_hostname = False
        sk.verify_mode = ssl.CERT_NONE
        sock2 = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

  
        
    
        


        #Use TCP keepalives here.  Note that this isn't really secure because it's at the TCP layer,
        #Someone could DoS it, but DoS is hard to stop no matter what.
        sock2.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock2.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        sock2.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
        sock2.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
        conn = sk.wrap_socket(sock2, server_hostname=service)

        conn.connect(host)

  
        for i in range(100):
            time.sleep(0.03)
            try:
                c = conn.getpeercert(True)
                break
            except ValueError:
                pass
        
        hashkey = libnacl.crypto_generichash(c)[:20].hex()
        if not hashkey==x[0].decode():
            raise ValueError("Server certificate does not match key in URL")

        #Wait for connection
        for i in range(50):
            r,w,x = select.select([],[conn],[],0.1)
            if w:
                break

        sendOOB = {}
        #Send our oob data header to the other end of things.
        conn.send(json.dumps(sendOOB, separators=(',', ':')).encode()+b"\n")


        oob= b''

        #The first part of the data is reserved for an OOB header
        for i in range(0,100):
            r,w,x = select.select([conn,],[],[],1)
            if r:
                oob += conn.recv(4096)
                if b"\n" in oob:
                    break
            time.sleep(0.01)
        

        oob, overflow = oob.split(b"\n")

        #Send any data that was after the newline, back up to the localhost client
        sock.send(overflow)


        oob = json.loads(oob)

        #The remote server is telling us how we can contact it in the future via WAN, should local discovery
        #fail.  We record this, indexed by the key hash.  Note that we do this inside the SSL channel
        #because we don't want anyone to make us write fake crap to our database
        if 'WANHosts' in oob:
            writeWanInfoToDatabase(service.decode(), oob['WANHosts'])

        




        while(1):
            r,w,x = select.select([sock,conn],[sock,conn] if rb else [],[],1)
            try:
                #Send the traffic we had to buffer in order to sniff for the destination
                if rb:
                    if w:
                        conn.send(rb)
                        rb=b''
                
                
                #Whichever one has data, shove it down the other one
                for i in r:
                    try:
                        if i==sock:
                            conn.send(i.recv(4096))
                        else:
                            sock.send(i.recv(4096))
                    except:
                        print(traceback.format_exc())
                        x=True
                
                if x:
                    print("socket closing")
                    sock.close()
                    conn.close()
            
                    return
            except:
                pass
    t=threading.Thread(target=f, daemon=True)
    t.start()
    



def handleClient( sock):
    server_thread(sock)
    
    

def handleP2PClient(sock):
    def f():
        p2p_server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

        #Use this list to get the name
        l=[]
        p2p_server_context.sni_callback = makeHelloHandler(l)
        conn = p2p_server_context.wrap_socket(sock,server_side=True)

        #handleP2PClientHello put the name in the list
        services[l[0]].handleConnectionReady(conn)
        

    threading.Thread(target=f,daemon=True).start()


def makeHelloHandler(l):
    def handleP2PClientHello(sock,name,ctd):
        if name in services:
            services[name].handleConnection(sock)
            l.append(name)
    return handleP2PClientHello




#This loop just refreshes the WAN addresses every five minutes.
#We need this so we can send them for clients to store, to later connect to us.
def upnploop():
    while 1:
        try:
            a=upnpwrapper.getWANAddresses()
            if a:
                ExternalAddrs[0]=a[0]
            else:
                ExternalAddrs[0]=''
        except:
            print(traceback.format_exc())

        time.sleep(5*60)

portMapping = None

def start(localport):
    global P2P_PORT,WANPort,portMapping
    
    #This is the server context we use for localhost coms


    
    bindsocket = socket.socket()
    bindsocket.bind(('localhost', localport))
    bindsocket.listen()

    #This is the server context we use for the remote coms, accepting incoming ssl connections from other instances and proxying them into
    #local services

    p2p_bindsocket = socket.socket()
    if services:
        p2p_bindsocket.bind(('0.0.0.0',P2P_PORT))
        p2p_bindsocket.listen() 

        #Only daemons exposing a service need a WAN mapping
        t = threading.Thread(target=upnploop, daemon=True)
        t.start()
        #We don't actually know what an unbusy port really is. Try a bunch till we find one.
        #Note that there is a slight bit of unreliableness here.  The router could get rebooted, and lose
        #our mapping, and someone else could have taken it when we retry.  But that is rather unlikely.
        #Default to the p2p port
        WANPortContainer[0]=P2P_PORT

        for i in range(0,25):
            try:
                portMapping = upnpwrapper.addMapping(P2P_PORT,"TCP", WANPort= WANPortContainer[0])
                break
            except:
                WANPortContainer[0] += 1
                print(traceback.format_exc())
                print("Failed to register port mapping, retrying")
        else:
            #Default to the p2p port
            print("Failed to register port mapping, you will need to manually configure.")
            WANPortContainer[0]=P2P_PORT

    while(1):


        # if time.time()-lastDHT > 60*12:
        #     try:
        #         for i in services:
        #             services[i].dhtPush()
        #     except:
        #         print(traceback.format_exc())


        r,w,x = select.select([bindsocket,p2p_bindsocket] if services else [bindsocket],[],[],1)
        try:
            
            #Whichever one has data, shove it down the other one
            for i in r:
                if i==bindsocket:
                    handleClient(i.accept()[0])
                else:
                    if services:
                        handleP2PClient(i.accept()[0])
        except:
            pass

