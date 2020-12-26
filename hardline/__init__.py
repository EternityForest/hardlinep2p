
import select,threading,re, weakref,os,socket,time,ssl,collections,binascii,traceback,random, sqlite3,json
from nacl.hash import blake2b
import nacl

from . import util


services = weakref.WeakValueDictionary()

socket.setdefaulttimeout(5)

#Todo fix this

# def createWifiChecker():

#     """Detects if we are on something like WiFi.  But if we aren't on android at all, assume that we are always connected to a LAN, even htough there are 4g laptops.
#        don't use for anything critical because of that.

#     """
#     def alwaysTrue():
#         return True
#     try:
#         from kivy.utils import platform
#         from jnius import autoclass
#     except:
#         return alwaysTrue

#     if platform != 'android':
#             return alwaysTrue


#     def check_connectivity():
        

#         Activity = autoclass('android.app.Activity')
#         PythonActivity = autoclass('org.kivy.android.PythonActivity')
#         activity = PythonActivity.mActivity
#         ConnectivityManager = autoclass('android.net.ConnectivityManager')

#         con_mgr = activity.getSystemService(Activity.CONNECTIVITY_SERVICE)

#         conn = con_mgr.getNetworkInfo(ConnectivityManager.TYPE_WIFI).isConnectedOrConnecting()
#         if conn:
#             return True
    
#     return check_connectivity()

# isOnLan= createWifiChecker()
isOnLan = lambda:True


P2P_PORT=7009

dhtlock=threading.RLock()

DHT_PROXIES = [
    "http://dhtproxy.jami.net/"
]


#Mutable containers we can pass to services
WANPortContainer = [0]
ExternalAddrs=['']

try:
    from android.storage import app_storage_path
    settings_path = app_storage_path()
except:
    settings_path = '~/.hardlinep2p/'


try:
    os.makedirs(os.path.expanduser(settings_path))
except:
    pass

DB_PATH = os.path.join(os.path.expanduser(settings_path),"peers.db")

discoveryDB  = sqlite3.connect(DB_PATH)
c=discoveryDB.cursor()

# Create table which we will use to store our peers.
c.execute('''CREATE TABLE IF NOT EXISTS peers
             (serviceID text, info text)''')



dbLock = threading.RLock()



#LThread local storage to store DB connections, we can only  use each from one thread.
dbLocal =threading.local()


from ipaddress import ip_network, ip_address

try:
    import netifaces
except:
    netifaces = None
    print("Did not find netifaces, mesh-awareness disabled")

def getWanHostsString():
    #String describing how a node might access us from the public internet, as a prioritized comma separated list.

    
    meshAddress = ''
    l=[]
    if netifaces:
        x = netifaces.interfaces()
        for i in x:
            
            y = netifaces.ifaddresses(i)
            
            if netifaces.AF_INET6 in y:
                y2 =y[netifaces.AF_INET6]
                for j in y2:
                    l.append(j['addr'].split("%")[0])

        for i in l:
            #Specifically look for the addresses the Yggdrasil mesh uses
            if ip_address(i) in  ip_network("200::/7"):
                meshAddress = i+":"+str(P2P_ADDR)
    
            
    s =[]
    if ExternalAddrs[0]:
        s.append(ExternalAddrs[0]+":"+str(WANPortContainer[0]))
    if meshAddress:
        s.append(meshAddress)

    return ",".join(s)

def getDB():
    try:
        return dbLocal.db
    except:
        dbLocal.db = sqlite3.connect(DB_PATH)
        return dbLocal.db


def parseHostsList(p):
    "Parse a comma separated list of hosts which may include bot ipv4 and ipv6, into a list of host port tuples "
    p=p.replace("[",'').replace("]","")
    d = p.split(",")
    l=[]
    for i in d:
        i=i.strip()
        #This could be IPv6 or IPv4, and if it's 4, we will need to take the last : separated part
        #as the port, and reassemble the rest.
        i = i.split(":")
        p=int(i[-1])
        h=":".join(i[:-1])
        l.append((h,p))
    return l

