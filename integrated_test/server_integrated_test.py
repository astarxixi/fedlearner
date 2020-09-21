#!/usr/bin/env python3
import time
import json
import getpass
import requests
import datetime


def login(url):
    while True:
        username = input("Enter your webconsole username: ")
        password = getpass.getpass('Password: ')
        login_res = requests.post(url + '/login',
                                  data={'username': username,
                                        'password': password})
        del password
        res_json = json.loads(login_res.content)
        if 'error' not in res_json.keys():
            print("Logged into webconsole.")
            return login_res.cookies
        else:
            print("Error: " + res_json["error"])


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
                        'Please check if API version concurs and json format is correct.')
    return _id, name


def build_federation_json(suffix, fed_args):
    with open('template_json/template_server_federation.json') as f:
        fed_json = json.load(f)
        fed_json['name'] = 'it-server-federation-' + suffix
        fed_json['x-federation'] = 'it-client-federation-' + suffix
        fed_json['trademark'] = fed_json['name'] + '-trademark'
        fed_json['k8s_settings']['grpc_spec']['extraHeaders']['x-federation'] = fed_json['x-federation']
        for d in fed_json['k8s_settings']['global_replica_spec']['template']['spec']['containers'][0]['env']:
            if d['name'] == 'EGRESS_HOST':
                d['value'] = fed_args['ehost']
            if d['name'] == 'EGRESS_DOMAIN':
                d['value'] = fed_args['edomain']
        fed_json['k8s_settings']['grpc_spec']['authority'] = fed_args['grpc_auth']
        fed_json['k8s_settings']['leader_peer_spec']['Follower']['authority'] = fed_args['leader_auth']
        fed_json['k8s_settings']['follower_peer_spec']['Leader']['authority'] = fed_args['follower_auth']
        fed_json = json.dumps(fed_json, separators=(',', ':'))
    return fed_json


def build_raw_data(suffix, fed_id, sdk):
    with open('template_json/template_raw_data.json') as f:
        raw_json = json.load(f)
        raw_json['name'] = 'it-server-raw-data-' + suffix
        raw_json['federation_id'] = fed_id
        raw_json['image'] += sdk
        fl_rep_spec = raw_json['context']['yaml_spec']['spec']['flReplicaSpecs']
        fl_rep_spec['Master']['template']['spec']['containers'][0]['image'] += sdk
        fl_rep_spec['Worker']['template']['spec']['containers'][0]['image'] += sdk
        raw_json = json.dumps(raw_json, separators=(',', ':'))
    return raw_json


def build_data_join_ticket(suffix, fed_id, sdk, raw_name):
    with open('template_json/template_join_ticket.json') as f:
        join_json = json.load(f)
        join_json['name'] = 'it-server-join-ticket-' + suffix
        join_json['federation_id'] = fed_id
        join_json['role'] = 'Follower'
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


def build_data_join_job(suffix, fed_id):
    with open('template_json/template_join_job.json') as f:
        job_json = json.load(f)
        job_json['name'] = 'it-data-join-job-' + suffix
        job_json['federation_id'] = fed_id
        job_json['client_ticket_name'] = 'it-server-join-ticket-' + suffix
        job_json['server_ticket_name'] = 'it-client-join-ticket-' + suffix
        job_json = json.dumps(job_json, separators=(',', ':'))
    return job_json


def build_train_ticket(suffix, fed_id, sdk):
    with open('template_json/template_client_train_ticket.json') as f:
        job_json = json.load(f)
        job_json['name'] = 'it-server-train-ticket-' + suffix
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


def wait_and_check(url, cookies, wait_time=15):
    while True:
        response = requests.get(url=url,
                                cookies=cookies)
        response = json.loads(response.text)
        state = response['data']['status']['appState']
        if state == 'FLStateComplete':
            return
        elif state == 'FLStateFailed':
            raise Exception('Join job failed, please head to webconsole and inspect pod log to debug.')
        else:
            time.sleep(wait_time)


def build_train_job(suffix, fed_id):
    with open('template_json/template_train_job.json') as f:
        job_json = json.load(f)
        job_json['name'] += suffix
        job_json['federation_id'] = fed_id
        job_json['client_ticket_name'] += suffix
        job_json['server_ticket_name'] += suffix
        job_json = json.dumps(job_json, separators=(',', ':'))
    return job_json


# https://fl.bytedance.net/
# http://127.0.0.1:1989/

if __name__ == '__main__':
    suffix = input("Enter the suffix provided by client: ")
    sdk_version = input("Enter the version of the image to be used (7-digit hash code), "
                        "should be the same as client's: ")
    url = input("Enter the URL of your webconsole: ").rstrip().rstrip('/') + "/api/v1"
    cookie = login(url)

    print("Default values below are for test on Ali clusters.")
    ehost = input("Enter EGRESS_HOST field of the federation "
                  "[fl-aliyun-test-client-auth.com]: ") or "fl-aliyun-test-client-auth.com"
    edomain = input("Enter EGRESS_DOMAIN filed of the federation: "
                    "[fl-aliyun-test.com]: ") or "fl-aliyun-test.com"
    grpc_auth = input("Enter authority field of grpc_spec of the federation "
                      "[fl-aliyun-test.com]: ") or "fl-aliyun-test.com"
    leader_auth = input("Enter authority field of leader_peer_spec of the federation "
                        "[fl-aliyun-test.com]: ") or "fl-aliyun-test.com"
    follower_auth = input("Enter authority field of follower_peer_spec of the federation "
                          "[fl-aliyun-test.com]: ") or "fl-aliyun-test.com"
    federation_args = {'ehost': ehost,
                       'edomain': edomain,
                       'grpc_auth': grpc_auth,
                       'leader_auth': leader_auth,
                       'follower_auth': follower_auth}

    federation_json = build_federation_json(suffix, federation_args)
    federation_id, federation_name = request_and_response(url=url + '/federations',
                                                          json_data=federation_json,
                                                          cookies=cookie)

    raw_data_json = build_raw_data(suffix, federation_id, sdk_version)
    raw_data_id, raw_data_name = request_and_response(url=url + '/raw_data',
                                                      json_data=raw_data_json,
                                                      cookies=cookie)
    requests.post(url=url + '/raw_data/' + str(raw_data_id) + '/submit',
                  cookies=cookie)

    join_ticket_json = build_data_join_ticket(suffix, federation_id, sdk_version, raw_data_name)
    join_ticket_id, join_ticket_name = request_and_response(url=url + '/tickets',
                                                            json_data=join_ticket_json,
                                                            cookies=cookie)

    join_job_json = build_data_join_job(suffix, federation_id)
    join_job_id, join_job_name = request_and_response(url=url + '/job',
                                                      json_data=join_job_json,
                                                      cookies=cookie)

    train_ticket_json = build_train_ticket(suffix, federation_id, sdk_version)
    train_ticket_id, train_ticket_name = request_and_response(url=url + '/tickets',
                                                              json_data=train_ticket_json,
                                                              cookies=cookie)

    train_job_json = build_train_job(suffix, federation_id)
    print("Waiting for join job to finish...")
    wait_and_check(url=url + '/job/' + str(join_job_id), cookies=cookie)
    train_job_id, train_job_name = request_and_response(url=url + '/job',
                                                        json_data=train_job_json,
                                                        cookies=cookie)
    print("All set. Please check the results on webconsole.")
