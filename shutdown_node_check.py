import os
import datetime
import sys
import socket
import subprocess
import configparser
import logging
import logging.handlers
import socket
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


def fetch_node_project_id(session):
    hostname = socket.gethostname()
    nova = nova_client.Client('2.1', session=session)
    aggregates = nova.aggregates.list()
    for aggregate in aggregates:
        if hostname in aggregate.hosts:
            return aggregate.metadata['filter_tenant_id']
    
 

def disable_node(session):
    hostname = socket.gethostname()
    nova = nova_client.Client('2.1', session=session)
    nova.services.disable_log_reason(hostname, reason="Power Saving", binary="nova-compute")
    os.system("shutdown -h now")


def central_logging(project_id):
    # Define the logger
    logger = logging.getLogger('PowerOptimisationLogger')
    logger.setLevel(logging.INFO)

    # Define the remote syslog server address and port
    remote_syslog_server = 'director'  
    remote_syslog_port = 514                

    # Define the syslog handler for TCP
    syslog_handler = logging.handlers.SysLogHandler(address=(remote_syslog_server, remote_syslog_port), socktype=socket.SOCK_STREAM, facility=logging.handlers.SysLogHandler.LOG_LOCAL0)

    # Define the log format
    hostname = socket.gethostname()
    formatter = logging.Formatter('%(asctime)s ' + hostname + ' %(name)s: %(message)s', datefmt='%b %d %H:%M:%S')

    # Add the formatter to the handler
    syslog_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(syslog_handler)

    # Send a test message
    message = f"Turning off node ({hostname}) Since no virtual machine on the node, other compute node in project {project_id} is capable of creating the buffer VM count of {REQUIRED_VM_BUFFEER}."
    logger.info(message)


def print_log(project_id):
    hostname = socket.gethostname()
    timestamp = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    print(f"{timestamp} {hostname} compute_status_check: ossec: output: 'make_node_down': True {project_id} {hostname}")

def is_virsh_node_empty():
    
    try:
        cmd = 'docker exec nova_libvirt bash -c "virsh list --all --name | xargs -I{} virsh dominfo {} | grep \'State:\'"'
        process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        count = len(process.stdout.splitlines())
        if count > 0:
            return False
        return True
    except Exception as e:
        print(f"Error: Failed to stop. Error message: {str(e)}")
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
    is_host_empty = False
    for hypervisor_name in hypervisors:
        hypervisor_metadata = nova.hypervisors.search(hypervisor_name)
        hypervisor_details = nova.hypervisors.get(hypervisor_metadata[0].id)
        if hypervisor_details.state == 'up' and hypervisor_details.status == 'enabled' and hostname != hypervisor_details.hypervisor_hostname:
            vcpu_vm_count = ((hypervisor_details.vcpus * int(CPU_ALLOCATION_RATIO)) -  hypervisor_details.vcpus_used) // max_flavor.vcpus
            ram_vm_count = ((hypervisor_details.memory_mb * int(RAM_ALLOCATION_RATIO) ) - hypervisor_details.memory_mb_used) // max_flavor.ram
            vm_count += min(vcpu_vm_count, ram_vm_count)
        if hostname == hypervisor_details.hypervisor_hostname  and hypervisor_details.vcpus_used <= 2:
            is_host_empty = True

    if vm_count >= int(REQUIRED_VM_BUFFEER) and is_host_empty:
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
    project_id = fetch_node_project_id(session=sess)
    if project_id:
        # Get the maximum flavor size
        max_flavor = get_max_flavor(session=sess)


        # Get the available nodes
        shutdown_node = check_node_available_for_project_down(max_flavor, session=sess, project_id=project_id)
        if shutdown_node:
            central_logging(project_id)
            print_log(project_id) # if it comes true then shutdown the node
            disable_node(session=sess)
        

if __name__ == "__main__":
    main()