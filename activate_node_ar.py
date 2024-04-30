#!/usr/bin/python3
import os
import datetime
import sys
import socket
import subprocess
from novaclient import client as nova_client
from keystoneauth1.identity import v3
from keystoneauth1 import session as ks_session




def make_node_active(session):
	nova = nova_client.Client('2.1', session=session)
	vm_id = "961bf47c-5e3a-4f40-be0d-0b1ee157ecfe"
	vm = nova.servers.get(vm_id)
	vm.start()
	print("node is active")


def main():
    # Create a Keystone session
    auth = v3.Password(auth_url="https://openstack.garycloud.alces.network:5000",
                       username="shubham.dang",
                       password="3YBZGord",
                       project_name='engineering',
                       user_domain_name='Default',
                       project_domain_name='Default')

    sess = ks_session.Session(auth=auth, verify=False)

    # Get the maximum flavor size
    max_flavor = make_node_active(session=sess)


if __name__ == "__main__":
    main()





