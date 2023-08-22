#!/home/marvin/.local/pipx/venvs/steamfiles/bin/python
from bs4 import BeautifulSoup
import urllib.request
import urllib
import zipfile
import argparse
import time
import json
import sys
import os



storefile = "orct-cmd-plugin-dl.json"

updatepluginconfig = 3600 # Only Update plugin page eatch 3600 secs (1 hour)
updateplugins = 86400 # Update plugins eatch 86400 secs (24 hours)

pagnum = "1"
maxpag = "1"

pages = '<li class="page-item"><a class="page-link" href="/list/'
plugin = '<a href="/plugin/'

baseurl = 'https://openrct2plugins.org'

parser = argparse.ArgumentParser(
    prog='orct-cmd-plugin-dl.py',
    description='A simple OpenRCT plugin finder and downloader',
    epilog='')
parser.add_argument('-q', '--query', default='', help='search for a online database plugin')
parser.add_argument('-r', '--remove', nargs="+", action='extend', help='remove installed plugin (supply empty str to remove all)')
parser.add_argument('-i', '--install', nargs="+", action='extend', help='install online database plugin')
parser.add_argument('-o', '--ols', action='store_true', help='list indexed online plugins')
parser.add_argument('-u', '--update', action='store_true', help='force update plugins (default auto update every 24 hours)')
parser.add_argument('-x', '--idxup', action='store_true', help='force update plugin index (default auto update every hour)')
parser.add_argument('-l', '--ls', action='store_true', help='list installed plugins')

args = parser.parse_args()

pluginlist = []
pluginnames = []

fjson = {}
lasttime = int(time.time())
plugintime = int(time.time())
fileup = True
if os.path.isfile(storefile) == True:
    f = open(storefile)
    fjson = json.loads(f.read())
    f.close()
    lasttime = fjson["indextime"]
    plugintime = fjson["plugintime"]
    timediv=lasttime-int(time.time())
    if timediv < updatepluginconfig:
        pluginlist = fjson["pluginlist"]
        for i in pluginlist:
            pluginnames.append(i.split("/")[-1])
        if args.idxup == False:
            fileup = False


if (args.install != None or args.query != '') and (pluginlist == [] or fileup == True):
    pluginlist = []
    pluginnames = []
    while int(pagnum) <= int(maxpag):
        webdatali = str(BeautifulSoup(urllib.request.urlopen(baseurl + '/list/?&p=' + pagnum).read(), "lxml"))
        webdatasp = webdatali.split("\n")

        for i in webdatasp:
            if len(i) >= len(pages) and i[:len(pages)] == pages:
                maxpag = i.split('"')[5][14:] # "1"
            elif len(i) >= len(plugin):
                #print(i[:len(plugin)])
                if i[:len(plugin)] == plugin:
                    if len(pluginlist) == 0 or pluginlist[-1] != i.split('"')[1]:
                        pluginlist.append(i.split('"')[1])
                        pluginnames.append(pluginlist[-1].split("/")[-1])
        pagnum = str(int(pagnum)+1)
        if int(maxpag) < int(pagnum)-1:
            maxpag = str(int(pagnum)-1)
        print("Finished page " + str(int(pagnum)-1) + " of " + maxpag)
        time.sleep(0.1)

if fileup == True:
    lasttime == int(time.time())
f = open(storefile, "w")
try:
    fjson["installed"] += []
except:
    fjson["installed"] = []
try:
    fjson["pluginfiles"] += []
except:
    fjson["pluginfiles"] = []
f.write(json.dumps({"indextime":lasttime,"plugintime":plugintime,"installed":fjson["installed"],"pluginfiles":fjson["pluginfiles"],"pluginnames":pluginnames}, indent=4, separators=(',', ': ')))
f.close()

querykeys = []
if args.query != '':
    for i in range(1,len(pluginnames)+1):
        if pluginnames[i-1].lower().find(args.query.lower()) != -1:
            querykeys.append(i-1)

    if len(querykeys) == 0:
        print("-- Your query returned no results --")
    else:
        print("-- Your query returned --")
    i = 0
    for i in range(1,len(querykeys)+1):
        print(pluginnames[querykeys[-i]],end="")
        if (i % 3) == 0:
            print("")
        elif (len(querykeys) != (i+1)):
            print("   ",end="")
    if (i % 3) != 0:
        print("")
    if len(querykeys) != 0:
        print("-- Finished query (the bottom result is the newest) --")
    print("")


