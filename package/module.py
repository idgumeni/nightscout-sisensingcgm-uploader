from setup import *
import urllib3
import json
import datetime

def return_ss_url(ss_region):
    match ss_region:
        case "CN":
            return region_cn
        # EU to be tested
        case "EU":
            return region_eu

def convert_mmoll_to_mgdl(x):
    return round(x*ns_unit_convert)

def convert_mgdl_to_mmoll(x):
    return round(x/ns_unit_convert, 1)

# Sisensing API
# process Sisensing data
def get_ss_entries(header):
    url = return_ss_url(ss_region.upper())
    r = urllib3.request("GET", url=url,headers=header, retries=retries, timeout=timeout)
    try:
        data = json.loads(r.data)
        print("Sisensing Response Status:" , r.status, r.reason)
    except json.JSONDecodeError:
        content_type = r.headers.get('Content-Type')
        print("Failed. Content Type" , content_type)
    return data

# Nightscout API v1
# Nightscout entries
# return last entry date. (Slice allows searching for modal times of day across days and months.)
def get_last_entry_date(header):
    url = ns_url+"api/v1/slice/entries/dateString/sgv/.*/.*?count=1"
    r = urllib3.request("GET", url=url,headers=header, retries=retries, timeout=timeout)
    # print(r.status,r.reason,json.loads(r.data))
    try:
        data = json.loads(r.data)
        print("Nightscout get last entry date:", r.status , r.reason)
        if data == []:
            print("Last entry date: no data")
            return 0
        else:
            print("Last entry date:", data[0]["date"] ,"( GMT",datetime.datetime.utcfromtimestamp(data[0]["date"]/1000),")")
            return data[0]["date"]
    except json.JSONDecodeError:
        content_type = r.headers.get('Content-Type')
        print("Failed. Content Type" + content_type)

def process_json_data_direction(i):
    try:
        match i:
            case -2:
                return 'SingleDown'
            case -1:
                return 'FortyFiveDown'
            case 0:
                return 'Flat'
            case 1:
                return 'FortyFiveUp'
            case 2:
                return 'SingleUp'
    except Exception as error:
        print("Error reading direction:", error)

# example of json to Nightscout
# {
#  "type": "sgv",
#  "sgv": 146,
#  "direction": "Flat",
#  "device": "Test-Uploader",
#  "date": 1725247634000,
#  "dateString": "2024-09-02T03:27:14.000Z"
# }


def process_json_data_prepare_entries(item,last_date,count,list_dict): # item type = dict
    try:
        for j in item["glucoseInfos"]:
            #
            if uploader_max_entries !=0 and count >= uploader_max_entries:
                break
            if j["t"]>last_date or uploader_all_data==True:
                entry_dict = {
                    "type" : "sgv",
                    "sgv" : convert_mmoll_to_mgdl(j["v"]),
                    "direction" : process_json_data_direction(j["s"]),
                    "device": ns_uploder,
                    "date" : j["t"],
                    "dateString": str(datetime.datetime.utcfromtimestamp(j["t"]/1000).isoformat(timespec='milliseconds')+"Z")
                }
                list_dict.append(entry_dict)
                count +=1
        return count,list_dict
    except Exception as error:
        print("Error reading glucoseInfos:", error)


def process_json_data(data,last_date):
    count = 0
    list_dict = []
    print("Processing data...")
    try:
        if type(data["data"]["glucoseDataList"]) == list:
            for i in data["data"]["glucoseDataList"]:
                count,list_dict = process_json_data_prepare_entries(i,last_date,count,list_dict)
        elif type(data["data"]["glucoseDataList"]) == dict:
            count,list_dict = process_json_data_prepare_entries(i,last_date,count,list_dict)
        else:
            print(type(data["data"]["glucoseDataList"]), " recieved. Check API content.")
    except Exception as error:
        print("Error reading glucose data:", error)
    # finally:
    #     print(str(count) + " entries read")

    if len(list_dict) > 0:
        upload_json = json.loads(json.dumps(list_dict))
        upload_entry(upload_json,ns_header,len(list_dict))
    else:
        print("No new entry found.")
    

def upload_entry(entries_json,header,n): #entries tpye = a list of dicts
    url = ns_url+"api/v1/entries"
    r = urllib3.request("POST", url=url,headers=header, json = entries_json, retries=retries, timeout=timeout)
    if r.status == 200:
        print("Nightscout post entries:", r.status, r.reason)
        print(n, "entries uploaded.")
    else:
        print("POST Failed.", r.status, r.reason)

# Nightscout treatment
# get last sensor start date
def get_last_treatment_sensorstart_date(header):
    url = ns_url+"api/v1/treatments.json?count=1&find[eventType]=Sensor Start&find[enteredBy]="+ns_uploder+"&find[created_at][$gte]=1970"
    r = urllib3.request("GET", url=url,headers=header, retries=retries, timeout=timeout)
    # print(r.status,r.reason,json.loads(r.data))
    try:
        data = json.loads(r.data)
        print("Nightscout get last sensor start date:", r.status , r.reason)
        if data == []:
            print("Last sensor date: no data")
            return "0"
        else:
            print("Last sensor date:", data[0]["created_at"])
            return data[0]["created_at"]
    except json.JSONDecodeError:
        content_type = r.headers.get('Content-Type')
        print("Failed. Content Type" + content_type)

def process_json_data_prepare_treatment_sensorstart(item,last_date,count,list_dict): # item type = dict
    try:
        if uploader_max_entries !=0 and count >= uploader_max_entries:
            return
        if item["GlucoseEntryDateTime"]>last_date or uploader_all_data==True:
            entry_dict = {
                "eventType": "BG Check",
                "created_at": datetime.datetime.fromisoformat(item["GlucoseEntryDateTime"]).isoformat(timespec="milliseconds")+"Z",
                "glucose": item["GlucoseLevel"],
                "glucoseType": "Finger",
                "units": "mmol",
                "enteredBy": ns_uploder,
            }
            list_dict.append(entry_dict)
            count +=1
        return count,list_dict
    except Exception as error:
        print("Error processing BloodGlucose:", error)