In our OpenStack environment, each customer is assigned a project, and within each project, there are associated compute nodes.

The `activate_node_check.py` script is executed on the Controller node to assess whether it's necessary to start a compute node. This script evaluates the availability of space on active nodes to accommodate buffer VMs. If sufficient space is not available, the compute node associated with the respective customer's project is activated using Wazuh's active-response feature.

Similarly, on all compute nodes, the `shutdown_node_check.py` script is deployed. This script checks whether the node hosts any active virtual machines or if other compute nodes within the same project have adequate space to spawn buffer VMs. If ample space is available, the node is gracefully shut down.


Install wazuh Manager.
Install Wazuh Agent on Controller and Compute nodes.


!!! note
    We are assuming agent is installed on the compute and controller node



## Allow Stacking of the node in the given host aggregate that belong to the a project/tenant

Below step will force the nova sceduler to fill the compute nodes that is already filled.

- Create Host Aggregates
- Add Hosts in the Host Aggregates 
- Add Project Filter metadata
- Add Weights as metadata to allow stacking 
    ```
    cpu_weight_multiplier = -100
    disk_weight_multiplier = -100
    ram_weight_multiplier = -100
    ```


## Node Shutdown Flow
In this step, we'll exclusively focus on the compute nodes that have been incorporated into a host aggregate associated with a specific project. Perform below operation on all the computes nodes.


- Install python openstack-client 6.4.0 in the virualenv
    ```
    mkdir -p /opt/power_optimisation
    cd /opt/power_optimisation/
    python3 -m venv venv 
    source venv/bin/activate
    pip install python-openstackclient==6.4.0
    deactivate
    ```

