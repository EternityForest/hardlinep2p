# hardlinep2p
Application-level P2P VPN for securely accessing personal servers without a VPN


## requirements

OpenSSL, libnacl

## What it does

Takes a service on computer A, and makes it available on computer B at KEYHASH.localhost:7009.  It does this with a daemon on both computers
and a tunnel between them, encrypted with SSL.





Computer B can discover the address of computer A if it is on the same network, eventually WAN discovery should exist.

On the computer that has the service(assuming it is on port 80), use  `python3 hardline.py --service localhost --serviceport 80 --certfile foo.cert --localport 6767 --p2pport 7684`

Now look at foo.cert.hash that will be created.  This is your key hash.  Absolutely do not use the included certificates for anything real, generate your own, they are only there for consistent testing.


On computer B, launch `python3 hardline.py` and visit e868423731872b8235a0adc9102bb45bb9e8321e.localhost:7009.  You may have to retry a few times, but you should see the service.
