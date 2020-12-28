# hardlinep2p
Application-level P2P tunnelling for securely accessing personal servers without a VPN. Currently alpha/everiything supbject to change!!


## requirements

OpenSSL, pynacl, dhtnode(On server side only), requests,six,lxml,dateutil

## What it does

Takes a service on computer A, and makes it available on computer B at KEYHASH.localhost:7009.  It does this with a daemon on both computers
and a tunnel between them, encrypted with SSL.


Computer B can discover the address of computer A if it is on the same network, otherwise it will fall back to using a public OpenDHT proxy(Still waiting to hear about
the official ToS for this proxy).  If computer B has ever successfully connected to that service before, it will remember the addresses and try those, even if ther DHT proxy
is down.  Even if the initial connection was via LAN, computer A will tell B where to find it on the WAN later.

Computer A can provide multiple prioritized WAN addresses.  If it is conected to the Yggdrasil mesh, it will provide that address in the list, after the normal WAN address,
so you should be able to connect even without the internet on isolated meshnets.

Computer A uses the native DHT, and does not rely on a proxy.

### Using It

On the computer that has the service(assuming it is on port 80), use  `python3 hardline.py --service localhost --serviceport 80 --certfile foo.cert --localport 6767 --p2pport 7684`

You must have UPnP on your router, or manually open a port to the P2P port if you want to access the service from outside the network.

Now look at foo.cert.hash that will be created.  This is your key hash.  Absolutely do not use the included certificates for anything real, generate your own, they are only there for consistent testing.


On computer B, launch `python3 hardline.py` and visit e868423731872b8235a0adc9102bb45bb9e8321e.localhost:7009.  You may have to retry a few times, but you should see the service.

## Android Support
There is an Android app that only supports client mode, but allows you to access the services on port 7009.  As it does not use any kind of DHT, data usage should be extremely low.
I don't have any new devices to test with, but it works fine on older android.  This is my very first android app ever, so expect bugs!

## Security Considerations

This is using SSL, and I've tried to keep things standard and avoid having too many places to mess up.  It provides an encrypted channel to a server, and does not allow
people to make malicious servers with the same hex identifier.

It does NOT provide any protection other than what you get with standard HTTPS. People can sniff what domain you are visiting, and ANYONE can connect to a site that
is made public with this tool.

Many applications already provide some basic username/password auth, and as such should be safe with this tool.

You, or the app you are using, have to provide your own login mechanism.  If you go to a site and don't see a password prompt, nobody else will either!


Another thing to keep in mind is that long strings of random chars all look the same. Don't open links from random places just because they look similar to the one you
want.

## Protocol

Bytes are tunneled 1-for-1 over an SSL connnection, except each side sends a JSON object followed by \\n before any payload data.
Discovery Message format(windoes style lien endinnggs)


### LAN Discovery

To look for something, multicast on addr= ("239.192.152.143", 6771).  An empty infohash indicates a general service discovery.

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

Title is free-text.

### WAN Access

Coming soon.  Because of the difficulty of this, a combination of a few approaches are needed.

First, UPnP is used to expose the port.   It tries to claim the same exact P2P port it uses on the LAN first, but if that fails it tries the next one,
and so on.   If everything fails, it expects you to manually configure a mapping using the same p2p port.


#### Storing the home WAN IP for later

To find the public IP, we use a WANHosts key in the OOB data.  This may be a full "host:port" string which the client will store in a database.

When you go offline, it it is unlikely that your IP address has changed, as dynamic home IPs are fairly stable, so this should work 95% of the time.


#### Other approaches

Since 95% isn't enough, some kind if DHT or discovery server is obviously going to be needed. Coming soon!

### Security

The key hash we use is the first 20 bytes of the blake2b hash of exactly the DER encoded certificate.
Everything in the SSL cert is completely ignored, except for checking whether the hash properly matches, so you can use any cert 
that you want.