- Place the script `shutdown_node_check.py` at /opt/power_optimisation/shutdown_node_check.py
    This script checks which project the current node is associated with using host aggregates mapping. Based on resouces available, it then decides whether the node needs to be shut down or not.
    [shutdown_node_check.py](https://github.com/shubhamdang/power-optimisation/blob/main/shutdown_node_check.py)

-  Now place `config.ini` at /opt/power_optimisation/config-down.ini and update the config values.
   [config.ini](https://github.com/shubhamdang/power-optimisation/blob/main/config.ini)


- Add the wodle execution config in wazuh agents at `sudo vi /var/ossec/etc/ossec.conf`, this is responsible for   execution of `shutdown_node_check.py` in fixed interval of 15 minutes.
    ```
    <ossec_config>
    <wodle name="command">
    <disabled>no</disabled>
    <tag>down_vm</tag>
    <command>/opt/power_optimisation/venv/bin/python /opt/power_optimisation/shutdown_node_check.py</command>
    <interval>15m</interval>
    <ignore_output>no</ignore_output>
    <run_on_start>yes</run_on_start>
    <timeout>0</timeout>
    </wodle>
    </ossec_config>
    ```

- Restart the wazuh agent
    ```
    sudo systemctl restart wazuh-agent
    ```


## Node Acitvation FLow
In this step, performing installation of python virtualenv and config update of wazuh is performed on the director node only.


- Install python openstack-client 6.4.0 in the virualenv
    ```
    mkdir -p /opt/power_optimisation
    cd /opt/power_optimisation/
    python3 -m venv venv 
    source venv/bin/activate
    pip install python-openstackclient==6.4.0
    deactivate
    ```

- Place the script `activate_node_check.py` at /opt/power_optimisation/activate_node_check.py
  This script checks the available resources on the compute nodes that are mapped to the project uuid provided in the command line args of the script. Based on resouces available, it then decides whether the node needs to be activated  or not.
    [`activate_node_check.py](https://github.com/shubhamdang/power-optimisation/blob/main/activate_node_check.py)

-  Now place `config.ini` at /opt/power_optimisation/config-up.ini and update the config values.
    [config.ini](https://github.com/shubhamdang/power-optimisation/blob/main/config.ini)

- Add the wodle execution config in wazuh agents at `sudo vi /var/ossec/etc/ossec.conf` 
    ```
    <ossec_config>
    <wodle name="command">
    <disabled>no</disabled>
    <tag>up_vm</tag>
    <command>/opt/power_optimisation/venv/bin/python /opt/power_optimisation/activate_node_check.py 17234a6cc8954d748ed74a31680ea39b</command>
    <interval>2m</interval>
    <ignore_output>no</ignore_output>
    <run_on_start>yes</run_on_start>
    <timeout>0</timeout>
    </wodle>
    </ossec_config>
    ```
    
    In the command we need to pass the project uuid, for each project or customer we need to create separate wodle like above.
    ```
    <command>/opt/power_optimisation/venv/bin/python /opt/power_optimisation/activate_node_check.py <project_uuid> </command>
    ```

- Restart the wazuh agent
    ```
    sudo systemctl restart wazuh-agent
    ```



## Add Config in Wazuh Manager for log decoder and rule event trigger

- Add Decoder in the file `/var/ossec/etc/decoders/local_decoder.xml`.
    ```
    <decoder name="compute_status_check">
        <program_name>compute_status_check</program_name>
    </decoder>

    <decoder name="compute_status_check1">
    <parent>compute_status_check</parent>
    <prematch>ossec: output: 'make_node_down': </prematch>
    <regex offset="after_prematch">(\S+)</regex>
    <order>compute_down</order>
    </decoder>

    <decoder name="compute_status_check2">
    <parent>compute_status_check</parent>
    <prematch>ossec: output: 'make_node_up': </prematch>
    <regex offset="after_prematch">(\S+)</regex>
    <order>compute_up</order>
    </decoder>
    ```

- Add rules in the File `/var/ossec/etc/rules/local_rules.xml`
    ```
    <group name="compute_metric,">
        <rule id="100054" level="3">
    <decoded_as>compute_status_check</decoded_as>
    <description>Compute Status Check</description>
    </rule>


    <rule id="100055" level="3">
    <if_sid>100054</if_sid>
    <field name="compute_down">True</field>
    <description>Making the compute node down.</description>
    <options>no_full_log</options>
    </rule>


    <rule id="100056" level="3">
    <if_sid>100054</if_sid>
    <field name="compute_up">True</field>
    <description>Making the compute node up.</description>
    <options>no_full_log</options>
    </rule>
    </group>
    ```

- Restart the wazuh manager
    ```
    sudo systemctl restart wazuh-manager
    ```

## Move compute nodes between Host Aggregate that is mapped to new project
For shutdown of the node no change at wazuh side

for activation of node we need to add new project wodle in director node in `/var/ossec/etc/ossec.conf`

    ```
    <ossec_config>
    <wodle name="command">
    <disabled>no</disabled>
    <tag>up_vm</tag>
    <command>/opt/power_optimisation/venv/bin/python /opt/power_optimisation/activate_node_check.py <project_uuid> </command>
    <interval>2m</interval>
    <ignore_output>no</ignore_output>
    <run_on_start>yes</run_on_start>
    <timeout>0</timeout>
    </wodle>
    </ossec_config>
    ```

Where project_uuid is new project uuid that is not added in config file.


## Move compute nodes between Host Aggregate that is mapped to existing project
In this case, no changes are needed on the Wazuh side. Simply move the host from one HA to another.


## Central Logging 
On the director node or the node where we wanted to collect all the logs place the below config.

    ```
    sudo vi  /etc/rsyslog.d/power_optimisation.conf

    # Provides TCP syslog reception
    #module(load="imtcp")
    #input(type="imtcp" port="514")

    # Define a custom log format template
    template(name="CustomLogFormat" type="string"
            string="<%pri%>%timegenerated% %HOSTNAME% %syslogtag%%msg%\n")

    # Use the custom log format for all incoming logs on a specific facility, e.g., local1
    local0.* action(type="omfile" file="/var/log/os_power_optimisation.log" template="CustomLogFormat")

    # Restart the rsyslog service
    systemctl restart rsyslog
    ```



## PROS

- No need to change openstack core logic.
- Can be extended to slurm and other clusters.
- Support for slack and central logging.

## CONS 

- If we need to updgrade the scripts, we need to make sure that all the nodes should be active.
- No support for timeout of scheduling the VM if compute node is not activated at the right moment.
