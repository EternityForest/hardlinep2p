
import socket,traceback,re,threading,time,struct,uuid,weakref
def makeLoopWorker(f):
    def f2():
        while 1:
            x = f()
            if x:
                try:
                    x.poll()
                except:
                    print(traceback.format_exc())
    return f2
                    
class LPDPeer():
    def parseLPD(self, m):
        t=''
        if self.searchTopic in m:
            t += 'search'
        elif self.announceTopic in m:
            t+='announce'
        else:
            return {}
        
        d = {}
        for i in re.findall('^(.*)?: *(.*)\r+$', m, re.MULTILINE):
            d[i[0]] = i[1]
            
        return (t,d)
    
    def onDiscovery(self,hash,host,port):
        pass

    def makeLPD(self, m,h):
        return (h+" * HTTP/1.1\r\nPort: {Port}\r\nInfohash: {Infohash}\r\ncookie: {cookie}\r\n\r\n\r\n").format(**m).encode('utf8')

    def makeLPDSearch(self, m,h):
        return (h+" * HTTP/1.1\r\nInfohash: {Infohash}\r\ncookie: {cookie}\r\n\r\n\r\n").format(**m).encode('utf8')
    
    def poll(self):
        try:
            d, addr = self.msock.recvfrom(4096)
        except socket.timeout:
            return

        t, msg = self.parseLPD(d.decode('utf-8', errors='ignore'))

        if msg:

            if 'search' in t:
                if not msg.get('cookie', '') == self.cookie:
                    with self.lock:
                        if msg['Infohash'] in self.activeHashes:
                            #Mcast works better on localhost to localhost in the same process it seems
                            self.advertise(msg['Infohash'],self.activeHashes[msg['Infohash']], ("239.192.152.143", 6771))
                            print("responding to lpd")
                            
            if 'announce' in t:
                if not msg.get('cookie', '') == self.cookie:
                    if msg.get("Infohash"):
                        self.onDiscovery(msg.get("Infohash"),addr[0],int(msg.get("Port")))
                    

    def advertise(self, hash, port, addr= ("239.192.152.143", 6771)):
        if self.lastAdvertised.get(hash, 0) > time.time()+10:
            return
        self.lastAdvertised[hash] = time.time()
        self.activeHashes[hash] = port
       
    
        self.msock.sendto(self.makeLPD({'Infohash': hash, 'Port': port, 'cookie': self.cookie},self.announceTopic), addr)

    def search(self, hash):
        #Not BT LPD compatible!! Use advertise for both searching and announcing
        self.msock.sendto(self.makeLPDSearch({'Infohash': hash, 'cookie': self.cookie}, self.searchTopic), ("239.192.152.143", 6771))


    def __init__(self, announceTopic="BT-SEARCH", searchTopic="BT-SEARCH"):
        
        #Message names used to search and announce.
        #You can use the same type for both, as in BT-SEARCH
        self.announceTopic=announceTopic
        self.searchTopic = searchTopic
        
        
        self.msock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.msock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.msock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.msock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Bind to the server address
        self.msock.bind(("0.0.0.0", 6771))
        self.msock.settimeout(1)

        group = socket.inet_aton("239.192.152.143")
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.msock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.cookie = str(uuid.uuid4())

        self.lastAdvertised = {}

        # hash:port mapping
        self.activeHashes = {}

        self.lock = threading.Lock()

        self.thread = threading.Thread(
            target=makeLoopWorker(weakref.ref(self)))
        self.thread.start()
        
