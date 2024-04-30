#!/usr/bin/env python -m venv /home/ubuntu/myenv --activate
import os
import datetime
import sys
import socket
import subprocess
import configparser
from novaclient import client as nova_client
from keystoneauth1.identity import v3
from keystoneauth1 import session as ks_session

config = configparser.ConfigParser()
config.read('config.ini')


REQUIRED_VM_BUFFEER = config['DEFAULT']['REQUIRED_VM_BUFFEER']
CPU_ALLOCATION_RATIO = config['DEFAULT']['CPU_ALLOCATION_RATIO']
RAM_ALLOCATION_RATIO = config['DEFAULT']['RAM_ALLOCATION_RATIO']
STORAGE_ALLOCATION_RATIO = config['DEFAULT']['STORAGE_ALLOCATION_RATIO']
AUTH_URL = config['DEFAULT']['AUTH_URL']
USERNAME = config['DEFAULT']['USERNAME']
PASSWORD = config['DEFAULT']['PASSWORD']
ADMIN_PROJECT_NAME = config['DEFAULT']['ADMIN_PROJECT_NAME']

PROJECT_ID = "14f365cf4d2749dbb95a43fe2d3b4281"


def shutdown_machine():
    os.system("shutdown -h now")


def print_log(message):
    hostname = socket.gethostname()
    timestamp = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    print(f"{timestamp} {hostname} compute_status_check: ossec: output: 'make_node_down': {message}")

def is_virsh_node_empty():
    
    try:
        cmd = "virsh list --all --name | xargs -I{} virsh dominfo {} | grep '^State:'"
        process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        count = len(process.stdout.splitlines())
        return True
    except Exception as e:
        print(f"Error: Failed to stop {service_name}. Error message: {str(e)}")
        return False



def get_max_flavor(session):
    """
    Get the maximum flavor size based on CPU size in the environment    
    """
    nova = nova_client.Client('2.1', session=session)
    flavors = nova.flavors.list(detailed=True)
    max_flavor = max(flavors, key=lambda x: x.vcpus)
    return max_flavor


def check_node_available_for_project_down(max_flavor, session, project_id):
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


    hostname = socket.gethostname()
    for hypervisor_name in hypervisors:
        hypervisor_metadata = nova.hypervisors.search(hypervisor_name)
        hypervisor_details = nova.hypervisors.get(hypervisor_metadata[0].id)
        if hypervisor_details.state == 'up' and hypervisor_details.status == 'enabled' and hostname != hypervisor_details.hypervisor_hostname:
            vcpu_vm_count = ((hypervisor_details.vcpus * CPU_ALLOCATION_RATIO) -  hypervisor_details.vcpus_used) // max_flavor.vcpus
            ram_vm_count = ((hypervisor_details.memory_mb * RAM_ALLOCATION_RATIO ) - hypervisor_details.memory_mb_used) // max_flavor.ram
            vm_count += min(vcpu_vm_count, ram_vm_count)

    if vm_count >= REQUIRED_VM_BUFFEER:
        return True
    return False



def main():
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
    shutdown_node = check_node_available_for_project_down(max_flavor, session=sess, project_id=PROJECT_ID) and is_virsh_node_empty()
    if shutdown_node:
        print_log(shutdown_node) # if it comes true then shutdown the node
        shutdown_machine()
    

if __name__ == "__main__":
    main()