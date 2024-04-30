In our OpenStack environment, each customer is assigned a project, and within each project, there are associated compute nodes.

The `activate_node_check.py` script is executed on the Controller node to assess whether it's necessary to start a compute node. This script evaluates the availability of space on active nodes to accommodate buffer VMs. If sufficient space is unavailable, the compute node associated with the respective customer's project is activated using Wazuh's active-response feature.

Similarly, on all compute nodes, the `shutdown_node_check.py` script is deployed. This script checks whether the node hosts any active virtual machines or if other compute nodes within the same project have adequate space to spawn buffer VMs. If ample space is available, the node is gracefully shut down.




Install wazuh Manager.
Install Wazuh Agent on Controller and Compute nodes.



!!! note
    We are assuming agent is installed on the compute and controller node

## Node Acitvation FLow
Setup 
In Contoller node agent


- Install python openstack-client 6.4.0 as root user because wodle works with user having sudo permission.
    ```
    sudo pip install python-openstackclient=6.4.0
    ```

- Place the script `activate_node_check.py` at /opt/power_optimisation/activate_node_check.py
    ```
    mkdir -p opt/power_optimisation
    ## place the code 
    ```

- Add the wodle execution config in wazuh agents at `sudo vi /var/ossec/etc/ossec.conf` 
    ```
    <ossec_config>
    <wodle name="command">
    <disabled>no</disabled>
    <tag>up_vm</tag>
    <command>/usr/bin/python3 /opt/power_optimisation/activate_node_check.py </command>
    <interval>1m</interval>
    <ignore_output>no</ignore_output>
    <run_on_start>yes</run_on_start>
    <timeout>0</timeout>
    </wodle>
    <ossec_config>
    ```



- Add the `activate_node_ar.py` script in the wazuh agent in directory `/var/ossec/active-response/bin/` and apply the below permission.
    ```
    sudo chmod 750  /var/ossec/active-response/bin/activate_node_ar.py
    sudo chown root:wazuh /var/ossec/active-response/bin/activate_node_ar.pyy
    ```


- Restart the wazuh agent
    ```
    sudo systemctl start wazuh-agent
    ```





## Node Shutdown Flow
In Compute node agent
Setup 

- Install python openstack-client 6.4.0 as root user because wodle works with user having sudo permission.
    ```
    sudo pip install python-openstackclient=6.4.0
    ```

- Place the script `shutdown_node_check.py` at /opt/power_optimisation/shutdown_node_check.py
    ```
    mkdir -p opt/power_optimisation
    ## place the code 
    ```

- Add the wodle execution config in wazuh agents at `sudo vi /var/ossec/etc/ossec.conf` 
```
<ossec_config>
<wodle name="command">
  <disabled>no</disabled>
  <tag>down_vm</tag>
  <command>/usr/bin/python3 /opt/power_optimisation/shutdown_node_check.py</command>
  <interval>1m</interval>
  <ignore_output>no</ignore_output>
  <run_on_start>yes</run_on_start>
  <timeout>0</timeout>
</wodle>
<ossec_config>
 ```




- Restart the wazuh agent
    ```
    sudo systemctl start wazuh-agent
    ```


## Add Config in Wazuh Manager for rules event trigger and active response 

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
    <group name="compute__metric,">
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

- Add active response in the file `/var/ossec/etc/ossec.conf`.

    ```
    <ossec_config>
        <command>
            <name>node-up-ar</name>
            <executable>node_up_ar.py</executable>
            <timeout_allowed>yes</timeout_allowed>
        </command>

        <active-response>
            <disabled>no</disabled>
            <command>node-up-ar</command>
            <location>local</location>
            <rules_id>100056</rules_id>
            <timeout>60</timeout>
        </active-response>
    </ossec_config>
    ```