class DiscoveryCache(util.LPDPeer):
    def __init__(self,hash):
        util.LPDPeer.__init__(self,"HARDLINE-SERVICE","HARDLINE-SEARCH")
        self.infohash = hash

        #We treat local discovery differently and cache in RAM, because it can change ofen
        #As we roam off the wifi, and it is not secure.
        self.LPDcacheRecord=(None,0,10)

        #Don't cache DHT all all, if gives the same info we will get and cache over SSL
        #But DO rate limit it.
        self.lastTriedDHT = time.time()



    def doDHTLookup(self):
        """Perform a DHT lookup using the public OpenDHT proxy service.  We don't cache the result of this, we just rate limit.
           and let the connection thread cache the same data that it will get via the server.
        """
        #Lock is needed mostly to avoid confusion in ratelimit logic when debugging

        with dhtlock:
            import requests
            if self.lastTriedDHT > (time.time()-60):
                #Rate limit queries to the public DHT proxy to one per minute
                return []

            self.lastTriedDHT = time.time()
            

            import opendht as dht

            k = dht.InfoHash.get(self.infohash).toString().decode()


            #Prioritized DHT proxies list
            for i in DHT_PROXIES:
                try:
                    r = requests.get(i+k)
                    r.raise_for_status()
                    break
                except:
                    print("DHT Proxy request to: "+i+" failed")

            if r.text:
                #This only tries the first item, which is a little too easy to DoS, but that's also part of the inherent problem with DHTs.
                d = base64.b64decode(json.loads(r.text.split("\n")[0].strip())['data'])
            
                
                #Return a list of candidates to try
                return parseHostsList(d)
                
            return []

    def doLookup(self):
        self.search(self.infohash)
        def cb(l):
            for i in l:
                #Priority
                if self.LPDcacheRecord[2]>=1:
                    self.LPDcacheRecord= (i,time.time(),1)

  
    def onDiscovery(self,hash, host,port):
        #Local discovery has priority zero
        self.LPDcacheRecord = ((host,port),time.time(),0)

     


    def get(self,invalidate=False):

        #Not on WiFi, refrain from trying and failing to do multicast discovery.
        if isOnLan():
            #Try a local serach
            for i in range(0,3):
            
                #Look in the cache first
                x = self.LPDcacheRecord    
                if x[1]> (time.time()- 60):
                    return [x[0]]

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
                p = json.loads(d[0])['WANHosts']
                #Return a list of candidates to try
                return parseHostsList(p)
        return []
                



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


def dhtDiscover(key,refresh=False):
    if len(discoveries)> 32:
        discoveries.popitem(True)
        discoveries.popitem(True)
        discoveries.popitem(True)
        discoveries.popitem(True)

    if not key in discoveries:
        discoveries[key]= DiscoveryCache(key)

    return discoveries[key].doDHTLookup()



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
                    d=json.loads(d[0])['WANHosts']
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

        self.lpd.advertise(self.keyhash.hex(),P2P_PORT)

       
                
    def dhtPublish(self,node):
        #Publish this service to the DHT for WAN discovery.

        #We never actually know if this will be available on the platform or not
        try:
            import opendht as dht
        except:
            return


        with dhtlock:
           node.put(dht.InfoHash.get(self.keyhash.hex()), dht.Value(getWanHostsString().encode()))


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
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
           
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
                 sendOOB['WANHosts']= getWanHostsString()

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

                #Whichever one has data, shove it down the other one
                for i in r:
                    try:
                        if i==sock:
                            d= i.recv(4096)
                            if d:
                                conn.send(d)
                            else:
                                raise ValueError("Zero length read, probably closed")
                        else:
                            d = i.recv(4096)
                            if d:
                                sock.send(d)
                            else:
                                raise ValueError("Zero length read, probably closed")
                    except:
                        print(traceback.format_exc())

                        print("socket closing")
                        try:
                            sock.close()
                        except:
                            pass
                        try:
                            conn.close()
                        except:
                            pass
                        return

                            
        t=threading.Thread(target=f, daemon=True)
        t.start()
            
            
    def cert_gen(self,fn):
        #None of these parameters matter.  We will be using the hash directly, comparing
        #exact certificate identity
        from OpenSSL import crypto, SSL

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
            f.write(blake2b(crypto.dump_certificate(crypto.FILETYPE_ASN1, cert), encoder=nacl.encoding.RawEncoder())[:20].hex())
            self.keyhash = blake2b(crypto.dump_certificate(crypto.FILETYPE_ASN1, cert),encoder=nacl.encoding.RawEncoder())[:20]

