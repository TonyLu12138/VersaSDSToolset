import sys
import time

import utils


class SystemOperation(object):
    def __init__(self, conn=None):
        self.conn = conn

    def modify_fstab(self):
        cmd = f"sed -i 's/\/swapfile/#\/swapfile/g' /etc/fstab"
        utils.exec_cmd(cmd, self.conn)

    def off_swap(self):
        cmd = "swapoff -a"
        utils.exec_cmd(cmd, self.conn)

    def apt_update(self):
        cmd = 'apt -y update'
        utils.exec_cmd(cmd, self.conn)

    def replace_sources(self):
        utils.exec_cmd('mv /etc/apt/sources.list /etc/apt/sources.list.1bak', self.conn)
        utils.exec_cmd('echo "deb [trusted=yes] http://10.203.1.9:80/versasvr ./" > /etc/apt/sources.list', self.conn)

    def replace_linbit_sources(self):
        utils.exec_cmd('mv /etc/apt/sources.list /etc/apt/sources.list.x86bak', self.conn)
        utils.exec_cmd('echo "deb [trusted=yes] http://10.203.1.9:80/x86vm ./" > /etc/apt/sources.list', self.conn)

    def recovery_linbit_sources(self):
        utils.exec_cmd('mv /etc/apt/sources.list.x86bak /etc/apt/sources.list', self.conn)

    def get_sources_list(self):
        cmd = f'find /etc/apt/sources.list.d -name "*.list"'
        result = utils.exec_cmd(cmd, self.conn)
        return result

    def bak_sources_list(self, name):
        cmd = f'mv {name} {name}.1bak'
        utils.exec_cmd(cmd, self.conn)


class Keepalived(object):
    def __init__(self, conn=None):
        self.conn = conn

    def install(self):
        cmd = "apt install -y keepalived"
        utils.exec_cmd(cmd, self.conn)

    def modify_conf(self, filepath, router_id, interface, virtual_router_id, priority, unicast_src_ip,
                    unicast_peer_list, virtual_ipaddress):
        editor = utils.FileEdit("./sample-keepalived.conf")
        editor.replace_data("router_id LVS_DEVEL", f"router_id {router_id}")
        editor.replace_data("priority 100", f"priority {priority}")
        editor.replace_data("interface eno1", f"interface {interface}")
        editor.replace_data("virtual_router_id 60", f"virtual_router_id {virtual_router_id}")
        editor.replace_data("unicast_src_ip 127.0.0.1", f"unicast_src_ip {unicast_src_ip}")
        unicast_peer_data = ""
        for unicast_peer in unicast_peer_list:
            unicast_peer_data += f"    {unicast_peer}\n"
        editor.insert_data(unicast_peer_data, anchor="  unicast_peer {", type='under')
        editor.insert_data(f"    {virtual_ipaddress}", anchor="  virtual_ipaddress {", type='under')

        editor.data = rf"{editor.data}"
        utils.exec_cmd(f"echo '{editor.data}' > {filepath}", self.conn)

    def restart(self):
        utils.exec_cmd("systemctl restart keepalived", self.conn)
        utils.exec_cmd("systemctl enable keepalived", self.conn)

    def set_check_apiserver_sh(self):
        editor = utils.FileEdit("./check_apiserver.sh")
        utils.exec_cmd(f"echo '{editor.data}' > /etc/keepalived/check_apiserver.sh", self.conn)
        utils.exec_cmd(f"chmod +x /etc/keepalived/check_apiserver.sh", self.conn)


class HAproxy(object):
    def __init__(self, conn=None):
        self.conn = conn

    def install(self):
        cmd = "apt install -y haproxy"
        utils.exec_cmd(cmd, self.conn)

    def get_server(self, hostname, ip, port):
        return f"    server {hostname} {ip}:{port} check\n"

    def modify_cfg(self, file_path, data):
        editor = utils.FileEdit("./sample-haproxy.cfg")
        editor.insert_data(f"{data}",
                           f'    default-server inter 10s downinter 5s rise 2 fall 2 slowstart 60s maxconn 250 maxqueue 256 weight 100',
                           type='under')
        utils.exec_cmd(f"echo '{editor.data}' > {file_path}", self.conn)

    def restart(self):
        utils.exec_cmd("systemctl restart haproxy", self.conn)
        utils.exec_cmd("systemctl enable haproxy", self.conn)


