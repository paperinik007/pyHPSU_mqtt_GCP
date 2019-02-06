#!/usr/bin/env python3
#
# -*- coding: utf-8 -*-
import configparser
import getopt
import sys
import socket
from HPSU.HPSU import HPSU
import time
from _thread import * 


def main(argv):
    cmd = []
    port = None
    driver = "PYCAN"
    verbose = "1"
    show_help = False
    output_type = "JSON"
    global default_conf_file
    default_conf_file = "/etc/pyHPSU/pyhpsu.conf"
    read_from_conf_file=False
    global config
    config = configparser.ConfigParser()
    languages = ["EN", "IT", "DE", "NL"]
    lg_code = "EN"
    socket_port=7060
    logger = None
    global n_hpsu
    options_list={}

    try:
        opts, args = getopt.getopt(argv,"p:d:v:o:l:g:f:P:", ["port=", "driver=", "verbose=", "output_type=", "language=", "log=", "config_file="])
    except getopt.GetoptError:
        print('pyHPSUserver.py -d DRIVER -c COMMAND')
        print(' ')
        print('           -P  --inetport        Networkport the server ist listen to')
        print('           -f  --config          Configfile, overrides given commandline arguments')
        print('           -d  --driver          driver name: [ELM327, PYCAN, EMU, HPSUD], Default: PYCAN')
        print('           -p  --port            port (eg COM or /dev/tty*, only for ELM327 driver)')
        #print('           -o  --output_type     output type: JSON')
        print('           -v  --verbose         verbosity: [1, 2]   default 1')
        print('           -l  --language        set the language to use [%s], default is \"EN\" ' % " ".join(languages))
        print('           -g  --log             set the log to file [_filename]')
        sys.exit(2)


    for opt, arg in opts:

        if opt in ("-f", "--config"):
            read_from_conf_file = True
            conf_file = arg
            options_list["config"]=arg

        if opt in ("-h", "--help"):
            show_help = True
            options_list["help"]=""

        elif opt in ("-d", "--driver"):
            driver = arg.upper()
            options_list["driver"]=arg.upper()

        elif opt in ("-p", "--port"):
            port = arg
            options_list["port"]=arg

        elif opt in ("-v", "--verbose"):
            verbose = arg
            options_list["verbose"]=""

        elif opt in ("-o", "--output_type"):
            output_type = arg.upper()
            options_list["output_type"]=arg.upper()

        elif opt in ("-l", "--language"):
            lg_code = arg.upper()
            options_list["language"]=arg.upper()
        
        elif opt in ("-P", "--inetport"):
            socket_port = arg()
            options_list["socket_port"]=arg

        elif opt in ("-g", "--log"):
            logger = logging.getLogger('pyhpsu')
            hdlr = logging.FileHandler(arg)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            hdlr.setFormatter(formatter)
            logger.addHandler(hdlr)
            logger.setLevel(logging.ERROR)
        options_list["cmd"]=cmd
    if verbose == "2":
        locale.setlocale(locale.LC_ALL, '')


    # get config from file if given....
    if read_from_conf_file:
        if conf_file==None:
            print("Error, please provide a config file")
            sys.exit(9)
        else:
            try:
                with open(conf_file) as f:
                    config.readfp(f)
            except IOError:
                print("Error: config file not found")
                sys.exit(9)
        config.read(conf_file)
        if config.has_option('PYHPSU','PYHPSU_DEVICE'):
            driver=config['PYHPSU']['PYHPSU_DEVICE']
        if config.has_option('PYHPSU','PYHPSU_PORT'):
            port=config['PYHPSU']['PYHPSU_PORT']
        if config.has_option('PYHPSU','PYHPSU_LANG'):
            lg_code=config['PYHPSU']['PYHPSU_LANG']
        if config.has_option('PYHPSU','OUTPUT_TYPE'):
            output_type=config['PYHPSU']['OUTPUT_TYPE']
        if config.has_option('PYHPSU','SOCKET_PORT'):
            socket_port=config['PYHPSU']['SOCKET_PORT']

    else:
        conf_file=default_conf_file

    #
    # now we should have all options...let's check them
    #
    # Check driver
    if driver not in ["ELM327", "PYCAN", "EMU", "HPSUD"]:
        print("Error, please specify a correct driver [ELM327, PYCAN, EMU, HPSUD] ")
        sys.exit(9)

    if driver == "ELM327" and port == "":
        print("Error, please specify a correct port for the ELM327 device ")
        sys.exit(9)

    # Check output type
    #if output_type not in PLUGIN_LIST:
    #    print("Error, please specify a correct output_type [" + PLUGIN_STRING + "]")
    #    sys.exit(9)

    # Check Language
    if lg_code not in languages:
        print("Error, please specify a correct language [%s]" % " ".join(languages))
        sys.exit(9)

    # Create a socket
    net_socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    net_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # bind to the socket
    net_socket.bind(('',socket_port))
    # listen to that socket
    net_socket.listen(3)
    print("pyHPSUserver is listening on port %s" % (socket_port) )
    
    while True:
        (clientsocket, address) = net_socket.accept() 
        print("Got connection from %s port %s " % (address[0],address[1]) ) 
        start_new_thread(clientthread, (clientsocket,address,driver,logger,port,cmd,lg_code,verbose,output_type))
        #print(address[0])
        #start_new_thread(testthread, (clientsocket,))
        

        
    clientsocket.close()




def clientthread(clientsocket,address,driver,logger,port,cmd,lg_code,verbose,output_type):
    cmd=[]
    global n_hpsu
    while True:
        try:
            read_command=clientsocket.recv(1024).decode()
            if "quit" in read_command:
                clientsocket.shutdown(socket.SHUT_RDWR)
                clientsocket.close()
                print("Connection from " + address[0] + " closed")
                return False
            else:
                cmd=read_command.split()
                n_hpsu = HPSU(driver=driver, logger=logger, port=port, cmd=cmd, lg_code=lg_code)
                return_command=read_can(driver, logger, port, cmd, lg_code,verbose,output_type)
                for item in return_command:
                    clientsocket.sendall((str(item) + "\n").encode("utf-8")) 

        except UnicodeDecodeError:
            pass
                        
        

def read_can(driver,logger,port,cmd,lg_code,verbose,output_type):
    arrResponse = []
    for c in n_hpsu.commands:
        setValue = None
        for i in cmd:
            if ":" in i and c["name"] == i.split(":")[0]:
                setValue = i.split(":")[1]

        i = 0
        while i <= 3:
            rc = n_hpsu.sendCommand(c, setValue)
            if rc != "KO":
                i = 4
                if not setValue:
                    response = n_hpsu.parseCommand(cmd=c, response=rc, verbose=verbose)
                    resp = n_hpsu.umConversion(cmd=c, response=response, verbose=verbose)
                    if resp:
                        arrResponse.append({"name":c["name"], "resp":resp, "timestamp":response["timestamp"]})
                            
                
            else:
                i += 1
                time.sleep(2.0)
                n_hpsu.printd('warning', 'retry %s command %s' % (i, c["name"]))
                if i == 4:
                    n_hpsu.printd('error', 'command %s failed' % (c["name"]))
    return arrResponse


if __name__ == "__main__":
    main(sys.argv[1:])


