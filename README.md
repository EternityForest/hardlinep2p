# hardlinep2p
Application-level P2P tunnelling for securely accessing personal servers without a VPN. Currently alpha/everiything supbject to change!!


## requirements

OpenSSL, pynacl, dhtnode(On server side only), requests,six,lxml,dateutil

## Building for Android
You have to move setup.py out of the directory before using buildozer.  Otherwise, it will not work.  For some reason the settings to ignore the setup.py file aren't having any effect.

## What it does

Takes a service on computer A, and makes it available on computer B at KEYHASH.localhost:7009.  It does this with a daemon on both computers
and a tunnel between them, encrypted with SSL, and works over the internet with no manual port forwarding or any need to sign up for a Dynamic DNS service,
get a certificate manually, or anything like that.

The closely integrated DrayerDB system provides extrememly easy synced databases that do not use a blockchain, instead using a doubly-ordered pseudochain
with time-based conflict resolution and fast incremental updates.

The app(written in Kivy, and available for Android as well as the desktop) also lets you browse services connected to your LAN, and view and edit posts in DrayerDB sync files in a wiki like manner.

Ideally, you'll be able to take home a smart device, plug it into your router, find it in the listing on the app, and click the button ot jump to the browser.

That bookmark will then work from anywhere in the world!


In addition to all of this, we also provide journalling and notetaking using distributed databases.

This feature is integrated into the same app and uses the services feature for Sync.


## Prior Art:

