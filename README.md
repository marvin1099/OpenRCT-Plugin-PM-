# OpenRCT-Plugin-PM Codeberg Index 
https://codeberg.org/marvin1099/OpenRCT-Plugin-PM#availability  
https://codeberg.org/marvin1099/OpenRCT-Plugin-PM#description  
https://codeberg.org/marvin1099/OpenRCT-Plugin-PM#install  
https://codeberg.org/marvin1099/OpenRCT-Plugin-PM#usage  
# OpenRCT-Plugin-PM Github Index 
https://github.com/marvin1099/OpenRCT-Plugin-PM#availability  
https://github.com/marvin1099/OpenRCT-Plugin-PM#description  
https://github.com/marvin1099/OpenRCT-Plugin-PM#install  
https://github.com/marvin1099/OpenRCT-Plugin-PM#usage  

# Availability
Main Repo: https://codeberg.org/marvin1099/OpenRCT-Plugin-PM  
Bakup Repo: https://github.com/marvin1099/OpenRCT-Plugin-PM  

# Description
A bady optimized portable OpenRCT plugin package manager written in python.  
The script gets all the plugins from the   
https://openrct2plugins.org/  
website mostly by web-scraping.  

# Install
First you need to download python and the python dependency  
```pip install beautifulsoup4 ```  
Then get the script from  
https://codeberg.org/marvin1099/OpenRCT-Plugin-PM/releases  
or get it from  
https://github.com/marvin1099/OpenRCT-Plugin-PM/releases  
Put the ```orct-cmd-plugin-dl.py``` in the openrct plugin folder  
Then run ```orct-cmd-plugin-dl.py``` inside the openrct plugin folder  
It is important that you run the script with the openrct plugin folder working directory  
This is so that the plugins and the config file all get written to the plugin folder

# Usage
    usage: orct-cmd-plugin-dl.py [-h] [-q QUERY] [-r REMOVE [REMOVE ...]] [-i INSTALL [INSTALL ...]] [-o] [-u] [-x] [-l]

    A simple OpenRCT plugin finder and downloader

    options:
    -h, --help            show this help message and exit
    -q QUERY, --query QUERY
                          search for a online database plugin
    -r REMOVE [REMOVE ...], --remove REMOVE [REMOVE ...]
                          remove installed plugin (supply empty str to remove all)
    -i INSTALL [INSTALL ...], --install INSTALL [INSTALL ...]
                          install online database plugin
    -o, --ols             list indexed online plugins
    -u, --update          force update plugins (default auto update every 24 hours)
    -x, --idxup           force update plugin index (default auto update every hour)
    -l, --ls              list installed plugins 