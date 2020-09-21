import json
import getpass
import requests
import datetime


def login(url):
    while True:
        username = input("Enter your webconsole username: ")
        password = getpass.getpass("Password: ")
        login_res = requests.post(url + '/api/v1/login',
                                  data={'username': username,
                                        'password': password})
        del password
        res_json = json.loads(login_res.content)
        if 'error' not in res_json.keys():
            return login_res.cookies
        else:
            print('Error: ' + res_json['error'])


def request_and_response(url, json_data, cookies):
    headers = {'Content-type': 'application/json'}
    response = requests.post(url=url,
                             data=json_data,
                             cookies=cookies,
                             headers=headers)
    response = json.loads(response.text)
    _id = -1
    name = ''
    if 'error' not in response.keys():
        _id = response['data']['id']
        name = response['data']['name']
    else:
        raise Exception('Build ' + url.split('/')[-1] + ' error: ' + response['error'] + '\n' +
                        'Please contact Bytedance for details.')
    return _id, name


def build_federation_json(suffix):
    with open("template_json/template_client_federation.json") as f:
        fed_json = json.load(f)
        fed_json['name'] = 'it-client-federation-' + suffix
        fed_json['x-federation'] = 'it-server-federation-' + suffix
        fed_json['trademark'] = fed_json['name'] + '-trademark'
        fed_json['k8s_settings']['grpc_spec']['extraHeaders']['x-federation'] = fed_json['x-federation']
        fed_json = json.dumps(fed_json, separators=(',', ':'))
    return fed_json


def build_raw_data(suffix, fed_id, sdk):
    with open("template_json/template_raw_data.json") as f:
        raw_json = json.load(f)
        raw_json['name'] = 'it-client-raw-data-' + suffix
        raw_json['federation_id'] = fed_id
        raw_json['image'] += sdk
        fl_rep_spec = raw_json['context']['yaml_spec']['spec']['flReplicaSpecs']
        fl_rep_spec['Master']['template']['spec']['containers'][0]['image'] += sdk
        fl_rep_spec['Worker']['template']['spec']['containers'][0]['image'] += sdk
        raw_json = json.dumps(raw_json, separators=(',', ':'))
    return raw_json


def build_data_join_ticket(suffix, fed_id, sdk, raw_name):
    with open("template_json/template_join_ticket.json") as f:
        join_json = json.load(f)
        join_json['name'] = 'it-client-join-ticket-' + suffix
        join_json['federation_id'] = fed_id
        join_json['role'] = 'Leader'
        join_json['sdk_version'] = sdk
        join_json['expire_time'] = str(datetime.datetime.now().year) + '-12-31'
        fl_rep_spec = join_json['public_params']['spec']['flReplicaSpecs']
        master_containers = fl_rep_spec['Master']['template']['spec']['containers'][0]
        for d in master_containers['env']:
            if d['name'] == 'RAW_DATA_SUB_DIR':
                d['value'] += raw_name
                break
        master_containers['image'] += sdk
        fl_rep_spec['Worker']['template']['spec']['containers'][0]['image'] += sdk
        join_json = json.dumps(join_json, separators=(',', ':'))
    return join_json


def build_train_ticket(suffix, fed_id, sdk):
    with open("template_json/template_server_train_ticket.json") as f:
        job_json = json.load(f)
        job_json['name'] = 'it-client-train-ticket-' + suffix
        job_json['federation_id'] = fed_id
        job_json['sdk_version'] = sdk
        job_json['expire_time'] = str(datetime.datetime.now().year) + '-12-31'
        fl_rep_spec = job_json['public_params']['spec']['flReplicaSpecs']
        master_containers = fl_rep_spec['Master']['template']['spec']['containers'][0]
        for d in master_containers['env']:
            if d['name'] == 'DATA_SOURCE':
                d['value'] += suffix
                break
        master_containers['image'] += sdk
        fl_rep_spec['PS']['template']['spec']['containers'][0]['image'] += sdk
        fl_rep_spec['Worker']['template']['spec']['containers'][0]['image'] += sdk
        job_json = json.dumps(job_json, separators=(',', ':'))
    return job_json


# https://fl.bytedance.net/
# http://127.0.0.1:1989/

suffix = input("Enter a unique suffix for this test. Time stamp is recommended.\n"
               "This suffix should be passed to Bytedance for later settings: ")
sdk_version = input("Enter the version of the image to be used (7-digit hash code): ")
url = input("Enter the URL of your webconsole: ").rstrip().rstrip('/')
cookie = login(url)

federation_json = build_federation_json(suffix)
federation_id, federation_name = request_and_response(url=url + '/api/v1/federations',
                                                      json_data=federation_json,
                                                      cookies=cookie)

raw_data_json = build_raw_data(suffix, federation_id, sdk_version)
raw_data_id, raw_data_name = request_and_response(url=url + '/api/v1/raw_data',
                                                  json_data=raw_data_json,
                                                  cookies=cookie)

join_ticket_json = build_data_join_ticket(suffix, federation_id, sdk_version, raw_data_name)
join_ticket_id, join_ticket_name = request_and_response(url=url + '/api/v1/tickets',
                                                        json_data=join_ticket_json,
                                                        cookies=cookie)

train_ticket_json = build_train_ticket(suffix, federation_id, sdk_version)
train_ticket_id, train_ticket_name = request_and_response(url=url + '/api/v1/tickets',
                                                          json_data=train_ticket_json,
                                                          cookies=cookie)

print("Client settings all set. Please wait for Bytedance to pull final jobs.")
