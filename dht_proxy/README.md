
Ye olde systemd Service, uise 
```
[Unit]
Description=OpenDHT crap proxy
After=network.target
Documentation=man:dhtnode(1)

[Service]
ExecStart=docker run -d -p4222:4222/udp  -p4223:4223/tcp aberaud/opendht dhtnode -b bootstrap.jami.net -p 4222 -s --proxyserver 4223

[Install]
WantedBy=multi-user.target
```