class VersaKBS(object):
    def __init__(self, conn=None):
        self.conn = conn

    def install(self):
        cmd = f"apt install -y kubeadm kubectl kubelet"
        utils.exec_cmd(cmd, self.conn)

    def install_docker(self, flag):
        if flag:
            utils.exec_cmd("curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun", self.conn)
        else:
            utils.exec_cmd("apt install -y docker-ce", self.conn)
        utils.exec_cmd("apt install -y socat conntrack", self.conn)
        utils.exec_cmd("apt install -y ntpdate", self.conn)

    def install_kk(self):
        utils.exec_cmd("export KKZONE=cn && curl -sfL https://get-kk.kubesphere.io | sh -", self.conn)
        utils.exec_cmd("chmod +x kk", self.conn)

    def create_config(self):
        utils.exec_cmd("rm -rf config-sample.yaml", self.conn)
        utils.exec_cmd("./kk create config --with-kubesphere v3.1.0 --with-kubernetes v1.20.4", self.conn)

    def modify_config(self, host, etcd, master, worker, vip, port, flag=False):
        editor = utils.FileEdit("./sample-kk.yaml")
        editor.insert_data(host, anchor="  hosts:", type="under")
        editor.insert_data(etcd, anchor="    etcd:", type="under")
        editor.insert_data(master, anchor="    master:", type="under")
        editor.insert_data(worker, anchor="    worker:", type="under")
        editor.replace_data('    address: ""', f'    address: {vip}')
        editor.replace_data('    port: 8443', f'    port: {port}')

        if flag:
            editor.replace_data('  controlPlaneEndpoint:', '#  controlPlaneEndpoint:')
            editor.replace_data('    domain: lb.kubesphere.local', '#    domain: lb.kubesphere.local')
            editor.replace_data(f'    address: {vip}', f'#    address: {vip}')
            editor.replace_data(f'    port: {port}', f'#    port: {port}')

        utils.exec_cmd(f"echo '{editor.data}' > config-sample.yaml", self.conn)

    def build(self):
        # utils.exec_cmd_realtime("./kk create cluster -f config-sample.yaml -y")
        utils.exec_cmd("./kk create cluster -f config-sample.yaml -y", self.conn)


class VersaSDS(object):
    def __init__(self, conn=None):
        self.conn = conn

    def sync_time(self):
        cmd = 'ntpdate -u ntp.api.bz'
        utils.exec_cmd(cmd, self.conn)

    # TODO
    def install_drbd_spc(self, times=8):
        """
        Can access the PPA source of LINSTOR to download their version
        """
        cmd1 = 'apt install -y software-properties-common'
        cmd2 = 'add-apt-repository -y ppa:linbit/linbit-drbd9-stack'
        utils.exec_cmd(cmd1, self.conn)
        time.sleep(2)
        utils.exec_cmd(cmd2, self.conn)
        while not self.is_exist_linbit_ppa():
            if self.conn:
                print(f'{self.conn._host}: failed to add linbit ppa，retry ...')
            else:
                print("localhost: failed to add linbit ppa，retry ...")
            utils.exec_cmd(cmd1, self.conn)
            utils.exec_cmd(cmd2, self.conn)
            times -= 1
            if times <= 0:
                return False
        return True

    # TODO
    def is_exist_linbit_ppa(self):
        cmd = 'find /etc/apt/sources.list.d/ -name "linbit-ubuntu-linbit-drbd9-stack-bionic.list"'
        if utils.exec_cmd(cmd, self.conn):
            return True

    # TODO
    def install(self):
        utils.exec_cmd('export DEBIAN_FRONTEND=noninteractive && apt install -y drbd-utils drbd-dkms', self.conn)
        utils.exec_cmd('apt install -y lvm2 linstor-satellite linstor-client', self.conn)

    # TODO
    def set_service(self):
        utils.exec_cmd('systemctl disable drbd', self.conn)
        utils.exec_cmd('systemctl enable linstor-satellite', self.conn)

    def create_conf(self, ips):

        conf_data = f"[global]\ncontrollers={ips}"  # ips逗号分割
        cmd = f'echo "{conf_data}" > /etc/linstor/linstor-client.conf'
        result = utils.exec_cmd(cmd, self.conn)
        if result:
            if 'No such file or directory' in result:
                utils.exec_cmd('mkdir -p /etc/linstor', self.conn)
                utils.exec_cmd(cmd, self.conn)

    def start_satellite(self, status='start'):
        cmd = f"systemctl {status} linstor-satellite"
        utils.exec_cmd(cmd, self.conn)

    def create_node(self, node, ip, type='Satellite'):
        cmd = f'linstor node create {node} {ip} --node-type {type}'
        utils.exec_cmd(cmd, self.conn)

    def check_status(self, name):
        cmd = f'systemctl is-enabled {name}'
        result = utils.exec_cmd(cmd, self.conn)
        if 'No such file or directory' in result:
            return
        return result

    def set_linstor_csi(self, vip):
        editor = utils.FileEdit("./linstor.yaml")
        editor.replace_data('              value: "http://10.203.1.67:3370"',
                            f'              value: "http://{vip}:3370"')
        utils.exec_cmd(f"echo '{editor.data}' > linstor.yaml", self.conn)
        utils.exec_cmd("kubectl apply -f linstor.yaml", self.conn)

    def set_console_image(self, version):
        utils.exec_cmd(
            f"kubectl set image deployment ks-console ks-console=feixitek/vtel-console:{version} -n kubesphere-system",
            self.conn)

    def set_server_image(self, version):
        utils.exec_cmd(
            f"kubectl set image deployment ks-apiserver ks-apiserver=feixitek/vtel-server:{version} -n kubesphere-system",
            self.conn)

    def connect_linstor_cluster(self, vip):
        utils.exec_cmd('kubectl get deployment.apps/ks-apiserver -n kubesphere-system -o yaml > ksapi.yaml', self.conn)
        string_ksapi = utils.exec_cmd('cat ksapi.yaml', self.conn)
        if not string_ksapi:
            sys.exit()
        utils.exec_cmd(f"echo '{string_ksapi}' > ksapi.yaml")
        editor = utils.FileEdit("./ksapi.yaml")
        editor.insert_data(f"        - '--linstor={vip}:3370'", anchor="        - --logtostderr=true", type="under")
        utils.exec_cmd(f"echo '{editor.data}' > ksapi.yaml", self.conn)
        utils.exec_cmd("kubectl apply -f ksapi.yaml", self.conn)
