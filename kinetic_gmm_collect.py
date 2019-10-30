import requests
import sys
import json
import time
import os
import uuid
import datetime
from contextlib import suppress

from elasticsearch import Elasticsearch

# http://127.0.0.1:5601/app/kibana#/dashboard/5851a2b0-f991-11e9-ae5c-2536d7a4115e

#############KINETIC-FUNCTIONS####################

# Login Function to retrieve token
def login(kin_url, email, password):
    url = 'https://{0}/sessions'.format(kin_url)
    body = {
        "email": email,
        "password": password
    }

    try:
        r = requests.post(url, json=body, timeout=10)
    except Exception as e:
        print(e)
        print('Error retrieving token, check credentials and try again')
        exit(1)
    else:
        response = r.text
    
    content = json.loads(response)

    print(content)

    # Get Kinetic Token
    # access_token = content['access_token']
    
    access_token = content['x_gwaas_api_key']

    # X-GWaaS-API-Key

    return access_token
    

def findOrgGWs(kin_url, orgid, token):
    url = 'https://{0}/organizations/{1}/gate_ways'.format(kin_url, orgid)

    kin_headers = {"X-GWaaS-API-Key": token}

    try:
        r = requests.get(url, headers=kin_headers)
    except Exception as e:
        print(e)
        print('Error in retrieving gateway information.')
        exit(1)
    else:
        response = r.text
    
    content = json.loads(response)

    # Get Gateway Details for all org gateways
    gws_details = content['gate_ways']
    
    return gws_details


def isGateway(kin_url, orgid, token):
    url = 'https://{0}/organizations/{1}/gate_ways'.format(kin_url, orgid)

    kin_headers = {"X-GWaaS-API-Key": token}

    try:
        r = requests.get(url, headers=kin_headers)
    except:
        print('error in getting gateways')
        exit(1)
    else:
        response = r.text
        print(response)
    #parse the response text
    content = json.loads(response)

    # gateways
    gws = content['gate_ways']
    
    if len(gws) > 0:
        return True
    else:
        return False

#############Elasticsearch-and-Kibana-FUNCTIONS####################
def api_geo_timestamp(gw):
    gw["api_timestamp"] = datetime.datetime.isoformat(datetime.datetime.now())
    gw["location"] = "%s,%s" % (gw["location_lat"], gw["location_lng"])

    return gw
    
def post_elastic_db(gateway, els_session, index_name):
    loc_id = uuid.uuid4()

    rev_gateway = api_geo_timestamp(gateway)

    res = els_session.index(index=index_name, id=loc_id, body=rev_gateway)

    return res['result']

def create_index_pattern(index, time_field, kib_url, index_pattern_id):
    url = '{0}/api/saved_objects/index-pattern/{1}'.format(kib_url, index_pattern_id)

    kib_headers = {"kbn-version": "7.4.1"}

    kib_data = {"attributes":{"title": index,"timeFieldName":time_field}}

    kib_req = requests.post(url, json=kib_data, headers=kib_headers)

    kib_resp = kib_req.text

    return kib_resp

# This function is deprecated for elasticsearch 7.0.0 and above
def update_mapping(index, els_session, conf_folder):
    conf_file = "{0}/elk6_mappings.json".format(conf_folder)

    with open(conf_file) as json_map:
        body_map_json = json.loads(json_map.read())
    
    res = els_session.indices.put_mapping(index=index, body=body_map_json, include_type_name=True)

    print(res)

def load_dashabord(kib_url, conf_folder):
    url = "{0}/api/saved_objects/_bulk_create".format(kib_url)

    conf_file = "{0}/kib_dash.json".format(conf_folder)

    with open(conf_file, 'r') as dash:
        kib_dash = dash.read()
    
    #print(kib_dash)

    kib_json = json.loads(kib_dash)

    kib_headers = {"kbn-version": "7.4.1"}

    # kib_params = {"overwrite": True}

    kib_req = requests.post(url, headers=kib_headers,json=kib_json)

    kib_resp = kib_req.text

    return kib_resp

def is_kibana_ready(kib_url):
    url = '{0}/api/status'.format(kib_url)

    kib_headers = {"kbn-version": "7.4.1"}

    try:
        req = requests.get(url, headers=kib_headers)

        resp = req.text

        if resp == "Kibana server is not ready yet":
            return {"kibana_state": "not_ready"}
        
        resp_json = json.loads(resp)

        kib_status = resp_json["status"]["overall"]["state"]

        if kib_status == "green":
            return {"kibana_state": "ready"}
        elif kib_status == "yellow":
            return {"elastic_state": "ready"}
        else:
            return {"kibana_state": "not_ready"}
    except Exception as e:
        print(e)
        return {"kibana_state": "not_ready"}

def is_elasticsearch_ready(els_session):
    try:
        req = els_session.cluster.health()
        status = req["status"]

        if status == "green":
            return {"elastic_state": "ready"}
        elif status == "yellow":
            return {"elastic_state": "ready"}
        else:
            print("Status not green yet")
            return {"elastic_state": "not_ready"}

    except Exception as e:
        print(e)
        return {"elastic_state": "not_ready"}

