import os
import sys
import socket
import subprocess
import datetime
import configparser
import time
from novaclient import client as nova_client
from keystoneauth1.identity import v3
from keystoneauth1 import session as ks_session

config = configparser.ConfigParser()
config.read('/opt/power_optimisation/config.ini')

REQUIRED_VM_BUFFEER = config['DEFAULT']['REQUIRED_VM_BUFFEER']
CPU_ALLOCATION_RATIO = config['DEFAULT']['CPU_ALLOCATION_RATIO']
RAM_ALLOCATION_RATIO = config['DEFAULT']['RAM_ALLOCATION_RATIO']
STORAGE_ALLOCATION_RATIO = config['DEFAULT']['STORAGE_ALLOCATION_RATIO']
AUTH_URL = config['DEFAULT']['AUTH_URL']
USERNAME = config['DEFAULT']['USERNAME']
PASSWORD = config['DEFAULT']['PASSWORD']
ADMIN_PROJECT_NAME = config['DEFAULT']['ADMIN_PROJECT_NAME']


def enable_node(session, hostname):
    nova = nova_client.Client('2.1', session=session)
    nova.services.enable(hostname, binary="nova-compute")

def check_and_activate_baremetal(ip):
    attempts = 0

    while attempts < 3:
        try:
            power_command = ['ipmitool', '-I', 'lanplus', '-U', USERNAME, '-P', PASSWORD, '-H', str(ip), 'power', 'status']
            power_out = subprocess.run(power_command, capture_output=True, text=True)
            power_state = power_out.stdout.split('\n')[-2].strip().split(' ')[-1]

            if power_state == 'on':
                return True

            power_on_command = ['ipmitool', '-I', 'lanplus', '-U', USERNAME, '-P', PASSWORD, '-H', str(ip), 'power', 'on']
            subprocess.call(power_on_command)
            time.sleep(180)

            attempts += 1

        except Exception as e:
            time.sleep(180)
    return False

def print_log(message, up_hostname):
    hostname = socket.gethostname()
    timestamp = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    print(f"{timestamp} {hostname} compute_status_check: ossec: output: 'make_node_up({up_hostname})': {message}")


def get_max_flavor(session):
    """
    Get the maximum flavor size based on CPU size in the environment    
    """
    nova = nova_client.Client('2.1', session=session)
    flavors = nova.flavors.list(detailed=True)
    max_flavor = max(flavors, key=lambda x: x.vcpus)
    return max_flavor

def check_node_available_for_project_up(max_flavor, session, project_id):
    """
    In this we are checking for compute host that is mapped to projects have enough space to launch the Buffer VMs
    """
    nova = nova_client.Client('2.1', session=session)
    vm_count = 0
    hypervisors = []
    aggregates = nova.aggregates.list()
    for aggregate in aggregates:
        aggregate_details = nova.aggregates.get(aggregate.id)
        if 'filter_tenant_id' in aggregate_details.metadata and aggregate_details.metadata['filter_tenant_id'] == project_id:
            hypervisors.extend(aggregate.hosts)


    disabled_nodes = []
    for hypervisor_name in hypervisors:
        hypervisor_metadata = nova.hypervisors.search(hypervisor_name)
        hypervisor_details = nova.hypervisors.get(hypervisor_metadata[0].id)
        if hypervisor_details.state == 'up' and hypervisor_details.status == 'enabled':
            vcpu_vm_count = ((hypervisor_details.vcpus * int(CPU_ALLOCATION_RATIO)) -  hypervisor_details.vcpus_used) // max_flavor.vcpus
            ram_vm_count = ((hypervisor_details.memory_mb * int(RAM_ALLOCATION_RATIO) ) - hypervisor_details.memory_mb_used) // max_flavor.ram
            vm_count += min(vcpu_vm_count, ram_vm_count)
        elif hypervisor_details.state == 'down' and hypervisor_details.status == 'disabled' \
        and hypervisor_details.service['disabled_reason'] == 'Power Saving':
            disabled_nodes.append(hypervisor_details.to_dict())
            #TODO sort list of dictionary on the basis of names
    disabled_nodes = sorted(disabled_nodes, key=lambda x: x['id'])
    
    if vm_count >= int(REQUIRED_VM_BUFFEER):
        return False, []
    return True, disabled_nodes


def main():
    try:
        project_id = sys.argv[1]
    # possible values of severity low, medium, high, critical 
    except IndexError:
        print("Usage: /opt/power_optimisation/venv/bin/python activate_node_check.py <project_id>")
        quit()

    # Create a Keystone session
    auth = v3.Password(auth_url=AUTH_URL,
                       username=USERNAME,
                       password=PASSWORD,
                       project_name=ADMIN_PROJECT_NAME,
                       user_domain_name='Default',
                       project_domain_name='Default')
    sess = ks_session.Session(auth=auth)

    # Get the maximum flavor size
    max_flavor = get_max_flavor(session=sess)

    # Get the available nodes
   
    new_node_needed, disabled_nodes = check_node_available_for_project_up(max_flavor, 
                                                                        session=sess, 
                                                                        project_id=project_id)
    

    if new_node_needed and disabled_nodes:
        disabled_node = disabled_nodes[0]
        host_mgmt_ip = f"10.11.11.{disabled_node['host_ip'].split('.')[-1]}"
        hostname = disabled_node['hypervisor_hostname']
        print_log(new_node_needed, hostname)
        if check_and_activate_baremetal(host_mgmt_ip):
            enable_node(session=sess, hostname=hostname)
    

if __name__ == "__main__":
    main()