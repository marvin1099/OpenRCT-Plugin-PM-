#!/usr/bin/python
import os
import sys
import time
import json
import select
import argparse
import requests
import datetime
import urllib.request
from bs4 import BeautifulSoup
import zipfile

class OpenRCTPluginDownloader:
    """
    A class for downloading and managing OpenRCT2 plugins.

    This class provides methods to download, install, update, and remove OpenRCT2 plugins
    from the official plugin repository. It allows users to search for plugins, install them,
    and manage their configurations.

    Attributes:
        storefile (str): The path to the configuration file storing plugin data.
        baseurl (str): The base URL for the OpenRCT2 plugin repository.
        pages (str): The URL suffix for pagination while fetching plugin data from the repository.
        plugin (str): The type of resource, in this case, 'plugin'.
        github (str): The base URL for GitHub repositories.
        repo_api_base (str): The base URL for the GitHub API to fetch repository details.
        scanurl (str): The URL suffix to scan repository files using GitHub API.
        plugin_ignore_url (str): The URL to fetch the list of plugins to be ignored during installation.
        plugin_ignore_list (list): A list of plugin names to be ignored during installation.
        dignore (bool): A flag to indicate whether to ignore plugins mentioned in the ignore list.
        online_plugins (list): A list to store information about plugins available in the online repository.
        local_plugins (list): A list to store information about installed plugins.
        last_config_sync (int): The timestamp when the configuration data was last synchronized.
        last_update (int): The timestamp when the plugin data was last updated.
        update_config_interval (int): The interval (in seconds) for syncing the configuration data.
        update_plugins_interval (int): The interval (in seconds) for updating plugin data from the repository.
    """
    def __init__(self,config):
        """
        Initializes the OpenRCTPluginDownloader object.

        Args:
            config (str): The path to the configuration file.
        """
        self.storefile = config
        self.baseurl = 'https://openrct2plugins.org'
        self.pages = '/list/?sort=new&p='
        self.plugin = "plugin"
        self.github = "https://github.com"
        self.repo_api_base = "https://api.github.com/repos"
        self.scanurl = "git/trees/master?recursive=1"
        self.plugin_ignore_url = "https://codeberg.org/marvin1099/OpenRCT-Plugin-PM/raw/branch/main/ignore.json"
        self.instant_timeout = False
        self.plugin_ignore_list = []
        self.dignore = False
        self.online_plugins = []
        self.local_plugins = []
        self.last_config_sync = 0
        self.last_update = 0
        self.update_config_interval = 60*60
        self.update_plugins_interval = 60*60*24

    def load_data(self):
        """
        Loads plugin data from the configuration file.
        """
        if os.path.isfile(self.storefile):
            with open(self.storefile, 'r') as file:
                data = json.load(file)
                self.online_plugins = data.get("online_plugins", [])
                self.local_plugins = data.get("local_plugins", [])
                self.plugin_ignore_url = data.get("plugin_ignore_url", self.plugin_ignore_url)
                self.plugin_ignore_list = data.get("plugin_ignore_list", [])
                self.last_config_sync = data.get("last_config_sync", 0)
                self.last_update = data.get("last_plugin_update", 0)
                self.update_config_interval = data.get("config_sync_interval", 60*60)
                self.update_plugins_interval = data.get("plugin_update_interval", 60*60*24)

    def save_data(self):
        """
        Saves plugin data to the configuration file.
        """
        data = {
            "online_plugins": self.online_plugins,
            "local_plugins": self.local_plugins,
            "plugin_ignore_url": self.plugin_ignore_url,
            "plugin_ignore_list": self.plugin_ignore_list,
            "last_config_sync": self.last_config_sync,
            "last_plugin_update": self.last_update,
            "config_sync_interval": self.update_config_interval,
            "plugin_update_interval": self.update_plugins_interval
        }
        with open(self.storefile, 'w') as file:
            json.dump(data, file, indent=4)

    def update_plugins(self,skipcurrent=True):
        """
        Updates installed plugins to their latest versions.

        Args:
            skip_current (bool, optional): If True, skip plugins that are already up to date.
        """
        print("Updating plugins")
        for local_plugin in self.local_plugins:
            online_plugin = self.is_plugin_available(local_plugin['name'])
            if online_plugin:
                combined_info = {
                    "name": local_plugin['name'],
                    "download_time": int(time.time()),
                    "last_updated": online_plugin['last_updated'],
                    "files": []
                }
                # Update local plugin information
                index = self.get_plugin_index_by_name(local_plugin['name'])
                self.local_plugins[index] = combined_info
                self.github_download(online_plugin,skipcurrent)
                print("")
            else:
                print(f"Plugin '{local_plugin['name']}' not found online.")
            self.last_update = int(time.time())


    def get_last_page_number(self, soup):
        """
        Get the last page number of the plugin repository pagination.

        Parses the BeautifulSoup object representing the repository page and extracts the last page number
        from the pagination section.

        Args:
            soup (BeautifulSoup): The BeautifulSoup object representing the HTML page.

        Returns:
            int: The last page number of the repository pagination.
        """
        pagination = soup.find('ul', class_='pagination')
        last_page = pagination.find_all('li')[-2].text.strip()  # The second-to-last li element contains the last page number
        return int(last_page)

    def extract_info(self, item, title):
        """
        Extract specific information from a plugin item.

        Extracts the specified information (title) from the plugin item represented by the BeautifulSoup object.
        Used during web scraping to extract details like plugin name, author, stars, etc.

        Args:
            item (BeautifulSoup): The BeautifulSoup object representing the plugin item.
            title (str): The title of the information to be extracted.

        Returns:
            str: Extracted information or "N/A" if not found.
        """
        tag = item.find('span', title=lambda t: t and t.startswith(title))
        if tag:
            return tag.text.replace(title, '').strip()
        return "N/A"

    def convert_to_seconds(self, time_str):
        """
        Convert a time duration string to seconds.

        Parses a time duration string in the format 'X unit(s)' and converts it to seconds.
        Supports units: 'm', 'min', 'h', 'd', 'mo', 'y' (minutes, hours, days, months, years).

        Args:
            time_str (str): The time duration string to convert.

        Returns:
            str: The duration in seconds as a string.
        """
        time_dict = {"m": 60, "min": 60, "h": 60 * 60, "d": 24 * 60 * 60, "mo": 30.44 * 24 * 60 * 60, "y": 365.25 * 24 * 60 * 60}
        num, unit = time_str.split()
        num = int(num)
        seconds = num * time_dict.get(unit, 1)  # Default to 1 second for unknown units
        return str(int(seconds))

    def generate_github_url(self, plugin_item):
        """
        Generate the GitHub URL for a plugin item.

        Generates the GitHub URL for a given plugin item using its author and name attributes.

        Args:
            plugin_item (dict): The dictionary containing plugin information.

        Returns:
            str: The GitHub URL for the plugin item.
        """
        return f"{self.github}/{plugin_item['author']}/{plugin_item['name']}"

    def generate_repo_api_url(self, plugin):
        """
        Generate the GitHub repository API URL for a plugin.

        Generates the GitHub repository API URL for a given plugin using its author and name attributes.

        Args:
            plugin (dict): The dictionary containing plugin information.

        Returns:
            str: The GitHub repository API URL for the plugin.
        """
        return f"{self.repo_api_base}/{plugin['author']}/{plugin['name']}"

    def generate_plugin_url(self, plugin_item):
        """
        Generate the plugin's URL on the plugin repository website.

        Generates the URL for a given plugin item on the OpenRCT2 plugin repository website.

        Args:
            plugin_item (dict): The dictionary containing plugin information.

        Returns:
            str: The plugin's URL on the repository website.
        """
        return f"{self.baseurl}/{self.plugin}/{plugin_item['url_identifier']}"

    def load_ignore_list(self):
        """
        Load the plugin ignore list from the specified URL and update the local ignore list.

        Attempts to load the plugin ignore list from the configured URL. If successful, updates the local
        plugin_ignore_list attribute. If an error occurs during loading, the function proceeds without
        updating the local ignore list and returns the current ignore list.

        Returns:
            list: The updated plugin ignore list, or the current ignore list if no update was made.
        """
        try:
            with urllib.request.urlopen(self.plugin_ignore_url) as response:
                ignore_list_data = json.loads(response.read())
                # Merge the data from ignore_list_data with self.plugin_ignore_list, ignoring duplicates
                updated_ignore_list = list(set(self.plugin_ignore_list + ignore_list_data))
                self.plugin_ignore_list = updated_ignore_list
                return updated_ignore_list
        except Exception as e:
            # Handle any loading errors and return the current ignore list
            print(f"Error loading plugin ignore list: {e}")
            return self.plugin_ignore_list

    def update_index(self):
        """
        Update the plugin repository index.

        Fetches the plugin information from the OpenRCT2 plugin repository, including plugin names, authors, descriptions,
        stars, submission time, last update time, licenses, URL identifiers, and tags. Updates the online_plugins attribute.

        Returns:
            None
        """
        #return # REMOVE LATER STOPS REQESTS WHEN TESTING
        page = 1
        print("Updating index")
        print("Getting Page " + str(page))
        response = urllib.request.urlopen(self.baseurl + self.pages + str(page))
        soup = BeautifulSoup(response, 'html.parser')
        last_page = self.get_last_page_number(soup)


        plugin_list = []

        # Loop through all pages
        for page in range(1, last_page + 1):
            #if page > 2: # DELETE LATER, STOPS LOTS OF REQESTS
            #    break
            if page > 1:
                print("Getting Page " + str(page))
                response = urllib.request.urlopen(self.baseurl + self.pages + str(page))
                soup = BeautifulSoup(response, 'html.parser')
            # Extract information for each plugin item on the page
            plugin_items = soup.find_all('div', class_='row list-item')
            for item in plugin_items:
                plugin_info = {}
                plugin_info['name'] = item.find('h4').text.strip()
                plugin_info['description'] = item.find('p', class_='description').text.strip()
                plugin_info['author'] = item.find('span').find('a').text.strip()
                plugin_info['stars'] = int(item.find('span', title='Stars on GitHub').text.strip())
                plugin_info['submitted'] = int(time.time()) - int(self.convert_to_seconds(self.extract_info(item, 'Submitted:')))
                plugin_info['last_updated'] = int(time.time()) - int(self.convert_to_seconds(self.extract_info(item, 'Last updated:')))
                license_span = item.find('span', title='License')
                plugin_info['license'] = license_span.text.strip() if license_span else "N/A"
                plugin_info['url_identifier'] = item.find('a')['href'].split('/')[-2]
                plugin_info['tags'] = [tag.text.strip() for tag in item.find_all('li')]
                plugin_list.append(plugin_info)
            if page >= last_page:
                print("Finished all " + str(page) + " pages")

        self.online_plugins = plugin_list
        self.last_config_sync = int(time.time())

    def print_results(self,results):
        """
        Prints the details of plugins from the search results.

        Args:
            results (list): List of dictionaries containing plugin information.
                Each dictionary should have the following keys:
                - 'name': Plugin name
                - 'description': Plugin description
                - 'author': Plugin author
                - 'stars': Number of stars received by the plugin
                - 'submitted': Date of plugin submission
                - 'last_updated': Date of last update to the plugin
                - 'license': Plugin license information
                - 'url_identifier': Unique identifier for the plugin's URL
                - 'tags' (optional): List of tags associated with the plugin
        """
        print("-" * 50)
        for plugin in reversed(results):
            print(f"Name: {plugin['name']}")
            print(f"Description: {plugin['description']}")
            print(f"Author: {plugin['author']}")
            print(f"Stars: {plugin['stars']}")
            print(f"Submitted: {plugin['submitted']}")
            print(f"Last Updated: {plugin['last_updated']}")
            print(f"License: {plugin['license']}")
            print(f"URL Identifier: {plugin['url_identifier']}")
            if plugin['name'] in self.plugin_ignore_list:
                print("In Ignore List: True")
            if plugin['tags']:
                print(f"Tags: {', '.join(plugin['tags'])}")
            print("-" * 50)

    def sort_plugins_by_key(self, search_results, keys=[None]):
        """
        Sorts the search results based on the specified sorting key.

        Sorts the given search results based on the specified sorting key.
        Supported keys: None, 'n' for name, 's' for stars, 'm' for submitted, 'l' for last_updated, 'r' to reverse the results.

        Args:
            search_results (list): List of dictionaries representing matching plugins.
            sort_key (str, optional): The key to sort the results. Default is None.

        Returns:
            list: A list of dictionaries representing sorted plugins.
        """
        rev=False
        sort_key=False
        for found_key in keys:
            if found_key in ['n', 's', 'm', 'l',None]:
                sort_key = found_key
            if found_key == "r":
                rev = True
        if sort_key == False:
            print("Invalid sort key. Supported keys are: None, 'n' for name, 's' for stars, 'm' for submitted, 'l' for last_updated, 'r' for reverse results.")
            return search_results
        elif sort_key == None:
            return search_results

        sorted_results = []
        if sort_key == 'n':
            sorted_results = sorted(search_results, key=lambda x: x['name'], reverse=rev)
        elif sort_key == 's':
            sorted_results = sorted(search_results, key=lambda x: x['stars'], reverse=not rev)
        elif sort_key == 'm':
            sorted_results = sorted(search_results, key=lambda x: x['submitted'], reverse=rev)
        elif sort_key == 'l':
            sorted_results = sorted(search_results, key=lambda x: x['last_updated'], reverse=rev)

        return sorted_results

    def search_plugins(self, query, fields=None, number=0):
        """
        Search for plugins based on the specified query and fields.

        Searches for plugins in the online repository based on the given query and optional search fields.
        Supported fields: 'n' (name), 'd' (description), 'a' (author), 's' (stars),
        'g' (greater (can be used with s,m,u) number needs to be specified), 'x' to disable UnixTime - number (then its just number),
        'b' (below (can be used with s,m,u) number needs to be specified), 'm' (submission time), 'u' (last_update),
        'l' (license), 'i' (URL identifier), 't' (tags), 'p' (partial tag search), r (query and number have to be true).

        Returns a list of matching plugins.

        Args:
            query (str): The search query.
            fields (list, optional): List of search fields. Default is ['n'] (name).

        Returns:
            list: A list of dictionaries representing matching plugins.

        Example:
            To search for plugins with a name containing 'coaster' and more than 20 stars:
            >>> search_results = search_plugins('coaster',['n', 's', 'r', 'g'], '20')

            To search for plugins submitted within the last 30 days (in seconds so 30*24*60*60 = 2592000):
            >>> search_results = search_plugins('',['m', 'g'],'2592000')
        """
        if not fields:
            fields = ["n"]  # Default to searching in plugin names if fields are not provided
        if number == None:
            number = 0
        if "x" not in fields:
            unumber = int(time.time()) - int(number)
        else:
            unumber = int(number)

        search_results = []

        for plugin in self.online_plugins:
            matched = False
            intmatch = False
            strict = False
            if "r" in fields:
                strict = True
            else:
                strict = False
            for field in fields:
                if "g" in fields and str(number).isdigit():
                    if (field == "s" and int(number) < plugin.get("stars", 0)) or \
                        (field == "m" and int(unumber) < plugin.get("submitted", 0)) or \
                        (field == "u" and int(unumber) < plugin.get("last_updated", 0)):
                        intmatch = True
                elif "b" in fields and str(number).isdigit():
                    if (field == "s" and int(number) > plugin.get("stars", 0)) or \
                        (field == "m" and int(unumber) > plugin.get("submitted", 0)) or \
                        (field == "u" and int(unumber) > plugin.get("last_updated", 0)):
                        intmatch = True
                if field == "n" and query.lower() in plugin['name'].lower():
                    matched = True
                elif field == "d" and query.lower() in plugin['description'].lower():
                    matched = True
                elif field == "a" and query.lower() in plugin['author'].lower():
                    matched = True
                elif field == "s" and str(number).isdigit() and int(number) == plugin['stars']:
                    intmatch = True
                elif field == "m" and str(number).isdigit() and int(number) == plugin['submitted']:
                    intmatch = True
                elif field == "u" and str(number).isdigit() and int(number) == plugin["last_updated"]:
                    intmatch = True
                #elif filed = "o" and query.lower() in str(plugin["download_time"]) #think about adding in but wolud need to be read from self.local_plugins
                #    matched = True
                elif field == "l" and query.lower() in plugin['license'].lower():
                    matched = True
                elif field == "i" and query.lower() in plugin['url_identifier'].lower():
                    matched = True
                elif field == "t" and any(tag.lower() == query.lower() for tag in plugin['tags']):
                    if "p" in fields:
                        if any(query.lower() in tag.lower() for tag in plugin['tags']):
                            matched = True
                    else:
                        if any(tag.lower() == query.lower() for tag in plugin['tags']):
                            matched = True

                if matched and intmatch and strict:
                    search_results.append(plugin)
                    break  # Break the inner loop if a match is found in any specified field
                elif (matched or intmatch) and not strict:
                    search_results.append(plugin)
                    break  # Break the inner loop if a match is found in any specified field
        return search_results

    def input_with_timeout(self, prompt, timeout=5):
        """
        Get user input with a timeout.

        Displays the given prompt and waits for user input. If no input is received within the specified timeout,
        returns None. Otherwise, returns the user input.

        Args:
            prompt (str): The input prompt.
            timeout (int, optional): The timeout duration in seconds. Default is 5 seconds.

        Returns:
            str or None: User input or None if no input is received within the timeout.
        """
        if self.instant_timeout:
            return None
        print(f"Timeout in {timeout} seconds\n{prompt}", end='', flush=True)
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.readline().strip()
        else:
            return None

    def scan_repository_for_files(self, repo_api_url, file_extension):
        """
        Scan the repository for files with the specified file extension.

        Args:
            repo_api_url (str): The URL to the repository API.
            file_extension (str): The file extension to search for (e.g., '.js').

        Returns:
            list: A list of dictionaries, where each dictionary represents a file
            found in the repository. Each dictionary contains 'path', 'url', and
            'release' keys indicating the file path, download URL, and release status
            respectively.

        Note:
            This function uses the GitHub API to fetch the repository tree and scans
            for files with the specified extension. It returns a list of dictionaries,
            each representing a file found in the repository.
        """
        files = []
        try:
            # Fetch the repository tree using the GitHub API v3
            tree_url = f"{repo_api_url}/{self.scanurl}"
            response = requests.get(tree_url, headers={"Accept": "application/vnd.github.v3+json"})
            tree_data = response.json()

            # Scan files in the repository tree
            if 'tree' in tree_data:
                for item in tree_data['tree']:
                    if item['type'] == 'blob' and item['path'].endswith(file_extension):
                        file_info = {
                            'path': item['path'],
                            'url': item['url'],
                            'release': False
                        }
                        files.append(file_info)
        except Exception as e:
            print(f"Error scanning repository: {e}")
        return files

    def sort_by_subfolder_depth(self, file_info):
        """
        Helper function to sort files based on their subfolder depth.

        Args:
            file_info (dict): Information about the file including its path.

        Returns:
            int: The depth of the subfolder containing the file.
        """
        return file_info['path'].count('/')

    def what_about_plugin(self, plugin_name):
        """
        Determine the status of a plugin (e.g., Current, Overdated, Uninstalled) based on its local and online data.

        Args:
            plugin_name (str): The name of the plugin.

        Returns:
            str: The status of the plugin (Outdated, Current, Overdated, Uninstalled, Missing, Offline).
        """
        local_plugin = next((p for p in self.local_plugins if p['name'] == plugin_name), None)
        online_plugin = next((p for p in self.online_plugins if p['name'] == plugin_name), None)

        if not local_plugin and not online_plugin:
            return "Missing"

        if not local_plugin:
            return "Uninstalled"

        if not online_plugin:
            return "Offline"

        local_last_updated = local_plugin['last_updated']
        #local_download_time = local_plugin['download_time']
        online_last_updated = online_plugin['last_updated']
        #online_submitted = online_plugin['submitted']

        if local_last_updated > online_last_updated:
            return "Overdated"
        elif local_last_updated == online_last_updated:
            return "Current"
        else:
            return "Outdated"

    def is_plugin_installed(self, plugin_name):
        """
        Check if a plugin is currently installed locally.

        Args:
            plugin_name (str): The name of the plugin.

        Returns:
            dict or None: The plugin information if installed, or None if not installed.
        """
        for plugin in self.local_plugins:
            if plugin['name'] == plugin_name:
                return plugin
        return None

    def match_installed_files_to_repo(self, installed_plugin, all_files):
        """
        Match files of an installed plugin to files available in the repository.

        Args:
            installed_plugin (dict): Information about the installed plugin.
            all_files (list): List of all files available in the repository.

        Returns:
            list, bool, list: List of matched files, boolean indicating if all files are matched, and list of unmatched files.
        """
        matched_files = []
        unmatched_files = []
        for installed_file in installed_plugin['files']:
            matched = False
            for repo_file in all_files:
                if repo_file['path'] == installed_file['path'] and repo_file['release'] == installed_file['release']:
                    matched_files.append(repo_file)
                    matched = True
                    break
            if not matched:
                unmatched_files.append(installed_file)

        all_files_matched = len(unmatched_files) == 0
        return matched_files, all_files_matched, unmatched_files

    def get_plugin_index_by_name(self, plugin_name):
        """
        Get the index of a plugin in the local plugins list based on its name.

        Args:
            plugin_name (str): The name of the plugin.

        Returns:
            int or None: The index of the plugin in the local plugins list, or None if not found.
        """
        for index, plugin in enumerate(self.local_plugins):
            if plugin['name'] == plugin_name:
                return index
        return None

    def remove_pl_files(self, files_to_remove):
        """
        Remove specified files from the local directory.

        Args:
            files_to_remove (list of dict): List of dictionaries containing file information.
                Each dictionary must have a 'path' key indicating the file path to be removed.

        Returns:
            None
        """
        for file_to_remove in files_to_remove:
            path_to_remove = os.path.basename(file_to_remove.get("path"))
            try:
                os.remove(path_to_remove)
            except:
                print(f"File not found: {path_to_remove}")
            else:
                print(f"Removed file: {path_to_remove}")

    def download_files(self, selected_files):
        """
        Download selected files from their URLs and save them locally.

        Args:
            selected_files (list): List of dictionaries containing file information including URLs.

        Returns:
            list: List of dictionaries containing information about the downloaded files.
        """
        downloaded_files = []
        for file_info in selected_files:
            try:
                response = requests.get(file_info['url'], stream=True)
                response.raise_for_status()
                file_name = os.path.basename(file_info['path'])
                with open(file_name, 'wb') as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                downloaded_files.append({"path": file_info['path'], "release": file_info['release']})
                print(f"Downloaded: {file_name}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to download: {file_info['path']} - {e}")
        return downloaded_files

    def fetch_repository_details(self, repo_api_url):
        """
        Fetch detailed information about a GitHub repository using its API URL.

        Args:
            repo_api_url (str): The GitHub API URL of the repository.

        Returns:
            dict or None: Dictionary containing repository details, or None if fetching fails.
        """
        try:
            response = requests.get(repo_api_url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            print(f"Error: {err}")
        return None

    def fetch_release_files(self, releases_url):
        """
        Fetch and return files available in a GitHub release.

        Args:
            releases_url (str): The GitHub API URL for the releases of a repository.

        Returns:
            list: List of dictionaries containing information about files available in the release.
        """
        try:
            release_data = requests.get(releases_url).json()
            assets = release_data[0].get('assets', [])
            return [{'path': asset['name'], 'url': asset['browser_download_url'], 'release': True} for asset in assets if asset['name'].endswith('.js')]
        except requests.exceptions.RequestException as e:
            print(f"Error fetching release files: {e}")
            return []

    def github_download(self,plugin,skipcurrent=False):
        """
        Download and install the specified plugin from GitHub.

        Args:
            plugin (dict): A dictionary containing plugin information including 'name',
                'author', etc.
            skipcurrent (bool, optional): Whether to skip downloading if the plugin is
                already up-to-date. Defaults to False.

        Note:
            This function downloads the plugin files, allows the user to select files
            for download, and updates the local plugin list with the downloaded files.
            It provides options to skip installation, reinstall the current file setup,
            or install with a different file setup.
        """
        #plugin_url = self.generate_github_url(plugin)
        repo_api_url = self.generate_repo_api_url(plugin)
        repo_data = self.fetch_repository_details(repo_api_url)
        last_update_time = repo_data['updated_at']
        state_select = None

        state = self.what_about_plugin(plugin['name'])
        if state == "Current" or state == "Overdated":
            if not skipcurrent:
                state_select = self.input_with_timeout("Version is allready up to date\n0. To skip install\n1. To reinstall the current file setup\n2. To reinstall with a other file setup\nYour choice: ", 20)
            else:
                print(f"Skiped {plugin['name']} becalse it was up to date")
            if not state_select or state_select == "0":
                return
            if state_select != "1":
                state_select = "2"

        downloaded_plugin = {
            "name": plugin['name'],
            "download_time": int(time.time()),  # Current Unix timestamp when the plugin is downloaded
            "last_updated": int(datetime.datetime.strptime(last_update_time, "%Y-%m-%dT%H:%M:%SZ").timestamp()),    # Use the last_update_time variable from your code
            "files": []
        }

        print("")
        # Scan files in the latest release
        if 'releases_url' in repo_data:
            release_files = self.fetch_release_files(repo_data['releases_url'].replace('{/id}', ''))
        else:
            release_files = []

        # Scan files in the repository
        files = self.scan_repository_for_files(repo_api_url, '.js')
        sorted_files = sorted(files, key=self.sort_by_subfolder_depth)

        all_files=release_files+sorted_files
        # Print result amount
        if state_select != "1":
            print(f"Found {len(release_files)} .js files in the latest release.")
            print(f"Found {len(files)} .js files in the repository.")
            print("")
            for index, file_info in enumerate(all_files, start=1):
                print(f"{index}. Path: {file_info['path']}, Release: {file_info['release']}")
                #URL: {file_info['url']}
            print("")

        if state_select:
            iplugin = self.is_plugin_installed(plugin['name'])
        if state_select == "1":
            selected_files, all_matched, unmatched = self.match_installed_files_to_repo(iplugin,all_files)
            if not all_matched:
                stayon = self.input_with_timeout("Not all files where matched, if you continue the following files will be removed\n" + '\n '.join(unmatched) + "\n0. skip\n1. continue anyway\nYour choice: ", 20)
                if not stayon or stayon == "0":
                    return
                self.remove_pl_files(unmatched)
        else:
            # Let the user select multiple files
            selections = self.input_with_timeout("Enter the numbers of the files to download (comma-separated), or '0' to abort: ", 40)
            print("")
            if not selections:
                selections = "1" # default selection is 1
            if selections and selections[0] != '0':
                selected_indices = selections.split(',')
                selected_files = [all_files[int(index)-1] for index in selected_indices if 1 <= int(index) <= len(sorted_files)]

        if selected_files:
            downloaded_plugin["files"] = self.download_files(selected_files)
        if downloaded_plugin["files"]:
            if state_select:
                self.local_plugins[self.get_plugin_index_by_name(plugin['name'])] = downloaded_plugin
            else:
                self.local_plugins.append(downloaded_plugin)
        else:
            if state_select:
                self.remove_pl_files(iplugin["files"])
                self.local_plugins.pop(self.get_plugin_index_by_name(plugin['name']))
            print(f"No Files selected, Skipping install")

    def is_plugin_available(self, plugin_name):
        """
        Check if the specified plugin is available in the online plugin repository.

        Args:
            plugin_name (str): The name of the plugin to check for availability.

        Returns:
            dict or None: A dictionary containing plugin information if the plugin is
            available online, or None if the plugin is not found.
        """
        for plugin in self.online_plugins:
            if plugin['name'] == plugin_name:
                return plugin
        return None

    def install_plugin(self, plugin_name):
        """
        Install the specified plugin.

        Args:
            plugin_name (str): The name of the plugin to install.

        Note:
            This function checks if the plugin is in the ignore list, searches for
            similar plugins if needed, allows the user to select a plugin, and installs
            the selected plugin. It provides options to skip installation or abort the
            installation process.
        """
        try:
            # Check if the plugin is already in the ignore list and if it is not found perfectly, then search for it
            if plugin_name in self.plugin_ignore_list and not self.dignore: # Only skip if the ignore list is enabled
                print(f"Plugin '{plugin_name}' is in the ignore list. looking for close matches")
                found_plugin = False
            else:
                found_plugin = self.is_plugin_available(plugin_name)
            if not found_plugin:
                if found_plugin == None:
                    print(f"Plugin '{plugin_name}' not found. Searching for similar plugins")
                search_results = self.search_plugins(plugin_name)

                if not self.dignore:
                    print("Checking for plugin results from ignore list and removing them")
                    search_results = [result for result in search_results if result['name'] not in self.plugin_ignore_list]

                if not search_results:
                    print(f"No similar plugins found for '{plugin_name}'. Installation aborted.")
                    return

                print(f"Similar plugins found:")
                for idx, result in enumerate(search_results, start=1):
                    print(f"{idx}. {result['name']}")
                print("")

                # Let the user select a plugin to install
                selection = self.input_with_timeout("Enter the number of the plugin to install, or '0' to abort: ",20)
                print("")
                if selection == None or selection == '0' or selection == '':
                    print("Installation aborted.")
                    return

                try:
                    selected_index = int(selection) - 1
                    selected_plugin = search_results[selected_index]
                    print(f"Installing plugin: {selected_plugin['name']}")
                    self.github_download(selected_plugin)
                    print("")
                except (ValueError, IndexError):
                    print("Invalid selection. Installation aborted.")
            else:
                print(f"Installing plugin: {plugin_name}")
                self.github_download(found_plugin)
                print("")
        except Exception as e:
            print(f"Error installing plugin: {e}")

    def remove_plugin(self, plugin_name):
        """
        Remove the specified plugin from the local installation.

        Args:
            plugin_name (str): The name of the plugin to remove.

        Note:
            This function removes the specified plugin's files from the local directory
            and updates the local plugin list.
        """
        state = self.what_about_plugin(plugin_name)
        if state == "Missing" or state == "Uninstalled":
            print("Plugin not installed, Skipping removeal")
            return
        idxplugin = self.get_plugin_index_by_name(plugin_name)
        self.remove_pl_files(self.local_plugins[idxplugin]['files'])
        self.local_plugins.pop(idxplugin)
        pass

    def list_installed_plugins(self):
        """
        List all installed plugins along with their details.

        Note:
            This function prints the names, last updated timestamps, download timestamps,
            and file details of all installed plugins.
        """
        print("-" * 50)
        for plugin in reversed(self.local_plugins):
            print(f"Name: {plugin['name']}")
            print(f"Last Updated: {plugin['last_updated']}")
            print(f"Downloaded On: {plugin['download_time']}")
            for plfile in plugin['files']:
                opath, fname = os.path.split(plfile['path'])
                if opath:
                    print(f"  File: {fname}, Online Path: {opath}/, Release: {plfile['release']}")
                else:
                    print(f"  File: {fname}, Release: {plfile['release']}")
            print("-" * 50)

    def list_online_plugins(self):
        """
        List all available online plugins along with their details.

        Note:
            This function prints the names, descriptions, authors, stars, submitted timestamps,
            last updated timestamps, licenses, URL identifiers, and tags of all available online plugins.
        """
        print("-" * 50)
        for plugin in reversed(self.online_plugins):
            print(f"Name: {plugin['name']}")
            print(f"Description: {plugin['description']}")
            print(f"Author: {plugin['author']}")
            print(f"Stars: {plugin['stars']}")
            print(f"Submitted: {plugin['submitted']}")
            print(f"Last Updated: {plugin['last_updated']}")
            print(f"License: {plugin['license']}")
            print(f"URL Identifier: {plugin['url_identifier']}")
            if plugin['name'] in self.plugin_ignore_list:
                print("In Ignore List: True")
            if plugin['tags']:
                print(f"Tags: {', '.join(plugin['tags'])}")
            print("-" * 50)

    def run(self, args):
        """
        Main function to run the plugin downloader based on the provided command-line arguments.

        Args:
            args (argparse.Namespace): Command-line arguments parsed by argparse.
        """
        self.load_data()

        if args.timeoutnow:
            self.instant_timeout = True

        if args.idxup or int(time.time()) - int(self.last_config_sync) > int(self.update_plugins_interval):
            self.update_index()

        if args.update or int(time.time()) - int(self.last_update) > int(self.update_plugins_interval):
            self.update_plugins()

        if args.dignore:
            self.dignore = True

        if args.ignoreurl:
            self.plugin_ignore_url = args.ignoreurl

        if args.query or args.install:
            self.plugin_ignore_list = self.load_ignore_list()

        if args.query or args.number:
            for plugin in args.query:
                self.print_results(self.sort_plugins_by_key(self.search_plugins(plugin, args.fields, args.number),args.sort))

        if args.install:
            for plugin in args.install:
                self.install_plugin(plugin)

        if args.remove:
            for plugin in args.remove:
                self.remove_plugin(plugin)

        if args.ols:
            self.list_online_plugins()

        if args.ls:
            self.list_installed_plugins()

        self.save_data()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='orct-pldl.py',
        description='A simple OpenRCT plugin finder and downloader',
        epilog='')
    parser.add_argument('-q', '--query', nargs="+", action='extend', help='search for an online database plugin')
    parser.add_argument('-n', '--number', type=int, help='search for stars, submitted and last_updated (use g or b in fields to specifie max or min)')
    parser.add_argument('-f', '--fields', nargs='+', default=['n'], choices=['n','d','a','s','g','b','m','l','i','x','t','r','p'],help='fields to search (n: name (default), d: description, a: author, s: stars, g: above, b: below, x: disable unixtime - number, m: submitted, l: license, i: url_identifier, t: tags, r: only query and number, p: enable partial tag search)')
    parser.add_argument('-s', '--sort', nargs='+',default=[None], choices=['n', 's', 'm', 'l', 'r'],help='field to sort the results (n: for name, s: stars, m: submitted, l: last_updated, r: reverse results)')
    parser.add_argument('-r', '--remove', nargs="+", action='extend', help='remove installed plugin')
    parser.add_argument('-i', '--install', nargs="+", action='extend', help='install online database plugin')
    parser.add_argument('-o', '--ols', action='store_true', help='list indexed online plugins')
    parser.add_argument('-u', '--update', action='store_true', help='force update plugins (default auto update every 24 hours)')
    parser.add_argument('-x', '--idxup', action='store_true', help='force update plugin index (default auto update every hour)')
    parser.add_argument('-t', '--timeoutnow', action='store_true', help='enable instant timeout (recommended on multiple installs, will just grab the first file for all online files)')
    parser.add_argument('-l', '--ls', action='store_true', help='list installed plugins')
    parser.add_argument('-d', '--dignore', action='store_true', help='disable ignore list')
    parser.add_argument('-g', '--ignoreurl', default='', help='set ignore url')
    parser.add_argument("-c", "--config", default="orct-pldl.json", help="Config file to use (default: orct-pldl.json)")
    args = parser.parse_args()
    downloader = OpenRCTPluginDownloader(args.config)
    downloader.run(args)
