#
# Author:      Lester Jackson
# GitHub:      https://github.com/lesterjackson
# Title:       MPSFastExitPython
# Published:   Inital September 8, 2021
# Description: A Python coded utility that can quickly (a) shutdown MPS active servers or (b) reduce max & standby limits to zero.
#              The utility be called from the command line or as a service from Azure Functions
# Support:     Implemented wtih Python 3.9.5
# Background:  The utility calls and returns PlayFab Multiplayer Server REST API responses
# Files:       mpsfastexit.py (app handlers), mpsfastexit.json (app configuration)
# Instructions:(1) Modify mpsfastexit.json, (2) Run mpsfastexit.py in same folder with mpsfastexit.json
# Tested:      Only tested in Windows, concievably should work in Linux and Mac OS X
# Copyright:   Lester Jackson (aka Bingfoot)
# License:     Apache License 2.0
# Resources:   https://docs.microsoft.com/en-us/rest/api/playfab/multiplayer/multiplayer-server
# Credits:     

#############################################################################
# MPS Fast Exit Import Modules
#############################################################################

import requests
import json
import os
import sys
import time
import uuid

#############################################################################
# MPS Fast Exit Global Variables
#############################################################################

#global dictionary settings
mps = {}
appchoice = {}
config = 'mpsfastexit.json'

#change endpoint for testing or unique vertical
endpoint = "playfabapi.com/" 

#default headers
headers = {
    "X-PlayFabSDK": "PostmanCollection-0.125.210628",
    "Content-Type": "application/json"    
}

#title id configured in mpsfastexit.json and populated at start of main loop
title_id = ""

#############################################################################
# MPS Fast Exit Helpers
#############################################################################

#Function that issues HTTP Post to PlayFab REST API
#Optional debug param of 1 prints status code, URL and API response
def MPSAPIHandler(method, headers, data, debug = 0):
    baseurl = "https://" + title_id + "." + endpoint + method
    responseAPI = requests.post(baseurl, headers = headers, json = data) 
    responseJSON = json.loads(responseAPI.text)
    if debug == 1:
        print("Status code: ", responseAPI.status_code)
        print(responseAPI.url)
        print(json.dumps(responseJSON, indent=2))
    
    return responseJSON
 
# Initializes utility as server side app; calls Authentication/GetEntityToken
def authUtility():

    method = "Authentication/GetEntityToken"
    data = {}
    resp = MPSAPIHandler(method, headers, data)
    if resp['code'] == 200:
        headers['X-EntityToken'] = resp['data']['EntityToken']
        return True
    else:
        print(method, " Fail")
        return False

# Initializes utility configuration; dependency on mpsutility.cfg file
# Populates secrete key and title id
def initConfig(debug=0):

    global config 
    mpsutilityconfig = {}

    try:
        fhand=open(config, "r")
    except:
        print("Required file {} not found".format(config))
        exit()

    count = 0

    jsonContent = fhand.read()
    mpsutilityconfig = json.loads(jsonContent)
    fhand.close()
    return mpsutilityconfig

def GetMaxAndStandbyLimits():

    maxservers = int(input("Enter max servers value between 0 to 200: "))
    while maxservers not in range(0,200):
        maxservers = int(input("Enter max servers value between 0 to 200: "))

    standbyservers = int(input("Enter standby servers value between 0 to 200: "))
    while standbyservers not in range(0,200):
        standbyservers = int(input("Enter standby servers value between 0 to 200: "))

    return maxservers, standbyservers 

#############################################################################
# MPS Hanbdlers
#############################################################################

# Lists MPS build settings; calls MultiplayerServer/ListBuildSummariesV2
def ListBuildSettings(debug):

    method = "MultiplayerServer/ListBuildSummariesV2"
    data = {'PageSize': '10'}
    resp = MPSAPIHandler(method, headers, data, debug)
    if resp['code'] == 200:
        buildlist=[]
        for x in resp['data']['BuildSummaries']:
            regionslist=[]
            build = {}

            build['BuildName'] = x['BuildName']
            build['BuildId'] = x['BuildId']

            for y in x['RegionConfigurations']:
                regionslist.append(y['Region'])
                
            build['RegionsList'] = regionslist
            buildlist.append(build)
            mps['builds']=buildlist
        return True
    else:
        return False

def UpdateServerLimits(bldDictionary):

    #Loop 1 - All Builds
    method = "MultiplayerServer/UpdateBuildRegion"
    bldregion = { 'Region': bldDictionary['Region'], 'MaxServers': mps['maxlimit'], 'StandbyServers': mps['standbylimit'] }
    data = {'BuildId': bldDictionary['BuildId'], 'BuildRegion': bldregion }
    resp = MPSAPIHandler(method, headers, data, 0)

    if resp['code'] == 200:
        return True
    else:
        print(json.dumps(resp, sort_keys=False, indent=4))
        return False