if args.remove != None and len(fjson["installed"]) > 0:

    for i in list(args.remove):
        for j in range(1,len(fjson["installed"])+1):
            if i == fjson["installed"][j-1] or args.remove == [""]:
                print("Removed the plugin: " + fjson["installed"].pop(j-1))
                rmfile = fjson["pluginfiles"].pop(j-1)
                try:
                    os.remove(rmfile)
                except:
                    pass
                break


if args.install != None:
    gitdown = '<a class="download-plugin text-white btn btn-primary" href="https://github.com' #
    for i in args.install:
        for j in range(1,len(pluginnames)):
            if pluginnames[j-1].lower() == i.lower():
                if i not in fjson["installed"]:
                    get = baseurl + pluginlist[j-1]
                    plugpage = str(BeautifulSoup(urllib.request.urlopen(get).read(), "lxml"))
                    singpluglist = plugpage.split("\n")
                    #https://api.github.com/repos/jbodner09/openrct2-waittime/releases/latest
                    #https://github.com/jbodner09/openrct2-waittime/releases/latest
                    for g in singpluglist:
                        if len(g) >= len(gitdown) and g[:len(gitdown)] == gitdown:
                            githubpage = g.split('"')[3]
                    gitapipage = githubpage.replace("https://github.com/","https://api.github.com/repos/")
                    try:
                        gitreturn = urllib.request.urlopen(gitapipage[:-7]).read()
                    except:
                        try:
                            gitapipage = githubpage[:-16] + ".git"
                            gitreturn = str(BeautifulSoup(urllib.request.urlopen(gitapipage).read(), "lxml"))
                        except:
                            print("Plugin or github page unavalible: " + githubpage)
                            break
                        else:
                            findjsf = '<span class="css-truncate css-truncate-target d-block width-fit"><a class="js-navigation-open Link--primary" data-turbo-frame="repo-content-turbo-frame"'
                            jsfilspreo = []
                            for g in gitreturn.split("\n"):
                                if len(g) >= len(findjsf):
                                    if g[:len(findjsf)] == findjsf:
                                        foundfile = g.split('"')[7]
                                        if foundfile.endswith(".js"):
                                            jsfilspreo.append(foundfile)
                            if len(jsfilspreo) == 0:
                                print("Plugin not found on: " + githubpage)
                            elif len(jsfilspreo) == 1:
                                jsfilspreo = jsfilspreo[0]
                                jsfilist = jsfilspreo.split("/")
                                jsfilist[-3] = "raw"
                                urlfil = "https://github.com" + "/".join(jsfilist)
                                strfil = str(BeautifulSoup(urllib.request.urlopen(urlfil).read(), "lxml"))[15:-18]
                                try:
                                    #urllib.request.urlretrieve(urlfil, jsfilist[-1])
                                    f = open(jsfilist[-1], "w")
                                    f.write(strfil)
                                    f.close()
                                except:
                                    print("Download failed skipping download")
                                    break
                                fjson["installed"].append(pluginnames[j-1])
                                fjson["pluginfiles"].append(jsfilist[-1])
                                print("The plugin was grabed through a backup method the file is: " + jsfilist[-1])
                                print("Got the plugin: " + pluginnames[j-1])
                            else:
                                print("Found multiple js files through a backup method: ")
                                print("0: Do not download anything")
                                for g in range(1,jsfilspreo):
                                    print(str(g) + ": " + jsfilspreo[g])
                                x = input("Enter plugin to download: ")
                                try:
                                    int(x)
                                except:
                                    print("Not a number skipping download")
                                    break
                                if x == 0:
                                    break
                                elif x > 0:
                                    try:
                                        jsfilspreo = jsfilspreo[x-1]
                                    except:
                                        print("Number above max skipping download")
                                    else:
                                        jsfilist = jsfilspreo.split("/")
                                        jsfilist[-3] = "raw"
                                        urlfil = "https://github.com" + "/".join(jsfilist)
                                        try:
                                            urllib.request.urlretrieve("/".join(jsfilist), jsfilist[-1])
                                        except:
                                            print("Download failed skipping download")
                                            break
                                        fjson["installed"].append(pluginnames[j-1])
                                        fjson["pluginfiles"].append(jsfilist[-1])
                                        print("Got the plugin: " + pluginnames[j-1])
                                else:
                                    print("Not a valid number skipping download")
                            break
                    #str(BeautifulSoup(urllib.request.urlopen(githubpage.replace("https://github.com/","https://api.github.com/repos/")).read(), "lxml"))
                    #print("Got github link: " gitreturn)
                    try:
                        gitreturn = urllib.request.urlopen(gitapipage).read()
                    except:
                        pass
                    try:
                        gitlatjs = json.loads(gitreturn)
                    except:
                        print("Error no asset url on " + gitreturn)
                    else:
                        if type(gitlatjs) == type([]):
                            gitassets = gitlatjs[0]["assets"][0]["url"]
                        else:
                            gitassets = gitlatjs["assets"][0]["url"]
                        #https://api.github.com/repos/jbodner09/openrct2-waittime/releases/assets/122131590
                        gitfiles = urllib.request.urlopen(gitassets).read()
                        try:
                            gitjsonfile = json.loads(gitfiles)
                            gitjsonurl = gitjsonfile["browser_download_url"]
                            gitjsonname = gitjsonfile["name"]
                        except:
                            print("Error download url on " + gitfiles)
                        else:
                            try:
                                urllib.request.urlretrieve(gitjsonurl, gitjsonname)
                            except:
                                print("The following download failed: " + gitjsonurl)
                            else:
                                if gitjsonname[-3:] == ".js":
                                    fjson["installed"].append(pluginnames[j-1])
                                    fjson["pluginfiles"].append(gitjsonname)
                                    print("Got the plugin: " + pluginnames[j-1])
                                elif gitjsonname[-4:] == ".zip":
                                    with zipfile.ZipFile(gitjsonname, 'r') as zipObject:
                                        listOfFileNames = zipObject.namelist()
                                        GotPlug = False
                                        for fileName in listOfFileNames:
                                            if fileName.endswith('.js'):
                                                zipObject.extract(fileName) # , 'folder'
                                                fjson["installed"].append(pluginnames[j-1])
                                                fjson["pluginfiles"].append(fileName)
                                                print("Got the plugin: " + pluginnames[j-1])
                                                GotPlug = True
                                                break
                                        if GotPlug == False:
                                            print("There was no plugin in the released zipfile: " + gitjsonfile)
                                    os.remove(gitjsonname)
                                else:
                                    print("The asset file has a unkown filetype: " + gitjsonfile)
                                    os.remove(gitjsonname)
                else:
                    print("The following plugin is allready installed: " + i)

