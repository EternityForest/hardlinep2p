#!/usr/bin/python3
import hardline 


if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='P2P Tunneling proxy on the LAN')


    parser.add_argument('--localport', help='Pages will be proxied at <KEYID>.localhost:<PORT>.  Set to 0 to disable proxying.',default="7009")
    parser.add_argument('--p2pport', help='Port used for secure P2P',default="7008")
    parser.add_argument('--service', help='hostname of a service you want to make available. Requires --certfile',default="localhost")
    parser.add_argument('--serviceport', help='port of a service you want to make available.',default="80")
    parser.add_argument('--certfile', help='Certificate file for publishing a service. Created if nonexistant.',default="foo.cert")
    parser.add_argument('--servicetitle', help='title of a service you want to make available.',default="Title here")

    args = vars(parser.parse_args())

    print("Local port: "+args['localport'])
    print("P2P port: "+args['p2pport'])
    hardline.P2P_PORT= int(args['p2pport'])

    if args['service']:
        print("Serving a service from "+args['service'])
        s = hardline.Service(args['certfile'], args['service'], args['serviceport'], {'title':args['servicetitle']}  )

    hardline.start(int(args['localport']))