def server_thread(sock):
    "Spawns a thread for the server that is meant to be accessed via localhost, and create the backend P2P"
    #In a thread, we are going to 
    def f():
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

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
        hosts = discover(service.decode())
        
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

        #Try our discovered hosts
        for host in hosts:
            try:
                connectingTo = host
                conn.connect(host)
                break
            except:
                print(traceback.format_exc())
        else:
            for host in discover(service.decode()):
                try:
                    connectingTo = host
                    conn.connect(host)
                    break
                except:
                    print(traceback.format_exc())
            else:
                for host in dhtDiscover(service.decode()):
                    try:
                        connectingTo = host
                        conn.connect(host)
                        break
                    except:
                        print(traceback.format_exc())
                else:
                    raise RuntimeError("All saved host options and dht options failed:"+str(hosts))
       # else:
            #We have failed, now we have to use DHT lookup
            

  
        c = conn.getpeercert(True)
   
        
        hashkey = blake2b(c,encoder=nacl.encoding.RawEncoder())[:20].hex()
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
            #Send the traffic we had to buffer in order to sniff for the destination
            if rb:
                if w:
                    conn.send(rb)
                    rb=b''
            
            
            #Whichever one has data, shove it down the other one
            for i in r:
                try:
                    if i==sock:
                        d = i.recv(4096)
                        if d:
                            conn.send(d)
                        else:
                            raise ValueError("Zero length read, probably closed")
                    else:
                        d= i.recv(4096)
                        if d:
                            sock.send(d)
                        else:
                            raise ValueError("Zero length read, probably closed")
                except:
                    print(traceback.format_exc())
  
                    try:
                        sock.close()
                    except:
                        pass
                    try:
                        conn.close()
                    except:
                        pass
            
                    return

    t=threading.Thread(target=f, daemon=True)
    t.start()
    



def handleClient( sock):
    server_thread(sock)
    
    

def handleP2PClient(sock):
    def f():
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

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


dhtContainer = [0]

#This loop just refreshes the WAN addresses every 8 minutes.
#We need this so we can send them for clients to store, to later connect to us.

#It also refreshes any OpenDHT keys that clients might have
def taskloop():
    from . import upnpwrapper
    while 1:
        try:
            a=upnpwrapper.getWANAddresses()
            if a:
                ExternalAddrs[0]=a[0]
            else:
                ExternalAddrs[0]=''
        except:
            print(traceback.format_exc())



        if dhtContainer[0]:
            try:
               for i in services:
                   services[i].dhtPublish(dhtContainer[0])
            except:
                print(traceback.format_exc())

        time.sleep(8*60)

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
        
        from . import upnpwrapper

        #Start the DHT.   Node that we would really like to avoid actually having to use this,
        #So although we publish to it, we try local discovery and the local cache first.
        try:
            import opendht as dht
        except:
            dht=None
            print("Unable to import openDHT.  If you would like to use this feature, install dhtnode if you are on debian.")

        if dht:
            node = dht.DhtRunner()
            node.run()

            # Join the network through any running node,
            # here using a known bootstrap node.
            node.bootstrap("bootstrap.jami.net", "4222")
            dhtContainer[0]=node


        p2p_bindsocket.bind(('0.0.0.0',P2P_PORT))
        p2p_bindsocket.listen() 

        #Only daemons exposing a service need a WAN mapping
        t = threading.Thread(target=taskloop, daemon=True)
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