def is_index_pattern(index, kib_url):
    url = '{0}/api/saved_objects/_find'.format(kib_url)

    querystring = {"type":"index-pattern","search_fields":"title","search":index}

    kib_headers = {"kbn-version": "7.4.1"}

    req = requests.get(url, headers=kib_headers, params=querystring)

    resp = req.text
    resp_json = json.loads(resp)
    obj_num = len(resp_json["saved_objects"])

    if obj_num > 0:
        return True
    else:
        return False
    

        
if __name__ == "__main__":

    # Environment Variables
    email = os.getenv("KINETIC_USER_EMAIL", "default@email.com")
    passwd = os.getenv("KINETIC_USER_PASS", "somepasswd")
    orgid = os.getenv("KINETIC_ORG_ID", 0000)
    els_host = os.getenv("ELS_HOST","127.0.0.1")
    els_port = os.getenv("ELS_PORT", 9200)
    kib_host = os.getenv("KIB_HOST", "127.0.0.1")
    kib_port = os.getenv("KIB_PORT", 5601)
    index_name = os.getenv("KIB_INDEX_NAME", "kinetic_gateway_stats")
    kib_index_pattern_id = os.getenv("KIB_INDEX_PATTERN_ID", "2a3d56f0-f778-11e9-ae5c-2536d7a4115e")
    els_db = "http://{0}:{1}".format(els_host, els_port)
    kibana_svc = "http://{0}:{1}".format(kib_host, kib_port)
    timefield = os.getenv("TIMEFIELD", "updated_at")
    config_folder = os.getenv("CONFIG_FOLDER", "./config")
    dashboard_on = os.getenv("DASHBOARD_ON", "yes")
    root_url = os.getenv("KINETIC_URL", "us.ciscokinetic.io")
    root_url_v1 = '{0}/api/v1'.format(root_url)
    root_url_v2 = '{0}/api/v2'.format(root_url)

    # Elasticsearch settings
    settings = {
            "index": {
                "blocks": {
                    "read_only_allow_delete": "false"
                }
            }
        }

    print("starting")

    # Session for Elasticsearc DB
    es = Elasticsearch([els_db], scheme="http")

    # Wait for elasticsearch to become available
    print("checking DB status")
    es_not_available = True

    while es_not_available:
        es = Elasticsearch([els_db], scheme="http")
        if is_elasticsearch_ready(es)["elastic_state"] == "not_ready":
            print("Waiting for Elasticsearch to become ready")
            print(is_elasticsearch_ready(es)["elastic_state"])
            time.sleep(1)
        else:
            print(is_elasticsearch_ready(es)["elastic_state"])
            es_not_available = False

    # Wait for Kibana to become available
    while is_kibana_ready(kibana_svc)["kibana_state"] == "not_ready":
        print("Waiting for Kibana to become ready")
        time.sleep(1)

    # PreConfigure Kibana and Elasticsearch if unavailable not previously done so
    if is_index_pattern(index_name, kibana_svc) == False:
        create_index_pattern(index_name, timefield, kibana_svc, kib_index_pattern_id)
        print("Index Creation")

        # Create Elasticsearch Gateway and ElasticSearch Mappings

        # Adjusting settings to not block requests for index
        # If you do not define storage space out right for your index
        # Your elasticsearch requests will block
        # this elasticsearch setting prevents blocking

        es.indices.put_settings(settings)

        config_file = "{0}/elk7_mappings.json".format(config_folder)

        with open(config_file) as json_map:
            body_map_json = json.loads(json_map.read())

        print(es.indices.create(index=index_name, body=body_map_json))

        # Function used for Elasticsearch 6.X.X - Tested on elasticsearch 6.8.4
        #update_mapping(index_name, es)

    # Initial Token and Gateways Find

    kin_token = login(root_url_v1, email, passwd)

    # Find Available Kinetic Gateways in Org
    
    gws = findOrgGWs(root_url_v2, orgid, kin_token)

    for i in gws:
        post_elastic_db(i, es, index_name)
    
    print("First set of Gateways added to Elasticsearch")

    # Add Prebuilt Dashboards if DASHBOARD_ON set to true (Default is true)

    if dashboard_on == "yes":
        load_dashabord(kibana_svc, config_folder)
        print("Dashboard Visualizations added")
    else:
        print("Prebuilt Dashboards were not deployed, per user")

    # Break before starting Continuous App

    time.sleep(30)
    new_kin_token = login(root_url_v1, email, passwd)

    # Continuously running operation for updating Kinetic Gateway info
    start = time.time()

    while True:
        current = time.time() - start
        new_gws = findOrgGWs(root_url_v2, orgid, new_kin_token)
        es.indices.put_settings(settings, index=index_name)

        for i in gws:
            post_elastic_db(i, es, index_name)
        
        print("Kinetic Gateways info added to Elasticsearch")
        
        if current > 3600:
            new_kin_token = login(root_url_v1, email, passwd)
            start = time.time()
            print("Generated new token")
            time.sleep(30)
        else:
            time.sleep(30)
