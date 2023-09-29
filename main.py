# Import all the things
import json
import datetime
import configparser
import colorama
from sys import exit

from mosyle import Mosyle
from snipe import Snipe
from colorama import Fore
from colorama import Style

# Converts datetim/e to timestamp for Mosyle
ts = datetime.datetime.now().timestamp() - 200

# Set some Variables from the settings.conf:
config = configparser.ConfigParser()
config.read('settings.ini')

# This is the address, cname, or FQDN for your snipe-it instance.
snipe_url = config['snipe-it']['url']
apiKey = config['snipe-it']['apiKey']
defaultStatus = config['snipe-it']['defaultStatus']
apple_manufacturer_id = config['snipe-it']['manufacturer_id']
macos_category_id = config['snipe-it']['macos_category_id']
ios_category_id =  config['snipe-it']['ios_category_id']
tvos_category_id =  config['snipe-it']['tvos_category_id']
macos_fieldset_id = config['snipe-it']['macos_fieldset_id']
ios_fieldset_id = config['snipe-it']['ios_fieldset_id']
tvos_fieldset_id = config['snipe-it']['tvos_fieldset_id']
deviceTypes = config['mosyle']['deviceTypes'].split(',')

snipe_rate_limit = int(config['snipe-it']['rate_limit'])

apple_image_check = config['snipe-it'].getboolean('apple_image_check')



# Set the token for the Mosyle Api
mosyle = Mosyle(config['mosyle']['token'], config['mosyle']['url'], config['mosyle']['user'], config['mosyle']['password'])

# Set the call type for Mosyle
calltype = config['mosyle']['calltype']

#setup the snipe-it api
snipe = Snipe(apiKey,snipe_url,apple_manufacturer_id,macos_category_id,ios_category_id,tvos_category_id,snipe_rate_limit, macos_fieldset_id, ios_fieldset_id, tvos_fieldset_id,apple_image_check)

for deviceType in deviceTypes:
    # Get the list of devices from Mosyle based on the deviceType and call type

    if calltype == "timestamp":
        mosyle_response = mosyle.listTimestamp(ts, ts, deviceType).json()
    else:
        mosyle_response = mosyle.list(deviceType).json()
    
    #print(mosyle_response)
    if 'status' in mosyle_response:
        if mosyle_response['status'] != "OK":
            print('There was an issue with the Mosyle API. Stopping.', mosyle_response['message'])
            exit();
    if 'status' in mosyle_response['response'][0]:
        print('There was an issue with the Mosyle API. Stopping script.')
        print(mosyle_response['response'][0]['info'])
        exit()

    



    print('starting snipe')


    print('Looping through Mosyle Hardware List')
    # Return Mosyle hardware and search them in snipe
    for sn in mosyle_response['response'][0]['devices']:
        print('Sarting for Mosyle Device ', sn['device_name'])
        if sn['serial_number'] == None:
            print('There is no serial number here. It must be user enrolled?')
            #print(sn)
            continue
        else:
            print('Device has serial number! ',str(sn['serial_number']))
        
        print('Checking snipe for Mosyle device by serial number: '+str(sn['serial_number']))
        asset = snipe.listHardware(sn['serial_number']).json()
        
        #check to see if Device model already exists on snipe
            
        print("Checking to see if device model already exist on SnipeIt:", sn['device_model'])
        model = snipe.searchModel(sn['device_model']).json()
        print("Model:", model)
        # Create the asset model if is not exist
        if model['total'] == 0:
            print('Model does not exist in Snipe. Need to make it.')
            if sn['os'] == "mac":
                print('Making a new Mac model', sn['device_model'])
                model = snipe.createModel(sn['device_model']).json()
                model = model['payload']['id']
            if sn['os'] == "ios":
                print('Making a new ios model', sn['device_model'])
                model = snipe.createMobileModel(sn['device_model']).json()
                model = model['payload']['id']
            if sn['os'] == "tvos":
                print('Making New Apple TV Model', sn['device_model'])
                model = snipe.createAppleTvModel(sn['device_model']).json()
                model = model['payload']['id']

        else:
            print('Model already exists in SnipeIt!')
            model = model['rows'][0]['id']

        
        if sn['CurrentConsoleManagedUser'] != None and "userid" in sn:
            mosyle_user = sn['userid']

        else:
            print('this device is not currently assigned. Dont try to assign it later');
            mosyle_user = None
            

        #Create payload translating Mosyle to SnipeIt
        devicePayload = snipe.buildPayloadFromMosyle(sn);
        
        # If asset doesnt exist create and assign it
        if ('messages' in asset and asset['messages'] == 'Asset does not exist.') or ('rows' in asset and len(asset['rows']) == 0):
            asset = snipe.createAsset(model, devicePayload).json()
            if mosyle_user != None:
                print('Assigning asset to SnipeIT user based on Mosyle Assignment')
                snipe.assignAsset(mosyle_user, asset['payload']['id'])
                continue

        # Update existing Devices              
        if 'total' in asset and asset['total'] == 1:
            #f"{x:.2f}"
            print('Asset ', sn['serial_number'],' already exists in SnipeIt. Update it.')
            print(asset['rows'][0]['name'])
            snipe.updateAsset(asset['rows'][0]['id'], devicePayload)

        # Check the asset assignement state
        if mosyle_user != None:
            if asset['rows'][0]['assigned_to'] == None and sn['userid'] != None:
                    snipe.assignAsset(sn['userid'], asset['rows'][0]['id'])
                    #continue

            elif sn['userid'] == None:
                snipe.unasigneAsset(asset['rows'][0]['id'])
                #continue

            elif asset['rows'][0]['assigned_to']['username'] == sn['userid']:
                print('nothing to see here')
            elif asset['rows'][0]['assigned_to']['username'] != sn['userid']:
                snipe.unasigneAsset(asset['rows'][0]['id'])
                snipe.assignAsset(sn['userid'], asset['rows'][0]['id'])
            else:
                print('no assignement actions')
        
        print("Checking to see if Mosyle needs an updated asset tag")
        #if there is no asset tag on mosyle, add the snipeit asset tag
        if(sn['asset_tag'] == None or sn['asset_tag'] == "" or sn['asset_tag'] != asset['rows'][0]['asset_tag']):
            if 'payload' in asset:
                asset_tag = asset['payload']['asset_tag']
            else:
                asset_tag = asset['rows'][0]['asset_tag']
            print('update the mosyle asset tag of device ', sn['serial_number'], 'to ', asset_tag)
            mosyle.setAssetTag(sn['serial_number'], asset_tag)
        else:
            print('Mosyle already has an assest tag of: ', sn['asset_tag'])
    
    print('Finished with OS: ', deviceType)
    print('')