if args.update == True or int(time.time())-plugintime > updateplugins:
    cmd = sys.argv[0] + " -x -r \"" + "\" \"".join(fjson["installed"]) + "\" -i \"" + "\" \"".join(fjson["installed"]) + "\""
    os.system(cmd)

f = open(storefile, "w")
f.write(json.dumps({"indextime":lasttime,"plugintime":plugintime,"installed":fjson["installed"],"pluginfiles":fjson["pluginfiles"],"pluginlist":pluginlist}, indent=4, separators=(',', ': ')))
f.close()

if args.ols == True:
    print("-- Listing Indexed Online Plugins --")
    lenplunam = len(fjson["pluginnames"])+1
    i = 0
    for i in range(1,lenplunam):
        print(fjson["pluginnames"][-i],end="")
        if (i % 3) == 0:
            print("")
        elif (lenplunam != (i+1)):
            print("   ",end="")
    if (i % 3) != 0:
        print("")
    print("-- Finished Listing (Bottom Result Is The Newest) --")

if args.ls == True:
    print("-- Listing Installed Plugins --")
    leninstal = len(fjson["installed"])+1
    i = 0
    for i in range(1,leninstal):
        print(fjson["installed"][-i],end="")
        if (i % 3) == 0:
            print("")
        elif (leninstal != (i+1)):
            print("   ",end="")
    if (i % 3) != 0:
        print("")
    print("-- Finished Listing --")