* Abandoned Mozilla project that was similar: [https://wiki.mozilla.org/FlyWeb]
* Tor/I2P hidden services provide similar functionality(but Hardline makes no attempt to be anonymous or hide your IP, only to secure trafffic.)

## Not similar

* IPFS: We aren't bittorrent, we don't use any sort of content-addressible stuff, we provide connections to self-hosted services, and mutable distributed databases. 
* Zerotier:  This is not a VPN. It will not conflict with a VPN(Although it may ignore it and use the LAN instead), and it does not act at the low-level network layer.

## Possibly Similar

* The GUN database seems to provide a similar eventually consistent database as the Streams feature
* DAT:  We have a similar data sharing capability, but we do not manage any version history.
* Scuttlebutt: We have a similar decentralized publishing capability, but we support multiple writers and don't use a chain.
* SyncThing seems to use a similar sharing model to sync files.  We don't currently sync files yet though.

## How it works.
Computer B can discover the address of computer A if it is on the same network, otherwise it will fall back to using a public OpenDHT proxy that I am hosting(If you run one, let me know, I'd love to add some redundancy!)

If computer B has ever successfully connected to that service before, it will remember the addresses and try those, even if ther DHT proxy
is down.  Even if the initial connection was via LAN, computer A will tell B where to find it on the WAN later.

Computer A can provide multiple prioritized WAN addresses.  If it is conected to the Yggdrasil mesh, it will provide that address in the list, after the normal WAN address,
so you should be able to connect even without the internet on isolated meshnets.

Computer A uses the native DHT, and does not rely on a proxy.



### Using it

On the computer that has the service(assuming it is on port 80), use  `python3 hardline.py --service localhost --serviceport 80 --certfile foo.cert --localport 6767 --p2pport 7684`

You must have UPnP on your router, or manually open a port to the P2P port if you want to access the service from outside the network.

Now look at foo.cert.hash that will be created.  This is your key hash.  Absolutely do not use the included certificates for anything real, generate your own, they are only there for consistent testing.

On computer B, launch `python3 hardline.py` and visit hfhfdysvtziz6-e868423731872b8235a0adc9102bb45bb9e8321e.localhost:7009(replace hfhfdysvtziz6-e868423731872b8235a0adc9102bb45bb9e8321e with your key hash file contents)  You may have to retry a few times, but you should see the service.

The part of the URL after the dash must be kept as is, or it won't connect, but you can freely choose the part before(hfhfdysvtziz6), replacing it with up to 23 chars, so long as there are 
no dashes in it.  This can be used either as a weak layer of password protection, or to add vanity text.  You really shouldn't rely on the password though, it was only meant
to protect from casual snoopers, and you can't have two services with dofferent freetext and the same main part of the URL.


If you have Kivy installed, you can also run the GUI version.


### DrayerDB

DrayerDB is not currently supported outside the GUI app.  It will eventually be designed as a library. Eventuallu KaithemAutomation should be able to act as a sync server.


### Running as a proper service

Install with setup.py install or pip3 install hardline.  Then you can use the command "hardlined", which acts as both the client and the server.

It takes the following options:

#### --servicedir
A directory of services that you would like to expose, in simple INI format.  See service_config_example for examples. Default is /etc/hardline/services.
Here's what a complete file looks like:

``` ini
[Service]
#The service you want to expose
service=localhost
port=80

#Use absolute paths for non-example applications. 
#The service file, and all it's associated files like the hash get created on-demand.
#Look in myservice.cert.hash to find the hash ID for the URL.
certfile=myservice.cert

[Info]
title="My Awesome Service"

#Cache mode lets hardlinep2p cache the service.  In this mode it will
#Only support plain static content and will try to refresh files more than
#a week old(configurability and more intelligence coming soon).

#Files are cached as just plain files that only have the content.  
# Leave the "service" blank and this becomes cache-only, and a
# very convenient way to serve some files from an Android device.

# Because files and directories are the same thing to the web, newly-downloaded
#files get postfixed with @http to avoid conflict with dirs.

#For compatibility with manually-created files you want to serve, if the unpostfixed
#file already exists, it will be used instead, and will be updated according to the same rules.

#The root page will just be /cachedir/@http. /foo/bar will be /cachedir/foo/bar@http, but /foo/bar/ with 
# a trailing slash is /cachedir/foo/bar/@http

#Caches do not support POST or cookies. When HTML files are smaller than 1MB and not served with chunked encoding or a download related content disposition,
#Any embedded videos, audio, css links, and scripts that reference an absolute domain will be transparently converted to /cache_external_resource/path
#links instead, allowing us to modern sites that use a ton of subdomains.

#Cache services act like any other service with regards to remote access and the like.

[Cache]
directory="Leave this as an empty string for no cache"

#All these are optional and have defaults:

#Time in seconds before trying to refresh a cache item.
maxAge= 36000000
#Size in bytes to try to limit the cache to
maxSize=256000000
#Try to keep the total downloading to under this many mb/s.
#Use this to protect your flash memory from cache churn!
#Bursts are allowed, the quota refills up to the 1 hour max.
downloadRateLimit=1200

#Dynamic content allows you to manually place a file ending with @mako
#as a handler.  /foo/bar?param=q gets mapped to /cachedir/foo/bar@mako.

#These files are never fetched from the site, updated, or deleted.  They are purely local,
#As a convenience for adding trivial bits of dynamic behavior to your app.
#There is NO sandboxing here whatsoever.  Use files containing @data if your app
#needs a bit of persistent storage.

#The template has access to variable:
#path, the str path,  __file__, the absolute location of the template file
dynamicContent=no

[Access]
#Set this to "no" to prevent publishing this service to the global DHT.
#This saves bandwidth but makes accessing the service unreliable outside your local network.
useDHT=yes
```

#### --p2pport
The port used for incoming secure connections. Default is 7008. This is the one you open on your firewall if you want to serve a public service(if UPnP doesn't do it for you).

### --localport
The port that your browser will use to connect to a hardline service.  Default is 7009.


## Android Support
There is an Android app that only supports client mode, but allows you to access the services on port 7009.  As it does not use any kind of DHT, data usage should be extremely low.
I don't have any new devices to test with, but it works fine on older android.  This is my very first android app ever, so expect bugs!

On Android, you can create services through the GUI. Cache and service info will Always be on the SD card if possible and will even be copied there from
internal storage. Keep both device and card safe if the private keys thereon are important!!!!!!


## Security Considerations

This is using SSL, and I've tried to keep things standard and avoid having too many places to mess up.  It provides an encrypted channel to a server, and does not allow
people to make malicious servers with the same hex identifier.

It does NOT provide any protection other than what you get with standard HTTPS(It tries to, but you shouldn't rely on that). People can sniff traffic to find the hex ID, and ANYONE can connect to a site that
is made public with this tool if they know that, meaning your service must provide any username/password auth thaty is neededed.

However, you should still keep your hex URLs secret from anyone who shouldn't be allowed to connect.  Many remote attackers cannot sniff traffic easily, and
we do not intentionally reveal the URL to anyone outside your network.  You should not rely on this, but it is a useful extra layer that makes attacks a bit harder.

Many applications already provide some basic username/password auth, and as such should be safe with this tool.

You, or the app you are using, have to provide your own login mechanism.  If you go to a site and don't see a password prompt, nobody else will either!

Another thing to keep in mind is that long strings of random chars all look the same. Don't open links from random places just because they look similar to the one you
want.


### The "password" before the hash

The "hfhfdysvtziz6" string before the hash is actually a very weak sort of extra password.  It is not sent until *after* the connection has already been set up using the main part of the URL, so it
cannot be sniffed the traditional way, except if you are on the same LAN as the server(not just the client), In which case you can get it through the service browsing feature.

In theory, it could be enough protection in 99% of cases, however, the browser or OS itself may leak this password through log files, analytics, DNS, etc, and attackers may well be on the same net as the server in some cases.  Still,  it should provide a useful bit of extra protection from remote attackers.

## Protocol

Bytes are tunneled 1-for-1 over an SSL connnection, except each side sends a JSON object for out-of-band setup info followed by \\n before any payload data.  The server uses the TL
server name to route, and the server buffers and sniffs the Host: in the HTTP stream.


### LAN Discovery

To look for something, multicast on addr= ("239.192.152.143", 6771).  An empty infohash indicates a general service discovery.

The multicast group and general format is the same as BitTorrent's LPD, but we do not use any of the BT protocol.

Discovery Message format(windoes style lien endinnggs)


HARDLINE-SEARCH * HTTP/1.1
Infohash: {Infohash}
cookie: {cookie}

To announce, use this packet, on multicast, or as a unicast response:

HARDLINE-SERVICE * HTTP/1.1
Port: {Port}
Infohash: {Infohash}
cookie: {cookie}
title: {title}


Cookie is to tell your messages apart from others.
Infohash is the 20 byte hex hash.  To slightly impede fingerprinting, we use a rolling code, rather than the real hash:
Take the raw bytes of the keyhash, append `struct.pack("<Q",int(time.time()/(3600*24)))` to the end, then blake2b hash it.  Take the first 20 bytes and hex encode it.


Port is the SSL server used to access the service, on the node sending the message
Title is free-text, only for the user, for use in local discovery.

### WAN Access

First, UPnP is used to expose the port.   It tries to claim the same exact P2P port it uses on the LAN first, but if that fails it tries the next one,
and so on.   If everything fails, it expects you to manually configure a mapping using the same p2p port. Currently this may not work at all without UPnP though.



#### Storing the home WAN IP for later

To find the public IP, we use a WANHosts key in the OOB data.  This may be a full "host:port" string which the client will store in a database.

When you go offline, it it is unlikely that your IP address has changed, as dynamic home IPs are fairly stable, so this should work 95% of the time.


#### Other approaches

Since 95% isn't enough, servers also advertise using OpenDHT, and clients use Jami's DHT proxy to make lookups, but only if everything else fails.

The DHT lookup key is computed as follows:

Take the raw bytes of the keyhash, append `struct.pack("<Q",int(time.time()/(3600*24)))` to the end, then blake2b hash it.  Take the first 20 bytes and hex encode it.

Pass that to the OpenDHT APIs.   If you want to use that key to make a raw looklup via the REST api of a DHT node, we then need to replicate the internal hashing that
seems to be customary with openDHT.

To do this, Take that hex value, encode it to bytes, and SHA1 it. Now take the first 20 bytes, hex encoded, and use it in the URL.

Complicated, but I wanted to stick to the most common OpenDHT APIs and follow along exactly.


The reason for the rolling-code is so that a very popular site can never permanently accidentally DDoS a small number of nodes, and to help hide your DHT address from
anyone who might want to DDoS you.

It also makes it harder for people who don't know the unhashed subdomain to use DHT lookups to tell when your service is, or is not online, which may provide some
useful information to some.

But largely, it is an abundance of caution due to ease of implementation.


### Security

The key hash we use is the first 20 bytes of the blake2b hash of exactly the DER encoded certificate.
Everything in the SSL cert is completely ignored, except for checking whether the hash properly matches, so you can use any cert 
that you want.



## DrayerDB in the GUI


### Posts

Everything centers around posts, which are basically social-media style posts, with(I think) way better search.

#### Table View

Every post has a "table view" with "data rows" which can be used for vaugely the same purpose as Excel spreadsheet rows.

#### Template Expressions

Posts have a sandboxed expression eval support.   You can put expressions inside {{ braces }} and the whole thing gets replaced with whatever is inside the
braces.

Expressions have can access data from the data rows. 

As we want to make the most common use case, summing up lists, as easy as possible, Columns are accessible as column objects.

You can just do SUM(value) to add up the "value" column of every row, ignoring rows that lack it, or have a non-numeric value.


#### Available Functions

##### SUM(column)

##### AVG(column)
Average column value, ignoring invalid non-numbers and missing values

##### LATEST(column)
Gets the first in a list, which will be be the most recent.

##### RANDSELECT(column)
Gets a random selection of one of the values from the column.  Note that the value is cached and might not change very often.

##### CONVERT(val, unit, to)
Convert val from unit to to, as in CONVERT(1,'in','mm'). Same as traditional spreadsheets.

##### NUMINPUT(val, default, unit)
Create an input box for the viewer, return the inputted val or the default.  User can change the unit, but returned value
is always in selected unit.

Input box values are not saved anywhere and disappear when you leave the page. They are meant for making quick calculators.

These input boxes show in feed view and and in table view, but currently do not show in edit view.


### Sync

To sync, you must enable the sync server on a node by giving it a server name in the global settings panel.  This creates a standard HardlineP2P service that will show up
in the service listing.

This URL may be used as the sync URL for a stream in it's stream settings.


To sync, the sync key must be the same on both nodes.   For 2-way sync, the write password must match. In fact, you cannot change stream data
at all without the write password.

This is the only requirement,  you can create two different streams on different devices, change the sync info to match, and all your records from
both will merge.

### Password issues
You can arrange any crazy tree structure of servers that you want.  The only issue is that changing the keys is rather heavyweight, and can cause issues when syncing to a read-only node.

Every record is digitally signed(the "writePassword" is technically an ECC private key), so changing the key will cause nodes not to trust old cached records on read-only nodes.
Nodes with the writePassword will have to re-sign old records when they are requested.  

You may want to delete the database and start over on any read only nodes that act as servers.




## Hardline as an embeddable app



### daemonconfig

`from hardline import daemonconfig`


Daemonconfig provides a high-level interface for controlling a daemon that uses a settings dir.   It uses the standard file-based ways of managing services.




#### makeUserService(dir, name, *, title="A service", service="localhost", port='80', cacheInfo={}, noStart=False, useDHT='yes')

Dir will be the dir in which ot store the service file.
Name will be the name.

Service and port are the web service you wish to expose.

noStart avoids starting immediately.

#### def delUserService(dir, name)


#### def listServices(serviceDir)

List out the active user services.

#### def loadUserServices(serviceDir, only=None):
Load a service into the set of active services, from the service dir.


#### def loadUserDatabases(dir, only=None, forceProxy=None, callbackFunction=None):
Load databases from a folder into the open set of databases.  Use only to only load one. forceProxy overrides the sync server.
Callbackfunction sets the dataCallback of each databases

#### userDatabases

Dict indexed by name of all user databases.

#### closeUserDatabase(name)

Close but don't delete the underlying file or anything


#### delDatabase(dir, name):
Delete a database and all it's related files from dir.  Actually consideres anything of the form <name>.db.* to be related.