def ShutdownAllServers(bldDictionary):
    
    #Loop 1 - Fetch all servers to capture session IDs
    #regLength = bldDictionary['RegionLength']
    #for listmps in range(regLength):
       
        method = "MultiplayerServer/ListMultiplayerServers"
        data = {'BuildId': bldDictionary['BuildId'], 'Region': bldDictionary['Region'], 'PageSize': 120}
        resp = MPSAPIHandler(method, headers, data, 0)

        if resp['code'] == 200:
            sessionList=[]
            #Loop 2 - Fetch all sessions
            for x in resp['data']['MultiplayerServerSummaries']:
                if 'SessionId' in x:
                    sessionList.append(x['SessionId'])
        else:
            print(json.dumps(resp, sort_keys=False, indent=4))
            return False
    
        sessionListLength = len(sessionList)
        bldDictionary['SessionIds'] = sessionList
        if sessionListLength > 0:

            #Loop 3 - Iterate each session
            for y in range(sessionListLength):
                print("Shutting down Build {} ID = {} in {} where session = {}".format(bldDictionary['BuildName'],
                    bldDictionary['BuildId'], bldDictionary['Region'], bldDictionary['SessionIds'][y] ) )
                
                #Shutdown server with bldDictionary key values
                method = "MultiplayerServer/ShutdownMultiplayerServer"
                data = {'BuildId': bldDictionary['BuildId'], 'SessionId': bldDictionary['SessionIds'][y], 'Region':  bldDictionary['Region'] }
                resp = MPSAPIHandler(method, headers, data, 0)

                if resp['code'] != 200:
                    print(json.dumps(resp, sort_keys=False, indent=4))
                    
        return                

#############################################################################
# MPS Fast Exit Main Loop Support
#############################################################################

def MainLoopHandler(choice, mps):

    #If Update, get user input max and standby limits
    if choice == 1:
        maxlimit, standbylimit = GetMaxAndStandbyLimits()
        mps['maxlimit'] = maxlimit
        mps['standbylimit'] = standbylimit

    #Get Builds and Regions
    bldIndex = 0
    bldDictionary = {}
    for bld in mps["builds"]:
        regIndex = 0
        regLength = len(bld['RegionsList'])     #Get length of regions within build
        for region in range(regLength):         #Iterator among regions within build
            print("[Build# {}] - {} - {} - [Region# {}] - {}".format(bldIndex+1, bld['BuildName'], bld['BuildId'], regIndex+1, bld["RegionsList"][region]))
            bldDictionary = {'BuildName': bld['BuildName'], 'BuildId': bld['BuildId'], 'Region': bld["RegionsList"][region], 'RegionLength': regLength }
            
            if choice == 1:             #Update Build Region and Reduce Standby Limits
                UpdateServerLimits(bldDictionary)

            if choice == 2:            #Shutdown Multiplayer Server
                ShutdownAllServers(bldDictionary)    

            regIndex += 1
        bldIndex += 1

    return

# Menu driven user interface
def MenuHandler():
    os.system('cls')
    print("1 - Fast Update Standbys to Zero")
    print("2 - Fast Shutdown Active Servers")
    print("3 - Exit")
    return

#Defines main console loop and processes user input
def MainLoop():

    global title_id

    cfgResult = initConfig()
    title_id = cfgResult['title_id']                    #change title id to titles title id
    headers['X-SecretKey'] = cfgResult['secret_key']    #change X-SecretKey to titles secret key

    authResult = authUtility()      #Authenticate with PlayFab service
    ListBuildSettings(0)            #Initializes global MPS dictionary object

    firstRun = True
    while authResult == True:
        
        MenuHandler()

        choice = 0
        while choice not in range(1,4):
            choice = input("Chose a utility option: ")
            if choice.isnumeric():
                choice = int(choice)

        if choice == 3:                     #Exit application
            print("Exiting application")
            quit()
        else:
            MainLoopHandler(choice, mps)    #Handle Shutdown or Reduce Standby Limits

        firstRun = False


def initCommandLineOptions():

    bldChoice = {}
    status = 0
    argumentLength = len(sys.argv)

    if argumentLength == 2:
        print("mpsfastexit operation[update {build|region|standby|max} |shutdown] {build|region}")
        exit()

    #elif argumentLength == __:
        #bldChoice['BuildId']    = sys.argv[1]
        #bldChoice['Region']     = sys.argv[2]
        #make call to handler
        #check if sys.argv[3] isnumeric() is isalpha()
        
    if status == True:
        print(str(sys.argv), "successfully executed")
        exit()
    else:
        print(str(sys.argv), "failed")
        exit()
    


#############################################################################
# MPS Fast Exit Main Loop
#############################################################################

os.system('cls')        #Clear screen
MainLoop()              #Start main loop
