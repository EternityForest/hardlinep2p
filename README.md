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

The app(written in Kivy, and available for Android as well as the desktop) also lets you browse services connected to your LAN, and will eventually provide a few other similar conveniences.


Ideally, you'll be able to take home a smart device, plug it into your router, find it in the listing on the app, and click the button ot jump to the browser.

That bookmark will then work from anywhere in the world!

## Prior Art:

* Abandoned Mozilla project that was similar: [https://wiki.mozilla.org/FlyWeb]
* Tor/I2P hidden services provide similar functionality(but Hardline makes no attempt to be anonymous or hide your IP, only to secure trafffic.)

## Not similar

* IPFS: We aren't bittorrent, we don't use any sort of content-addressible stuff, we provide connections to self-hosted services. 
* Zerotier:  This is not a VPN. It will not conflict with a VPN(Although it may ignore it and use the LAN instead), and it does not act at the low-level network layer.


## How it works.
Computer B can discover the address of computer A if it is on the same network, otherwise it will fall back to using a public OpenDHT proxy that I am hosting(If you run one, let me know, I'd love to add some redundancy!)

If computer B has ever successfully connected to that service before, it will remember the addresses and try those, even if ther DHT proxy
is down.  Even if the initial connection was via LAN, computer A will tell B where to find it on the WAN later.

Computer A can provide multiple prioritized WAN addresses.  If it is conected to the Yggdrasil mesh, it will provide that address in the list, after the normal WAN address,
so you should be able to connect even without the internet on isolated meshnets.

Computer A uses the native DHT, and does not rely on a proxy.



### Using It

On the computer that has the service(assuming it is on port 80), use  `python3 hardline.py --service localhost --serviceport 80 --certfile foo.cert --localport 6767 --p2pport 7684`

You must have UPnP on your router, or manually open a port to the P2P port if you want to access the service from outside the network.

Now look at foo.cert.hash that will be created.  This is your key hash.  Absolutely do not use the included certificates for anything real, generate your own, they are only there for consistent testing.

On computer B, launch `python3 hardline.py` and visit hfhfdysvtziz6-e868423731872b8235a0adc9102bb45bb9e8321e.localhost:7009(replace hfhfdysvtziz6-e868423731872b8235a0adc9102bb45bb9e8321e with your key hash file contents)  You may have to retry a few times, but you should see the service.

The part of the URL after the dash must be kept as is, or it won't connect, but you can freely choose the part before(hfhfdysvtziz6), replacing it with up to 23 chars, so long as there are 
no dashes in it.  This can be used either as a weak layer of password protection, or to add vanity text.  You really shouldn't rely on the password though, it was only meant
to protect from casual snoopers, and you can't have two services with dofferent freetext and the same main part of the URL.


If you have Kivy installed, you can also run the GUI version.


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
```

#### --p2pport
The port used for incoming secure connections. Default is 7008. This is the one you open on your firewall if you want to serve a public service(if UPnP doesn't do it for you).

### --localport
The port that your browser will use to connect to a hardline service.  Default is 7009.


## Android Support
There is an Android app that only supports client mode, but allows you to access the services on port 7009.  As it does not use any kind of DHT, data usage should be extremely low.
I don't have any new devices to test with, but it works fine on older android.  This is my very first android app ever, so expect bugs!

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
Infohash is the 20 byte hex hash.
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

### Security

The key hash we use is the first 20 bytes of the blake2b hash of exactly the DER encoded certificate.
Everything in the SSL cert is completely ignored, except for checking whether the hash properly matches, so you can use any cert 
that you want.
